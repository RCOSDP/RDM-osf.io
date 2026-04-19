# -*- coding: utf-8 -*-
"""Service helpers for workflow templates and process execution."""

import json
import logging

from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status as http_status

from framework.exceptions import HTTPError
from osf.utils.permissions import ADMIN, READ, WRITE
from website import settings as website_settings

from addons.workflow.gateway_client import (
    WorkflowGatewayClient,
    WorkflowGatewayClientError,
    get_gateway_client,
)
from addons.workflow.models import (
    WorkflowActivation,
    WorkflowDefinitionSnapshot,
    WorkflowEngine,
    WorkflowEngineKey,
    WorkflowExecutorToken,
    WorkflowTemplate,
)
from addons.workflow.token import create_delegation_token, revoke_delegation_token
from osf.models import AbstractNode, ApiOAuth2PersonalToken, Comment, Guid, OSFUser
from website.mails import Mail, send_mail


_REQUIRED_DEFINITION_FIELDS = {'id', 'key', 'name', 'version'}
_ALLOWED_KEY_ALGORITHMS = {'RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'}


def import_gateway_public_keys(engine: WorkflowEngine) -> int:
    """Fetch the gateway keyset and register public keys for the engine."""

    client = get_gateway_client(engine.engine_id)
    payload = client.get_public_keyset()
    keys = payload.get('keys')
    if not isinstance(keys, list):
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'Workflow gateway returned malformed keyset payload.'},
        )
    if not keys:
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'Workflow gateway did not return any public keys.'},
        )

    imported = 0
    with transaction.atomic():
        for entry in keys:
            try:
                kid = entry['kid']
                algorithm = entry['alg']
                public_key = entry['public_key']
            except KeyError as error:
                raise HTTPError(
                    http_status.HTTP_502_BAD_GATEWAY,
                    data={'message': 'Workflow gateway keyset entry missing required fields.'},
                ) from error

            if algorithm not in _ALLOWED_KEY_ALGORITHMS:
                raise HTTPError(
                    http_status.HTTP_400_BAD_REQUEST,
                    data={'message': f'Unsupported key algorithm "{algorithm}" for kid {kid}.'},
                )

            WorkflowEngineKey.objects.update_or_create(
                engine_id=engine.engine_id,
                kid=kid,
                defaults={
                    'algorithm': algorithm,
                    'public_key': public_key,
                    'is_active': True,
                },
            )
            imported += 1

    return imported


def _validate_payload(payload: Dict[str, Any]) -> None:
    missing = _REQUIRED_DEFINITION_FIELDS.difference(payload.keys())
    if missing:
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': f'workflow engine response missing fields: {", ".join(sorted(missing))}'},
        )


def _extract_definition_defaults(payload: Dict[str, Any], form_schema: Optional[Any]) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        'definition_key': payload['key'],
        'name': payload.get('name') or payload['key'],
        'version': int(payload.get('version') or 0),
        'category': payload.get('category') or '',
        'deployment_id': payload.get('deploymentId') or '',
        'description': payload.get('description') or '',
        'form_schema': form_schema if form_schema is not None else {},
        'definition_metadata': payload,
    }
    return defaults


def _adapt_form_payload(form_payload: Any) -> Any:
    if not isinstance(form_payload, dict):
        return form_payload

    properties = form_payload.get('formProperties')
    if not isinstance(properties, list) or form_payload.get('fields'):
        return form_payload

    fields: List[Dict[str, Any]] = []
    for entry in properties:
        if not isinstance(entry, dict):
            continue
        field_type = str(entry.get('type') or '').lower()
        field: Dict[str, Any] = {
            'id': entry.get('id'),
            'name': entry.get('name'),
            'type': field_type,
            'required': entry.get('required', False),
        }
        if entry.get('value') is not None:
            field['value'] = entry['value']
            field['defaultValue'] = entry['value']
        enum_values = entry.get('enumValues')
        if isinstance(enum_values, list) and enum_values:
            options: List[Dict[str, Any]] = []
            for item in enum_values:
                if not isinstance(item, dict):
                    continue
                option_value = item.get('id')
                options.append(
                    {
                        'id': option_value,
                        'name': item.get('name', option_value),
                        'value': option_value,
                    }
                )
            field['options'] = options
        fields.append(field)

    adapted = dict(form_payload)
    adapted['fields'] = fields
    return adapted


def _upsert_definition(
    engine: WorkflowEngine,
    payload: Dict[str, Any],
    form_schema: Optional[Any] = None,
) -> WorkflowDefinitionSnapshot:
    _validate_payload(payload)
    defaults = _extract_definition_defaults(payload, form_schema)
    snapshot, _ = WorkflowDefinitionSnapshot.objects.update_or_create(
        engine=engine,
        definition_id=payload['id'],
        defaults=defaults,
    )
    return snapshot


def sync_definition_snapshot(engine_id: str, definition_id: str) -> WorkflowDefinitionSnapshot:
    """Fetch a process definition from the gateway and persist a snapshot."""

    client = get_gateway_client(engine_id)
    payload = client.get_process_definition(definition_id)
    if not isinstance(payload, dict):
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'workflow engine returned unexpected payload for definition lookup.'},
        )

    form_schema: Optional[Any]
    try:
        form_schema = client.get_process_definition_start_form(definition_id)
    except WorkflowGatewayClientError as error:
        if _status_code_from_error(error) == http_status.HTTP_404_NOT_FOUND:
            form_schema = None
        else:
            raise

    if form_schema is not None:
        form_schema = _adapt_form_payload(form_schema)

    try:
        engine = WorkflowEngine.objects.get(engine_id=engine_id)
    except WorkflowEngine.DoesNotExist as error:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': f'workflow engine not found: {engine_id}'},
        ) from error

    return _upsert_definition(engine, payload, form_schema)


def get_user_accessible_templates(user: OSFUser, **filters) -> List[WorkflowTemplate]:
    """Get workflow templates accessible to a user based on visibility rules.

    Args:
        user: The user to check access for
        **filters: Additional QuerySet filters to apply

    Returns:
        List of WorkflowTemplate objects the user can access
    """
    accessible_nodes = AbstractNode.objects.filter(_contributors=user, is_deleted=False)

    visibility_filter = Q(pk__in=[])
    visibility_filter |= Q(visibility=WorkflowTemplate.VISIBILITY_PUBLIC)

    user_institution_ids = set(user.affiliated_institutions.values_list('id', flat=True))
    if user_institution_ids:
        visibility_filter |= Q(
            visibility=WorkflowTemplate.VISIBILITY_INSTITUTION,
            node__affiliated_institutions__in=list(user_institution_ids),
        )

    return list(
        WorkflowTemplate.objects.filter(
            Q(node__in=accessible_nodes) | visibility_filter,
            node__is_deleted=False,
            **filters,
        )
        .select_related('node', 'definition__engine')
        .distinct()
    )


def _status_code_from_error(error: Exception) -> Optional[int]:
    code = getattr(error, 'status_code', None)
    if code is not None:
        return code
    return getattr(error, 'code', None)


@transaction.atomic
def upsert_workflow_template(
    node: 'AbstractNode',
    *,
    engine_id: str,
    definition_id: str,
    registered_by: 'OSFUser',
    token_settings: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
    auto_activate: Optional[bool] = None,
) -> Tuple[WorkflowTemplate, bool]:
    """Register a workflow definition for a given node."""

    if token_settings is not None and not isinstance(token_settings, dict):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'token_settings must be an object.'},
        )

    snapshot = sync_definition_snapshot(engine_id, definition_id)

    defaults = {
        'registered_by': registered_by,
        'label': label or snapshot.name,
        'description': description or snapshot.description,
        'token_settings': token_settings or {},
        'is_active': True,
        'visibility': visibility or WorkflowTemplate.VISIBILITY_PROJECT,
        'auto_activate': auto_activate if auto_activate is not None else False,
    }

    template, created = WorkflowTemplate.objects.get_or_create(
        node=node,
        definition=snapshot,
        defaults=defaults,
    )

    if created:
        current_creator_mode = 'none'
    else:
        current_creator_mode = template.token_settings.get('creator_mode') or 'none'

        if label:
            template.label = label
        if description is not None:
            template.description = description
        if token_settings is not None:
            template.token_settings = token_settings
        if visibility is not None:
            template.visibility = visibility
        if auto_activate is not None:
            template.auto_activate = auto_activate
        template.is_active = True
        template.save()

    desired_creator_mode = (token_settings or {}).get('creator_mode') or 'none'

    if desired_creator_mode != current_creator_mode:
        if current_creator_mode != 'none':
            revoke_delegation_token(template.delegation_tokens['creator']['token_id'])
        delegation_tokens = dict(template.delegation_tokens)
        if desired_creator_mode != 'none':
            token_data = create_delegation_token(
                user=registered_by,
                role='creator',
                mode=desired_creator_mode,
                label=template.label or '',
            )
            delegation_tokens['creator'] = token_data
        else:
            del delegation_tokens['creator']
        template.delegation_tokens = delegation_tokens
        template.save(update_fields=['delegation_tokens', 'modified'])

    return template, created


def _build_delegation_tokens_payload(
    activation: WorkflowActivation,
    started_by: 'OSFUser',
) -> Dict[str, Dict[str, str]]:
    """Build delegation tokens payload for Gateway.

    Returns dictionary of role -> token data for Gateway to store.
    Gateway will generate proxy URLs and MODE variables.
    """
    from addons.workflow.token import ALLOWED_TOKEN_ROLES

    merged_settings: Dict[str, Any] = {}
    if activation.template.token_settings:
        merged_settings.update(activation.template.token_settings)

    merged_tokens: Dict[str, Any] = {}
    if activation.template.delegation_tokens:
        merged_tokens.update(activation.template.delegation_tokens)
    if activation.delegation_tokens:
        merged_tokens.update(activation.delegation_tokens)

    delegation_tokens: Dict[str, Dict[str, str]] = {}

    for role in ALLOWED_TOKEN_ROLES:
        mode = merged_settings.get(f'{role}_mode', 'none')

        if mode != 'none':
            if role == 'executor':
                executor_token = WorkflowExecutorToken.objects.filter(
                    activation=activation,
                    user=started_by,
                ).first()

                needs_new_token = False
                if executor_token:
                    pat = ApiOAuth2PersonalToken.objects.filter(_id=executor_token.token_id).first()
                    if not pat or not pat.is_active:
                        needs_new_token = True
                        executor_token.delete()
                        executor_token = None
                else:
                    needs_new_token = True

                if needs_new_token:
                    token_data = create_delegation_token(
                        user=started_by,
                        role='executor',
                        mode=mode,
                        label=f'{activation.template.definition_name} on {activation.node.title}',
                    )
                    executor_token = WorkflowExecutorToken(
                        activation=activation,
                        user=started_by,
                        token_id=token_data['token_id'],
                        token_value=token_data['token_value'],
                    )
                    executor_token.save()

                delegation_tokens['executor'] = {
                    'tokenValue': executor_token.token_value,
                    'tokenOwner': started_by._id,
                    'mode': mode,
                }
            else:
                if role not in merged_tokens:
                    raise ValueError(f'Token mode is {mode} for role {role}, but no token exists')
                token_data = merged_tokens[role]
                delegation_tokens[role] = {
                    'tokenValue': token_data['token_value'],
                    'tokenOwner': token_data['token_owner'],
                    'mode': mode,
                }

    return delegation_tokens


def _extract_metadata(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Extract _RDM_WORKFLOW_METADATA from process instance variables."""
    process_id = instance['id']
    variables = instance['variables']
    for entry in variables:
        if entry['name'] != '_RDM_WORKFLOW_METADATA':
            continue
        raw_value = entry.get('value')
        parsed = json.loads(raw_value)
        if not isinstance(parsed, dict):
            raise ValueError(f'Workflow process instance {process_id} metadata is malformed (expected dict, got {type(parsed).__name__}).')
        return parsed

    raise ValueError(f'Workflow process instance {process_id} is missing _RDM_WORKFLOW_METADATA.')


def _get_visible_activations(
    node: 'AbstractNode',
    user: Optional['OSFUser'] = None,
) -> List[WorkflowActivation]:
    """Get all workflow activations visible from a node.

    Returns activations directly on the node, plus activations on other nodes
    that use templates from this node (if user has write permission).

    Note: Includes inactive activations so that existing runs and tasks
    remain visible after deactivation.

    Args:
        node: The node to get activations for
        user: Optional user for permission checks on shared activations

    Returns:
        List of visible WorkflowActivation objects
    """
    # Direct activations on this node (including inactive ones)
    direct_activations = list(
        WorkflowActivation.objects.filter(
            node=node,
        ).select_related('node', 'template__definition__engine')
    )

    # Shared activations (other nodes using templates from this node)
    shared_activations: List[WorkflowActivation] = []
    templates_on_node = list(
        WorkflowTemplate.objects.filter(
            node=node,
        ).select_related('definition__engine')
    )

    if templates_on_node and (not user or node.has_permission(user, WRITE)):
        shared_activations = list(
            WorkflowActivation.objects.filter(
                template__in=templates_on_node,
            ).select_related('node', 'template__definition__engine')
        )

    return direct_activations + shared_activations


def start_workflow_process(
    node: 'AbstractNode',
    *,
    template: WorkflowTemplate,
    activation: WorkflowActivation,
    started_by: 'OSFUser',
    business_key: Optional[str] = None,
    label: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if activation.node_id != node.id:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow activation not found for this project.'},
        )

    if not activation.is_effectively_active:
        raise HTTPError(
            http_status.HTTP_409_CONFLICT,
            data={'message': 'Workflow is not active.'},
        )

    delegation_tokens = _build_delegation_tokens_payload(activation, started_by)

    resolved_business_key = business_key or f'rdm:node:{node._id}:activation:{activation.id}'
    run_label = label or template.label or template.definition_name or template.definition_key
    started_at = timezone.now()
    engine_id = template.definition.engine.engine_id

    payload = _build_gateway_payload(
        node_id=node._id,
        node_title=node.title,
        template_id=template.id,
        template_node_id=template.node._id,
        activation_id=activation.id,
        started_by_id=started_by._id,
        engine_id=engine_id,
        process_definition_id=template.process_definition_id,
        label=run_label,
        business_key=resolved_business_key,
        started_at=started_at.isoformat(),
        delegation_tokens=delegation_tokens,
        variables=variables,
    )

    client = get_gateway_client(template.definition.engine.engine_id)
    try:
        response = client.start_process_instance(payload)
    except WorkflowGatewayClientError as error:
        raise HTTPError(
            _status_code_from_error(error),
            data={
                'message': 'Workflow engine request failed.',
                'detail': error.data,
            },
        ) from error

    if not isinstance(response, dict):
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'Workflow engine returned unexpected payload for process start.'},
        )

    process_instance_id = response.get('id')
    if not process_instance_id:
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'Workflow engine response missing process instance ID.'},
        )

    return {
        'id': process_instance_id,
        'status': 'running',
        'label': run_label,
        'node_id': node._id,
        'node_title': node.title,
        'template_id': str(template.id),
        'activation_id': str(activation.id),
        'started_by': started_by._id,
        'started_at': started_at.isoformat(),
        'business_key': resolved_business_key,
        'engine_response': response,
    }


def _build_gateway_payload(
    *,
    node_id: str,
    node_title: str,
    template_id: int,
    template_node_id: str,
    activation_id: int,
    started_by_id: str,
    engine_id: str,
    process_definition_id: str,
    label: str,
    business_key: str,
    started_at: str,
    delegation_tokens: Dict[str, Dict[str, str]],
    variables: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    variable_list: List[Dict[str, Any]] = [
        {'name': 'RDM_NODE_ID', 'type': 'string', 'value': node_id},
        {'name': 'RDM_TEMPLATE_ID', 'type': 'string', 'value': str(template_id)},
        {'name': 'RDM_TEMPLATE_NODE_ID', 'type': 'string', 'value': template_node_id},
        {'name': 'RDM_ACTIVATION_ID', 'type': 'string', 'value': str(activation_id)},
        {'name': 'RDM_STARTED_BY', 'type': 'string', 'value': started_by_id},
        {'name': 'RDM_ENGINE_ID', 'type': 'string', 'value': engine_id},
        {'name': 'RDM_DOMAIN', 'type': 'string', 'value': website_settings.DOMAIN},
        {'name': 'RDM_API_DOMAIN', 'type': 'string', 'value': website_settings.API_DOMAIN},
        {'name': 'RDM_WATERBUTLER_URL', 'type': 'string', 'value': website_settings.WATERBUTLER_URL},
    ]

    if variables:
        variable_list.extend(variables)

    metadata_payload: Dict[str, Any] = {
        'node_id': node_id,
        'node_title': node_title,
        'template_id': str(template_id),
        'activation_id': str(activation_id),
        'started_by': started_by_id,
        'engine_id': engine_id,
        'label': label,
        'business_key': business_key,
        'started_at': started_at,
    }

    variable_list.append(
        {
            'name': '_RDM_WORKFLOW_METADATA',
            'type': 'string',
            'value': json.dumps(metadata_payload),
        }
    )

    payload = {
        'processDefinitionId': process_definition_id,
        'name': label,
        'businessKey': business_key,
        'variables': variable_list,
        'delegationTokens': delegation_tokens,
    }

    return payload


def cancel_workflow_run(
    node: 'AbstractNode',
    process_instance_id: str,
    *,
    cancelled_by: 'OSFUser',
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel a workflow process instance.

    Args:
        node: The project node
        process_instance_id: Flowable process instance ID
        cancelled_by: User cancelling the process
        reason: Optional cancellation reason

    Returns:
        Serialized process instance data

    Raises:
        HTTPError: If process not found or cannot be cancelled
    """
    # Get all activations visible to this node
    all_activations = _get_visible_activations(node)
    engine_ids = list({act.template.definition.engine.engine_id for act in all_activations if act.template.definition.engine_id})

    if not engine_ids:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow run not found.'},
        )

    # Try to find the process instance in available engines by searching each activation
    for activation in all_activations:
        activation_node = activation.node
        if activation_node.is_deleted:
            continue

        template = activation.template
        engine_id = template.definition.engine.engine_id
        business_key = f'rdm:node:{activation_node._id}:activation:{activation.id}'

        client = get_gateway_client(engine_id)

        try:
            # Search using business_key to filter only this activation's instances
            response = client.list_process_instances({
                'businessKey': business_key,
                'includeProcessVariables': 'true',
                'size': 100,
            })
            instances = response.get('data') if isinstance(response, dict) else []

            if not instances or not isinstance(instances, list):
                continue

            # Find the specific process instance in the results
            instance = None
            for inst in instances:
                if inst.get('id') == process_instance_id:
                    instance = inst
                    break

            if not instance:
                continue

            # Extract and verify metadata
            try:
                metadata = _extract_metadata(instance)
            except HTTPError as e:
                logger.warning(
                    'Skipping process instance due to metadata error: %s',
                    e.data.get('message'),
                    extra={'process_id': instance.get('id'), 'node': node._id},
                )
                continue

            # Verify node matches
            node_id = metadata.get('node_id')
            if node_id != node._id:
                continue

            # Check if already completed
            if instance.get('ended'):
                raise HTTPError(
                    http_status.HTTP_409_CONFLICT,
                    data={'message': 'Workflow run has already completed and cannot be cancelled.'},
                )

            # Terminate the process instance
            client.terminate_process_instance(process_instance_id, reason=reason)

            # Return the terminated instance info
            return {
                'id': process_instance_id,
                'template_id': metadata.get('template_id'),
                'activation_id': metadata.get('activation_id'),
                'node_id': metadata['node_id'],
                'node_title': metadata['node_title'],
                'engine_id': engine_id,
                'engine_process_id': process_instance_id,
                'engine_definition_id': instance.get('processDefinitionId'),
                'label': metadata['label'],
                'status': 'cancelled',
                'business_key': metadata.get('business_key'),
                'started_at': metadata.get('started_at') or instance.get('startTime'),
                'completed_at': timezone.now().isoformat(),
                'started_by': metadata['started_by'],
                'cancelled_by': cancelled_by._id,
                'cancel_reason': reason,
                'created': metadata.get('started_at') or instance.get('startTime'),
            }

        except WorkflowGatewayClientError as error:
            if _status_code_from_error(error) == http_status.HTTP_404_NOT_FOUND:
                continue
            raise

    raise HTTPError(
        http_status.HTTP_404_NOT_FOUND,
        data={'message': 'Workflow run not found.'},
    )


def _serialize_task_payload(
    task_payload: Dict[str, Any],
    *,
    engine_id: str,
    instance: Dict[str, Any],
) -> Dict[str, Any]:
    from addons.workflow.views import STATUS_RUNNING, STATUS_COMPLETED, STATUS_CANCELLED

    metadata = _extract_metadata(instance)
    process_instance_id = task_payload['processInstanceId']
    end_time = task_payload.get('endTime')
    # Runtime tasks use 'createTime'; historic tasks use 'startTime'
    created = task_payload.get('createTime') or task_payload.get('startTime')

    if end_time:
        delete_reason = task_payload.get('deleteReason')
        if delete_reason:
            task_status = STATUS_CANCELLED
        else:
            task_status = STATUS_COMPLETED
    else:
        task_status = STATUS_RUNNING

    return {
        'id': task_payload['id'],
        'name': task_payload['name'],
        'description': task_payload.get('description'),
        'assignee': task_payload.get('assignee'),
        'owner': task_payload.get('owner'),
        'task_status': task_status,
        'delete_reason': task_payload.get('deleteReason'),
        'created': created,
        'end_time': end_time,
        'completed': end_time,
        'due': task_payload.get('dueDate'),
        'priority': task_payload.get('priority'),
        'category': task_payload.get('category'),
        'form_key': task_payload.get('formKey'),
        'engine_id': engine_id,
        'process_definition_id': task_payload['processDefinitionId'],
        'process_instance_id': process_instance_id,
        'business_key': task_payload.get('processInstanceBusinessKey'),
        'run_id': process_instance_id,
        'node_id': metadata['node_id'],
        'node_title': metadata['node_title'],
        'variables': instance['variables'],
    }


def list_workflow_tasks(
    node: 'AbstractNode',
    user: 'OSFUser',
    *,
    limit: int = 100,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    from addons.workflow.views import STATUS_RUNNING

    all_activations = _get_visible_activations(node, user)

    activation_map: Dict[int, WorkflowActivation] = {}
    for activation in all_activations:
        activation_map[activation.id] = activation

    if not activation_map:
        return []

    # Build per-activation context
    contexts: List[tuple] = []
    for activation in activation_map.values():
        if activation.node.is_deleted:
            continue
        template = activation.template
        engine_id = template.definition.engine.engine_id
        business_key = f'rdm:node:{activation.node._id}:activation:{activation.id}'
        client = get_gateway_client(engine_id)
        contexts.append((activation, client, engine_id, business_key))

    if not contexts:
        return []

    def _serialize_entry(entry, activation, engine_id):
        serialized = _serialize_task_payload(entry, engine_id=engine_id, instance=entry)
        serialized['can_complete'] = (
            serialized['task_status'] == STATUS_RUNNING and
            _can_complete_task(activation.node, user, entry['assignee'], _extract_metadata(entry))
        )
        return serialized

    # Phase 1: Collect runtime tasks from all activations
    runtime_tasks: List[Dict[str, Any]] = []
    runtime_ids: set = set()

    for activation, client, engine_id, business_key in contexts:
        response = client.list_tasks({
            'processInstanceBusinessKey': business_key,
            'includeProcessVariables': 'true',
            'sort': 'createTime',
            'order': 'desc',
            'size': limit,
        })
        for entry in response['data']:
            runtime_tasks.append(_serialize_entry(entry, activation, engine_id))
            runtime_ids.add(entry['id'])

    if status_filter == 'active':
        runtime_tasks.sort(key=lambda item: item['created'], reverse=True)
        return runtime_tasks[:limit]

    # Phase 2: Collect historic tasks from all activations
    remaining = limit - len(runtime_tasks)
    historic_tasks: List[Dict[str, Any]] = []

    if remaining > 0:
        for activation, client, engine_id, business_key in contexts:
            response = client.list_historic_tasks({
                'processBusinessKey': business_key,
                'includeProcessVariables': 'true',
                'sort': 'startTime',
                'order': 'desc',
                'size': remaining,
            })
            for entry in response['data']:
                if entry['id'] in runtime_ids:
                    continue
                historic_tasks.append(_serialize_entry(entry, activation, engine_id))

    # Runtime tasks are always included; limit applies only to historic
    historic_tasks.sort(key=lambda item: item['created'], reverse=True)
    all_tasks = runtime_tasks + historic_tasks[:max(0, remaining)]
    all_tasks.sort(key=lambda item: item['created'], reverse=True)
    return all_tasks


def _fetch_task_from_engines(
    node: 'AbstractNode',
    user: 'OSFUser',
    task_id: str,
    *,
    engine_id: str,
) -> Tuple[Dict[str, Any], str, Dict[str, Any], WorkflowActivation]:
    client = get_gateway_client(engine_id)
    task_payload = client.get_task(task_id)
    if not isinstance(task_payload, dict):
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow task not found.'},
        )

    process_instance_id = task_payload.get('processInstanceId')
    if not process_instance_id:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow task missing process instance.'},
        )

    # Use list API with 'id' parameter to get instance with variables
    # Note: GET /process-instances/{id} does not return variables,
    # but list API with id parameter does
    instance_response = client.list_process_instances({
        'id': process_instance_id,
        'includeProcessVariables': 'true',
    })
    instances = instance_response.get('data') if isinstance(instance_response, dict) else []
    if not instances or not isinstance(instances, list) or len(instances) == 0:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow process instance not found.'},
        )

    instance = instances[0]
    metadata = _extract_metadata(instance)
    activation_id = str(metadata['activation_id'])
    visible_activations = _get_visible_activations(node, user)
    activation = next(
        (entry for entry in visible_activations if str(entry.id) == activation_id),
        None,
    )
    if activation is None:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow task not found.'},
        )
    return task_payload, engine_id, instance, activation


def _can_complete_task(
    node: 'AbstractNode',
    user: 'OSFUser',
    assignee: Optional[str],
    metadata: Dict[str, Any],
) -> bool:
    """Check if user can complete a task based on flowable:assignee attribute.

    Supports:
    - empty assignee: anyone with read permission can complete
    - 'executor': user who started the workflow run
    - 'creator': WorkflowTemplate project's contributors with write permission
    - 'manager': project admin
    - 'contributor': project contributor (read permission)
    - email address: users with matching username
    """
    if not assignee:
        return node.has_permission(user, READ)

    assignee_lower = assignee.lower()

    if assignee_lower == 'executor':
        started_by_id = metadata.get('started_by')
        return user._id == started_by_id

    if assignee_lower == 'creator':
        template_id = metadata.get('template_id')
        if not template_id:
            return False
        try:
            template = WorkflowTemplate.objects.select_related('node').get(id=int(template_id))
            return template.node.has_permission(user, WRITE)
        except (WorkflowTemplate.DoesNotExist, ValueError):
            return False

    if assignee_lower == 'manager':
        return node.has_permission(user, ADMIN)

    if assignee_lower == 'contributor':
        return node.has_permission(user, READ)

    return user.username == assignee


def get_workflow_task(
    node: 'AbstractNode',
    task_id: str,
    user: 'OSFUser',
    *,
    engine_id: str,
    include_form: bool = False,
) -> Dict[str, Any]:
    task_payload, engine_id, instance, activation = _fetch_task_from_engines(node, user, task_id, engine_id=engine_id)
    client = get_gateway_client(engine_id)

    form_payload: Optional[Dict[str, Any]] = None
    if include_form:
        try:
            form_response = client.get_task_form(task_id)
            if isinstance(form_response, dict):
                form_payload = _adapt_form_payload(form_response)
        except WorkflowGatewayClientError as error:
            status_code = _status_code_from_error(error)
            logger.warning(f'get_task_form failed for task_id={task_id}: status={status_code}')
            if status_code not in {http_status.HTTP_404_NOT_FOUND, http_status.HTTP_400_BAD_REQUEST}:
                raise

    serialized = _serialize_task_payload(task_payload, engine_id=engine_id, instance=instance)
    if form_payload is not None:
        serialized['form'] = form_payload

    metadata = _extract_metadata(instance)
    assignee = task_payload.get('assignee')
    serialized['can_complete'] = _can_complete_task(activation.node, user, assignee, metadata)

    return serialized


def _normalize_task_variables(variables: Any) -> Optional[List[Dict[str, Any]]]:
    if variables is None:
        return None
    if isinstance(variables, list):
        return [entry for entry in variables if isinstance(entry, dict)]
    if isinstance(variables, dict):
        normalized: List[Dict[str, Any]] = []
        for name, value in variables.items():
            normalized.append({'name': name, 'value': value})
        return normalized
    raise HTTPError(
        http_status.HTTP_400_BAD_REQUEST,
        data={'message': 'variables must be an object or array.'},
    )


def submit_workflow_task_action(
    node: 'AbstractNode',
    task_id: str,
    user: 'OSFUser',
    *,
    engine_id: str,
    action: str,
    variables: Any = None,
    assignee: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    task_payload, engine_id, instance, activation = _fetch_task_from_engines(node, user, task_id, engine_id=engine_id)

    metadata = _extract_metadata(instance)
    task_assignee = task_payload.get('assignee')
    if not _can_complete_task(activation.node, user, task_assignee, metadata):
        raise HTTPError(
            http_status.HTTP_403_FORBIDDEN,
            data={'message': 'You are not assigned to this task.'},
        )

    client = get_gateway_client(engine_id)

    normalized_variables = _normalize_task_variables(variables)

    request_payload: Dict[str, Any] = {'action': action}
    if normalized_variables:
        request_payload['variables'] = normalized_variables
    if assignee:
        request_payload['assignee'] = assignee

    client.update_task(task_id, request_payload)

    try:
        return get_workflow_task(node, task_id, user, engine_id=engine_id, include_form=False)
    except HTTPError as error:
        if error.code == http_status.HTTP_404_NOT_FOUND:
            return None
        raise


def activate_workflow_activation(activation: WorkflowActivation, activated_by: 'OSFUser') -> None:
    """Activate a workflow activation, creating delegation tokens."""
    update_fields = []

    manager_mode = activation.template.token_settings.get('manager_mode')
    if manager_mode and manager_mode != 'none' and not activation.delegation_tokens.get('manager'):
        token_data = create_delegation_token(
            user=activated_by,
            role='manager',
            mode=manager_mode,
            label=activation.template.label or '',
        )
        delegation_tokens = dict(activation.delegation_tokens)
        delegation_tokens['manager'] = token_data
        activation.delegation_tokens = delegation_tokens
        update_fields.append('delegation_tokens')

    if not activation.is_enabled:
        activation.is_enabled = True
        update_fields.append('is_enabled')

    if activation.is_dismissed:
        activation.is_dismissed = False
        update_fields.append('is_dismissed')

    if activation.activated_by_id != activated_by.id:
        activation.activated_by = activated_by
        update_fields.append('activated_by')

    if not update_fields:
        return

    update_fields.append('modified')
    activation.save(update_fields=update_fields)


def dismiss_workflow_activation(activation: WorkflowActivation) -> None:
    """Dismiss a pending auto-activate template for a node.

    Creates a disabled+dismissed activation record to suppress the pending banner.
    """
    if activation.is_dismissed:
        return

    activation.is_dismissed = True
    activation.is_enabled = False
    activation.save(update_fields=['is_dismissed', 'is_enabled', 'modified'])


def deactivate_workflow_activation(activation: WorkflowActivation) -> None:
    """Deactivate a workflow activation.

    Deactivation prohibits new workflow runs but preserves access to existing data.
    Delegation tokens are NOT revoked - they are only revoked on deletion.
    """
    if not activation.is_enabled:
        return

    activation.is_enabled = False
    activation.save(update_fields=['is_enabled', 'modified'])


def has_running_workflows(activation: WorkflowActivation) -> bool:
    """Check if an activation has any running workflow process instances.

    A process instance is considered running if it exists in Flowable runtime
    with endTime = null.
    """
    engine_id = activation.template.definition.engine.engine_id
    client = WorkflowGatewayClient(engine_id, allow_inactive=True)

    # business_key format: rdm:node:{node_id}:activation:{activation_id}
    business_key_pattern = f'%:activation:{activation.id}'

    response = client.list_process_instances({
        'businessKeyLike': business_key_pattern,
        'size': 1,
    })

    return len(response['data']) > 0


def can_delete_activation(activation: WorkflowActivation) -> bool:
    """Check if an activation can be deleted.

    An activation can be deleted when:
    - It is not active (is_effectively_active=False)
    - It has no running workflow process instances

    Note: If the activation's node is deleted, we allow deletion regardless of
    running workflows since there's no way to recover them.
    """
    if activation.is_effectively_active:
        return False

    has_running = has_running_workflows(activation)

    if activation.node.is_deleted:
        if has_running:
            logger.warning(
                'Allowing deletion of activation %s on deleted node %s - running workflows will be orphaned',
                activation.id,
                activation.node._id,
            )
        return True

    return not has_running


def delete_workflow_activation(activation: WorkflowActivation) -> None:
    """Delete a workflow activation and revoke all delegation tokens.

    This permanently removes the activation. Delegation tokens (manager, executor)
    are revoked as part of the deletion.

    Raises:
        ValueError: If the activation cannot be deleted (is active or has running workflows)
    """
    if not can_delete_activation(activation):
        raise ValueError('Cannot delete activation: still active or has running workflows')

    # Revoke manager token
    if activation.delegation_tokens.get('manager'):
        revoke_delegation_token(activation.delegation_tokens['manager']['token_id'])

    # Revoke all executor tokens
    for executor_token in activation.executor_tokens.all():
        revoke_delegation_token(executor_token.token_id)

    activation.delete()


def activate_workflow_template(template: WorkflowTemplate, activated_by: 'OSFUser') -> None:
    """Activate a workflow template, creating delegation tokens."""
    update_fields = []

    creator_mode = template.token_settings.get('creator_mode')
    if creator_mode and creator_mode != 'none' and not template.delegation_tokens.get('creator'):
        token_data = create_delegation_token(
            user=activated_by,
            role='creator',
            mode=creator_mode,
            label=template.label or '',
        )
        delegation_tokens = dict(template.delegation_tokens)
        delegation_tokens['creator'] = token_data
        template.delegation_tokens = delegation_tokens
        update_fields.append('delegation_tokens')

    if not template.is_active:
        template.is_active = True
        update_fields.append('is_active')

    if not update_fields:
        return

    update_fields.append('modified')
    template.save(update_fields=update_fields)


def deactivate_workflow_template(template: WorkflowTemplate) -> None:
    """Deactivate a workflow template.

    Deactivation prohibits new activations but preserves access to existing data.
    Delegation tokens are NOT revoked - they are only revoked on deletion.
    """
    if not template.is_active:
        return

    template.is_active = False
    template.save(update_fields=['is_active', 'modified'])


def can_delete_template(template: WorkflowTemplate) -> bool:
    """Check if a template can be deleted.

    A template can be deleted when:
    - It is inactive (is_active=False or engine.is_active=False)
    - All its activations can be deleted (no running workflows)
    """
    if template.is_effectively_active:
        return False

    for activation in template.activations.all():
        if not can_delete_activation(activation):
            return False

    return True


def delete_workflow_template(template: WorkflowTemplate) -> None:
    """Delete a workflow template and all its activations.

    This permanently removes the template. All activations and delegation tokens
    are revoked as part of the deletion.

    Raises:
        ValueError: If the template cannot be deleted
    """
    if not can_delete_template(template):
        raise ValueError('Cannot delete template: still active or has running workflows')

    # Delete all activations first
    for activation in template.activations.all():
        delete_workflow_activation(activation)

    # Revoke creator token
    if template.delegation_tokens.get('creator'):
        revoke_delegation_token(template.delegation_tokens['creator']['token_id'])

    template.delete()


def deactivate_workflow_engine(engine: WorkflowEngine) -> None:
    """Deactivate a workflow engine.

    Deactivation prohibits new templates but preserves access to existing data.
    Related templates are NOT automatically deactivated - they become 'disabled'
    (parent inactive) state.
    """
    if not engine.is_active:
        return

    engine.is_active = False
    engine.save(update_fields=['is_active', 'modified'])


def can_delete_engine(engine: WorkflowEngine) -> bool:
    """Check if an engine can be deleted.

    An engine can be deleted when:
    - It is inactive (is_active=False)
    - All its templates can be deleted (no running workflows)
    """
    if engine.is_active:
        return False

    for template in WorkflowTemplate.objects.filter(definition__engine=engine):
        if not can_delete_template(template):
            return False

    return True


def delete_workflow_engine(engine: WorkflowEngine) -> None:
    """Delete a workflow engine and all its templates.

    This permanently removes the engine. All templates, activations, and
    delegation tokens are deleted as part of the deletion.

    Raises:
        ValueError: If the engine cannot be deleted
    """
    if not can_delete_engine(engine):
        raise ValueError('Cannot delete engine: still active or has running workflows')

    # Delete all templates first
    for template in WorkflowTemplate.objects.filter(definition__engine=engine):
        delete_workflow_template(template)

    # Delete definition snapshots
    WorkflowDefinitionSnapshot.objects.filter(engine=engine).delete()

    # Delete engine keys
    WorkflowEngineKey.objects.filter(engine_id=engine.engine_id).delete()

    engine.delete()


def resolve_workflow_notification_recipients(
    node: 'AbstractNode',
    *,
    metadata: Dict[str, Any],
    assignees: Optional[List[str]] = None,
    user_ids: Optional[List[str]] = None,
) -> Set[OSFUser]:
    """Resolve notification recipients from assignee roles and user IDs."""
    if not assignees and not user_ids:
        raise ValueError('Must specify either assignees or user_ids.')

    recipients: Set[OSFUser] = set()

    if assignees:
        for role in assignees:
            if role == 'executor':
                started_by = metadata['started_by']
                user = OSFUser.load(started_by)
                if not user:
                    raise ValueError(f'Executor user not found: {started_by}')
                recipients.add(user)
            elif role == 'manager':
                activation_id = metadata['activation_id']
                activation = WorkflowActivation.objects.filter(
                    id=activation_id
                ).select_related('activated_by').first()
                recipients.add(activation.activated_by)
            elif role == 'creator':
                template_id = metadata['template_id']
                template = WorkflowTemplate.objects.filter(
                    id=template_id
                ).select_related('registered_by').first()
                recipients.add(template.registered_by)
            elif role == 'contributor':
                for contributor in node.contributors.all():
                    recipients.add(contributor)
            else:
                raise ValueError(f'Invalid assignee role: {role}')

    if user_ids:
        for user_id in user_ids:
            user = OSFUser.load(user_id)
            if not user:
                raise ValueError(f'User not found: {user_id}')
            recipients.add(user)
    return recipients


def send_workflow_notification(
    node: 'AbstractNode',
    process_instance_id: str,
    *,
    auth,
    metadata: Dict[str, Any],
    title: str,
    body: List[Dict[str, str]],
    assignees: Optional[List[str]] = None,
    user_ids: Optional[List[str]] = None,
    send_email: bool = False,
    add_comment: bool = False,
) -> List[str]:
    """Send workflow notification to users via NodeLog, email, and/or comment."""
    recipients = resolve_workflow_notification_recipients(
        node,
        metadata=metadata,
        assignees=assignees,
        user_ids=user_ids,
    )

    plain_text = None
    html_text = None
    for entry in body:
        content_type = entry['type']
        content = entry['content']
        if content_type == 'text/plain':
            plain_text = content
        elif content_type == 'text/html':
            html_text = content
        else:
            raise ValueError(f'Invalid body content type: {content_type}')

    if not plain_text:
        raise ValueError('Body must contain at least one text/plain entry.')

    activation_id = metadata['activation_id']
    activation = WorkflowActivation.objects.select_related('template__definition').get(id=activation_id)
    workflow_name = activation.template.definition.name

    node.add_log(
        action='workflow_notification',
        params={
            'node': node._id,
            'process_instance_id': process_instance_id,
            'title': title,
            'message': plain_text,
            'workflow_name': workflow_name,
        },
        auth=auth,
        save=True,
    )

    if add_comment:
        target = Guid.load(node._id)
        comment = Comment(
            node=node,
            user=auth.user,
            content=f'**{title}**\n\n{plain_text}',
            target=target,
            root_target=target,
        )
        comment.save()

    if send_email:
        workflow_notification_mail = Mail(
            tpl_prefix='workflow_notification',
            subject=title,
        )

        for recipient in recipients:
            primary_email = recipient.emails.first().address
            send_mail(
                to_addr=primary_email,
                mail=workflow_notification_mail,
                title=title,
                plain_text=plain_text,
                html_text=html_text,
                node_title=node.title,
                node_url=node.absolute_url,
                can_change_preferences=False,
            )

    return [user._id for user in recipients]

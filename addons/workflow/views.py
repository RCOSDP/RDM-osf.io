# -*- coding: utf-8 -*-
"""Views for workflow gateway integration."""

import io
import json
import logging
import uuid
import zipfile
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import request
from rest_framework import status as http_status
from django.db.models import Q

from framework.auth.decorators import must_be_logged_in
from framework.exceptions import HTTPError
from website.project.decorators import (
    must_be_valid_project,
    must_have_permission,
    must_have_addon,
    must_be_contributor_or_public,
)
from website.ember_osf_web.views import use_ember_app

from framework.celery_tasks import app as celery_app
from addons.workflow import settings as workflow_settings
from addons.workflow.engine_keys import get_engine_public_key
from addons.workflow.keyset import build_public_keyset
from addons.workflow.gateway_client import (
    WorkflowGatewayClientError,
    WorkflowGatewayConfigurationError,
    get_gateway_client,
)
from addons.workflow.models import (
    WorkflowActivation,
    WorkflowEngine,
    WorkflowEngineKey,
    WorkflowTemplate,
)
from addons.workflow.token import validate_token_settings
from osf.models import AbstractNode
from osf.utils.permissions import WRITE
from addons.workflow.services import (
    _extract_metadata,
    _get_visible_activations,
    activate_workflow_activation,
    activate_workflow_template,
    can_delete_activation,
    can_delete_engine,
    can_delete_template,
    cancel_workflow_run,
    deactivate_workflow_activation,
    deactivate_workflow_template,
    delete_workflow_activation,
    delete_workflow_engine,
    delete_workflow_template,
    get_user_accessible_templates,
    get_workflow_task,
    list_workflow_tasks,
    send_workflow_notification,
    upsert_workflow_template,
)
from addons.workflow.tasks import start_workflow_process_async, submit_task_action_async

_ALLOWED_ALGORITHMS = {'RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'}
_TEMPLATE_VISIBILITY_VALUES = {
    WorkflowTemplate.VISIBILITY_PROJECT,
    WorkflowTemplate.VISIBILITY_INSTITUTION,
    WorkflowTemplate.VISIBILITY_PUBLIC,
}

# Workflow run status constants
STATUS_QUEUED = 'queued'
STATUS_RUNNING = 'running'
STATUS_COMPLETED = 'completed'
STATUS_FAILED = 'failed'
STATUS_CANCELLED = 'cancelled'
STATUS_UNKNOWN = 'unknown'

SHORT_NAME = 'workflow'
PREFERRED_PROCESS_KEY_PREFIX = 'rdm-main-'
WORKFLOW_JOB_PREFIX = 'wf-'

logger = logging.getLogger(__name__)


def require_admin(func):
    @wraps(func)
    def wrapper(auth, *args, **kwargs):
        user = auth.user
        if not user or not (user.is_superuser or user.is_staff):
            raise HTTPError(
                http_status.HTTP_403_FORBIDDEN,
                data={'message': 'Administrator privileges required for this action.'},
            )
        return func(auth, *args, **kwargs)

    return wrapper


def _serialize_engine(engine: WorkflowEngine, node_id: str = None) -> Dict[str, Any]:
    data = {
        'engine_id': engine.engine_id,
        'label': engine.label,
        'gateway_base_url': engine.gateway_base_url,
        'signing_kid': engine.signing_kid,
        'created_by': engine.created_by._id if engine.created_by else None,
        'institution_id': engine.institution.id if engine.institution_id else None,
        'institution_name': engine.institution.name if engine.institution_id else None,
        'verify_ssl': engine.verify_ssl,
        'token_subject': engine.token_subject,
        'token_scope': engine.token_scope,
        'token_audience': engine.token_audience,
        'token_issuer': engine.token_issuer,
        'engine_claim': engine.engine_claim,
        'engine_claim_value': engine.engine_claim_value,
        'token_lifetime_seconds': engine.token_lifetime_seconds,
        'request_timeout': engine.request_timeout,
        'is_active': engine.is_active,
    }

    if node_id is not None:
        whitelist = engine.upload_whitelist_node_ids
        data['allow_upload'] = node_id in whitelist

    return data


def gateway_keyset(**kwargs):
    """Return the RDM workflow service keyset for gateway verification."""
    return build_public_keyset()


@must_be_valid_project
@must_be_contributor_or_public
@must_have_addon(SHORT_NAME, 'node')
def project_workflow(**kwargs):
    """Render the Ember workflow console."""
    return use_ember_app()


def _serialize_definition_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    definition_id = entry.get('definition_id') or entry.get('id') or entry.get('definitionId')
    return {
        'definition_id': definition_id,
        'definition_key': entry.get('definition_key') or entry.get('key') or entry.get('definitionKey'),
        'definition_name': entry.get('definition_name') or entry.get('name'),
        'definition_version': entry.get('definition_version') or entry.get('version'),
        'definition_category': entry.get('definition_category') or entry.get('category'),
        'definition_description': entry.get('definition_description') or entry.get('description'),
        'definition_deployment_id': entry.get('definition_deployment_id') or entry.get('deploymentId'),
    }


def _normalize_engine_id(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        raise ValueError('engine_id must be a non-empty string')
    try:
        return str(uuid.UUID(raw))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError('engine_id must be a valid UUID.') from error


def _user_institution_ids(user):
    return set(user.affiliated_institutions.values_list('id', flat=True))


def _user_can_access_template_via_visibility(user, template: WorkflowTemplate) -> bool:
    visibility = template.visibility or WorkflowTemplate.VISIBILITY_PROJECT

    if visibility == WorkflowTemplate.VISIBILITY_PUBLIC:
        return True

    if visibility == WorkflowTemplate.VISIBILITY_INSTITUTION:
        node_institution_ids = set(template.node.affiliated_institutions.values_list('id', flat=True))
        if not node_institution_ids:
            return False
        return bool(_user_institution_ids(user) & node_institution_ids)

    return False


def _normalize_template_visibility(user, raw_visibility: Optional[str]) -> str:
    visibility = raw_visibility or WorkflowTemplate.VISIBILITY_PROJECT
    if visibility not in _TEMPLATE_VISIBILITY_VALUES:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Invalid workflow template visibility value.'},
        )

    if visibility == WorkflowTemplate.VISIBILITY_PUBLIC:
        if not user.is_super_admin:
            raise HTTPError(
                http_status.HTTP_403_FORBIDDEN,
                data={'message': 'Only super administrators can share templates with everyone.'},
            )
    elif visibility == WorkflowTemplate.VISIBILITY_INSTITUTION:
        if not (user.is_super_admin or user.is_institutional_admin):
            raise HTTPError(
                http_status.HTTP_403_FORBIDDEN,
                data={'message': 'Only institutional administrators can share templates with their institution.'},
            )

    return visibility


def _user_has_engine_admin_access(user, engine: WorkflowEngine) -> bool:
    if user.is_superuser:
        return True
    if not user.is_institutional_admin:
        return False
    return engine.institution_id in _user_institution_ids(user)


def _get_engine_or_404(engine_id: str, user) -> WorkflowEngine:
    if not user:
        logger.info('Engine lookup denied: missing user for engine_id=%s', engine_id)
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow engine not found.'},
        )

    # TODO: テストのため一旦無効化 ... admin画面でUUIDを指定してもらうように（生成されるように）する
    # try:
    #     normalized_id = _normalize_engine_id(engine_id)
    # except ValueError:
    #     logger.info('Engine lookup failed: invalid UUID engine_id=%s', engine_id)
    #     raise HTTPError(
    #         http_status.HTTP_404_NOT_FOUND,
    #         data={'message': 'Workflow engine not found.'},
    #     )
    normalized_id = engine_id

    try:
        engine = WorkflowEngine.objects.select_related('created_by').get(engine_id=normalized_id)
    except WorkflowEngine.DoesNotExist as error:
        logger.info('Engine lookup failed: not found engine_id=%s', normalized_id)
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow engine not found.'},
        ) from error

    logger.info('Engine lookup retrieved engine_id=%s created_by=%s requested_by=%s', engine.engine_id, getattr(engine.created_by, '_id', None), user._id)

    has_institution_access = _user_has_engine_admin_access(user, engine)
    if not has_institution_access:
        accessible_nodes = AbstractNode.objects.filter(_contributors=user, is_deleted=False)
        has_template_access = WorkflowTemplate.objects.filter(
            node__in=accessible_nodes,
            definition__engine=engine,
        ).exists()
        if not has_template_access:
            has_template_access = WorkflowActivation.objects.filter(
                node___contributors=user,
                node__is_deleted=False,
                template__definition__engine=engine,
            ).exists()

        if not has_template_access:
            logger.info(
                'Engine lookup denied: user=%s lacks access to engine=%s',
                user._id,
                engine.engine_id,
            )
            raise HTTPError(
                http_status.HTTP_404_NOT_FOUND,
                data={'message': 'Workflow engine not found.'},
            )

    logger.info('Engine lookup authorized: user=%s engine=%s', user._id, engine.engine_id)
    return engine


def _get_template_or_404(template_id: str, user) -> WorkflowTemplate:
    if not user:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow template not found.'},
        )

    template = WorkflowTemplate.load(template_id)
    if template is None:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow template not found.'},
        )

    if template.node.is_deleted:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow template not found.'},
        )

    has_direct_access = template.node.contributors.filter(id=user.id).exists()
    if not has_direct_access:
        has_activation_access = WorkflowActivation.objects.filter(
            template=template,
            node___contributors=user,
            node__is_deleted=False,
        ).exists()
        if not has_activation_access and not _user_can_access_template_via_visibility(user, template):
            raise HTTPError(
                http_status.HTTP_404_NOT_FOUND,
                data={'message': 'Workflow template not available.'},
            )

    return template


def _flatten_form_models_in_zip(zip_content: bytes) -> io.BytesIO:
    """Flatten form-models directory in workflow ZIP to avoid Tomcat encoded slash issues.

    Renames files from 'form-models/filename.ext' to 'form-models-filename.ext' at root level.

    Args:
        zip_content: Original ZIP file content as bytes

    Returns:
        BytesIO object containing the modified ZIP
    """
    input_zip = zipfile.ZipFile(io.BytesIO(zip_content), 'r')
    output_buffer = io.BytesIO()
    output_zip = zipfile.ZipFile(output_buffer, 'w', zipfile.ZIP_DEFLATED)

    for item in input_zip.namelist():
        if item.startswith('form-models/') and not item.endswith('/'):
            # Extract filename from form-models/filename.ext
            filename = item.split('/', 1)[1]
            new_name = f'form-models-{filename}'
            output_zip.writestr(new_name, input_zip.read(item))
        elif not item.startswith('form-models/'):
            # Copy other files as-is
            output_zip.writestr(item, input_zip.read(item))
        # Skip the form-models/ directory itself

    input_zip.close()
    output_zip.close()
    output_buffer.seek(0)
    return output_buffer


def _get_definition_id_from_deployment(client, deployment_id: str) -> str:
    """Query process definitions to find the definition_id for a deployed workflow.

    Args:
        client: Gateway client instance
        deployment_name: Name used for deployment
        deployment_id: Deployment ID returned from deployment (optional)

    Returns:
        Process definition ID

    Raises:
        HTTPError: If no matching process definition found
    """
    response = client.list_process_definitions({'latest': 'true', 'size': 100})
    definitions = response['data']
    if not definitions:
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'No process definitions found after deployment.'},
        )

    def _has_preferred_key(entry: Dict[str, Any]) -> bool:
        key = entry['key']
        return key.startswith(PREFERRED_PROCESS_KEY_PREFIX)

    def _select_definition(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not entries:
            return None
        for candidate in entries:
            if _has_preferred_key(candidate):
                return candidate
        return entries[0]

    deployment_matches: List[Dict[str, Any]] = [
        entry for entry in definitions if entry['deploymentId'] == deployment_id
    ]
    selection = _select_definition(deployment_matches)
    if selection:
        return selection['id']

    raise HTTPError(
        http_status.HTTP_404_NOT_FOUND,
        data={'message': f'No process definition found for deployment: {deployment_id}'},
    )


def _serialize_activation(activation: WorkflowActivation) -> Dict[str, Any]:
    return {
        'id': activation._id,
        'node_id': activation.node._id,
        'node_title': activation.node.title,
        'template_id': activation.template._id,
        'template': _serialize_template(activation.template),
        'is_enabled': activation.is_enabled,
        'is_effectively_active': activation.is_effectively_active,
        'activated_by': activation.activated_by._id,
    }


def _serialize_process_instance(
    instance: Dict[str, Any],
    *,
    node: AbstractNode,
    engine_id: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    process_id = instance['id']

    node_id = metadata.get('node_id')
    if node_id and node_id != node._id:
        raise HTTPError(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            data={'message': f'Workflow process instance {process_id} node mismatch.'},
        )

    label = metadata['label']
    template_id = metadata.get('template_id')
    activation_id = metadata.get('activation_id')
    started_by = metadata['started_by']
    business_key = metadata['business_key']
    start_time = metadata['started_at'] or instance['startTime']
    end_time = instance.get('endTime')

    # Determine status: completed if endTime exists, otherwise running
    if end_time:
        delete_reason = instance.get('deleteReason')
        if delete_reason:
            status = STATUS_CANCELLED
        else:
            status = STATUS_COMPLETED
    else:
        status = STATUS_RUNNING

    return {
        'id': process_id,
        'template_id': str(template_id) if template_id is not None else None,
        'activation_id': str(activation_id) if activation_id is not None else None,
        'node_id': node._id,
        'node_title': node.title,
        'engine_id': engine_id,
        'engine_process_id': process_id,
        'engine_definition_id': instance['processDefinitionId'],
        'label': label,
        'status': status,
        'delete_reason': instance.get('deleteReason'),
        'business_key': business_key,
        'started_at': start_time,
        'completed_at': end_time,
        'started_by': started_by,
        'created': start_time,
        'metadata': {'workflow': metadata},
    }


def _business_key_prefix(node: AbstractNode) -> str:
    return f'rdm:node:{node._id}'


def _serialize_template(
    template: WorkflowTemplate,
    *,
    current_node: Optional['AbstractNode'] = None,
    current_user: Optional['OSFUser'] = None,
    activation: Optional[WorkflowActivation] = None,
) -> Dict[str, Any]:
    engine = template.definition.engine
    is_local = (template.node_id == current_node.id) if current_node is not None else None
    has_write = current_node.has_permission(current_user, WRITE) if current_node and current_user else False
    result = {
        'id': template._id,
        'node_id': template.node._id if template.node_id else None,
        'node_title': template.node.title if template.node_id else None,
        'is_local': is_local,
        'engine_id': template.engine_id,
        'engine_label': engine.label,
        'engine_is_active': engine.is_active,
        'definition_id': template.process_definition_id,
        'definition_key': template.definition_key,
        'definition_name': template.definition_name,
        'definition_version': template.definition_version,
        'definition_category': template.definition_category,
        'definition_description': template.definition_description,
        'definition_deployment_id': template.definition_deployment_id,
        'definition_form_schema': template.definition_form_schema,
        'token_settings': template.token_settings,
        'label': template.label,
        'description': template.description,
        'is_active': template.is_active,
        'is_effectively_active': activation.is_effectively_active if activation else template.is_effectively_active,
        'auto_activate': template.auto_activate,
        'activation_id': activation._id if activation else None,
        'is_enabled': activation.is_enabled if activation else False,
        'activation_activated_by': activation.activated_by._id if activation and activation.activated_by_id else None,
        'visibility': template.visibility,
    }
    # Only include activations list for local templates with write permission
    if is_local and has_write:
        activations = []
        for act in template.activations.select_related('node', 'activated_by').all():
            if act.node.is_deleted:
                continue
            activations.append({
                'id': act._id,
                'node_id': act.node._id,
                'node_title': act.node.title,
                'is_enabled': act.is_enabled,
                'is_effectively_active': act.is_effectively_active,
                'activated_by': act.activated_by._id if act.activated_by_id else None,
            })
        result['activations'] = activations
    return result


@must_be_logged_in
@require_admin
def list_engine_keys(auth, engine_id: str, **kwargs):
    engine = _get_engine_or_404(engine_id, auth.user)
    engine_id = engine.engine_id
    records = []
    for key in WorkflowEngineKey.objects.filter(engine_id=engine_id, is_active=True):
        records.append({
            'engine_id': key.engine_id,
            'kid': key.kid,
            'algorithm': key.algorithm,
            'public_key': key.public_key,
        })
    return {'data': records}


@must_be_logged_in
@require_admin
def upsert_engine_key(auth, engine_id: str, **kwargs):

    engine = _get_engine_or_404(engine_id, auth.user)
    engine_id = engine.engine_id

    try:
        payload = request.get_json(force=True)
    except Exception as error:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Invalid JSON payload.'}) from error

    kid = payload.get('kid')
    algorithm = payload.get('algorithm')
    public_key = payload.get('public_key')
    is_active = payload.get('is_active', True)

    payload_engine_id = payload.get('engine_id')
    if payload_engine_id:
        try:
            normalized_payload_engine_id = _normalize_engine_id(payload_engine_id)
        except ValueError:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'engine_id must be a valid UUID.'},
            )
        if normalized_payload_engine_id != engine_id:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'engine_id in payload must match route parameter.'},
            )

    if not kid or not algorithm or not public_key:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'kid, algorithm, and public_key are required.'})

    algorithm = algorithm.upper()
    if algorithm not in _ALLOWED_ALGORITHMS:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': f'Unsupported algorithm: {algorithm}.'})

    obj, _created = WorkflowEngineKey.objects.update_or_create(
        engine_id=engine_id,
        kid=kid,
        defaults={
            'algorithm': algorithm,
            'public_key': public_key.strip(),
            'is_active': bool(is_active),
        },
    )

    response = {
        'engine_id': obj.engine_id,
        'kid': obj.kid,
        'algorithm': obj.algorithm,
        'public_key': obj.public_key,
        'is_active': obj.is_active,
    }
    return {'data': response}, http_status.HTTP_201_CREATED


@must_be_logged_in
@require_admin
def deactivate_engine_key(auth, engine_id: str, kid: str, **kwargs):
    engine = _get_engine_or_404(engine_id, auth.user)
    engine_id = engine.engine_id

    try:
        obj = WorkflowEngineKey.objects.get(engine_id=engine_id, kid=kid)
    except WorkflowEngineKey.DoesNotExist as error:
        raise HTTPError(http_status.HTTP_404_NOT_FOUND, data={'message': 'Workflow engine key not found.'}) from error

    obj.is_active = False
    obj.save(update_fields=['is_active', 'modified'])

    return {}, http_status.HTTP_204_NO_CONTENT


@must_be_logged_in
@require_admin
def retrieve_engine_key(auth, engine_id: str, kid: str, **kwargs):
    engine = _get_engine_or_404(engine_id, auth.user)
    key = get_engine_public_key(engine.engine_id, kid)
    return {
        'data': {
            'engine_id': key.engine_id,
            'kid': key.kid,
            'algorithm': key.algorithm,
            'public_key': key.public_key,
        }
    }


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def upsert_template(auth, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    visibility_value: Optional[str] = None

    if request.files and 'workflow_zip' in request.files:
        uploaded_file = request.files['workflow_zip']
        if not uploaded_file.filename:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'No file provided.'})

        if not uploaded_file.filename.endswith('.zip'):
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Only ZIP files are supported.'})

        raw_engine_id = request.form.get('engine_id')
        label = request.form.get('label')
        description = request.form.get('description')
        token_settings_json = request.form.get('token_settings')
        raw_visibility = request.form.get('visibility') if request.form else None
        raw_auto_activate = request.form.get('auto_activate') if request.form else None

        if not raw_engine_id:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'engine_id is required.'})

        try:
            engine_id = _normalize_engine_id(raw_engine_id)
        except ValueError:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'engine_id must be a valid UUID.'})

        engine = _get_engine_or_404(engine_id, auth.user)

        can_upload = node._id in engine.upload_whitelist_node_ids
        if not can_upload:
            can_upload = _user_has_engine_admin_access(auth.user, engine)
        if not can_upload:
            raise HTTPError(
                http_status.HTTP_403_FORBIDDEN,
                data={'message': 'This project is not authorized to upload workflow ZIP files. Contact administrator.'},
            )

        deployment_name = label or uploaded_file.filename.rsplit('.', 1)[0]

        try:
            client = get_gateway_client(engine.engine_id)
        except WorkflowGatewayConfigurationError as error:
            raise HTTPError(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                data={'message': str(error)},
            ) from error

        # Read ZIP content and flatten form-models directory
        zip_content = uploaded_file.read()
        flattened_zip = _flatten_form_models_in_zip(zip_content)

        deployment_response = client.deploy_process_definition(flattened_zip, deployment_name, uploaded_file.filename)

        deployment_id = deployment_response['id']
        definition_id = _get_definition_id_from_deployment(client, deployment_id)

        token_settings = None
        if token_settings_json:
            try:
                token_settings = json.loads(token_settings_json)
            except ValueError as error:
                raise HTTPError(
                    http_status.HTTP_400_BAD_REQUEST,
                    data={'message': 'token_settings must be valid JSON.'},
                ) from error

        if raw_visibility is not None and raw_visibility != '':
            visibility_value = _normalize_template_visibility(auth.user, raw_visibility)

    else:
        try:
            payload = request.get_json(force=True)
        except Exception as error:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Invalid JSON payload.'}) from error

        raw_engine_id = payload.get('engine_id')
        definition_id = payload.get('definition_id')
        label = payload.get('label')
        description = payload.get('description')
        token_settings = payload.get('token_settings')
        raw_visibility = payload.get('visibility')
        raw_auto_activate = payload.get('auto_activate')

        if not raw_engine_id:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'engine_id is required.'})
        try:
            engine_id = _normalize_engine_id(raw_engine_id)
        except ValueError:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'engine_id must be a valid UUID.'})

        if not definition_id or not isinstance(definition_id, str):
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'definition_id is required.'})

        engine = _get_engine_or_404(engine_id, auth.user)

        if raw_visibility is not None:
            visibility_value = _normalize_template_visibility(auth.user, raw_visibility)

    if token_settings is not None:
        token_settings = validate_token_settings(token_settings)

    auto_activate_value = None
    if raw_auto_activate is not None:
        if isinstance(raw_auto_activate, bool):
            auto_activate_value = raw_auto_activate
        elif isinstance(raw_auto_activate, str):
            auto_activate_value = raw_auto_activate.lower() in ('true', '1', 'yes')
        else:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'auto_activate must be a boolean.'},
            )

    template, created = upsert_workflow_template(
        node,
        engine_id=engine.engine_id,
        definition_id=definition_id,
        registered_by=auth.user,
        token_settings=token_settings,
        label=label,
        description=description,
        visibility=visibility_value,
        auto_activate=auto_activate_value,
    )

    activation = WorkflowActivation.objects.filter(
        node=node,
        template=template,
    ).select_related('activated_by').first()

    status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return {
        'data': _serialize_template(
            template,
            current_node=node,
            current_user=auth.user,
            activation=activation,
        ),
        'created': created,
    }, status

@must_be_valid_project
@must_be_logged_in
@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
def list_templates(auth, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    templates = get_user_accessible_templates(user)

    seen_ids = set()
    combined = []
    for template in templates:
        if template.id in seen_ids:
            continue
        seen_ids.add(template.id)
        combined.append(template)

    activation_map: Dict[int, WorkflowActivation] = {}
    if combined:
        activation_map = {
            activation.template_id: activation
            for activation in WorkflowActivation.objects.filter(
                node=node,
                template__in=[reg.id for reg in combined],
            ).select_related('template', 'activated_by')
        }

    data = [
        _serialize_template(
            reg,
            current_node=node,
            current_user=user,
            activation=activation_map.get(reg.id),
        )
        for reg in combined
    ]
    return {'data': data}


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def update_template(auth, template_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    template = _get_template_or_404(template_id, user)

    if template.node_id != node.id:
        raise HTTPError(
            http_status.HTTP_403_FORBIDDEN,
            data={'message': 'Cannot update template from a different project.'},
        )

    try:
        payload = request.get_json(force=True)
    except Exception as error:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Invalid JSON payload.'}) from error

    is_active = payload.get('is_active')
    if is_active is not None:
        if not isinstance(is_active, bool):
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'is_active must be a boolean.'})

        if is_active:
            if not template.definition.engine.is_active:
                raise HTTPError(
                    http_status.HTTP_400_BAD_REQUEST,
                    data={'message': 'Cannot activate template: workflow engine is inactive.'},
                )
            activate_workflow_template(template, user)
        else:
            deactivate_workflow_template(template)

    auto_activate = payload.get('auto_activate')
    if auto_activate is not None:
        if not isinstance(auto_activate, bool):
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'auto_activate must be a boolean.'})
        template.auto_activate = auto_activate
        template.save(update_fields=['auto_activate', 'modified'])

    # Handle label, description, and visibility updates
    update_fields = []

    label = payload.get('label')
    if label is not None:
        if not isinstance(label, str) or not label.strip():
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'label must be a non-empty string.'})
        template.label = label.strip()
        update_fields.append('label')

    description = payload.get('description')
    if description is not None:
        if not isinstance(description, str):
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'description must be a string.'})
        template.description = description
        update_fields.append('description')

    visibility = payload.get('visibility')
    if visibility is not None:
        normalized_visibility = _normalize_template_visibility(user, visibility)
        template.visibility = normalized_visibility
        update_fields.append('visibility')

    if update_fields:
        update_fields.append('modified')
        template.save(update_fields=update_fields)

    activation = WorkflowActivation.objects.filter(
        node=node,
        template=template,
    ).select_related('activated_by').first()

    return {
        'data': _serialize_template(
            template,
            current_node=node,
            current_user=auth.user,
            activation=activation,
        ),
    }


@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def delete_template(auth, template_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    template = _get_template_or_404(template_id, user)

    if template.node_id != node.id:
        raise HTTPError(
            http_status.HTTP_403_FORBIDDEN,
            data={'message': 'Cannot delete template from a different project.'},
        )

    if template.is_effectively_active:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Cannot delete active template. Disable it first.'},
        )

    if not can_delete_template(template):
        raise HTTPError(
            http_status.HTTP_409_CONFLICT,
            data={'message': 'Cannot delete template with running workflows.'},
        )

    delete_workflow_template(template)

    return {}, http_status.HTTP_204_NO_CONTENT


@must_be_valid_project
@must_be_logged_in
@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
def list_activations(auth, **kwargs):
    node = kwargs.get('node') or kwargs['project']

    activations = WorkflowActivation.objects.filter(
        node=node,
    ).select_related('template__definition__engine', 'template__node', 'activated_by')

    data = [_serialize_activation(activation) for activation in activations]
    return {'data': data}


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def retrieve_activation(auth, template_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    template = _get_template_or_404(template_id, user)

    try:
        activation = WorkflowActivation.objects.select_related('template', 'node', 'activated_by').get(
            node=node,
            template=template,
        )
    except WorkflowActivation.DoesNotExist as error:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow activation not found.'},
        ) from error

    return {'data': _serialize_activation(activation)}


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def upsert_activation(auth, template_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    template = _get_template_or_404(template_id, user)
    if not template.is_effectively_active:
        raise HTTPError(
            http_status.HTTP_409_CONFLICT,
            data={'message': 'Workflow template is not active.'},
        )

    try:
        payload = request.get_json(force=True)
    except Exception as error:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Invalid JSON payload.'}) from error

    is_enabled = payload.get('is_enabled', True)
    if not isinstance(is_enabled, bool):
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'is_enabled must be a boolean.'})

    defaults = {
        'activated_by': user,
        'is_enabled': is_enabled,
    }
    activation, created = WorkflowActivation.objects.get_or_create(
        node=node,
        template=template,
        defaults=defaults,
    )

    if is_enabled:
        activate_workflow_activation(activation, user)
    else:
        deactivate_workflow_activation(activation)

    status = http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
    return {
        'data': _serialize_activation(activation),
        'created': created,
    }, status


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def delete_activation(auth, template_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    template = _get_template_or_404(template_id, user)

    try:
        activation = WorkflowActivation.objects.select_related('template').get(node=node, template=template)
    except WorkflowActivation.DoesNotExist as error:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow activation not found.'},
        ) from error

    if not can_delete_activation(activation):
        if activation.is_effectively_active:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'Cannot delete active activation. Deactivate it first.'},
            )
        raise HTTPError(
            http_status.HTTP_409_CONFLICT,
            data={'message': 'Cannot delete activation with running workflows.'},
        )

    delete_workflow_activation(activation)

    return {}, http_status.HTTP_204_NO_CONTENT


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def start_run(auth, template_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    template = _get_template_or_404(template_id, user)

    try:
        activation = WorkflowActivation.objects.get(node=node, template=template)
    except WorkflowActivation.DoesNotExist as error:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow activation not found.'},
        ) from error

    if not activation.is_effectively_active:
        raise HTTPError(
            http_status.HTTP_409_CONFLICT,
            data={'message': 'Workflow is not active.'},
        )

    try:
        payload = request.get_json(force=True)
    except Exception as error:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Invalid JSON payload.'},
        ) from error

    if not isinstance(payload, dict):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Request payload must be an object.'},
        )

    business_key = payload.get('business_key')
    label = payload.get('label')
    variables = payload.get('variables')

    if label is not None and not isinstance(label, str):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'label must be a string.'},
        )

    if business_key is not None and not isinstance(business_key, str):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'business_key must be a string.'},
        )

    if variables is not None and not isinstance(variables, list):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'variables must be an array.'},
        )

    job_id = f'{WORKFLOW_JOB_PREFIX}{uuid.uuid4()}'
    start_workflow_process_async.apply_async(
        args=[node._id, template.id, activation.id, user._id],
        kwargs={
            'business_key': business_key,
            'label': label,
            'variables': variables,
        },
        task_id=job_id,
    )

    return {
        'data': {
            'job_id': job_id,
            'status': 'pending',
            'status_url': f'/api/v1/project/{node._id}/workflow/jobs/{job_id}/',
        }
    }, http_status.HTTP_202_ACCEPTED


@must_be_valid_project
@must_be_logged_in
@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
def list_runs(auth, **kwargs):
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    status_filter = request.args.get('status')
    limit_raw = request.args.get('limit')

    logger.info('Listing workflow runs: node=%s user=%s', node._id, user._id)

    if status_filter:
        allowed_statuses = {STATUS_RUNNING}
        if status_filter not in allowed_statuses:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'Invalid status filter.'},
            )

    limit = 50
    if limit_raw:
        if not limit_raw.isdigit():
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'limit must be a positive integer.'},
            )
        limit = max(1, min(200, int(limit_raw)))

    all_activations = _get_visible_activations(node, user)

    activation_map: Dict[int, WorkflowActivation] = {}
    for activation in all_activations:
        activation_map[activation.id] = activation

    if not activation_map:
        logger.info('No workflow activations available for runs query')
        return {
            'data': [],
            'meta': {
                'total': 0,
                'returned': 0,
                'limit': limit,
            },
        }

    collected: List[Dict[str, Any]] = []

    for activation in activation_map.values():
        activation_node = activation.node
        if activation_node.is_deleted:
            continue

        template = activation.template
        engine_id = template.definition.engine.engine_id
        business_key = f'rdm:node:{activation_node._id}:activation:{activation.id}'

        client = get_gateway_client(engine_id)
        params = {
            'businessKey': business_key,
            'includeProcessVariables': 'true',
            'sort': 'startTime',
            'order': 'desc',
            'size': limit,
        }

        # Fetch both runtime and historic instances
        runtime_response = client.list_process_instances(params)
        runtime_instances = runtime_response.get('data')

        historic_response = client.list_historic_process_instances(params)
        historic_instances = historic_response.get('data')

        # Merge runtime and historic, removing duplicates (prefer runtime for running instances)
        instance_map: Dict[str, Dict[str, Any]] = {}
        for instance in historic_instances:
            instance_map[instance['id']] = instance
        for instance in runtime_instances:
            instance_map[instance['id']] = instance

        instances = list(instance_map.values())

        for instance in instances:
            process_id = instance['id']
            try:
                metadata = _extract_metadata(instance)
            except HTTPError:
                logger.warning('Workflow process instance missing metadata', extra={'process_id': process_id})
                continue

            record = _serialize_process_instance(
                instance,
                node=activation_node,
                engine_id=engine_id,
                metadata=metadata,
            )
            if status_filter and record.get('status') != status_filter:
                continue
            collected.append(record)
            if len(collected) >= limit:
                break
        if len(collected) >= limit:
            break

    collected.sort(key=lambda item: item['started_at'], reverse=True)

    total = len(collected)
    data = collected[:limit]

    return {
        'data': data,
        'meta': {
            'total': total,
            'returned': len(data),
            'limit': limit,
        },
    }


@must_be_valid_project
@must_be_logged_in
@must_have_permission('admin')
@must_have_addon(SHORT_NAME, 'node')
def cancel_run(auth, run_id: str, **kwargs):
    """Cancel a workflow process instance.

    Note: run_id is now the process_instance_id (Flowable process instance ID).
    """
    node = kwargs.get('node') or kwargs['project']
    user = auth.user

    process_instance_id = run_id

    reason = request.args.get('reason')
    if reason is not None and not isinstance(reason, str):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'reason must be a string.'},
        )

    result = cancel_workflow_run(
        node,
        process_instance_id,
        cancelled_by=user,
        reason=reason,
    )

    return {'data': result}, http_status.HTTP_200_OK


@must_be_valid_project
@must_be_logged_in
@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
def list_tasks(auth, **kwargs):
    node = kwargs.get('node') or kwargs['project']

    status_filter = request.args.get('status')
    limit_raw = request.args.get('limit')
    limit = 100
    if limit_raw:
        if not limit_raw.isdigit():
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': 'limit must be a positive integer.'},
            )
        limit = max(1, min(200, int(limit_raw)))

    tasks = list_workflow_tasks(node, auth.user, limit=limit, status_filter=status_filter)

    return {
        'data': tasks,
        'meta': {
            'returned': len(tasks),
            'limit': limit,
        },
    }


@must_be_valid_project
@must_be_logged_in
@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
def retrieve_task(auth, engine_id: str, task_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']

    _get_engine_or_404(engine_id, auth.user)

    include_form_raw = (request.args.get('include_form') or '').lower()
    include_form = include_form_raw in {'1', 'true', 'yes'}

    task = get_workflow_task(node, task_id, auth.user, engine_id=engine_id, include_form=include_form)
    return {'data': task}


@must_be_valid_project
@must_be_logged_in
@must_have_permission('write')
@must_have_addon(SHORT_NAME, 'node')
def submit_task_action(auth, engine_id: str, task_id: str, **kwargs):
    node = kwargs.get('node') or kwargs['project']

    _get_engine_or_404(engine_id, auth.user)

    try:
        payload = request.get_json(force=True)
    except Exception as error:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Invalid JSON payload.'},
        ) from error

    if not isinstance(payload, dict):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Request payload must be an object.'},
        )

    action = payload.get('action')
    if not action or not isinstance(action, str):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'action must be a non-empty string.'},
        )

    job_id = f'{WORKFLOW_JOB_PREFIX}{uuid.uuid4()}'
    submit_task_action_async.apply_async(
        args=[node._id, task_id, auth.user._id, engine_id, action],
        kwargs={
            'variables': payload.get('variables'),
            'assignee': payload.get('assignee'),
        },
        task_id=job_id,
    )

    return {
        'data': {
            'job_id': job_id,
            'status': 'pending',
            'status_url': f'/api/v1/project/{node._id}/workflow/jobs/{job_id}/',
        }
    }, http_status.HTTP_202_ACCEPTED


@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
@must_be_logged_in
def list_engines(auth, **kwargs):
    user = auth.user
    node = kwargs.get('node') or kwargs.get('project')

    user_institution_ids = list(user.affiliated_institutions.values_list('id', flat=True))
    filters = Q(created_by=user)
    if user_institution_ids:
        filters |= Q(created_by__affiliated_institutions__in=user_institution_ids)

    queryset = WorkflowEngine.objects.filter(filters).distinct().select_related('created_by')

    data = [_serialize_engine(engine, node_id=node._id) for engine in queryset]
    return {
        'data': data,
        'meta': {
            'is_super_admin': bool(user.is_super_admin),
            'is_institutional_admin': bool(user.is_institutional_admin),
        },
    }


@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
@must_be_logged_in
def list_engine_definitions(auth, engine_id: str, **kwargs):
    engine = _get_engine_or_404(engine_id, auth.user)

    params = request.args.to_dict() if request.args else {}
    params.setdefault('size', 200)
    params.setdefault('latest', 'true')

    try:
        client = get_gateway_client(engine.engine_id)
    except WorkflowGatewayConfigurationError as error:
        logger.warning(
            'Workflow gateway configuration error for engine=%s: %s',
            engine.engine_id,
            error,
        )
        raise HTTPError(
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            data={'message': str(error)},
        ) from error

    try:
        payload = client.list_process_definitions(params)
    except WorkflowGatewayClientError as error:
        raise error
    except Exception as error:  # pragma: no cover - unexpected path
        logger.exception(
            'Unexpected error while listing workflow definitions for engine=%s',
            engine.engine_id,
        )
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={
                'message': 'Unexpected error while contacting the workflow gateway.',
                'detail': str(error),
            },
        ) from error

    if not isinstance(payload, dict):
        raise HTTPError(
            http_status.HTTP_502_BAD_GATEWAY,
            data={'message': 'Workflow gateway returned unexpected payload.'},
        )

    entries = payload.get('data') or []
    definitions = []
    for entry in entries:
        serialized = _serialize_definition_entry(entry)
        serialized['engine_id'] = engine.engine_id
        definitions.append(serialized)

    return {
        'data': definitions,
        'total': payload.get('total'),
    }


@must_be_logged_in
@require_admin
def upsert_engine(auth, **kwargs):

    try:
        payload = request.get_json(force=True)
    except Exception as error:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Invalid JSON payload.'}) from error

    raw_engine_id = payload.get('engine_id')
    label = payload.get('label', '')
    base_url = payload.get('gateway_base_url')
    signing_kid = payload.get('signing_kid')

    if not raw_engine_id or not base_url or not signing_kid:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'engine_id, gateway_base_url, and signing_kid are required.'})

    try:
        engine_id = _normalize_engine_id(raw_engine_id)
    except ValueError:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'engine_id must be a valid UUID.'})

    try:
        token_lifetime = int(payload.get('token_lifetime_seconds', 300))
        request_timeout = int(payload.get('request_timeout', 10))
    except (TypeError, ValueError):
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'token_lifetime_seconds and request_timeout must be integers.'})

    if token_lifetime <= 0:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'token_lifetime_seconds must be positive.'})
    if request_timeout <= 0:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'request_timeout must be positive.'})

    key_specs = workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS or []
    if not any(spec.get('kid') == signing_kid for spec in key_specs):
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': f'Unknown signing_kid: {signing_kid}. Configure RDM_TO_WORKFLOW_GATEWAY_KEYS first.'})

    defaults = {
        'label': label,
        'gateway_base_url': base_url,
        'signing_kid': signing_kid,
        'verify_ssl': bool(payload.get('verify_ssl', True)),
        'token_subject': payload.get('token_subject') or 'rdm-workflow-service',
        'token_scope': payload.get('token_scope') or 'workflow::delegate',
        'token_audience': payload.get('token_audience'),
        'token_issuer': payload.get('token_issuer'),
        'engine_claim': payload.get('engine_claim') or 'engine_id',
        'engine_claim_value': payload.get('engine_claim_value'),
        'token_lifetime_seconds': token_lifetime,
        'request_timeout': request_timeout,
        'is_active': bool(payload.get('is_active', True)),
    }

    obj, created = WorkflowEngine.objects.update_or_create(
        engine_id=engine_id,
        defaults=defaults,
    )

    if auth.user and (created or obj.created_by is None):
        obj.created_by = auth.user
        obj.save(update_fields=['created_by'])

    from addons.workflow.gateway_client import get_gateway_client  # local import to avoid circular dependency
    get_gateway_client.cache_clear()

    return {'data': _serialize_engine(obj)}, http_status.HTTP_201_CREATED


@must_be_logged_in
def retrieve_engine(auth, engine_id: str, **kwargs):
    engine = _get_engine_or_404(engine_id, auth.user)
    return {'data': _serialize_engine(engine)}


@must_be_logged_in
@require_admin
def delete_engine(auth, engine_id: str, **kwargs):
    engine = _get_engine_or_404(engine_id, auth.user)

    if engine.is_active:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'Cannot delete active engine. Deactivate it first.'},
        )

    if not can_delete_engine(engine):
        raise HTTPError(
            http_status.HTTP_409_CONFLICT,
            data={'message': 'Cannot delete engine with running workflows.'},
        )

    delete_workflow_engine(engine)

    from addons.workflow.gateway_client import get_gateway_client
    get_gateway_client.cache_clear()
    return {}, http_status.HTTP_204_NO_CONTENT


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
@must_be_logged_in
@must_have_permission('read')
def workflow_notification(auth, engine_id: str, process_instance_id: str, **kwargs):
    """Receive notification from workflow engine."""
    node = kwargs.get('node') or kwargs['project']

    payload = request.get_json()
    title = payload['title']
    body = payload['body']
    assignees = payload.get('assignees')
    user_ids = payload.get('user_ids')
    send_email = payload.get('send_email', False)
    add_comment = payload.get('add_comment', False)

    client = get_gateway_client(engine_id)
    # Use list API with 'id' parameter to get instance with variables
    # Note: GET /process-instances/{id} does not return variables,
    # but list API with id parameter does
    instance_response = client.list_process_instances({
        'id': process_instance_id,
        'includeProcessVariables': 'true',
    })
    if len(instance_response['data']) == 0:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Process instance not found.'},
        )
    response = instance_response['data'][0]
    metadata = _extract_metadata(response)

    send_workflow_notification(
        node,
        process_instance_id,
        auth=auth,
        metadata=metadata,
        title=title,
        body=body,
        assignees=assignees,
        user_ids=user_ids,
        send_email=send_email,
        add_comment=add_comment,
    )

    return {'message': 'Notification sent'}


@must_be_valid_project
@must_be_logged_in
@must_have_permission('read')
@must_have_addon(SHORT_NAME, 'node')
def get_job_status(auth, job_id: str, **kwargs):
    if not job_id.startswith(WORKFLOW_JOB_PREFIX):
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Job not found.'},
        )

    aresult = celery_app.AsyncResult(job_id)

    state = aresult.state

    if state == 'PENDING':
        return {'data': {'status': 'pending'}}

    if state == 'STARTED':
        return {'data': {'status': 'running'}}

    if state == 'SUCCESS':
        return {'data': {'status': 'completed'}}

    if state == 'FAILURE':
        return {'data': {'status': 'failed', 'error': str(aresult.result)}}

    raise HTTPError(
        http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        data={'message': f'Unexpected task state: {state}'},
    )

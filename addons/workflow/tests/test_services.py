# -*- coding: utf-8 -*-

import json
import uuid
from unittest import mock

import pytest
from rest_framework import status as http_status

from framework.auth.core import Auth
from framework.exceptions import HTTPError

from addons.workflow import services
from addons.workflow.gateway_client import WorkflowGatewayClientError
from addons.workflow.models import (
    WorkflowActivation,
    WorkflowDefinitionSnapshot,
    WorkflowEngine,
    WorkflowEngineKey,
    WorkflowTemplate,
)
from osf.models.comment import Comment
from osf_tests.factories import AuthUserFactory, InstitutionFactory, ProjectFactory
from tests.base import OsfTestCase


class ImportGatewayPublicKeysTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://gateway.example.com/',
            signing_kid='kid-test',
            verify_ssl=False,
            institution=institution,
        )

    def test_import_creates_or_updates_keys(self):
        payload = {
            'keys': [
                {
                    'kid': 'kid-1',
                    'alg': 'RS256',
                    'public_key': '-----BEGIN PUBLIC KEY-----\nAAA\n-----END PUBLIC KEY-----',
                },
                {
                    'kid': 'kid-2',
                    'alg': 'ES256',
                    'public_key': '-----BEGIN PUBLIC KEY-----\nBBB\n-----END PUBLIC KEY-----',
                },
            ],
        }

        client = mock.Mock()
        client.get_public_keyset.return_value = payload

        with mock.patch('addons.workflow.services.get_gateway_client', return_value=client) as mocked:
            imported = services.import_gateway_public_keys(self.engine)

        mocked.assert_called_once_with(self.engine.engine_id)
        self.assertEqual(imported, 2)

        stored_keys = WorkflowEngineKey.objects.filter(engine_id=self.engine.engine_id).order_by('kid')
        self.assertEqual(stored_keys.count(), 2)
        self.assertEqual(stored_keys[0].kid, 'kid-1')
        self.assertEqual(stored_keys[0].algorithm, 'RS256')
        self.assertTrue(stored_keys[0].is_active)
        self.assertIn('AAA', stored_keys[0].public_key)
        self.assertEqual(stored_keys[1].kid, 'kid-2')
        self.assertEqual(stored_keys[1].algorithm, 'ES256')

        # Update existing key with new material
        updated_payload = {
            'keys': [
                {
                    'kid': 'kid-1',
                    'alg': 'RS256',
                    'public_key': '-----BEGIN PUBLIC KEY-----\nNEW\n-----END PUBLIC KEY-----',
                },
            ],
        }
        client.get_public_keyset.return_value = updated_payload
        with mock.patch('addons.workflow.services.get_gateway_client', return_value=client):
            services.import_gateway_public_keys(self.engine)
        refreshed = WorkflowEngineKey.objects.get(engine_id=self.engine.engine_id, kid='kid-1')
        self.assertIn('NEW', refreshed.public_key)

    def test_import_raises_on_invalid_payload(self):
        client = mock.Mock()
        client.get_public_keyset.return_value = {'unexpected': []}

        with mock.patch('addons.workflow.services.get_gateway_client', return_value=client):
            with self.assertRaises(HTTPError) as context:
                services.import_gateway_public_keys(self.engine)

        self.assertEqual(context.exception.code, http_status.HTTP_502_BAD_GATEWAY)


class StartWorkflowProcessTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.owner = AuthUserFactory()
        self.node = ProjectFactory(creator=self.owner)
        self.node.add_addon('workflow', auth=Auth(self.owner))
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://gateway.example.com/',
            signing_kid='kid-test',
            verify_ssl=False,
            institution=institution,
        )
        definition = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='workflow-definition-1',
            definition_key='workflow-definition-1',
            name='Workflow Definition 1',
            version=1,
        )
        self.template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=definition,
            registered_by=self.owner,
        )
        self.activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
        )

    def test_start_workflow_process_validates_activation_node(self):
        other_node = ProjectFactory(creator=self.owner)
        # activation is tied to self.node, passing other_node should 404
        with self.assertRaises(HTTPError) as ctx:
            services.start_workflow_process(
                other_node,
                template=self.template,
                activation=self.activation,
                started_by=self.owner,
            )
        assert ctx.exception.code == http_status.HTTP_404_NOT_FOUND

    def test_start_workflow_process_rejects_disabled_activation(self):
        self.activation.is_enabled = False
        self.activation.save()
        with self.assertRaises(HTTPError) as ctx:
            services.start_workflow_process(
                self.node,
                template=self.template,
                activation=self.activation,
                started_by=self.owner,
            )
        assert ctx.exception.code == http_status.HTTP_409_CONFLICT

    def test_start_workflow_process_rejects_inactive_template(self):
        self.template.is_active = False
        self.template.save()
        with self.assertRaises(HTTPError) as ctx:
            services.start_workflow_process(
                self.node,
                template=self.template,
                activation=self.activation,
                started_by=self.owner,
            )
        assert ctx.exception.code == http_status.HTTP_409_CONFLICT

    @mock.patch('addons.workflow.services.get_gateway_client')
    def test_start_workflow_process_propagates_gateway_error(self, mock_get_client):
        client = mock.Mock()
        error = WorkflowGatewayClientError(http_status.HTTP_503_SERVICE_UNAVAILABLE, 'gateway down')
        client.start_process_instance.side_effect = error
        mock_get_client.return_value = client

        with self.assertRaises(HTTPError) as ctx:
            services.start_workflow_process(
                self.node,
                template=self.template,
                activation=self.activation,
                started_by=self.owner,
            )

        assert ctx.exception.code == http_status.HTTP_503_SERVICE_UNAVAILABLE
        assert 'Workflow engine request failed.' in ctx.exception.data['message']

    @mock.patch('addons.workflow.services.get_gateway_client')
    def test_start_workflow_process_successful_payload(self, mock_get_client):
        client = mock.Mock()
        mock_get_client.return_value = client
        client.start_process_instance.return_value = {'id': 'process-42', 'status': 'RUNNING'}

        result = services.start_workflow_process(
            self.node,
            template=self.template,
            activation=self.activation,
            started_by=self.owner,
            variables=[{'name': 'foo', 'type': 'string', 'value': 'bar'}],
        )

        assert result['id'] == 'process-42'
        assert result['status'] == 'running'
        assert result['node_id'] == self.node._id
        assert result['template_id'] == str(self.template.id)
        client.start_process_instance.assert_called_once()


class GetVisibleActivationsTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.owner = AuthUserFactory()
        self.node = ProjectFactory(creator=self.owner)
        self.node.add_addon('workflow', auth=Auth(self.owner))
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://gateway.example.com/',
            signing_kid='kid-test',
            verify_ssl=False,
            institution=institution,
        )
        definition = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='workflow-definition-shared',
            definition_key='workflow-definition-shared',
            name='Workflow Definition Shared',
            version=1,
        )
        self.template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=definition,
            registered_by=self.owner,
        )
        # Activation on this node
        self.local_activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
        )
        # Activation on another node that uses template from self.node
        self.shared_node = ProjectFactory()
        self.shared_activation = WorkflowActivation.objects.create(
            node=self.shared_node,
            template=self.template,
            activated_by=self.owner,
        )

    def _activation_ids(self, activations):
        return {activation.id for activation in activations}

    def test_write_user_can_see_shared_activations(self):
        write_user = AuthUserFactory()
        self.node.add_contributor(write_user, permissions='write', auth=Auth(self.owner), save=True)

        activations = services._get_visible_activations(self.node, write_user)

        assert self._activation_ids(activations) == {self.local_activation.id, self.shared_activation.id}

    def test_read_user_sees_only_local_activations(self):
        read_user = AuthUserFactory()
        self.node.add_contributor(read_user, permissions='read', auth=Auth(self.owner), save=True)

        activations = services._get_visible_activations(self.node, read_user)

        assert self._activation_ids(activations) == {self.local_activation.id}

    def test_system_calls_include_shared_activations(self):
        activations = services._get_visible_activations(self.node)

        assert self._activation_ids(activations) == {self.local_activation.id, self.shared_activation.id}


class WorkflowNotificationTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.owner = AuthUserFactory()
        self.node = ProjectFactory(creator=self.owner)
        self.node.add_addon('workflow', auth=Auth(self.owner))
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://gateway.example.com/',
            signing_kid='kid-test',
            verify_ssl=False,
            institution=institution,
        )
        self.definition = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='workflow-definition-notify',
            definition_key='workflow-definition-notify',
            name='Workflow Definition Notify',
            version=1,
        )
        self.template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=self.definition,
            registered_by=self.owner,
        )
        self.activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
        )
        self.executor = AuthUserFactory()
        self.manager = AuthUserFactory()
        self.creator = self.owner
        self.node.add_contributor(self.manager, permissions='write', auth=Auth(self.owner), save=True)
        self.node.add_contributor(self.executor, permissions='read', auth=Auth(self.owner), save=True)
        self.metadata = {
            'started_by': self.executor._id,
            'activation_id': self.activation.id,
            'template_id': self.template.id,
            'node_id': self.node._id,
            'node_title': self.node.title,
        }

    def test_resolve_notification_recipients_for_roles(self):
        extra_user = AuthUserFactory()
        recipients = services.resolve_workflow_notification_recipients(
            self.node,
            metadata=self.metadata,
            assignees=['executor', 'manager', 'creator', 'contributor'],
            user_ids=[extra_user._id],
        )

        expected = {self.executor, self.manager, self.creator, extra_user}
        assert recipients == expected

    def test_resolve_requires_targets(self):
        with pytest.raises(ValueError):
            services.resolve_workflow_notification_recipients(self.node, metadata=self.metadata)

    @mock.patch('addons.workflow.services.send_mail')
    def test_send_workflow_notification_logs_comment_and_email(self, mock_send_mail):
        auth = Auth(self.manager)
        body = [
            {'type': 'text/plain', 'content': 'Please review the workflow task.'},
            {'type': 'text/html', 'content': '<p>Please review the workflow task.</p>'},
        ]

        recipients = services.send_workflow_notification(
            self.node,
            process_instance_id='instance-123',
            auth=auth,
            metadata=self.metadata,
            title='Workflow Update',
            body=body,
            assignees=['executor'],
            user_ids=[self.manager._id],
            send_email=True,
            add_comment=True,
        )

        # Recipients include executor and explicitly provided manager
        assert set(recipients) == {self.executor._id, self.manager._id}

        log = self.node.logs.order_by('-created').first()
        assert log.action == 'workflow_notification'
        assert log.params['title'] == 'Workflow Update'
        assert 'Please review the workflow task.' in log.params['message']

        comment = Comment.objects.filter(node=self.node).order_by('-created').first()
        assert comment is not None
        assert 'Workflow Update' in comment.content

        # send_mail is called for each recipient with email addresses
        assert mock_send_mail.call_count == 2


class WorkflowTaskServiceTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.owner = AuthUserFactory()
        self.node = ProjectFactory(creator=self.owner)
        self.node.add_addon('workflow', auth=Auth(self.owner))
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://gateway.example.com/',
            signing_kid='kid-test',
            verify_ssl=False,
            institution=institution,
        )
        self.definition = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='workflow-definition-tasks',
            definition_key='workflow-definition-tasks',
            name='Workflow Definition Tasks',
            version=1,
        )
        self.template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=self.definition,
            registered_by=self.owner,
        )
        self.activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
        )

    def _metadata(self, *, started_by=None):
        return {
            'node_id': self.node._id,
            'node_title': self.node.title,
            'template_id': str(self.template.id),
            'activation_id': str(self.activation.id),
            'started_by': started_by or self.owner._id,
            'engine_id': self.engine.engine_id,
            'label': 'Workflow Run',
            'business_key': f'rdm:node:{self.node._id}:activation:{self.activation.id}',
            'started_at': '2024-01-01T00:00:00Z',
        }

    def _variables(self, metadata=None):
        payload = metadata or self._metadata()
        return [
            {
                'name': '_RDM_WORKFLOW_METADATA',
                'type': 'string',
                'value': json.dumps(payload),
            }
        ]

    def _task_entry(self, task_id='task-1', **overrides):
        entry = {
            'id': task_id,
            'name': overrides.get('name', 'Review Submission'),
            'description': overrides.get('description', 'Please review'),
            'assignee': overrides.get('assignee', 'executor'),
            'owner': overrides.get('owner', self.owner._id),
            'processInstanceId': overrides.get('process_instance_id', 'instance-1'),
            'processInstanceBusinessKey': overrides.get('business_key') or f'rdm:node:{self.node._id}:activation:{self.activation.id}',
            'processDefinitionId': self.definition.definition_id,
            'createTime': overrides.get('createTime', '2024-01-01T00:00:00Z'),
            'endTime': overrides.get('endTime'),
            'deleteReason': overrides.get('deleteReason'),
            'dueDate': overrides.get('dueDate'),
            'priority': overrides.get('priority', 50),
            'category': overrides.get('category', 'default'),
            'formKey': overrides.get('formKey', 'form-1'),
            'variables': overrides.get('variables') or self._variables(overrides.get('metadata')),
        }
        return entry

    def _instance(self, metadata=None):
        return {
            'id': 'instance-1',
            'variables': self._variables(metadata),
        }

    @mock.patch('addons.workflow.services.get_gateway_client')
    def test_list_workflow_tasks_merges_runtime_and_historic_results(self, mock_get_client):
        mock_client = mock.Mock()
        mock_get_client.return_value = mock_client
        runtime_entry = self._task_entry('task-runtime')
        historic_entry = self._task_entry('task-runtime', endTime='2024-01-02T00:00:00Z')

        mock_client.list_tasks.return_value = {'data': [runtime_entry]}
        mock_client.list_historic_tasks.return_value = {'data': [historic_entry]}

        results = services.list_workflow_tasks(self.node, self.owner, limit=5)

        assert len(results) == 1
        assert results[0]['id'] == 'task-runtime'
        assert results[0]['task_status'] == 'running'
        assert results[0]['can_complete'] is True
        mock_client.list_historic_tasks.assert_called_once()

    @mock.patch('addons.workflow.services.get_gateway_client')
    def test_list_workflow_tasks_active_filter_uses_runtime_only(self, mock_get_client):
        mock_client = mock.Mock()
        mock_get_client.return_value = mock_client
        runtime_entry = self._task_entry('task-active')
        mock_client.list_tasks.return_value = {'data': [runtime_entry]}

        results = services.list_workflow_tasks(self.node, self.owner, status_filter='active')

        assert len(results) == 1
        assert results[0]['task_status'] == 'running'
        mock_client.list_historic_tasks.assert_not_called()

    @mock.patch('addons.workflow.services.get_gateway_client')
    @mock.patch('addons.workflow.services._fetch_task_from_engines')
    def test_get_workflow_task_includes_form_payload(self, mock_fetch, mock_get_client):
        task_payload = self._task_entry('task-form')
        instance = self._instance()
        mock_fetch.return_value = (task_payload, self.engine.engine_id, instance)
        mock_client = mock.Mock()
        mock_client.get_task_form.return_value = {
            'formProperties': [
                {
                    'id': 'field-1',
                    'name': 'Field 1',
                    'type': 'string',
                    'required': True,
                    'value': 'default',
                }
            ]
        }
        mock_get_client.return_value = mock_client

        task = services.get_workflow_task(
            self.node,
            'task-form',
            self.owner,
            engine_id=self.engine.engine_id,
            include_form=True,
        )

        assert task['id'] == 'task-form'
        assert 'form' in task
        assert task['form']['fields'][0]['id'] == 'field-1'
        assert task['can_complete'] is True
        mock_client.get_task_form.assert_called_once_with('task-form')

    @mock.patch('addons.workflow.services.get_gateway_client')
    @mock.patch('addons.workflow.services._fetch_task_from_engines')
    def test_get_workflow_task_ignores_missing_form(self, mock_fetch, mock_get_client):
        task_payload = self._task_entry('task-form-missing')
        instance = self._instance()
        mock_fetch.return_value = (task_payload, self.engine.engine_id, instance)
        mock_client = mock.Mock()
        mock_client.get_task_form.side_effect = WorkflowGatewayClientError(http_status.HTTP_404_NOT_FOUND, 'missing')
        mock_get_client.return_value = mock_client

        task = services.get_workflow_task(
            self.node,
            'task-form-missing',
            self.owner,
            engine_id=self.engine.engine_id,
            include_form=True,
        )

        assert task['id'] == 'task-form-missing'
        assert 'form' not in task

    @mock.patch('addons.workflow.services.get_workflow_task')
    @mock.patch('addons.workflow.services.get_gateway_client')
    @mock.patch('addons.workflow.services._fetch_task_from_engines')
    def test_submit_workflow_task_action_updates_task(self, mock_fetch, mock_get_client, mock_get_task):
        task_payload = self._task_entry('task-complete')
        instance = self._instance()
        mock_fetch.return_value = (task_payload, self.engine.engine_id, instance)
        mock_client = mock.Mock()
        mock_get_client.return_value = mock_client
        mock_get_task.return_value = {'id': 'task-complete', 'task_status': 'completed'}

        result = services.submit_workflow_task_action(
            self.node,
            'task-complete',
            self.owner,
            engine_id=self.engine.engine_id,
            action='complete',
            variables={'approved': True},
            assignee='executor',
        )

        mock_client.update_task.assert_called_once_with(
            'task-complete',
            {
                'action': 'complete',
                'variables': [{'name': 'approved', 'value': True}],
                'assignee': 'executor',
            },
        )
        assert result['id'] == 'task-complete'

    @mock.patch('addons.workflow.services.get_workflow_task')
    @mock.patch('addons.workflow.services.get_gateway_client')
    @mock.patch('addons.workflow.services._fetch_task_from_engines')
    def test_submit_workflow_task_action_returns_none_when_task_missing(self, mock_fetch, mock_get_client, mock_get_task):
        task_payload = self._task_entry('task-vanished')
        instance = self._instance()
        mock_fetch.return_value = (task_payload, self.engine.engine_id, instance)
        mock_get_client.return_value = mock.Mock()
        mock_get_task.side_effect = HTTPError(http_status.HTTP_404_NOT_FOUND)

        result = services.submit_workflow_task_action(
            self.node,
            'task-vanished',
            self.owner,
            engine_id=self.engine.engine_id,
            action='complete',
        )

        assert result is None

    @mock.patch('addons.workflow.services.get_gateway_client')
    @mock.patch('addons.workflow.services._fetch_task_from_engines')
    def test_submit_workflow_task_action_enforces_permissions(self, mock_fetch, mock_get_client):
        other_user = AuthUserFactory()
        metadata = self._metadata(started_by=self.owner._id)
        instance = self._instance(metadata)
        payload = self._task_entry('task-forbidden', assignee='executor', variables=self._variables(metadata))
        mock_fetch.return_value = (payload, self.engine.engine_id, instance)

        with pytest.raises(HTTPError) as context:
            services.submit_workflow_task_action(
                self.node,
                'task-forbidden',
                other_user,
                engine_id=self.engine.engine_id,
                action='complete',
            )

        assert context.value.code == http_status.HTTP_403_FORBIDDEN
        mock_get_client.assert_not_called()


class DismissWorkflowActivationTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.owner = AuthUserFactory()
        self.node = ProjectFactory(creator=self.owner)
        self.node.add_addon('workflow', auth=Auth(self.owner))
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://gateway.example.com/',
            signing_kid='kid-test',
            institution=institution,
        )
        definition = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='dismiss-test-def',
            definition_key='dismiss-test-def',
            name='Dismiss Test',
            version=1,
        )
        self.template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=definition,
            registered_by=self.owner,
            auto_activate=True,
        )

    def test_dismiss_sets_is_dismissed_and_disables(self):
        activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
            is_enabled=True,
        )
        services.dismiss_workflow_activation(activation)
        activation.refresh_from_db()
        assert activation.is_dismissed is True
        assert activation.is_enabled is False

    def test_dismiss_is_idempotent(self):
        activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
            is_enabled=False,
            is_dismissed=True,
        )
        services.dismiss_workflow_activation(activation)
        activation.refresh_from_db()
        assert activation.is_dismissed is True

    def test_activate_clears_is_dismissed(self):
        activation = WorkflowActivation.objects.create(
            node=self.node,
            template=self.template,
            activated_by=self.owner,
            is_enabled=False,
            is_dismissed=True,
        )
        services.activate_workflow_activation(activation, self.owner)
        activation.refresh_from_db()
        assert activation.is_dismissed is False
        assert activation.is_enabled is True

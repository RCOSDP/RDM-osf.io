# -*- coding: utf-8 -*-
"""Integration tests for workflow engine views."""

import json
import uuid
from unittest import mock

import pytest
from rest_framework import status as http_status

from framework.auth.core import Auth
from framework.exceptions import HTTPError
from addons.workflow.models import (
    WorkflowActivation,
    WorkflowDefinitionSnapshot,
    WorkflowEngine,
    WorkflowTemplate,
)
from addons.workflow.views import (
    STATUS_CANCELLED,
    STATUS_RUNNING,
)
from osf_tests.factories import AuthUserFactory, InstitutionFactory, ProjectFactory
from tests.base import OsfTestCase
from website.util import api_url_for


pytestmark = pytest.mark.django_db


class WorkflowEngineViewTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.gateway_keyset_url = api_url_for('gateway_keyset')
        self.upsert_engine_url = api_url_for('upsert_engine')
        services_gateway_patcher = mock.patch(
            'addons.workflow.services.get_gateway_client',
            side_effect=self._build_services_gateway_client,
        )
        self.mock_services_gateway = services_gateway_patcher.start()
        self.addCleanup(services_gateway_patcher.stop)
        delegation_patcher = mock.patch(
            'addons.workflow.services.create_delegation_token',
            side_effect=self._build_delegation_token,
        )
        self.mock_create_delegation_token = delegation_patcher.start()
        self.addCleanup(delegation_patcher.stop)
        revoke_patcher = mock.patch('addons.workflow.services.revoke_delegation_token')
        revoke_patcher.start()
        self.addCleanup(revoke_patcher.stop)

    @staticmethod
    def _engine_keys_url(engine_id: str) -> str:
        return api_url_for('list_engine_keys', engine_id=engine_id)

    @staticmethod
    def _engine_definitions_url(node, engine_id: str) -> str:
        return api_url_for('list_engine_definitions', pid=node._id, engine_id=engine_id)

    def _create_engine(self, owner=None, institution=None, signing_kid=None) -> WorkflowEngine:
        engine_id = str(uuid.uuid4())
        institution = institution or InstitutionFactory()
        signing_kid = signing_kid or 'test-signing-kid'
        return WorkflowEngine.objects.create(
            engine_id=engine_id,
            gateway_base_url=f'https://{engine_id}.example.com/api/',
            signing_kid=signing_kid,
            created_by=owner,
            institution=institution,
        )

    @staticmethod
    def _template_url(node) -> str:
        return api_url_for('upsert_template', pid=node._id)

    @staticmethod
    def _create_project_with_workflow(owner):
        node = ProjectFactory(creator=owner)
        node.add_addon('workflow', auth=Auth(owner))
        return node

    def _build_services_gateway_client(self, engine_id: str):
        client = mock.Mock(name=f'gateway-client[{engine_id}]')

        def _definition_payload(definition_id: str):
            snapshot = WorkflowDefinitionSnapshot.objects.filter(
                engine__engine_id=engine_id,
                definition_id=definition_id,
            ).order_by('-id').first()
            if snapshot is not None:
                metadata = snapshot.definition_metadata or {}
                return {
                    'id': snapshot.definition_id,
                    'key': snapshot.definition_key,
                    'name': snapshot.name,
                    'version': snapshot.version,
                    'category': snapshot.category,
                    'deploymentId': metadata.get('deploymentId', ''),
                    'description': snapshot.description,
                }
            return {
                'id': definition_id,
                'key': definition_id,
                'name': definition_id,
                'version': 1,
                'category': '',
                'deploymentId': '',
                'description': '',
            }

        client.get_process_definition.side_effect = _definition_payload
        client.get_process_definition_start_form.return_value = None
        return client

    def _build_delegation_token(self, user, role, mode, label=''):
        return {
            'token_id': f'mock-token-{role}',
            'token_value': f'secret-{role}',
            'scope': mode,
            'token_owner': user._id,
        }

    def _register_template(self, node, owner, engine, definition_id):
        self._ensure_engine_admin(owner, engine)
        self.app.post_json(
            self._template_url(node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
            },
            auth=owner.auth,
        )
        template = WorkflowTemplate.objects.get(
            node=node,
            definition__definition_id=definition_id,
        )
        activation, _ = WorkflowActivation.objects.get_or_create(
            node=node,
            template=template,
            defaults={'activated_by': owner},
        )
        return template, activation

    def _ensure_engine_admin(self, user, engine):
        if engine is None or not engine.institution_id:
            return
        if not user.affiliated_institutions.filter(id=engine.institution_id).exists():
            user.affiliated_institutions.add(engine.institution)
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])

    def _build_process_instance(self, node, template, activation, *, process_id='proc-1', delete_reason=None):
        metadata = {
            'node_id': node._id,
            'node_title': node.title,
            'template_id': template._id,
            'activation_id': activation.id,
            'started_by': activation.activated_by._id,
            'label': template.definition.name,
            'business_key': f'rdm:node:{node._id}:activation:{activation.id}',
            'started_at': '2024-01-01T00:00:00Z',
        }
        variables = [
            {
                'name': '_RDM_WORKFLOW_METADATA',
                'type': 'string',
                'value': json.dumps(metadata),
            }
        ]
        instance = {
            'id': process_id,
            'processDefinitionId': template.definition.definition_id,
            'startTime': metadata['started_at'],
            'variables': variables,
        }
        if delete_reason is not None:
            instance['endTime'] = '2024-01-02T00:00:00Z'
            instance['deleteReason'] = delete_reason
        return instance

    @staticmethod
    def _activation_url(route: str, node, template) -> str:
        template_id = template._id if hasattr(template, '_id') else template
        return api_url_for(route, pid=node._id, template_id=template_id)

    @staticmethod
    def _list_engines_url(node) -> str:
        return api_url_for('list_engines', pid=node._id)

    @staticmethod
    def _run_url(node, template) -> str:
        template_id = template._id if hasattr(template, '_id') else template
        return api_url_for('start_run', pid=node._id, template_id=template_id)

    @staticmethod
    def _run_detail_url(node, run_id: int) -> str:
        return api_url_for('cancel_run', pid=node._id, run_id=run_id)

    @staticmethod
    def _tasks_url(node) -> str:
        return api_url_for('list_tasks', pid=node._id)

    @staticmethod
    def _task_detail_url(node, engine, task_id: str) -> str:
        engine_id = engine.engine_id if hasattr(engine, 'engine_id') else engine
        return api_url_for('retrieve_task', pid=node._id, engine_id=engine_id, task_id=task_id)

    @staticmethod
    def _task_action_url(node, engine, task_id: str) -> str:
        engine_id = engine.engine_id if hasattr(engine, 'engine_id') else engine
        return api_url_for('submit_task_action', pid=node._id, engine_id=engine_id, task_id=task_id)

    def test_list_engines_limits_to_owner_and_affiliation(self):
        user = AuthUserFactory()
        shared_institution = InstitutionFactory()
        user.affiliated_institutions.add(shared_institution)

        same_institution_owner = AuthUserFactory()
        same_institution_owner.affiliated_institutions.add(shared_institution)

        other_institution = InstitutionFactory()
        other_owner = AuthUserFactory()
        other_owner.affiliated_institutions.add(other_institution)

        node = self._create_project_with_workflow(user)
        own_engine = self._create_engine(owner=user)
        shared_engine = self._create_engine(owner=same_institution_owner)
        other_engine = self._create_engine(owner=other_owner)
        ownerless_engine = self._create_engine()

        response = self.app.get(self._list_engines_url(node), auth=user.auth)
        engine_ids = {item['engine_id'] for item in response.json['data']}

        assert engine_ids == {own_engine.engine_id, shared_engine.engine_id}
        assert other_engine.engine_id not in engine_ids
        assert ownerless_engine.engine_id not in engine_ids
        assert response.json['meta']['is_super_admin'] is False
        assert response.json['meta']['is_institutional_admin'] is False

    def test_list_engines_applies_same_rules_to_admin(self):
        admin = AuthUserFactory()
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        other = AuthUserFactory()
        node = self._create_project_with_workflow(admin)
        own_engine = self._create_engine(owner=admin)
        other_engine = self._create_engine(owner=other)
        ownerless_engine = self._create_engine()

        response = self.app.get(self._list_engines_url(node), auth=admin.auth)
        engine_ids = {item['engine_id'] for item in response.json['data']}

        assert engine_ids == {own_engine.engine_id}
        assert other_engine.engine_id not in engine_ids
        assert ownerless_engine.engine_id not in engine_ids
        assert response.json['meta']['is_super_admin'] is True
        assert response.json['meta']['is_institutional_admin'] is False

    def test_list_engine_definitions_returns_payload(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)
        self._ensure_engine_admin(owner, engine)

        mock_client = mock.Mock()
        mock_client.list_process_definitions.return_value = {
            'data': [
                {
                    'id': 'workflow:definition:alpha',
                    'name': 'Process Alpha',
                    'version': 3,
                    'key': 'alpha',
                    'category': 'demo',
                    'deploymentId': 'deploy-1',
                    'description': 'Example definition',
                }
            ],
            'total': 1,
        }

        with mock.patch('addons.workflow.views.get_gateway_client', return_value=mock_client):
            response = self.app.get(
                self._engine_definitions_url(node, engine.engine_id),
                auth=owner.auth,
            )

        assert response.status_code == http_status.HTTP_200_OK
        payload = response.json
        assert payload['total'] == 1
        definitions = payload['data']
        assert len(definitions) == 1
        assert definitions[0]['definition_id'] == 'workflow:definition:alpha'
        assert definitions[0]['definition_name'] == 'Process Alpha'
        assert definitions[0]['definition_version'] == 3
        assert definitions[0]['definition_deployment_id'] == 'deploy-1'

    def test_retrieve_engine_allows_owner(self):
        user = AuthUserFactory()
        engine = self._create_engine(owner=user)
        self._ensure_engine_admin(user, engine)

        response = self.app.get(
            api_url_for('retrieve_engine', engine_id=engine.engine_id),
            auth=user.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['data']['engine_id'] == engine.engine_id

    def test_retrieve_engine_allows_affiliated_user(self):
        user = AuthUserFactory()
        shared_institution = InstitutionFactory()
        user.affiliated_institutions.add(shared_institution)

        owner = AuthUserFactory()
        owner.affiliated_institutions.add(shared_institution)

        engine = self._create_engine(owner=owner, institution=shared_institution)
        self._ensure_engine_admin(user, engine)

        response = self.app.get(
            api_url_for('retrieve_engine', engine_id=engine.engine_id),
            auth=user.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['data']['engine_id'] == engine.engine_id

    def test_retrieve_engine_denies_unrelated_user(self):
        user = AuthUserFactory()
        other = AuthUserFactory()
        engine = self._create_engine(owner=other)

        response = self.app.get(
            api_url_for('retrieve_engine', engine_id=engine.engine_id),
            auth=user.auth,
            expect_errors=True,
        )
        assert response.status_code == http_status.HTTP_404_NOT_FOUND

    def test_admin_requirement_allows_staff_but_not_regular_user(self):
        staff_user = AuthUserFactory()
        staff_user.is_staff = True
        staff_user.is_superuser = False
        staff_user.save()

        engine = self._create_engine(owner=staff_user)
        staff_user.affiliated_institutions.add(engine.institution)

        response = self.app.get(self._engine_keys_url(engine.engine_id), auth=staff_user.auth)
        assert response.status_code == http_status.HTTP_200_OK
        assert response.json == {'data': []}

        regular_user = AuthUserFactory()
        response = self.app.get(
            self._engine_keys_url(engine.engine_id),
            auth=regular_user.auth,
            expect_errors=True,
        )
        assert response.status_code == http_status.HTTP_403_FORBIDDEN

    def test_engine_keys_rejects_staff_without_visibility(self):
        owner = AuthUserFactory()
        engine = self._create_engine(owner=owner)

        staff_user = AuthUserFactory()
        staff_user.is_staff = True
        staff_user.is_superuser = False
        staff_user.save()

        response = self.app.get(
            self._engine_keys_url(engine.engine_id),
            auth=staff_user.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_404_NOT_FOUND

    @mock.patch('addons.workflow.views.build_public_keyset')
    def test_gateway_keyset_returns_configured_keys(self, mock_build_keyset):
        payload = {
            'keys': [
                {
                    'kid': 'test-key',
                    'alg': 'RS256',
                    'public_key': 'PEM DATA',
                }
            ]
        }
        mock_build_keyset.return_value = payload

        response = self.app.get(self.gateway_keyset_url)
        assert response.status_code == http_status.HTTP_200_OK
        assert response.json == payload
        mock_build_keyset.assert_called_once_with()

    @mock.patch('addons.workflow.views.build_public_keyset')
    def test_gateway_keyset_returns_503_when_unconfigured(self, mock_build_keyset):
        mock_build_keyset.side_effect = HTTPError(
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            data={'message': 'Workflow gateway keys are not configured.'},
        )

        response = self.app.get(self.gateway_keyset_url, expect_errors=True)
        assert response.status_code == http_status.HTTP_503_SERVICE_UNAVAILABLE

    def test_register_workflow_success(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)
        definition_id = 'process-definition-1'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Example Process',
            version=1,
        )

        token_settings = {'creator_mode': 'read', 'manager_mode': 'readwrite'}
        self._ensure_engine_admin(owner, engine)
        response = self.app.post_json(
            self._template_url(node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
                'label': 'My Workflow',
                'description': 'Test template',
                'token_settings': token_settings,
            },
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_201_CREATED
        payload = response.json
        assert payload['created'] is True
        data = payload['data']
        assert data['engine_id'] == engine.engine_id
        assert data['definition_id'] == definition_id
        assert data['label'] == 'My Workflow'
        assert data['token_settings'] == token_settings
        assert data['is_enabled'] is False
        assert data['activation_id'] is None
        assert data['activation_activated_by'] is None

        template = WorkflowTemplate.objects.get(
            node=node,
            definition__definition_id=definition_id,
        )
        assert not WorkflowActivation.objects.filter(
            node=node,
            template=template,
        ).exists()

    def test_register_workflow_rejects_invalid_engine_id(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        response = self.app.post_json(
            self._template_url(node),
            {
                'engine_id': 'not-a-uuid',
                'definition_id': 'definition-1',
            },
            auth=owner.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_register_workflow_requires_write_permission(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)
        definition_id = 'process-definition-2'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Example Process',
            version=1,
        )

        outsider = AuthUserFactory()
        response = self.app.post_json(
            self._template_url(node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
            },
            auth=outsider.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_403_FORBIDDEN

    def test_register_workflow_reuses_existing_template(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)
        definition_id = 'process-definition-3'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Example Process',
            version=1,
        )

        # First call creates the template
        self._ensure_engine_admin(owner, engine)
        self.app.post_json(
            self._template_url(node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
            },
            auth=owner.auth,
        )

        # Second call should reuse existing record
        self._ensure_engine_admin(owner, engine)
        response = self.app.post_json(
            self._template_url(node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
                'label': 'Updated Label',
            },
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['created'] is False
        data = response.json['data']
        assert data['label'] == 'Updated Label'

    @mock.patch('addons.workflow.views.workflow_settings')
    def test_register_engine_rejects_non_uuid_engine_id(self, mock_settings):
        admin = AuthUserFactory()
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        kid = 'test-signing-kid'
        mock_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = [{'kid': kid}]

        response = self.app.post_json(
            self.upsert_engine_url,
            {
                'engine_id': 'not-a-uuid',
                'gateway_base_url': 'https://workflow.example/api/',
                'signing_kid': kid,
            },
            auth=admin.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    @mock.patch('addons.workflow.views.workflow_settings')
    def test_register_engine_accepts_uuid_and_normalizes(self, mock_settings):
        admin = AuthUserFactory()
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        kid = 'test-signing-kid'
        mock_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = [{'kid': kid}]

        raw_engine_id = str(uuid.uuid4()).upper()
        normalized_engine_id = str(uuid.UUID(raw_engine_id))
        placeholder_institution = InstitutionFactory()
        WorkflowEngine.objects.create(
            engine_id=normalized_engine_id,
            gateway_base_url='https://placeholder.example/api/',
            signing_kid=kid,
            institution=placeholder_institution,
        )
        response = self.app.post_json(
            self.upsert_engine_url,
            {
                'engine_id': raw_engine_id,
                'gateway_base_url': 'https://workflow.example/api/',
                'signing_kid': kid,
                'token_lifetime_seconds': 600,
                'request_timeout': 15,
            },
            auth=admin.auth,
        )

        assert response.status_code == http_status.HTTP_201_CREATED
        stored_id = response.json['data']['engine_id']
        assert stored_id == str(uuid.UUID(raw_engine_id))
        assert WorkflowEngine.objects.filter(engine_id=stored_id).exists()
        WorkflowEngine.objects.filter(engine_id=stored_id).delete()

    def test_list_templates_includes_local_and_shared(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)
        definition_id_local = 'process-definition-local'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id_local,
            definition_key='process-def-key',
            name='Local Process',
            version=1,
        )

        self._ensure_engine_admin(owner, engine)
        self.app.post_json(
            self._template_url(node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id_local,
                'label': 'Local Flow',
            },
            auth=owner.auth,
        )

        shared_owner = AuthUserFactory()
        shared_node = self._create_project_with_workflow(shared_owner)
        shared_node.add_contributor(owner, auth=Auth(shared_owner), save=True)
        engine_shared = self._create_engine(owner=shared_owner)
        definition_id_shared = 'process-definition-shared'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine_shared,
            definition_id=definition_id_shared,
            definition_key='process-def-key',
            name='Shared Process',
            version=1,
        )
        self._ensure_engine_admin(shared_owner, engine_shared)
        self.app.post_json(
            self._template_url(shared_node),
            {
                'engine_id': engine_shared.engine_id,
                'definition_id': definition_id_shared,
                'label': 'Shared Flow',
            },
            auth=shared_owner.auth,
        )

        hidden_owner = AuthUserFactory()
        hidden_node = self._create_project_with_workflow(hidden_owner)
        engine_hidden = self._create_engine(owner=hidden_owner)
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine_hidden,
            definition_id='process-definition-hidden',
            definition_key='process-def-key',
            name='Hidden Process',
            version=1,
        )
        self._ensure_engine_admin(hidden_owner, engine_hidden)
        self.app.post_json(
            self._template_url(hidden_node),
            {
                'engine_id': engine_hidden.engine_id,
                'definition_id': 'process-definition-hidden',
            },
            auth=hidden_owner.auth,
        )

        response = self.app.get(
            api_url_for('list_templates', pid=node._id),
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        templates = response.json['data']
        guids = {entry['definition_id']: entry for entry in templates}
        assert definition_id_local in guids
        assert definition_id_shared in guids
        assert 'process-definition-hidden' not in guids
        assert guids[definition_id_local]['is_local'] is True
        assert guids[definition_id_shared]['is_local'] is False
        assert guids[definition_id_local]['node_id'] == node._id
        assert guids[definition_id_shared]['node_id'] == shared_node._id
        assert guids[definition_id_local]['visibility'] == WorkflowTemplate.VISIBILITY_PROJECT
        assert guids[definition_id_shared]['visibility'] == WorkflowTemplate.VISIBILITY_PROJECT
        assert guids[definition_id_local]['is_enabled'] is False
        assert guids[definition_id_shared]['is_enabled'] is False
        assert guids[definition_id_local]['activation_id'] is None
        assert guids[definition_id_shared]['activation_id'] is None

    def test_list_templates_includes_institution_visibility_for_affiliates(self):
        owner = AuthUserFactory()
        shared_node = self._create_project_with_workflow(owner)
        viewer = AuthUserFactory()
        viewer_node = self._create_project_with_workflow(viewer)
        institution = InstitutionFactory()
        owner.affiliated_institutions.add(institution)
        viewer.affiliated_institutions.add(institution)
        shared_node.affiliated_institutions.add(institution)

        engine = self._create_engine(owner=owner, institution=institution)
        definition_id = 'institution-visible-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Institution Visible Flow',
            version=1,
        )

        self._ensure_engine_admin(owner, engine)
        self.app.post_json(
            self._template_url(shared_node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
                'label': 'Institution Template',
                'visibility': WorkflowTemplate.VISIBILITY_INSTITUTION,
            },
            auth=owner.auth,
        )

        response = self.app.get(
            api_url_for('list_templates', pid=viewer_node._id),
            auth=viewer.auth,
        )
        data = response.json['data']
        guids = {entry['definition_id']: entry for entry in data}
        assert definition_id in guids
        assert guids[definition_id]['visibility'] == WorkflowTemplate.VISIBILITY_INSTITUTION

    def test_list_templates_includes_public_visibility_for_all_users(self):
        owner = AuthUserFactory()
        shared_node = self._create_project_with_workflow(owner)
        viewer = AuthUserFactory()
        viewer_node = self._create_project_with_workflow(viewer)
        owner.is_staff = True
        owner.is_superuser = True
        owner.save(update_fields=['is_staff', 'is_superuser'])

        engine = self._create_engine(owner=owner)
        definition_id = 'public-visible-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Public Visible Flow',
            version=1,
        )

        self._ensure_engine_admin(owner, engine)
        self.app.post_json(
            self._template_url(shared_node),
            {
                'engine_id': engine.engine_id,
                'definition_id': definition_id,
                'label': 'Public Template',
                'visibility': WorkflowTemplate.VISIBILITY_PUBLIC,
            },
            auth=owner.auth,
        )

        response = self.app.get(
            api_url_for('list_templates', pid=viewer_node._id),
            auth=viewer.auth,
        )
        data = response.json['data']
        guids = {entry['definition_id']: entry for entry in data}
        assert definition_id in guids
        assert guids[definition_id]['visibility'] == WorkflowTemplate.VISIBILITY_PUBLIC

    def test_engine_endpoints_reject_invalid_identifier(self):
        user = AuthUserFactory()
        response = self.app.get(
            api_url_for('retrieve_engine', engine_id='invalid-id'),
            auth=user.auth,
            expect_errors=True,
        )
        assert response.status_code == http_status.HTTP_404_NOT_FOUND

        admin = AuthUserFactory()
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        response = self.app.get(
            self._engine_keys_url('invalid-id'),
            auth=admin.auth,
            expect_errors=True,
        )
        assert response.status_code == http_status.HTTP_404_NOT_FOUND

    def test_activation_lifecycle_for_shared_template(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        shared_owner = AuthUserFactory()
        shared_node = self._create_project_with_workflow(shared_owner)
        shared_node.add_contributor(owner, auth=Auth(shared_owner), save=True)

        engine_shared = self._create_engine(owner=shared_owner)
        definition_id_shared = 'activation-shared-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine_shared,
            definition_id=definition_id_shared,
            definition_key='process-def-key',
            name='Shared Activation Process',
            version=1,
        )

        self._ensure_engine_admin(shared_owner, engine_shared)
        self.app.post_json(
            self._template_url(shared_node),
            {
                'engine_id': engine_shared.engine_id,
                'definition_id': definition_id_shared,
                'label': 'Shared Flow',
            },
            auth=shared_owner.auth,
        )

        template = WorkflowTemplate.objects.get(
            node=shared_node,
            definition__definition_id=definition_id_shared,
        )

        response = self.app.put_json(
            self._activation_url('upsert_activation', node, template),
            {'is_enabled': True},
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_201_CREATED
        data = response.json['data']
        assert data['is_enabled'] is True
        assert data['activated_by'] == owner._id

        activation = WorkflowActivation.objects.get(node=node, template=template)
        assert activation.is_enabled is True

        response = self.app.get(
            self._activation_url('retrieve_activation', node, template),
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['data']['is_enabled'] is True

        response = self.app.put_json(
            self._activation_url('upsert_activation', node, template),
            {'is_enabled': False},
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        activation.refresh_from_db()
        assert activation.is_enabled is False

        response = self.app.put_json(
            self._activation_url('upsert_activation', node, template),
            {'is_enabled': True},
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        activation.refresh_from_db()
        assert activation.is_enabled is True

    @mock.patch('addons.workflow.views.start_workflow_process_async')
    def test_start_run_returns_service_payload(self, mock_start_async):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'start-process-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Process to Start',
            version=1,
        )

        template, activation = self._register_template(node, owner, engine, definition_id)

        response = self.app.post_json(
            self._run_url(node, template),
            {'label': 'Custom Run Label'},
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_202_ACCEPTED
        assert response.json['data']['job_id'].startswith('wf-')
        assert response.json['data']['status'] == 'pending'
        assert 'status_url' in response.json['data']
        mock_start_async.apply_async.assert_called_once()
        call_kwargs = mock_start_async.apply_async.call_args
        assert call_kwargs[1]['args'] == [node._id, template.id, activation.id, owner._id]
        assert call_kwargs[1]['kwargs'] == {
            'business_key': None,
            'label': 'Custom Run Label',
            'variables': None,
        }

    @mock.patch('addons.workflow.views.get_gateway_client')
    def test_list_runs_returns_recent_runs(self, mock_get_client):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'listing-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Listable Process',
            version=1,
        )

        template, activation = self._register_template(node, owner, engine, definition_id)

        client = mock.Mock()
        mock_get_client.return_value = client
        runtime_instance = self._build_process_instance(node, template, activation, process_id='proc-runtime')
        historic_instance = self._build_process_instance(
            node,
            template,
            activation,
            process_id='proc-historic',
            delete_reason='completed',
        )
        client.list_process_instances.return_value = {'data': [runtime_instance]}
        client.list_historic_process_instances.return_value = {'data': [historic_instance]}

        listing = self.app.get(
            api_url_for('list_runs', pid=node._id),
            auth=owner.auth,
        )

        assert listing.status_code == http_status.HTTP_200_OK
        data = listing.json['data']
        assert len(data) == 2
        statuses = {entry['status'] for entry in data}
        assert statuses == {STATUS_RUNNING, STATUS_CANCELLED}

    @mock.patch('addons.workflow.views.cancel_workflow_run')
    def test_cancel_run_by_admin_returns_payload(self, mock_cancel):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        run_id = 'proc-cancel'
        mock_cancel.return_value = {
            'id': run_id,
            'status': STATUS_CANCELLED,
            'business_key': f'rdm:node:{node._id}:activation:1',
        }

        response = self.app.delete(
            f'{self._run_detail_url(node, run_id)}?reason=manual',
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['data']['status'] == STATUS_CANCELLED
        mock_cancel.assert_called_once_with(
            node,
            run_id,
            cancelled_by=owner,
            reason='manual',
        )

    def test_cancel_run_requires_admin_permissions(self):
        owner = AuthUserFactory()
        contributor = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        node.add_contributor(contributor, permissions='write')
        node.save()

        run_id = 'proc-forbidden'
        forbidden = self.app.delete(
            self._run_detail_url(node, run_id),
            auth=contributor.auth,
            expect_errors=True,
        )

        assert forbidden.status_code == http_status.HTTP_403_FORBIDDEN

    @mock.patch('addons.workflow.views.list_workflow_tasks')
    def test_list_tasks_returns_service_payload(self, mock_list_tasks):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        mock_list_tasks.return_value = [
            {
                'id': 'task-1',
                'engine_id': 'engine-a',
                'status': 'running',
            }
        ]

        response = self.app.get(
            f'{self._tasks_url(node)}?status=running&limit=25',
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['data'] == mock_list_tasks.return_value
        assert response.json['meta']['returned'] == 1
        assert response.json['meta']['limit'] == 25
        mock_list_tasks.assert_called_once_with(
            node,
            owner,
            limit=25,
            status_filter='running',
        )

    @mock.patch('addons.workflow.views.get_workflow_task')
    def test_retrieve_task_with_form_flag(self, mock_get_task):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)

        mock_get_task.return_value = {
            'id': 'task-2',
            'name': 'Review Submission',
            'form': {'key': 'review-form'},
        }

        self._ensure_engine_admin(owner, engine)
        response = self.app.get(
            f'{self._task_detail_url(node, engine, "task-2")}?include_form=true',
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_200_OK
        assert response.json['data'] == mock_get_task.return_value
        mock_get_task.assert_called_once_with(
            node,
            'task-2',
            owner,
            engine_id=engine.engine_id,
            include_form=True,
        )

    @mock.patch('addons.workflow.views.get_workflow_task')
    def test_retrieve_task_returns_not_found_for_invisible_task(self, mock_get_task):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)

        self._ensure_engine_admin(owner, engine)
        mock_get_task.side_effect = HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': 'Workflow task not found.'},
        )

        response = self.app.get(
            self._task_detail_url(node, engine, 'task-other-node'),
            auth=owner.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_404_NOT_FOUND

    @mock.patch('addons.workflow.views.send_workflow_notification')
    @mock.patch('addons.workflow.views.get_gateway_client')
    def test_workflow_notification_allows_visible_shared_activation(self, mock_get_client, mock_send):
        owner = AuthUserFactory()
        template_node = self._create_project_with_workflow(owner)
        executor_node = ProjectFactory(creator=owner)
        executor_node.add_addon('workflow', auth=Auth(owner))
        engine = self._create_engine(owner=owner)

        self._ensure_engine_admin(owner, engine)
        definition_id = 'notification-shared-test'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key=definition_id,
            name='Notification Shared Test',
            version=1,
        )
        template, activation = self._register_template(template_node, owner, engine, definition_id)
        activation.node = executor_node
        activation.save(update_fields=['node'])

        process_instance = self._build_process_instance(
            executor_node,
            template,
            activation,
            process_id='process-shared',
        )

        mock_client = mock.Mock()
        mock_client.list_process_instances.return_value = {
            'data': [process_instance],
        }
        mock_get_client.return_value = mock_client

        response = self.app.post_json(
            api_url_for('workflow_notification', pid=template_node._id, engine_id=engine.engine_id, process_instance_id='process-shared'),
            {
                'title': 'Workflow Update',
                'body': [{'type': 'text/plain', 'content': 'hello'}],
            },
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_200_OK
        mock_send.assert_called_once()

    @mock.patch('addons.workflow.views.send_workflow_notification')
    @mock.patch('addons.workflow.views.get_gateway_client')
    def test_workflow_notification_returns_not_found_for_invisible_shared_activation(self, mock_get_client, mock_send):
        owner = AuthUserFactory()
        read_user = AuthUserFactory()
        template_node = self._create_project_with_workflow(owner)
        template_node.add_contributor(read_user, permissions='read', auth=Auth(owner), save=True)
        executor_node = ProjectFactory(creator=owner)
        executor_node.add_addon('workflow', auth=Auth(owner))
        engine = self._create_engine(owner=owner)

        self._ensure_engine_admin(owner, engine)
        self._ensure_engine_admin(read_user, engine)
        definition_id = 'notification-invisible-test'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key=definition_id,
            name='Notification Invisible Test',
            version=1,
        )
        template, activation = self._register_template(template_node, owner, engine, definition_id)
        activation.node = executor_node
        activation.save(update_fields=['node'])

        process_instance = self._build_process_instance(
            executor_node,
            template,
            activation,
            process_id='process-hidden',
        )

        mock_client = mock.Mock()
        mock_client.list_process_instances.return_value = {
            'data': [process_instance],
        }
        mock_get_client.return_value = mock_client

        response = self.app.post_json(
            api_url_for('workflow_notification', pid=template_node._id, engine_id=engine.engine_id, process_instance_id='process-hidden'),
            {
                'title': 'Workflow Update',
                'body': [{'type': 'text/plain', 'content': 'hello'}],
            },
            auth=read_user.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_404_NOT_FOUND
        mock_send.assert_not_called()

    @mock.patch('addons.workflow.views.submit_task_action_async')
    def test_submit_task_action_returns_job_info(self, mock_submit_async):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)
        engine = self._create_engine(owner=owner)

        self._ensure_engine_admin(owner, engine)
        response = self.app.post_json(
            self._task_action_url(node, engine, 'task-3'),
            {
                'action': 'complete',
                'variables': {'decision': 'approve'},
                'assignee': 'user-123',
            },
            auth=owner.auth,
        )

        assert response.status_code == http_status.HTTP_202_ACCEPTED
        assert response.json['data']['job_id'].startswith('wf-')
        assert response.json['data']['status'] == 'pending'
        assert 'status_url' in response.json['data']
        mock_submit_async.apply_async.assert_called_once()
        call_kwargs = mock_submit_async.apply_async.call_args
        assert call_kwargs[1]['args'] == [node._id, 'task-3', owner._id, engine.engine_id, 'complete']
        assert call_kwargs[1]['kwargs'] == {
            'variables': {'decision': 'approve'},
            'assignee': 'user-123',
        }

    def test_start_run_rejects_disabled_activation(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'disabled-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Disabled Process',
            version=1,
        )

        template, activation = self._register_template(node, owner, engine, definition_id)
        activation.is_enabled = False
        activation.save()

        response = self.app.post_json(
            self._run_url(node, template),
            {},
            auth=owner.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_409_CONFLICT

    def test_start_run_rejects_non_dict_parameters(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'parameter-definition'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='process-def-key',
            name='Parameter Process',
            version=1,
        )

        template, _ = self._register_template(node, owner, engine, definition_id)

        response = self.app.post_json(
            self._run_url(node, template),
            {'variables': 'not-a-list'},
            auth=owner.auth,
            expect_errors=True,
        )

        assert response.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_upsert_activation_dismiss(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'dismiss-view-test'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='dismiss-view-test',
            name='Dismiss View Test',
            version=1,
        )

        template, activation = self._register_template(node, owner, engine, definition_id)

        response = self.app.put_json(
            self._activation_url('upsert_activation', node, template),
            {'is_dismissed': True},
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK

        activation.refresh_from_db()
        assert activation.is_dismissed is True
        assert activation.is_enabled is False

    def test_list_activations_excludes_dismissed(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'dismissed-list-test'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='dismissed-list-test',
            name='Dismissed List Test',
            version=1,
        )

        template, activation = self._register_template(node, owner, engine, definition_id)
        activation.is_dismissed = True
        activation.is_enabled = False
        activation.save(update_fields=['is_dismissed', 'is_enabled'])

        response = self.app.get(
            api_url_for('list_activations', pid=node._id),
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK
        assert len(response.json['data']) == 0

    def test_upsert_activation_enable_clears_dismissed(self):
        owner = AuthUserFactory()
        node = self._create_project_with_workflow(owner)

        engine = self._create_engine(owner=owner)
        definition_id = 'reactivate-dismissed-test'
        WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id=definition_id,
            definition_key='reactivate-dismissed-test',
            name='Reactivate Dismissed Test',
            version=1,
        )

        template, activation = self._register_template(node, owner, engine, definition_id)
        activation.is_dismissed = True
        activation.is_enabled = False
        activation.save(update_fields=['is_dismissed', 'is_enabled'])

        response = self.app.put_json(
            self._activation_url('upsert_activation', node, template),
            {'is_enabled': True},
            auth=owner.auth,
        )
        assert response.status_code == http_status.HTTP_200_OK

        activation.refresh_from_db()
        assert activation.is_dismissed is False
        assert activation.is_enabled is True

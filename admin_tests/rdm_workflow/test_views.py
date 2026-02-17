# -*- coding: utf-8 -*-

import uuid
from unittest import mock
from urllib.parse import urljoin

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.test import RequestFactory

from tests.base import AdminTestCase
from admin_tests.utilities import setup_user_view
from osf_tests.factories import AuthUserFactory, InstitutionFactory

from addons.workflow.models import WorkflowEngine, WorkflowEngineKey
from admin.rdm_workflow import forms as workflow_forms, views
from addons.workflow import settings as workflow_settings


class WorkflowEngineAdminTests(AdminTestCase):
    def setUp(self):
        super(WorkflowEngineAdminTests, self).setUp()
        self.factory = RequestFactory()

        self.super_admin = AuthUserFactory()
        self.super_admin.is_staff = True
        self.super_admin.is_superuser = True
        self.super_admin.save()

        self.institution = InstitutionFactory()
        self.institution_admin = AuthUserFactory()
        self.institution_admin.is_staff = True
        self.institution_admin.save()
        self.institution_admin.affiliated_institutions.add(self.institution)

        self.engine_list_url = reverse('rdm_workflow:engine-list', kwargs={'institution_id': self.institution.id})
        self.home_url = reverse('rdm_workflow:home')
        self._original_specs = workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS
        workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = [
            {'kid': 'kid-1', 'alg': 'RS256', 'public_key_path': '/tmp/pub', 'private_key_path': '/tmp/priv'},
        ]

    def tearDown(self):
        workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = self._original_specs
        super(WorkflowEngineAdminTests, self).tearDown()

    def _request_with_messages(self, method, path, user, data=None):
        if method == 'post':
            request = self.factory.post(path, data=data or {})
        else:
            request = self.factory.get(path, data=data or {})
        request.user = user
        request.session = {}
        storage = FallbackStorage(request)
        setattr(request, '_messages', storage)
        return request

    def _keys_url(self, engine_id):
        return reverse('rdm_workflow:engine-keys', kwargs={'institution_id': self.institution.id, 'engine_id': engine_id})

    def _create_engine_payload(self):
        return {
            'action': 'create_engine',
            'gateway_base_url': 'https://example.com/api/',
            'signing_kid': 'kid-1',
            'verify_ssl': 'on',
            'token_subject': 'rdm-workflow-service',
            'token_scope': 'workflow::delegate',
            'token_audience': '',
            'token_issuer': '',
            'engine_claim': 'engine_id',
            'engine_claim_value': '',
            'token_lifetime_seconds': 300,
            'request_timeout': 10,
        }

    def test_super_admin_can_view_engine_list(self):
        request = self._request_with_messages('get', self.engine_list_url, self.super_admin)
        response = views.WorkflowEngineListView.as_view()(request, institution_id=self.institution.id)
        self.assertEqual(response.status_code, 200)

    def test_staff_without_institution_is_forbidden(self):
        staff_user = AuthUserFactory()
        staff_user.is_staff = True
        staff_user.save()

        request = self.factory.get(self.engine_list_url)
        request.user = staff_user
        view = views.WorkflowEngineListView.as_view()
        with self.assertRaises(PermissionDenied):
            view(request, institution_id=self.institution.id)

    def test_institution_admin_only_sees_own_engines(self):
        other_admin = AuthUserFactory()
        other_admin.is_staff = True
        other_admin.save()

        WorkflowEngine.objects.create(
            engine_id='engine-admin',
            gateway_base_url='https://admin.example.com/',
            signing_kid='kid-admin',
            created_by=self.institution_admin,
            institution=self.institution,
        )
        other_institution = InstitutionFactory()
        WorkflowEngine.objects.create(
            engine_id='engine-other',
            gateway_base_url='https://other.example.com/',
            signing_kid='kid-other',
            created_by=other_admin,
            institution=other_institution,
        )

        request = self.factory.get(self.engine_list_url)
        request.user = self.institution_admin
        view = views.WorkflowEngineListView()
        view = setup_user_view(view, request, user=self.institution_admin)
        view.kwargs = {'institution_id': self.institution.id}
        view.institution = self.institution
        queryset = view.get_engine_queryset()
        engines = list(queryset)
        self.assertEqual(len(engines), 1)
        self.assertEqual(engines[0].engine_id, 'engine-admin')

    def test_register_engine(self):
        request = self._request_with_messages('post', self.engine_list_url, self.super_admin, self._create_engine_payload())
        response = views.WorkflowEngineListView.as_view()(request, institution_id=self.institution.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkflowEngine.objects.count(), 1)
        engine = WorkflowEngine.objects.first()
        self.assertIsNotNone(engine)
        uuid.UUID(engine.engine_id, version=4)

    def test_signing_kid_choices_populated_from_settings(self):
        original_specs = workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS
        workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = [
            {'kid': 'kid-choice-1'},
            {'kid': 'kid-choice-2'},
        ]
        try:
            form = workflow_forms.WorkflowEngineForm()
            choices = form.fields['signing_kid'].choices
            self.assertIn(('kid-choice-1', 'kid-choice-1'), choices)
            self.assertIn(('kid-choice-2', 'kid-choice-2'), choices)
        finally:
            workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = original_specs

    def test_register_engine_with_keyset_import(self):
        payload = self._create_engine_payload()
        payload['import_gateway_keyset'] = 'on'

        with mock.patch('admin.rdm_workflow.views.import_gateway_public_keys', return_value=2) as importer:
            request = self._request_with_messages('post', self.engine_list_url, self.super_admin, payload)
            response = views.WorkflowEngineListView.as_view()(request, institution_id=self.institution.id)

        self.assertEqual(response.status_code, 302)
        engine = WorkflowEngine.objects.first()
        expected_keyset_url = urljoin(engine.gateway_base_url.rstrip('/') + '/', 'keyset')
        self.assertEqual(engine.keyset_url, expected_keyset_url)
        importer.assert_called_once()
        imported_engine = importer.call_args[0][0]
        self.assertIsInstance(imported_engine, WorkflowEngine)
        self.assertEqual(imported_engine.engine_id, engine.engine_id)

    def test_deactivate_engine_keeps_keys_active(self):
        # Create engine first
        create_request = self._request_with_messages('post', self.engine_list_url, self.super_admin, self._create_engine_payload())
        views.WorkflowEngineListView.as_view()(create_request, institution_id=self.institution.id)

        engine = WorkflowEngine.objects.first()
        WorkflowEngineKey.objects.create(
            engine_id=engine.engine_id,
            kid='kidA',
            algorithm='RS256',
            public_key='dummy',
            is_active=True,
        )

        deactivate_request = self._request_with_messages('post', self.engine_list_url, self.super_admin, {
            'action': 'deactivate_engine',
            'engine_id': engine.engine_id,
        })
        response = views.WorkflowEngineListView.as_view()(deactivate_request, institution_id=self.institution.id)
        self.assertEqual(response.status_code, 302)
        engine.refresh_from_db()
        self.assertFalse(engine.is_active)
        self.assertTrue(WorkflowEngineKey.objects.get(engine_id=engine.engine_id, kid='kidA').is_active)

    def test_activate_engine(self):
        create_request = self._request_with_messages('post', self.engine_list_url, self.super_admin, self._create_engine_payload())
        views.WorkflowEngineListView.as_view()(create_request, institution_id=self.institution.id)

        engine = WorkflowEngine.objects.first()

        deactivate_request = self._request_with_messages('post', self.engine_list_url, self.super_admin, {
            'action': 'deactivate_engine',
            'engine_id': engine.engine_id,
        })
        views.WorkflowEngineListView.as_view()(deactivate_request, institution_id=self.institution.id)
        engine.refresh_from_db()
        self.assertFalse(engine.is_active)

        activate_request = self._request_with_messages('post', self.engine_list_url, self.super_admin, {
            'action': 'activate_engine',
            'engine_id': engine.engine_id,
        })
        response = views.WorkflowEngineListView.as_view()(activate_request, institution_id=self.institution.id)
        self.assertEqual(response.status_code, 302)
        engine.refresh_from_db()
        self.assertTrue(engine.is_active)

    def test_manage_keys_add_and_deactivate(self):
        # Register engine first
        create_request = self._request_with_messages('post', self.engine_list_url, self.super_admin, self._create_engine_payload())
        views.WorkflowEngineListView.as_view()(create_request, institution_id=self.institution.id)
        engine = WorkflowEngine.objects.first()

        keys_url = self._keys_url(engine.engine_id)

        add_request = self._request_with_messages('post', keys_url, self.super_admin, {
            'action': 'add_key',
            'kid': 'kidX',
            'algorithm': 'RS256',
            'public_key': '-----BEGIN PUBLIC KEY-----\nABC\n-----END PUBLIC KEY-----',
        })
        response = views.WorkflowEngineKeyView.as_view()(add_request, institution_id=self.institution.id, engine_id=engine.engine_id)
        self.assertEqual(response.status_code, 302)
        key = WorkflowEngineKey.objects.get(engine_id=engine.engine_id, kid='kidX')
        self.assertTrue(key.is_active)

        deactivate_request = self._request_with_messages('post', keys_url, self.super_admin, {
            'action': 'deactivate_key',
            'kid': 'kidX',
        })
        response = views.WorkflowEngineKeyView.as_view()(deactivate_request, institution_id=self.institution.id, engine_id=engine.engine_id)
        self.assertEqual(response.status_code, 302)
        key.refresh_from_db()
        self.assertFalse(key.is_active)

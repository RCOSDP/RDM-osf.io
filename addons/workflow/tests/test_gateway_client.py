# -*- coding: utf-8 -*-

import json
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase

from addons.workflow import settings as workflow_settings
from addons.workflow.gateway_client import (
    WorkflowGatewayClient,
    WorkflowGatewayClientError,
    WorkflowGatewayConfigurationError,
    _get_key_spec_by_kid,
    get_gateway_client,
    list_gateways,
)
from addons.workflow.models import WorkflowEngine
from osf_tests.factories import InstitutionFactory


class WorkflowGatewayClientTests(TestCase):
    def setUp(self):
        super().setUp()
        self.institution = InstitutionFactory()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        private_key_path = Path(self.tempdir.name) / 'rdm.key'
        public_key_path = Path(self.tempdir.name) / 'rdm.pub'

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        private_key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        public_key_path.write_bytes(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

        self.engine_id = str(uuid.uuid4())

        workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = [
            {
                'kid': 'rdm-test-key',
                'alg': 'RS256',
                'private_key_path': str(private_key_path),
                'public_key_path': str(public_key_path),
            },
        ]
        WorkflowEngine.objects.create(
            engine_id=self.engine_id,
            gateway_base_url='https://gateway.example/api',
            signing_kid='rdm-test-key',
            verify_ssl=False,
            institution=self.institution,
        )
        _get_key_spec_by_kid.cache_clear()
        get_gateway_client.cache_clear()

    def tearDown(self):
        workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS = []
        WorkflowEngine.objects.all().delete()
        _get_key_spec_by_kid.cache_clear()
        get_gateway_client.cache_clear()
        super().tearDown()

    def test_unknown_signing_key_raises_configuration_error(self):
        engine = WorkflowEngine.objects.get(engine_id=self.engine_id)
        engine.signing_kid = 'missing-kid'
        engine.save(update_fields=['signing_kid'])
        WorkflowEngine.objects.filter(engine_id=self.engine_id).update(signing_kid='missing-kid')

        with self.assertRaises(WorkflowGatewayConfigurationError):
            WorkflowGatewayClient(self.engine_id)

    def test_missing_adapter_configuration(self):
        WorkflowEngine.objects.all().delete()
        get_gateway_client.cache_clear()
        with self.assertRaises(WorkflowGatewayConfigurationError):
            WorkflowGatewayClient(str(uuid.uuid4()))

    @mock.patch('addons.workflow.gateway_client.requests.request')
    def test_process_definition_request(self, mock_request):
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.content = json.dumps({'data': []}).encode('utf-8')
        mock_response.json.return_value = {'data': []}
        mock_request.return_value = mock_response

        client = get_gateway_client(self.engine_id)
        result = client.list_process_definitions({'latest': 'true'})

        self.assertEqual(result, {'data': []})
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'GET')
        self.assertTrue(args[1].startswith('https://gateway.example/api/flowable/process-definitions'))
        headers = kwargs['headers']
        self.assertIn('Authorization', headers)
        self.assertTrue(headers['Authorization'].startswith('Bearer '))
        self.assertEqual(kwargs['params'], {'latest': 'true'})
        self.assertFalse(kwargs['verify'])
        self.assertEqual(kwargs['timeout'], 10)

    @mock.patch('addons.workflow.gateway_client.requests.request')
    def test_error_response_raises_client_error(self, mock_request):
        mock_response = mock.Mock()
        mock_response.status_code = 502
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.content = json.dumps({'error': 'upstream'}).encode('utf-8')
        mock_response.json.return_value = {'error': 'upstream'}
        mock_request.return_value = mock_response

        client = get_gateway_client(self.engine_id)
        with self.assertRaises(WorkflowGatewayClientError) as ctx:
            client.start_process_instance({'processDefinitionId': 'example'})

        self.assertEqual(ctx.exception.code, 502)
        self.assertIn('Workflow gateway request failed', ctx.exception.data['message'])
        self.assertEqual(ctx.exception.data['detail'], {'error': 'upstream'})

    def test_list_gateways(self):
        data = list_gateways()
        self.assertIn(self.engine_id, data)
        self.assertEqual(data[self.engine_id]['signing_kid'], 'rdm-test-key')

    @mock.patch('addons.workflow.gateway_client.requests.request')
    def test_request_returns_text_payload_when_not_json(self, mock_request):
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.content = b'ok'
        mock_response.text = 'ok'
        mock_request.return_value = mock_response

        client = get_gateway_client(self.engine_id)
        result = client._request('GET', '/ping')

        self.assertEqual(result, 'ok')
        mock_request.assert_called_once()

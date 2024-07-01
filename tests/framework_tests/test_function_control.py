import json
import unittest

import mock
import pytest
from django.http import JsonResponse
from flask import Flask

from framework.flask import add_handlers
from framework.function_control.handlers import handlers, check_api_service_access, function_control_before_request
from framework.routing import Rule, process_rules, json_renderer
from osf_tests.factories import AuthUserFactory, ServiceAccessControlSettingFactory, FunctionFactory, InstitutionFactory
from tests.base import ApiTestCase
from webtest_plus import TestApp


@pytest.mark.django_db
class TestFunctionControlUtils(ApiTestCase):
    def setUp(self):
        self.institution = InstitutionFactory()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()
        self.service_access_control_setting = ServiceAccessControlSettingFactory(
            institution_id=self.institution.guid,
            domain='default',
            user_domain='default',
            is_whitelist=True
        )
        self.function = FunctionFactory(function_code='function_001', service_access_control_setting=self.service_access_control_setting)
        self.test_config_json = json.dumps({
            'function_001': {
                'function_name': 'test',
                'api_group': [{
                    'api': r'^/test/?',
                    'method': 'GET',
                }]
            }
        })

    def test_check_api_service_access__no_user(self):
        assert check_api_service_access('/test/', 'GET', None) is None

    def test_check_api_service_access__config_data_error(self):
        with mock.patch('framework.function_control.handlers.open', mock.mock_open(read_data=self.test_config_json)) as mock_open_file:
            mock_open_file.side_effect = ValueError('test parse json fail')
            assert check_api_service_access('/test/', 'GET', self.user) is None
            mock_open_file.assert_called()

    def test_check_api_service_access__user_is_allowed(self):
        with mock.patch('framework.function_control.handlers.open', mock.mock_open(read_data=self.test_config_json)) as mock_open_file:
            assert check_api_service_access('/test/', 'GET', self.user) is None
            mock_open_file.assert_called()

    def test_check_api_service_access__config_invalid_regex(self):
        self.test_config_json = json.dumps({
            'function_002': {
                'function_name': 'test',
                'api_group': [{
                    'api': r'/[test/',
                    'method': 'GET',
                }]
            }
        })
        with mock.patch('framework.function_control.handlers.open', mock.mock_open(read_data=self.test_config_json)) as mock_open_file:
            assert check_api_service_access('/test/', 'GET', self.user) is None
            mock_open_file.assert_called()

    def test_check_api_service_access__user_is_not_allowed_type_0(self):
        self.test_config_json = json.dumps({
            'function_002': {
                'function_name': 'test',
                'api_group': [{
                    'api': r'^/test/?',
                    'method': 'GET',
                }]
            }
        })
        with mock.patch('framework.function_control.handlers.open', mock.mock_open(read_data=self.test_config_json)) as mock_open_file:
            error_response = check_api_service_access('/test/', 'GET', self.user)
            assert error_response is not None
            assert error_response.status_code == 403
            error_dict = json.loads(error_response.content.decode('utf-8'))
            assert len(error_dict['errors']) == 1
            assert error_dict['errors'][0].get('type') == 0
            mock_open_file.assert_called()

    def test_check_api_service_access__user_is_not_allowed_type_0_invalid_regex(self):
        invalid_api_list = [{
            'api': r'^/[test/$',
            'method': 'GET',
        }, None]
        self.test_config_json = json.dumps({
            'function_002': {
                'function_name': 'test',
                'api_group': [{
                    'api': r'^/test/?',
                    'method': 'GET',
                }]
            }
        })
        with mock.patch('framework.function_control.handlers.open', mock.mock_open(read_data=self.test_config_json)) as mock_open_file:
            with mock.patch('api.base.settings.ERROR_MESSAGE_API_LIST', invalid_api_list):
                error_response = check_api_service_access('/test/', 'GET', self.user)
                assert error_response is not None
                assert error_response.status_code == 403
                error_dict = json.loads(error_response.content.decode('utf-8'))
                assert len(error_dict['errors']) == 1
                assert error_dict['errors'][0].get('type') == 0
                mock_open_file.assert_called()

    def test_check_api_service_access__user_is_not_allowed_type_1(self):
        api_list = [{
            'api': r'^/search/$',
            'method': 'GET',
        }]
        self.test_config_json = json.dumps({
            'function_002': {
                'function_name': 'test',
                'api_group': api_list
            }
        })
        with mock.patch('framework.function_control.handlers.open', mock.mock_open(read_data=self.test_config_json)) as mock_open_file:
            with mock.patch('api.base.settings.ERROR_MESSAGE_API_LIST', api_list):
                error_response = check_api_service_access('/search/', 'GET', self.user)
                assert error_response is not None
                assert error_response.status_code == 403
                error_dict = json.loads(error_response.content.decode('utf-8'))
                assert len(error_dict['errors']) == 1
                assert error_dict['errors'][0].get('type') == 1
                mock_open_file.assert_called()


@pytest.mark.django_db
class TestFunctionControlHandler(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.debug = True
        add_handlers(self.app, handlers)

        self.webTestApp = TestApp(self.app)
        rule = Rule(['/search/'], 'get', {}, renderer=json_renderer)
        process_rules(self.app, [rule])

    @mock.patch('framework.function_control.handlers.check_api_service_access')
    def test_function_control_before_request__no_error(self, mock_check_api_service_access):
        mock_check_api_service_access.return_value = None
        res = self.webTestApp.get('/search/')
        assert res.status_code == 200
        assert mock_check_api_service_access.called

    @mock.patch('framework.function_control.handlers.check_api_service_access')
    def test_function_control_before_request__error_html(self, mock_check_api_service_access):
        mock_check_api_service_access.return_value = JsonResponse({
            'errors': [{
                'message': 'User is not allowed to access this API.',
                'type': 0,
                'status': 403
            }]
        }, status=403)
        headers = {
            'Accept': 'text/html'
        }
        res = self.webTestApp.get('/search/', headers=headers, expect_errors=True)
        assert res.status_code == 302
        assert '/403' in res.location
        assert mock_check_api_service_access.called

    @mock.patch('framework.function_control.handlers.check_api_service_access')
    def test_function_control_before_request__error_message(self, mock_check_api_service_access):
        mock_check_api_service_access.return_value = JsonResponse({
            'errors': [{
                'message': 'User is not allowed to access this API.',
                'type': 1,
                'status': 403
            }]
        }, status=403)
        res = self.webTestApp.get('/search/', expect_errors=True)
        assert res.status_code == 403
        assert mock_check_api_service_access.called

    def test_handlers(self):
        assert handlers.get('before_request') == function_control_before_request

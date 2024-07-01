import json
import mock

from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import reverse
from nose import tools as nt
from rest_framework import status as http_status

from admin.service_access_control_setting.views import get_rowspan, ServiceAccessControlSettingView, ServiceAccessControlSettingCreateView
from admin_tests.utilities import setup_user_view
from framework.auth import Auth
from osf.models import ServiceAccessControlSetting
from osf_tests.factories import AuthUserFactory, ServiceAccessControlSettingFactory, FunctionFactory, InstitutionFactory
from tests.base import AdminTestCase


class TestServiceAccessControlSettingSimpleTag:
    def test_get_rowspan(self):
        # Key exist in dict
        row_info_dict = {'gakunin': 20}
        filter_key = 'gakunin'
        nt.assert_equal(get_rowspan(row_info_dict, filter_key), 20)

        # Key does not exist in dict
        row_info_dict = {'openidp': 5}
        filter_key = 'gakunin'
        nt.assert_equal(get_rowspan(row_info_dict, filter_key), 1)


class TestServiceAccessControlSettingView(AdminTestCase):
    def setUp(self):
        super(TestServiceAccessControlSettingView, self).setUp()

        self.request = RequestFactory().get(reverse('service_access_control_setting:list'))
        self.institution = InstitutionFactory()
        self.user = AuthUserFactory(is_active=True, is_registered=True)
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()
        self.auth = Auth(self.user)
        self.service_access_control_setting = ServiceAccessControlSettingFactory()
        FunctionFactory(service_access_control_setting=self.service_access_control_setting)
        self.view = ServiceAccessControlSettingView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.mock_config_json = json.dumps({
            'function_001': {
                'function_name': 'test',
                'api_group': [{
                    'api': '/search/',
                    'method': 'GET',
                }]
            }
        })

    def test_unauthorized(self):
        self.request.user = AnonymousUser()
        nt.assert_false(self.view.test_func())
        nt.assert_false(self.view.raise_exception)

    def test_normal_user_login(self):
        nt.assert_false(self.view.test_func())
        nt.assert_true(self.view.raise_exception)

    def test_admin_login(self):
        self.request.user.is_superuser = False
        self.request.user.is_staff = True
        nt.assert_true(self.view.test_func())

    def test_super_login(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        nt.assert_true(self.view.test_func())

    def test_get_queryset__super_admin(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        res = self.view.get_queryset()
        nt.assert_equal(len(res), 1)
        nt.assert_equal(res[0], self.service_access_control_setting)

    def test_get_queryset__admin(self):
        self.request.user.is_superuser = False
        self.request.user.is_staff = True
        service_access_control_setting = ServiceAccessControlSettingFactory(institution_id=self.institution.guid)
        FunctionFactory(service_access_control_setting=service_access_control_setting)
        res = self.view.get_queryset()
        nt.assert_equal(len(res), 1)
        nt.assert_equal(res[0], service_access_control_setting)

    def test_get_queryset__none(self):
        res = self.view.get_queryset()
        nt.assert_equal(len(res), 0)

    def test_get_context_data(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            self.view.object_list = self.view.get_queryset()
            res = self.view.get_context_data()
            mock_open_file.assert_called()
            nt.assert_is_not_none(res)
            nt.assert_not_equal(res['column_data'], {})
            nt.assert_not_equal(res['row_data'], [])

    def test_get_context_data__read_config_file_error(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            with mock.patch('admin.service_access_control_setting.views.validate_config_schema') as mock_validate_config_schema:
                mock_validate_config_schema.side_effect = ValueError('test fail to load file')
                self.view.object_list = self.view.get_queryset()
                res = self.view.get_context_data()
                mock_open_file.assert_called()
                mock_validate_config_schema.assert_called()
                nt.assert_is_not_none(res)
                nt.assert_equal(res['column_data'], {})
                nt.assert_equal(res['row_data'], [])


class TestServiceAccessControlSettingCreateView(AdminTestCase):
    def setUp(self):
        super(TestServiceAccessControlSettingCreateView, self).setUp()

        self.institution = InstitutionFactory()
        test_dict = {
            'data': [
                {
                    'institution_id': self.institution.guid,
                    'domain': 'test.com',
                    'is_ial2_or_aal2': True,
                    'user_domain': '@test.com',
                    'project_limit_number': 10,
                    'is_whitelist': False,
                    'function_codes': ['function_001']
                }
            ]
        }
        binary_json = json.dumps(test_dict).encode('utf-8')
        self.upload_file = SimpleUploadedFile('file.json', binary_json)
        self.user = AuthUserFactory(is_active=True, is_registered=True)
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()
        self.auth = Auth(self.user)
        self.request = RequestFactory().post(reverse('service_access_control_setting:create_setting'))
        self.request.FILES['file'] = self.upload_file
        self.view = ServiceAccessControlSettingCreateView()
        self.view = setup_user_view(self.view, self.request, user=self.user)
        self.mock_config_json = json.dumps({
            'function_001': {
                'function_name': 'test',
                'api_group': [{
                    'api': r'^\/test\/$',
                    'method': 'GET',
                }]
            }
        })

    def test_unauthorized(self):
        self.request.user = AnonymousUser()
        nt.assert_false(self.view.test_func())
        nt.assert_false(self.view.raise_exception)

    def test_normal_user_login(self):
        nt.assert_false(self.view.test_func())
        nt.assert_true(self.view.raise_exception)

    def test_admin_login(self):
        self.request.user.is_superuser = False
        self.request.user.is_staff = True
        nt.assert_false(self.view.test_func())
        nt.assert_true(self.view.raise_exception)

    def test_super_login(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        nt.assert_true(self.view.test_func())

    def test_post(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            res = self.view.post(self.request)
            mock_open_file.assert_called()
            nt.assert_equal(res.status_code, http_status.HTTP_200_OK)
            nt.assert_equal(res.content, b'{}')

    def test_post__read_upload_file_not_json(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        self.request.FILES['file'] = SimpleUploadedFile('text.txt', b'text')
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            res = self.view.post(self.request)
            mock_open_file.assert_not_called()
            nt.assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)
            nt.assert_equal(res.content, b'{"message": "JSON file is invalid."}')

    def test_post__read_upload_file_error(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        self.request.FILES['file'] = None
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            with nt.assert_raises(Exception):
                self.view.post(self.request)
            mock_open_file.assert_not_called()

    def test_post__validate_upload_file_fail(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        self.request.FILES['file'] = SimpleUploadedFile('text.json', b'{}')
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            res = self.view.post(self.request)
            mock_open_file.assert_not_called()
            nt.assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)
            nt.assert_equal(res.content, b'{"message": "JSON file is invalid."}')

    def test_post__read_config_file_error(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            mock_open_file.side_effect = ValueError('test read config file fail')
            res = self.view.post(self.request)
            mock_open_file.assert_called()
            nt.assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)
            nt.assert_equal(res.content, b'{"message": "Config data is invalid."}')

    def test_post__institution_id_not_found(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        test_dict = {
            'data': [
                {
                    'institution_id': f'{self.institution.guid}+',
                    'domain': 'test.com',
                    'is_ial2_or_aal2': True,
                    'user_domain': '@test.com',
                    'project_limit_number': 10,
                    'is_whitelist': False,
                    'function_codes': ['function_001']
                }
            ]
        }
        binary_json = json.dumps(test_dict).encode('utf-8')
        self.upload_file = SimpleUploadedFile('file.json', binary_json)
        self.request.FILES['file'] = self.upload_file
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            res = self.view.post(self.request)
            mock_open_file.assert_called()
            nt.assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)
            nt.assert_equal(res.content, b'{"message": "JSON file is invalid."}')

    def test_post__function_code_not_in_config(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        mock_config_json = json.dumps({
            'function_002': {
                'function_name': 'test not exist function code',
                'api_group': [{
                    'api': r'^\/[a-z0-9A-Z]+\/addons\/?$',
                    'method': 'GET',
                }]
            }
        })
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=mock_config_json)) as mock_open_file:
            res = self.view.post(self.request)
            mock_open_file.assert_called()
            nt.assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)
            nt.assert_equal(res.content, b'{"message": "JSON file is invalid."}')

    def test_post__not_unique_together(self):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        test_dict = {
            'data': [
                {
                    'institution_id': self.institution.guid,
                    'domain': 'test.com',
                    'is_ial2_or_aal2': True,
                    'user_domain': '@test.com',
                    'project_limit_number': 10,
                    'is_whitelist': False,
                    'function_codes': ['function_001']
                },
                {
                    'institution_id': self.institution.guid,
                    'domain': 'test.com',
                    'is_ial2_or_aal2': True,
                    'user_domain': '@test.com',
                    'is_whitelist': True,
                    'function_codes': ['function_001']
                }
            ]
        }
        binary_json = json.dumps(test_dict).encode('utf-8')
        self.upload_file = SimpleUploadedFile('file.json', binary_json)
        self.request.FILES['file'] = self.upload_file
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            res = self.view.post(self.request)
            mock_open_file.assert_called()
            nt.assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)
            nt.assert_equal(res.content, b'{"message": "JSON file is invalid."}')

    @mock.patch.object(ServiceAccessControlSetting.objects, 'bulk_create')
    def test_post__transaction_error(self, mock_bulk_create):
        self.request.user.is_superuser = True
        self.request.user.affiliated_institutions.clear()
        with mock.patch('admin.service_access_control_setting.views.open', mock.mock_open(read_data=self.mock_config_json)) as mock_open_file:
            mock_bulk_create.side_effect = IntegrityError('test existed pk')
            with nt.assert_raises(IntegrityError):
                self.view.post(self.request)
                mock_open_file.assert_called()

    def test_parse_file(self):
        nt.assert_is_not_none(self.view.parse_file(self.upload_file))

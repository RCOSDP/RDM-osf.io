import json
import mock
import pytest
from admin.login_access_control import views
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse
from nose import tools as nt

from admin.login_access_control.views import BaseLogicAccessControlUpdateView
from osf.models import LoginControlAuthenticationAttribute, LoginControlMailAddress
from osf_tests.factories import (
    AuthUserFactory,
    InstitutionFactory,
    LoginControlAuthenticationAttributeFactory, LoginControlMailAddressFactory,
)
from tests.base import AdminTestCase
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponseBadRequest

pytestmark = pytest.mark.django_db


class TestLoginAccessControlListView(AdminTestCase):
    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')

        # Not login user
        self.anon = AnonymousUser()

        # Admin user
        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        # Super user
        self.superuser = AuthUserFactory(fullname='Jeff Hardy')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.user = AuthUserFactory()
        self.user.save()

        self.request = RequestFactory().get('/fake_path')

        self.view = views.LoginAccessControlListView()

    def test_permission__anonymous(self):
        request = RequestFactory().get(reverse('login_access_control:list'))
        request.user = self.anon

        response = views.LoginAccessControlListView.as_view()(request)
        self.assertEqual(response.status_code, 302)

    def test_permission__admin_with_permission(self):
        request = RequestFactory().get(reverse('login_access_control:list') + '?institution_id=' + str(self.institution01.id))
        request.user = self.institution01_admin

        response = views.LoginAccessControlListView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_permission__admin_without_permission(self):
        # institution_id not same institution of login user
        request = RequestFactory().get(reverse('login_access_control:list') + '?institution_id=' + str(self.institution01.id))
        request.user = self.institution02_admin

        with self.assertRaises(PermissionDenied):
            views.LoginAccessControlListView.as_view()(request)

        # admin not in institution
        request = RequestFactory().get(reverse('login_access_control:list') + '?institution_id=' + str(self.institution01.id))
        self.institution02_admin.affiliated_institutions = []
        request.user = self.institution02_admin

        with self.assertRaises(PermissionDenied):
            views.LoginAccessControlListView.as_view()(request)

    def test_permission__institution_not_exist(self):
        request = RequestFactory().get(reverse('login_access_control:list') + '?institution_id=1234')
        request.user = self.superuser

        with self.assertRaises(Http404):
            views.LoginAccessControlListView.as_view()(request)

    def test_get_queryset(self):
        queryset = self.view.get_queryset()
        nt.assert_false(queryset.exists())

    def test_get(self):
        request = RequestFactory().get(f'/fake_path')

        self.view.request = request
        self.view.request.user = self.superuser
        self.view.kwargs = {}
        self.view.object_list = self.view.get_queryset()
        response = self.view.get(request)
        self.assertEqual(response.status_code, 200)

    @mock.patch('admin.login_access_control.views.render_bad_request_response')
    def test_get__invalid_institution_id(self, mock_bad_request_response):
        mock_bad_request_response.return_value = HttpResponseBadRequest(content='institution_id is invalid.')
        request = RequestFactory().get('/fake_path?institution_id=test')
        self.view.request = request
        self.view.request.user = self.superuser
        self.view.kwargs = {'institution_id': 'test'}
        self.view.object_list = self.view.get_queryset()
        response = self.view.get(request)
        self.assertEqual(response.status_code, 400)

    def test_get__institution_id_not_exist(self):
        request = RequestFactory().get(f'/fake_path?institution_id=-1')
        self.view.request = request
        self.view.request.user = self.superuser
        self.view.kwargs = {'institution_id': -1}
        self.view.object_list = self.view.get_queryset()

        with self.assertRaises(Http404):
            self.view.get(request)

    def test_get_context_data__super_admin(self):
        authentication_attribute = LoginControlAuthenticationAttributeFactory(institution=self.institution01)

        request = RequestFactory().get(f'/fake_path')

        self.view.request = request
        self.view.request.user = self.superuser
        self.view.kwargs = {}
        self.view.object_list = self.view.get_queryset()
        res = self.view.get_context_data()

        nt.assert_is_instance(res, dict)
        nt.assert_equal(res['is_admin'], False)
        nt.assert_equal(res['institutions'][0].id, self.institution01.id)
        nt.assert_equal(res['selected_institution'], self.institution01)
        nt.assert_equal(res['login_control_authentication_attribute_list'], [authentication_attribute])

    def test_get_context_data__super_admin_with_institution_id(self):
        institution = InstitutionFactory(name='test')
        authentication_attribute = LoginControlAuthenticationAttributeFactory(institution=institution)

        request = RequestFactory().get(f'/fake_path?institution_id={institution.id}')

        self.view.request = request
        self.view.request.user = self.superuser
        self.view.kwargs = {'institution_id': institution.id}
        self.view.object_list = self.view.get_queryset()
        res = self.view.get_context_data()

        nt.assert_is_instance(res, dict)
        nt.assert_equal(res['is_admin'], False)
        nt.assert_equal(res['institutions'][0].id, self.institution01.id)
        nt.assert_equal(res['selected_institution'], institution)
        nt.assert_equal(res['login_control_authentication_attribute_list'], [authentication_attribute])

    def test_get_context_data__admin(self):
        authentication_attribute = LoginControlAuthenticationAttributeFactory(institution=self.institution01)

        request = RequestFactory().get(f'/fake_path')
        self.view.request = request
        self.view.request.user = self.institution01_admin
        self.view.kwargs = {}
        self.view.object_list = self.view.get_queryset()
        res = self.view.get_context_data()

        nt.assert_is_instance(res, dict)
        nt.assert_equal(res['is_admin'], True)
        nt.assert_equal(res['institutions'][0].id, self.institution01.id)
        nt.assert_equal(res['selected_institution'], self.institution01)
        nt.assert_equal(res['login_control_authentication_attribute_list'], [authentication_attribute])

    def test_get_context_data__admin_with_institution_id(self):
        institution = InstitutionFactory(name='test')
        authentication_attribute = LoginControlAuthenticationAttributeFactory(institution=institution)

        self.institution01_admin.affiliated_institutions.add(institution)
        self.institution01_admin.save()

        request = RequestFactory().get(f'/fake_path?institution_id={institution.id}')
        self.view.request = request
        self.view.request.user = self.institution01_admin
        self.view.kwargs = {'institution_id': institution.id}
        self.view.object_list = self.view.get_queryset()
        res = self.view.get_context_data()

        nt.assert_is_instance(res, dict)
        nt.assert_equal(res['is_admin'], True)
        nt.assert_equal(res['institutions'][0].id, self.institution01.id)
        nt.assert_equal(res['selected_institution'], institution)
        nt.assert_equal(res['login_control_authentication_attribute_list'], [authentication_attribute])

    def test_get_context_data__no_institutions(self):
        self.institution01.is_deleted = True
        self.institution01.save()

        request = RequestFactory().get(f'/fake_path?institution_id={self.institution01.id}')
        self.view.request = request
        self.view.request.user = self.superuser
        self.view.kwargs = {'institution_id': self.institution01.id}
        self.view.object_list = self.view.get_queryset()

        with self.assertRaises(Http404):
            self.view.get_context_data()

    def test_get_context_data__raise_permission_denied(self):
        institution = InstitutionFactory(name='test')

        request = RequestFactory().get(f'/fake_path?institution_id={institution.id}')
        self.view.request = request
        self.view.request.user = self.institution02_admin
        self.view.kwargs = {'institution_id': institution.id}
        self.view.object_list = self.view.get_queryset()

        with self.assertRaises(PermissionDenied):
            self.view.get_context_data()


class TestBaseLogicAccessControlUpdateView(AdminTestCase):
    def setUp(self):
        self.institution = InstitutionFactory(name='inst01')

        self.anon = AnonymousUser()

        self.normal_user = AuthUserFactory(fullname='normal_user')

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.admin = AuthUserFactory(fullname='admin001')
        self.admin.is_staff = True
        self.admin.save()

        self.institution_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution_admin.is_staff = True
        self.institution_admin.affiliated_institutions.add(self.institution)
        self.institution_admin.save()

        self.view = BaseLogicAccessControlUpdateView()
        self.request = RequestFactory().post(f'/fake_path')
        self.view.request = self.request

    def test_permission__anonymous(self):
        self.view.request.user = self.anon
        result = self.view.test_func()
        nt.assert_false(result)
        nt.assert_false(self.view.raise_exception)

    def test_permission__normal_user(self):
        self.view.request.user = self.normal_user
        result = self.view.test_func()
        nt.assert_false(result)
        nt.assert_true(self.view.raise_exception)

    def test_permission__super_admin(self):
        self.view.request.user = self.superuser
        result = self.view.test_func()
        nt.assert_true(result)

    def test_permission__admin_with_no_institution(self):
        self.view.request.user = self.admin
        result = self.view.test_func()
        nt.assert_false(result)
        nt.assert_true(self.view.raise_exception)

    def test_permission__admin(self):
        self.view.request.user = self.institution_admin
        result = self.view.test_func()
        nt.assert_true(result)

    def test_parse_json_request(self):
        test_json = json.dumps({'institution_id': 1})
        request = RequestFactory().post(
            '/fake_path',
            json.dumps(test_json),
            content_type='application/json'
        )
        data, error = self.view.parse_json_request(request)
        nt.assert_is_not_none(data)
        nt.assert_is_none(error)

    def test_parse_json_request__invalid_json(self):
        test_invalid_json = '{a}'
        request = RequestFactory().post(
            '/fake_path',
            test_invalid_json,
            content_type='application/json'
        )
        data, error = self.view.parse_json_request(request)
        nt.assert_is_none(data)
        nt.assert_is_not_none(error)

    def test_parse_json_request__empty_json(self):
        request = RequestFactory().post(
            '/fake_path',
            None,
            content_type='application/json'
        )
        data, error = self.view.parse_json_request(request)
        nt.assert_is_none(data)
        nt.assert_is_not_none(error)

    def test_is_affiliated_with_not_deleted_institution(self):
        self.view.request.user = self.institution_admin
        result = self.view.is_affiliated_with_not_deleted_institution(self.institution.id)
        nt.assert_true(result)

    def test_is_affiliated_with_not_deleted_institution__false(self):
        self.view.request.user = self.admin
        result = self.view.is_affiliated_with_not_deleted_institution(self.institution.id)
        nt.assert_false(result)


class TestUpdateLoginAvailabilityDefaultView(AdminTestCase):
    def setUp(self):
        self.institution = InstitutionFactory(name='inst01')
        self.user = AuthUserFactory(fullname='superuser', is_superuser=True)
        self.view = views.UpdateLoginAvailabilityDefaultView.as_view()

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:update_login_availability_default'),
            None,
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post_invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'login_availability_default': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_availability_default'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post_invalid_login_availability_default(self):
        params = {
            'institution_id': self.institution.id,
            'login_availability_default': 'test',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_availability_default'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "login_availability_default is invalid."}')

    def test_post_admin_not_affiliated(self):
        self.user.is_staff = True
        self.user.is_superuser = False
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

        institution = InstitutionFactory(name='inst02')

        params = {
            'institution_id': institution.id,
            'login_availability_default': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_availability_default'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post(self):
        params = {
            'institution_id': self.institution.id,
            'login_availability_default': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_availability_default'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 204)


class TestSaveAuthenticationAttributeListView(AdminTestCase):

    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        self.view = views.SaveAuthenticationAttributeListView.as_view()
        self.view_permission = views.SaveAuthenticationAttributeListView

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            None,
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post__invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'attribute_data': [{
                'attribute_name': 'mail',
                'attribute_value': 'test.com',
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post__admin_not_affiliated(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': 'mail',
                'attribute_value': 'test.com',
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.institution02_admin
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__empty_attribute_data(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': []
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Group (attribute name, attribute value) is required."}')

    def test_post__attribute_name_is_none(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': None,
                'attribute_value': 'test.com',
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Attribute name is required."}')

    def test_post__attribute_name_invalid(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': 'test_invalid_attribute',
                'attribute_value': 'test.com',
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Attribute name is not exist in config."}')

    def test_post__attribute_value_is_none(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': 'mail',
                'attribute_value': None,
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Attribute value is required."}')

    def test_post__attribute_name_too_long(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': 'ou',
                'attribute_value': 'X' * 257,
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Length of attribute value > 255 characters."}')

    def test_post__attributes_are_not_unique(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': 'mail',
                'attribute_value': 'test.com',
            }, {
                'attribute_name': 'mail',
                'attribute_value': 'test.com',
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Group (attribute name, attribute value) MUST be unique."}')

    def test_post(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_data': [{
                'attribute_name': 'mail',
                'attribute_value': 'test.com',
            }]
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_authentication_attribute_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 201)
        attribute_list = LoginControlAuthenticationAttribute.objects.filter(institution=self.institution01)
        nt.assert_true(len(attribute_list), 1)
        first_attribute = attribute_list.first()
        nt.assert_true(first_attribute.attribute_name, 'mail')
        nt.assert_true(first_attribute.attribute_value, 'test.com')


class TestUpdateAuthenticationAttributeView(AdminTestCase):

    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')
        self.attribute_1 = LoginControlAuthenticationAttributeFactory(institution=self.institution01)
        self.attribute_2 = LoginControlAuthenticationAttributeFactory(institution=self.institution02)

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        self.view = views.UpdateAuthenticationAttributeView.as_view()
        self.view_permission = views.UpdateAuthenticationAttributeView

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            None,
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post__missing_institution_id(self):
        params = {
            'attribute_id': self.attribute_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is required."}')

    def test_post__invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'attribute_id': self.attribute_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post__missing_attribute_id(self):
        params = {
            'institution_id': self.institution01.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "attribute_id is required."}')

    def test_post__invalid_attribute_id(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': 'test',
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "attribute_id is invalid."}')

    def test_post__attribute_id_not_exist(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': 0,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "attribute_id is invalid."}')

    def test_post__missing_is_availability(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "is_availability is required."}')

    def test_post__invalid_is_availability(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
            'is_availability': 'test',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "is_availability is invalid."}')

    def test_post__admin_not_affiliated(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.institution02_admin
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__attribute_not_match_with_institution(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_2.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "Can not setting login access control of the institution into the other institution."}')

    def test_post__attribute_set_in_logic_condition(self):
        self.institution01.login_logic_condition = f'!{self.attribute_1.id}'
        self.institution01.save()
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Can not switch toggle the attribute element due to it is using in the logic condition."}')

    def test_post(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 204)
        attribute_list = LoginControlAuthenticationAttribute.objects.filter(institution=self.institution01)
        nt.assert_true(len(attribute_list), 1)
        first_attribute = attribute_list.first()
        nt.assert_false(first_attribute.is_availability)


class TestDeleteAuthenticationAttributeView(AdminTestCase):

    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')
        self.attribute_1 = LoginControlAuthenticationAttributeFactory(institution=self.institution01)
        self.attribute_2 = LoginControlAuthenticationAttributeFactory(institution=self.institution02)

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        self.view = views.DeleteAuthenticationAttributeView.as_view()
        self.view_permission = views.DeleteAuthenticationAttributeView

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            None,
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post__missing_institution_id(self):
        params = {
            'attribute_id': self.attribute_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is required."}')

    def test_post__invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'attribute_id': self.attribute_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post__missing_attribute_id(self):
        params = {
            'institution_id': self.institution01.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "attribute_id is required."}')

    def test_post__invalid_attribute_id(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': 'test',
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "attribute_id is invalid."}')

    def test_post__attribute_id_not_exist(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': 0,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "attribute_id is invalid."}')

    def test_post__admin_not_affiliated(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.institution02_admin
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__attribute_not_match_with_institution(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_2.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "Can not setting login access control of the institution into the other institution."}')

    def test_post__attribute_set_in_logic_condition(self):
        self.institution01.login_logic_condition = f'!{self.attribute_1.id}'
        self.institution01.save()
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Can not delete the attribute element due to it is using in the logic condition."}')

    def test_post(self):
        params = {
            'institution_id': self.institution01.id,
            'attribute_id': self.attribute_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_authentication_attribute'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 204)
        attribute_list = LoginControlAuthenticationAttribute.objects.filter(institution=self.institution01)
        nt.assert_true(len(attribute_list), 1)
        first_attribute = attribute_list.first()
        nt.assert_true(first_attribute.is_deleted)


class TestUpdateLoginLogicConditionView(AdminTestCase):
    def setUp(self):
        self.institution = InstitutionFactory(name='inst01')
        self.user = AuthUserFactory(fullname='superuser', is_superuser=True)
        self.view = views.UpdateLoginLogicConditionView.as_view()

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            None,
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post_missing_institution_id(self):
        params = {
            'logic_condition': '1&&2',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is required."}')

    def test_post_invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'logic_condition': '1&&2',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post_invalid_login_condition(self):
        params = {
            'institution_id': self.institution.id,
            'logic_condition': 'test',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Logic condition is invalid."}')

    def test_post_admin_not_affiliated(self):
        self.user.is_staff = True
        self.user.is_superuser = False
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

        institution = InstitutionFactory(name='inst02')

        params = {
            'institution_id': institution.id,
            'logic_condition': '1&&2',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__attribute_index_not_exist(self):
        params = {
            'institution_id': self.institution.id,
            'logic_condition': '1&&2',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Index number does not exist."}')

    def test_post(self):
        attribute = LoginControlAuthenticationAttributeFactory(institution=self.institution)
        params = {
            'institution_id': self.institution.id,
            'logic_condition': f'!{attribute.id}',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_login_logic_condition'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.user
        response = self.view(request)

        nt.assert_equal(response.status_code, 204)


class TestSaveMailAddressListView(AdminTestCase):
    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        self.view = views.SaveMailAddressListView.as_view()

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            None,
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post__missing_institution_id(self):
        params = {
            'mail_address_list': ['test.com', '@test2.com'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is required."}')

    def test_post__invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'mail_address_list': ['test.com', '@test2.com'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post__admin_not_affiliated(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': ['test.com', '@test2.com'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.institution02_admin
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__empty_mail_address_list(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': [],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Mail address is required."}')

    def test_post__mail_address_is_empty(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': [''],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Mail address is required."}')

    def test_post__mail_address_too_long(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': [f'{"X"* 320}@test.com'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Length of mail address > 320 characters."}')

    def test_post__mail_address_invalid(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': ['test'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Mail address format is invalid."}')

    def test_post__mail_address_not_unique(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': ['test.com', 'test.com'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "Mail address MUST be unique."}')

    def test_post(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_list': ['test.com', '@test2.com'],
        }
        request = RequestFactory().post(
            reverse('login_access_control:save_mail_address_list'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 201)
        mail_address = LoginControlMailAddress.objects.filter(institution=self.institution01)
        nt.assert_true(len(mail_address), 2)
        nt.assert_true(mail_address.first().mail_address, 'test.com')
        nt.assert_true(mail_address.last().mail_address, '@test2.com')


class TestUpdateMailAddressView(AdminTestCase):
    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')
        self.mail_address_1 = LoginControlMailAddressFactory(institution=self.institution01)
        self.mail_address_2 = LoginControlMailAddressFactory(institution=self.institution02)

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        self.view = views.UpdateMailAddressView.as_view()

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            None,
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post__missing_institution_id(self):
        params = {
            'mail_address_id': self.mail_address_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is required."}')

    def test_post__invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'mail_address_id': self.mail_address_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post__missing_mail_address_id(self):
        params = {
            'institution_id': self.institution01.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "mail_address_id is required."}')

    def test_post__invalid_mail_address_id(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': 'test',
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "mail_address_id is invalid."}')

    def test_post__mail_address_id_not_exist(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': 0,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "mail_address_id is invalid."}')

    def test_post__missing_is_availability(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "is_availability is required."}')

    def test_post__invalid_is_availability(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_1.id,
            'is_availability': 'test',
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "is_availability is invalid."}')

    def test_post__admin_not_affiliated(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.institution02_admin
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__mail_address_not_match_with_institution(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_2.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "Can not setting login access control of the institution into the other institution."}')

    def test_post(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_1.id,
            'is_availability': False,
        }
        request = RequestFactory().post(
            reverse('login_access_control:update_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 204)
        mail_address = LoginControlMailAddress.objects.filter(institution=self.institution01)
        nt.assert_true(len(mail_address), 1)
        nt.assert_false(mail_address.first().is_availability)


class TestDeleteMailAddressView(AdminTestCase):
    def setUp(self):
        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')
        self.mail_address_1 = LoginControlMailAddressFactory(institution=self.institution01)
        self.mail_address_2 = LoginControlMailAddressFactory(institution=self.institution02)

        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.save()

        self.institution01_admin = AuthUserFactory(fullname='admin001_inst01')
        self.institution01_admin.is_staff = True
        self.institution01_admin.affiliated_institutions.add(self.institution01)
        self.institution01_admin.save()

        self.institution02_admin = AuthUserFactory(fullname='admin001_inst02')
        self.institution02_admin.is_staff = True
        self.institution02_admin.affiliated_institutions.add(self.institution02)
        self.institution02_admin.save()

        self.view = views.DeleteMailAddressView.as_view()

    def test_post_invalid_body_request(self):
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            None,
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)

    def test_post__missing_institution_id(self):
        params = {
            'mail_address_id': self.mail_address_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is required."}')

    def test_post__invalid_institution_id(self):
        params = {
            'institution_id': 'test',
            'mail_address_id': self.mail_address_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "institution_id is invalid."}')

    def test_post__missing_mail_address_id(self):
        params = {
            'institution_id': self.institution01.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "mail_address_id is required."}')

    def test_post__invalid_mail_address_id(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': 'test',
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "mail_address_id is invalid."}')

    def test_post__mail_address_id_not_exist(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': 0,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 400)
        nt.assert_equal(response.content, b'{"error_message": "mail_address_id is invalid."}')

    def test_post__admin_not_affiliated(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )
        request.user = self.institution02_admin
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "You do not have permission to setting login access control of the other institution."}')

    def test_post__mail_address_not_match_with_institution(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_2.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 403)
        nt.assert_equal(response.content, b'{"error_message": "Can not setting login access control of the institution into the other institution."}')

    def test_post(self):
        params = {
            'institution_id': self.institution01.id,
            'mail_address_id': self.mail_address_1.id,
        }
        request = RequestFactory().post(
            reverse('login_access_control:delete_mail_address'),
            json.dumps(params),
            content_type='application/json'
        )

        request.user = self.superuser
        response = self.view(request)

        nt.assert_equal(response.status_code, 204)
        mail_address = LoginControlMailAddress.objects.filter(institution=self.institution01)
        nt.assert_true(len(mail_address), 1)
        nt.assert_true(mail_address.first().is_deleted)

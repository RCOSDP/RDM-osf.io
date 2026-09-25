# -*- coding: utf-8 -*-
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
import json
import mock
from nose import tools as nt

from admin.quota_recalc import views
from api.base import settings as api_settings
from osf.models import UserQuota
from osf_tests.factories import AuthUserFactory, InstitutionFactory, RegionFactory
from tests.base import AdminTestCase


class TestQuotaRecalcView(AdminTestCase):
    def setUp(self):
        super(TestQuotaRecalcView, self).setUp()
        self.superuser = AuthUserFactory()
        self.superuser.is_superuser = True
        self.superuser.save()

    def get_request(self, view, **kwargs):
        request = RequestFactory().get('/fake_path')
        request.user = self.superuser
        return view(request, **kwargs)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_create_userquota_record(self, mock_usedquota):
        mock_usedquota.return_value = 1500

        user = AuthUserFactory()
        UserQuota.objects.filter(user=user).delete()
        response = self.get_request(views.user, guid=user._id)
        res_json = json.loads(response.content)
        nt.assert_equal(response.status_code, 200)
        nt.assert_equal(res_json['status'], 'OK')

        user_quota = UserQuota.objects.get(user=user, storage_type=UserQuota.NII_STORAGE)
        nt.assert_equal(user_quota.max_quota, api_settings.DEFAULT_MAX_QUOTA)
        nt.assert_equal(user_quota.used, 1500)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_update_userquota_record(self, mock_usedquota):
        mock_usedquota.return_value = 7000

        user = AuthUserFactory()
        UserQuota.objects.create(
            user=user,
            storage_type=UserQuota.NII_STORAGE,
            max_quota=200,
            used=5000
        )
        response = self.get_request(views.user, guid=user._id)
        res_json = json.loads(response.content)
        nt.assert_equal(response.status_code, 200)
        nt.assert_equal(res_json['status'], 'OK')

        user_quota = UserQuota.objects.get(user=user, storage_type=UserQuota.NII_STORAGE)
        nt.assert_equal(user_quota.max_quota, 200)
        nt.assert_equal(user_quota.used, 7000)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_invalid_guid(self, mock_usedquota):
        mock_usedquota.return_value = 3000

        response = self.get_request(views.user, guid='cuzidontcare')
        res_json = json.loads(response.content)
        nt.assert_equal(response.status_code, 404)
        nt.assert_equal(res_json['status'], 'failed')
        nt.assert_equal(res_json['message'], 'User not found.')

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_users_create_userquota_record(self, mock_usedquota):
        mock_usedquota.return_value = 1500
        user = AuthUserFactory()
        user2 = AuthUserFactory()
        UserQuota.objects.filter(user=user).delete()
        UserQuota.objects.filter(user=user2).delete()
        response = self.get_request(views.user, guid=user._id)
        res_json = json.loads(response.content)
        nt.assert_equal(response.status_code, 200)
        nt.assert_equal(res_json['status'], 'OK')

        response2 = self.get_request(views.user, guid=user2._id)
        res_json2 = json.loads(response2.content)
        nt.assert_equal(response2.status_code, 200)
        nt.assert_equal(res_json2['status'], 'OK')
        user_quota2 = UserQuota.objects.get(user=user2, storage_type=UserQuota.NII_STORAGE)
        nt.assert_equal(user_quota2.max_quota, api_settings.DEFAULT_MAX_QUOTA)
        nt.assert_equal(user_quota2.used, 1500)

        response3 = self.get_request(views.all_users)
        res_json3 = json.loads(response3.content)
        nt.assert_equal(response3.status_code, 200)
        nt.assert_equal(res_json3['status'], 'OK')
        nt.assert_true('3' in res_json3['message'])


class TestQuotaRecalcPermission(AdminTestCase):
    """all_users/user must be restricted to Integrated Admin (is_superuser)."""

    def setUp(self):
        super(TestQuotaRecalcPermission, self).setUp()
        self.general_user = AuthUserFactory()
        self.superuser = AuthUserFactory()
        self.superuser.is_superuser = True
        self.superuser.save()
        self.target_user = AuthUserFactory()

    def test_all_users_denied_for_general_user(self):
        request = RequestFactory().get('/fake_path')
        request.user = self.general_user
        with nt.assert_raises(PermissionDenied):
            views.all_users(request)

    def test_all_users_denied_for_anonymous(self):
        request = RequestFactory().get('/fake_path')
        request.user = AnonymousUser()
        with nt.assert_raises(PermissionDenied):
            views.all_users(request)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_all_users_allowed_for_superuser(self, mock_usedquota):
        mock_usedquota.return_value = 0
        request = RequestFactory().get('/fake_path')
        request.user = self.superuser
        response = views.all_users(request)
        nt.assert_equal(response.status_code, 200)

    def test_user_denied_for_general_user(self):
        request = RequestFactory().get('/fake_path')
        request.user = self.general_user
        with nt.assert_raises(PermissionDenied):
            views.user(request, guid=self.target_user._id)

    def test_user_denied_for_anonymous(self):
        request = RequestFactory().get('/fake_path')
        request.user = AnonymousUser()
        with nt.assert_raises(PermissionDenied):
            views.user(request, guid=self.target_user._id)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_allowed_for_superuser(self, mock_usedquota):
        mock_usedquota.return_value = 0
        request = RequestFactory().get('/fake_path')
        request.user = self.superuser
        response = views.user(request, guid=self.target_user._id)
        nt.assert_equal(response.status_code, 200)


class TestCalculateQuota(AdminTestCase):

    def setUp(self):
        super(TestCalculateQuota, self).setUp()
        self.user = AuthUserFactory()

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_without_institution(self, mock_usedquota):
        mock_usedquota.return_value = 5000

        views.calculate_quota(self.user)

        user_quota = UserQuota.objects.filter(user=self.user).all()
        nt.assert_equal(len(user_quota), 1)
        nt.assert_equal(user_quota[0].used, 5000)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_institution_without_custom_storage(self, mock_usedquota):
        mock_usedquota.return_value = 6000

        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)

        views.calculate_quota(self.user)

        user_quota = UserQuota.objects.filter(user=self.user).all()
        nt.assert_equal(len(user_quota), 1)
        nt.assert_equal(user_quota[0].used, 6000)

    @mock.patch('admin.quota_recalc.views.used_quota')
    def test_user_institution_with_custom_storage(self, mock_usedquota):
        mock_usedquota.side_effect = \
            lambda uid, storage_type: 300 if storage_type == UserQuota.NII_STORAGE else 7000

        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        RegionFactory(_id=institution._id)

        views.calculate_quota(self.user)

        user_quota = UserQuota.objects.filter(user=self.user).all()
        nt.assert_equal(len(user_quota), 2)

        expected = {
            UserQuota.NII_STORAGE: 300,
            UserQuota.CUSTOM_STORAGE: 7000,
        }

        nt.assert_equal(user_quota[0].used, expected[user_quota[0].storage_type])
        nt.assert_equal(user_quota[1].used, expected[user_quota[1].storage_type])

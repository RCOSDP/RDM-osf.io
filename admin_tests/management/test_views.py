# -*- coding: utf-8 -*-
from nose import tools as nt
import mock
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied

from admin.management import views
from osf_tests.factories import AuthUserFactory
from tests.base import AdminTestCase


class TestManagementCommandsPermission(AdminTestCase):
    """ManagementCommands must be restricted to Integrated Admin (is_super_admin)."""

    def setUp(self):
        super(TestManagementCommandsPermission, self).setUp()
        self.superuser = AuthUserFactory()
        self.superuser.is_superuser = True
        self.superuser.save()
        self.general_user = AuthUserFactory()

    def test_get_denied_for_general_user(self):
        request = RequestFactory().get('/fake_path')
        request.user = self.general_user
        with nt.assert_raises(PermissionDenied):
            views.ManagementCommands.as_view()(request)

    def test_get_denied_for_anonymous(self):
        request = RequestFactory().get('/fake_path')
        request.user = AnonymousUser()
        with nt.assert_raises(PermissionDenied):
            views.ManagementCommands.as_view()(request)

    def test_get_allowed_for_superuser(self):
        request = RequestFactory().get('/fake_path')
        request.user = self.superuser
        response = views.ManagementCommands.as_view()(request)
        nt.assert_equal(response.status_code, 200)


class TestWaffleFlagPermission(AdminTestCase):
    """WaffleFlag must be restricted to Integrated Admin (is_super_admin)."""

    def setUp(self):
        super(TestWaffleFlagPermission, self).setUp()
        self.superuser = AuthUserFactory()
        self.superuser.is_superuser = True
        self.superuser.save()
        self.general_user = AuthUserFactory()

    def test_post_denied_for_general_user(self):
        request = RequestFactory().post('/fake_path')
        request.user = self.general_user
        with nt.assert_raises(PermissionDenied):
            views.WaffleFlag.as_view()(request)

    def test_post_denied_for_anonymous(self):
        request = RequestFactory().post('/fake_path')
        request.user = AnonymousUser()
        with nt.assert_raises(PermissionDenied):
            views.WaffleFlag.as_view()(request)

    @mock.patch('admin.management.views.manage_waffle')
    def test_post_allowed_for_superuser(self, mock_manage_waffle):
        request = RequestFactory().post('/fake_path')
        request.user = self.superuser
        response = views.WaffleFlag.as_view()(request)
        nt.assert_equal(response.status_code, 302)
        nt.assert_true(mock_manage_waffle.called)

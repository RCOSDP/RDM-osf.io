# -*- coding: utf-8 -*-
import mock
from django.urls import clear_url_caches, resolve
from django.http import Http404
from django.test import RequestFactory
from django.utils.six.moves import reload_module
from nose import tools as nt

from admin.base import urls as admin_urls_module
from tests.base import AdminTestCase


class TestAdminLoginUrl(AdminTestCase):
    """/admin/login/ (AdminSite.login from admin.site.urls) is a second entry point
    of password-based authentication, so it must follow ENABLE_LOGIN_FORM."""

    def _reload_urls(self):
        reload_module(admin_urls_module)
        clear_url_caches()

    def _with_login_form(self, enabled):
        patcher = mock.patch('admin.base.settings.ENABLE_LOGIN_FORM', enabled)
        patcher.start()
        self.addCleanup(self._restore_urls)
        self.addCleanup(patcher.stop)
        self._reload_urls()

    def _restore_urls(self):
        # cleanups run LIFO: patcher.stop() has already run, so this reloads with the real setting
        reload_module(admin_urls_module)
        clear_url_caches()

    def _call_login_view(self, request):
        match = resolve('/admin/login/')
        return match.func(request, *match.args, **match.kwargs)

    def test_login_is_404_for_get_when_login_form_disabled(self):
        self._with_login_form(False)
        request = RequestFactory().get('/admin/login/')
        with nt.assert_raises(Http404):
            self._call_login_view(request)

    def test_login_is_404_for_post_when_login_form_disabled(self):
        self._with_login_form(False)
        request = RequestFactory().post('/admin/login/', {'username': 'user@example.com', 'password': 'secret'})
        with nt.assert_raises(Http404):
            self._call_login_view(request)

    def test_login_route_is_disabled_view_when_login_form_disabled(self):
        self._with_login_form(False)
        nt.assert_equal(resolve('/admin/login/').url_name, 'admin_login_disabled')

    def test_login_route_is_admin_site_login_when_login_form_enabled(self):
        self._with_login_form(True)
        nt.assert_equal(resolve('/admin/login/').view_name, 'admin:login')

    def test_admin_site_urls_other(self):
        self._with_login_form(False)
        nt.assert_equal(resolve('/admin/').view_name, 'admin:index')

# -*- coding: utf-8 -*-
import mock
from django.urls import clear_url_caches
from django.test import Client
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

    def test_login_is_404_for_get_when_login_form_disabled(self):
        self._with_login_form(False)
        response = Client().get('/admin/login/')
        nt.assert_equal(response.status_code, 404)

    def test_login_is_404_for_post_when_login_form_disabled(self):
        self._with_login_form(False)
        response = Client().post('/admin/login/', {'username': 'user@example.com', 'password': 'secret'})
        nt.assert_equal(response.status_code, 404)

    def test_login_is_shown_when_login_form_enabled(self):
        self._with_login_form(True)
        response = Client().get('/admin/login/')
        nt.assert_equal(response.status_code, 200)

    def test_admin_site_urls_other(self):
        self._with_login_form(False)
        # AdminSite.admin_view redirects non-staff users to the admin login page
        response = Client().get('/admin/', follow=False)
        nt.assert_equal(response.status_code, 302)

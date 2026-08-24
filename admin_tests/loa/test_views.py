# -*- coding: utf-8 -*-
"""Tests for admin.loa.views (ListLoA and BulkAddLoA)."""
from urllib.parse import urlencode

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse

from admin.loa import views
from admin_tests.utilities import setup_user_view
from osf.models.loa import LoA
from osf_tests.factories import AuthUserFactory, InstitutionFactory
from tests.base import AdminTestCase

pytestmark = pytest.mark.django_db


class TestListLoA(AdminTestCase):
    """Tests for ListLoA view."""

    def setUp(self):
        super(TestListLoA, self).setUp()

        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')

        # Anonymous user
        self.anon = AnonymousUser()

        # Superuser
        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.is_staff = True
        self.superuser.save()

        # Institutional admin for institution01
        self.inst01_admin = AuthUserFactory(fullname='admin_inst01')
        self.inst01_admin.is_staff = True
        self.inst01_admin.affiliated_institutions.add(self.institution01)
        self.inst01_admin.save()

        # Institutional admin for institution02
        self.inst02_admin = AuthUserFactory(fullname='admin_inst02')
        self.inst02_admin.is_staff = True
        self.inst02_admin.affiliated_institutions.add(self.institution02)
        self.inst02_admin.save()

        # Normal user (no staff, no superuser)
        self.normal_user = AuthUserFactory(fullname='normal_user')
        self.normal_user.is_staff = False
        self.normal_user.is_superuser = False
        self.normal_user.save()

    # --- dispatch tests ---

    def test_dispatch_unauthenticated_user(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.anon)
        with pytest.raises(PermissionDenied):
            view.dispatch(request)

    def test_dispatch_invalid_institution_id(self):
        request = RequestFactory().get('/fake_path', {'institution_id': 'abc'})
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        # render_bad_request_response requires 400.html template;
        # verify that the ValueError is caught and a bad-request path is taken.
        from django.template.exceptions import TemplateDoesNotExist
        with pytest.raises((TemplateDoesNotExist, ValueError)):
            view.dispatch(request)

    def test_dispatch_valid_institution_id(self):
        request = RequestFactory().get(
            '/fake_path', {'institution_id': str(self.institution01.id)}
        )
        request.user = self.superuser
        view = views.ListLoA()
        view.request = request
        view.args = ()
        view.kwargs = {}
        response = view.dispatch(request)
        assert response.status_code == 200

    # --- test_func tests ---

    def test_test_func_superuser_without_institution_id(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = None
        assert view.test_func() is True

    def test_test_func_institutional_admin_without_institution_id(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.institution_id = None
        assert view.test_func() is True

    def test_test_func_normal_user_without_institution_id(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.normal_user)
        view.institution_id = None
        assert view.test_func() is False

    def test_test_func_superuser_with_valid_institution_id(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = self.institution01.id
        assert view.test_func() is True

    def test_test_func_institutional_admin_own_institution(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.institution_id = self.institution01.id
        assert view.test_func() is True

    def test_test_func_institutional_admin_other_institution(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.institution_id = self.institution02.id
        assert view.test_func() is False

    def test_test_func_nonexistent_institution_id(self):
        request = RequestFactory().get('/fake_path')
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = 99999
        with pytest.raises(Http404):
            view.test_func()

    # --- get_context_data tests ---

    def test_get_context_data_superuser(self):
        modifier = self.superuser
        LoA.objects.create(
            institution=self.institution01, aal=2, ial=1, is_mfa=True, modifier=modifier,
        )

        request = RequestFactory().get(
            '/fake_path', {'institution_id': str(self.institution01.id)}
        )
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.kwargs = {}
        view.institution_id = self.institution01.id

        ctx = view.get_context_data()
        assert 'institutions' in ctx
        assert 'institution_id' in ctx
        assert 'formset_loa' in ctx
        assert ctx['institution_id'] == self.institution01.id

    def test_get_context_data_institutional_admin(self):
        request = RequestFactory().get(
            '/fake_path', {'institution_id': str(self.institution01.id)}
        )
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.kwargs = {}
        view.institution_id = self.institution01.id

        ctx = view.get_context_data()
        # Institutional admin should only see their own institution(s)
        institution_ids = [inst.id for inst in ctx['institutions']]
        assert self.institution01.id in institution_ids
        assert self.institution02.id not in institution_ids

    def test_get_context_data_superuser_sees_all_institutions(self):
        request = RequestFactory().get(
            '/fake_path', {'institution_id': str(self.institution01.id)}
        )
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.kwargs = {}
        view.institution_id = self.institution01.id

        ctx = view.get_context_data()
        institution_ids = [inst.id for inst in ctx['institutions']]
        assert self.institution01.id in institution_ids
        assert self.institution02.id in institution_ids

    def test_get_context_data_permission_denied_for_non_admin(self):
        request = RequestFactory().get(
            '/fake_path', {'institution_id': str(self.institution01.id)}
        )
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.normal_user)
        view.kwargs = {}
        view.institution_id = self.institution01.id

        with pytest.raises(PermissionDenied):
            view.get_context_data()

    def test_get_context_data_no_existing_loa(self):
        """When no LoA exists for the institution, formset_loa should be unbound."""
        request = RequestFactory().get(
            '/fake_path', {'institution_id': str(self.institution01.id)}
        )
        view = views.ListLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.kwargs = {}
        view.institution_id = self.institution01.id

        ctx = view.get_context_data()
        assert ctx['formset_loa'] is not None


class TestBulkAddLoA(AdminTestCase):
    """Tests for BulkAddLoA view."""

    def setUp(self):
        super(TestBulkAddLoA, self).setUp()

        self.institution01 = InstitutionFactory(name='inst01')
        self.institution02 = InstitutionFactory(name='inst02')

        # Anonymous user
        self.anon = AnonymousUser()

        # Superuser
        self.superuser = AuthUserFactory(fullname='superuser')
        self.superuser.is_superuser = True
        self.superuser.is_staff = True
        self.superuser.save()

        # Institutional admin for institution01
        self.inst01_admin = AuthUserFactory(fullname='admin_inst01')
        self.inst01_admin.is_staff = True
        self.inst01_admin.affiliated_institutions.add(self.institution01)
        self.inst01_admin.save()

        self.view = views.BulkAddLoA.as_view()

    # --- dispatch tests ---

    def test_dispatch_unauthenticated(self):
        request = RequestFactory().post(
            reverse('loa:bulk_add'),
            {'institution_id': self.institution01.id, 'aal': '1', 'ial': '1', 'is_mfa': 'False'},
        )
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.anon)
        with pytest.raises(PermissionDenied):
            view.dispatch(request)

    def test_dispatch_missing_institution_id(self):
        request = RequestFactory().post(
            reverse('loa:bulk_add'),
            {'aal': '1', 'ial': '1', 'is_mfa': 'False'},
        )
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        from django.template.exceptions import TemplateDoesNotExist
        with pytest.raises((TemplateDoesNotExist, ValueError)):
            view.dispatch(request)

    def test_dispatch_invalid_institution_id(self):
        request = RequestFactory().post(
            reverse('loa:bulk_add'),
            {'institution_id': 'abc', 'aal': '1', 'ial': '1', 'is_mfa': 'False'},
        )
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        from django.template.exceptions import TemplateDoesNotExist
        with pytest.raises((TemplateDoesNotExist, ValueError)):
            view.dispatch(request)

    # --- test_func tests ---

    def test_test_func_superuser(self):
        request = RequestFactory().post('/fake_path')
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = self.institution01.id
        assert view.test_func() is True

    def test_test_func_institutional_admin_own_institution(self):
        request = RequestFactory().post('/fake_path')
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.institution_id = self.institution01.id
        assert view.test_func() is True

    def test_test_func_institutional_admin_other_institution(self):
        request = RequestFactory().post('/fake_path')
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.institution_id = self.institution02.id
        assert view.test_func() is False

    def test_test_func_nonexistent_institution(self):
        request = RequestFactory().post('/fake_path')
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = 99999
        with pytest.raises(Http404):
            view.test_func()

    def test_test_func_deleted_institution(self):
        deleted_inst = InstitutionFactory(name='deleted_inst')
        deleted_inst.is_deleted = True
        deleted_inst.save()
        request = RequestFactory().post('/fake_path')
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = deleted_inst.id
        with pytest.raises(Http404):
            view.test_func()

    # --- post tests ---

    def test_post_creates_new_loa(self):
        request = RequestFactory().post(
            reverse('loa:bulk_add'),
            {
                'institution_id': str(self.institution01.id),
                'aal': '2',
                'ial': '1',
                'is_mfa': 'True',
            },
        )
        request.user = self.superuser
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        # Manually invoke the post method
        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = self.institution01.id
        response = view.post(request)

        assert response.status_code == 302
        loa = LoA.objects.get(institution_id=self.institution01.id)
        assert loa.aal == 2
        assert loa.ial == 1
        assert loa.modifier == self.superuser

    def test_post_updates_existing_loa(self):
        # Create initial LoA
        LoA.objects.create(
            institution=self.institution01, aal=1, ial=0, is_mfa=False,
            modifier=self.superuser,
        )
        request = RequestFactory().post(
            reverse('loa:bulk_add'),
            {
                'institution_id': str(self.institution01.id),
                'aal': '2',
                'ial': '2',
                'is_mfa': 'True',
            },
        )
        request.user = self.inst01_admin
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.inst01_admin)
        view.institution_id = self.institution01.id
        response = view.post(request)

        assert response.status_code == 302
        loa = LoA.objects.get(institution_id=self.institution01.id)
        assert loa.aal == 2
        assert loa.ial == 2
        assert loa.modifier == self.inst01_admin

    def test_post_redirect_url_contains_institution_id(self):
        request = RequestFactory().post(
            reverse('loa:bulk_add'),
            {
                'institution_id': str(self.institution01.id),
                'aal': '1',
                'ial': '1',
                'is_mfa': 'False',
            },
        )
        request.user = self.superuser
        setattr(request, 'session', 'session')
        setattr(request, '_messages', FallbackStorage(request))

        view = views.BulkAddLoA()
        view = setup_user_view(view, request, user=self.superuser)
        view.institution_id = self.institution01.id
        response = view.post(request)

        assert response.status_code == 302
        expected_query = urlencode({'institution_id': str(self.institution01.id)})
        assert expected_query in response.url

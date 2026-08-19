from nose import tools as nt
import mock

from django.test import RequestFactory
from django.http import Http404
from django.urls import reverse
from django.contrib.auth import REDIRECT_FIELD_NAME
from tests.base import AdminTestCase
from osf_tests.factories import AuthUserFactory, InstitutionFactory

from admin_tests.utilities import setup_form_view, setup_view

from osf.models.user import OSFUser
from admin.common_auth.views import RegisterUser, ShibLoginView
from admin.common_auth.forms import UserRegistrationForm


class TestRegisterUser(AdminTestCase):
    def setUp(self):
        super(TestRegisterUser, self).setUp()
        self.user = AuthUserFactory()
        self.data = {
            'osf_id': 'abc12',
        }
        self.view = RegisterUser()
        self.request = RequestFactory().post('fake_path')

    def test_osf_id_invalid(self):
        form = UserRegistrationForm(data=self.data)
        nt.assert_true(form.is_valid())
        view = setup_form_view(self.view, self.request, form)
        with nt.assert_raises(Http404):
            view.form_valid(form)

    @mock.patch('admin.common_auth.views.messages.success')
    def test_add_user(self, mock_save):
        count = OSFUser.objects.count()
        self.data.update(osf_id=self.user._id)
        form = UserRegistrationForm(data=self.data)
        nt.assert_true(form.is_valid())
        view = setup_form_view(self.view, self.request, form)
        view.form_valid(form)
        nt.assert_true(mock_save.called)
        nt.assert_equal(OSFUser.objects.count(), count + 1)

class TestShibLoginView(AdminTestCase):
    """
    Test ShibLoginView.dispatch and get_success_url.
    """

    EPPN_DOMAIN = 'example.ac.jp'
    EPPN = 'testuser@' + EPPN_DOMAIN
    ENTITLEMENT_ADMIN = 'GakuNinRDMAdmin'
    DISPLAY_NAME = 'Test User'

    def setUp(self):
        super(TestShibLoginView, self).setUp()
        self.institution = InstitutionFactory(domains=[self.EPPN_DOMAIN])

    def _make_request(self, eppn=None, entitlement='', displayname=None):
        """Helper: create a GET request with Shibboleth environ headers."""
        eppn = eppn if eppn is not None else self.EPPN
        displayname = displayname or self.DISPLAY_NAME
        request = RequestFactory().get('fake_path')
        request.environ['HTTP_AUTH_EPPN'] = eppn
        request.environ['HTTP_AUTH_ENTITLEMENT'] = entitlement
        request.environ['HTTP_AUTH_DISPLAYNAME'] = displayname
        return request

    # ------------------------------------------------------------------
    # No institution found for the eppn domain
    # ------------------------------------------------------------------
    def test_no_institution_redirects_to_login(self):
        request = self._make_request(eppn='user@unknown.domain.jp')
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        nt.assert_equal(response.status_code, 302)
        nt.assert_in('login', response.url)

    # ------------------------------------------------------------------
    # eppn is empty string but institution lookup is mocked to
    #           return a result (otherwise empty domain fails at branch A)
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.messages.error')
    def test_empty_eppn_redirects_to_login(self, mock_error):
        request = self._make_request(eppn='')
        with mock.patch('admin.common_auth.views.Institution') as mock_inst_cls:
            mock_inst_cls.objects.filter.return_value.first.return_value = self.institution
            view = setup_view(ShibLoginView(), request)
            response = view.dispatch(request)
        nt.assert_equal(response.status_code, 302)
        nt.assert_in('login', response.url)
        nt.assert_true(mock_error.called)

    # ------------------------------------------------------------------
    # Existing user + GakuNinRDMAdmin entitlement → login
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    def test_existing_user_with_admin_entitlement_logs_in(self, mock_login, mock_check, mock_keygen):
        user = AuthUserFactory()
        user.eppn = self.EPPN
        user.save()
        request = self._make_request(entitlement=self.ENTITLEMENT_ADMIN)
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        user.refresh_from_db()
        nt.assert_true(user.is_staff)
        nt.assert_true(mock_login.called)
        nt.assert_true(mock_keygen.called)
        nt.assert_equal(response.status_code, 302)

    # ------------------------------------------------------------------
    # Existing user + no admin entitlement → redirect error
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.messages.error')
    def test_existing_user_without_admin_entitlement_redirects(self, mock_error):
        user = AuthUserFactory()
        user.eppn = self.EPPN
        user.save()
        request = self._make_request(entitlement='SomeOtherEntitlement')
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        user.refresh_from_db()
        nt.assert_false(user.is_staff)
        nt.assert_true(mock_error.called)
        nt.assert_equal(response.status_code, 302)
        nt.assert_in('login', response.url)

    # ------------------------------------------------------------------
    # New user (no eppn match) + no admin entitlement → redirect error
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.messages.error')
    def test_new_user_without_admin_entitlement_redirects(self, mock_error):
        request = self._make_request(
            eppn='nouser@' + self.EPPN_DOMAIN,
            entitlement='SomeOtherEntitlement',
        )
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        nt.assert_true(mock_error.called)
        nt.assert_equal(response.status_code, 302)
        nt.assert_in('login', response.url)

    # ------------------------------------------------------------------
    # New user + admin entitlement → user created, is_staff=True
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    def test_new_user_with_admin_entitlement_creates_and_logs_in(self, mock_login, mock_check, mock_keygen):
        new_eppn = 'brandnew@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        count_before = OSFUser.objects.count()
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        nt.assert_equal(OSFUser.objects.count(), count_before + 1)
        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_true(new_user.is_staff)
        nt.assert_false(new_user.have_email)
        nt.assert_true(mock_login.called)
        nt.assert_equal(response.status_code, 302)

    # ------------------------------------------------------------------
    # Existing user → other institutions removed, current added
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=True)
    @mock.patch('admin.common_auth.views.login')
    def test_existing_user_institution_updated(self, mock_login, mock_check, mock_keygen):
        other_institution = InstitutionFactory()
        user = AuthUserFactory()
        user.eppn = self.EPPN
        user.affiliated_institutions.add(other_institution)
        user.save()
        request = self._make_request(entitlement=self.ENTITLEMENT_ADMIN)
        view = setup_view(ShibLoginView(), request)
        view.dispatch(request)
        user.refresh_from_db()
        nt.assert_false(
            user.affiliated_institutions.filter(id=other_institution.id).exists()
        )
        nt.assert_true(
            user.affiliated_institutions.filter(id=self.institution.id).exists()
        )

    # ------------------------------------------------------------------
    # userkey_generation_check=True → userkey_generation NOT called
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=True)
    @mock.patch('admin.common_auth.views.login')
    def test_userkey_not_regenerated_when_exists(self, mock_login, mock_check, mock_keygen):
        user = AuthUserFactory()
        user.eppn = self.EPPN
        user.save()
        request = self._make_request(entitlement=self.ENTITLEMENT_ADMIN)
        view = setup_view(ShibLoginView(), request)
        view.dispatch(request)
        nt.assert_false(mock_keygen.called)

    # ------------------------------------------------------------------
    # get_success_url with no param → reverse('home')
    # ------------------------------------------------------------------
    def test_get_success_url_defaults_to_home(self):
        request = RequestFactory().get('fake_path')
        view = setup_view(ShibLoginView(), request)
        nt.assert_equal(view.get_success_url(), reverse('home'))

    # '/' param also falls back to home
    def test_get_success_url_with_slash_defaults_to_home(self):
        request = RequestFactory().get('fake_path', {REDIRECT_FIELD_NAME: '/'})
        view = setup_view(ShibLoginView(), request)
        nt.assert_equal(view.get_success_url(), reverse('home'))

    # ------------------------------------------------------------------
    # get_success_url with custom redirect param
    # ------------------------------------------------------------------
    def test_get_success_url_uses_redirect_param(self):
        request = RequestFactory().get('fake_path', {REDIRECT_FIELD_NAME: '/admin/nodes/'})
        view = setup_view(ShibLoginView(), request)
        nt.assert_equal(view.get_success_url(), '/admin/nodes/')

    # ------------------------------------------------------------------
    # New user + admin entitlement + USE_EPPN=True
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=True)
    def test_new_user_use_eppn_true(self, mock_use_eppn, mock_login, mock_check, mock_keygen):
        new_eppn = 'eppntrue@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_true(new_user.is_staff)
        nt.assert_false(new_user.have_email)
        nt.assert_equal(new_user.eppn, new_eppn)
        nt.assert_equal(response.status_code, 302)

    # ------------------------------------------------------------------
    # New user + admin entitlement + USE_EPPN=False
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=False)
    def test_new_user_use_eppn_false(self, mock_use_eppn, mock_login, mock_check, mock_keygen):
        new_eppn = 'eppnfalse@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        view = setup_view(ShibLoginView(), request)
        response = view.dispatch(request)
        # Lines 120-121 override the else-branch values, so final state is same
        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_true(new_user.is_staff)
        nt.assert_false(new_user.have_email)
        nt.assert_equal(new_user.eppn, new_eppn)
        nt.assert_equal(response.status_code, 302)

    # ------------------------------------------------------------------
    # Japanese displayname: Apache/WSGI passes UTF-8 bytes as Latin-1 (mojibake).
    # Fix encodes back to iso-8859-1 then decodes as utf-8 → original Japanese.
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=True)
    def test_new_user_japanese_displayname_decoded_correctly(
            self, mock_use_eppn, mock_login, mock_check, mock_keygen):
        japanese_name = '山田 太郎'
        # Simulate WSGI: UTF-8 bytes of the Japanese string interpreted as Latin-1
        mojibake = japanese_name.encode('utf-8').decode('latin-1')

        new_eppn = 'jauser@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        request.environ['HTTP_AUTH_DISPLAYNAME'] = mojibake

        view = setup_view(ShibLoginView(), request)
        view.dispatch(request)

        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_equal(new_user.fullname, japanese_name)

    # ------------------------------------------------------------------
    # Multi-byte Japanese name with organization prefix (real-world case).
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=True)
    def test_new_user_japanese_fullwidth_displayname_decoded_correctly(
            self, mock_use_eppn, mock_login, mock_check, mock_keygen):
        japanese_name = '国立情報学研究所　鈴木一郎'
        mojibake = japanese_name.encode('utf-8').decode('latin-1')

        new_eppn = 'jafull@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        request.environ['HTTP_AUTH_DISPLAYNAME'] = mojibake

        view = setup_view(ShibLoginView(), request)
        view.dispatch(request)

        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_equal(new_user.fullname, japanese_name)

    # ------------------------------------------------------------------
    # Empty displayname → falls back to 'NO NAME'
    # covers: display_name = '' → get_or_create_user('' or 'NO NAME', ...)
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=True)
    def test_new_user_empty_displayname_falls_back_to_no_name(
            self, mock_use_eppn, mock_login, mock_check, mock_keygen):
        new_eppn = 'noname@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        request.environ['HTTP_AUTH_DISPLAYNAME'] = ''  # override helper default

        view = setup_view(ShibLoginView(), request)
        view.dispatch(request)

        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_equal(new_user.fullname, 'NO NAME')

    # ------------------------------------------------------------------
    # ASCII displayname passes through unchanged
    # encode('iso-8859-1').decode('utf-8') on pure ASCII is identity
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.userkey_generation')
    @mock.patch('admin.common_auth.views.userkey_generation_check', return_value=False)
    @mock.patch('admin.common_auth.views.login')
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=True)
    def test_new_user_ascii_displayname_passes_through(
            self, mock_use_eppn, mock_login, mock_check, mock_keygen):
        new_eppn = 'ascii@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        request.environ['HTTP_AUTH_DISPLAYNAME'] = 'John Smith'

        view = setup_view(ShibLoginView(), request)
        view.dispatch(request)

        new_user = OSFUser.objects.get(eppn=new_eppn)
        nt.assert_equal(new_user.fullname, 'John Smith')

    # ------------------------------------------------------------------
    # Missing HTTP_AUTH_DISPLAYNAME header → KeyError
    # ------------------------------------------------------------------
    @mock.patch('admin.common_auth.views.login_by_eppn', return_value=True)
    def test_new_user_missing_displayname_header_raises_key_error(self, mock_use_eppn):
        new_eppn = 'missing@' + self.EPPN_DOMAIN
        request = self._make_request(eppn=new_eppn, entitlement=self.ENTITLEMENT_ADMIN)
        del request.environ['HTTP_AUTH_DISPLAYNAME']
        view = setup_view(ShibLoginView(), request)
        with nt.assert_raises(KeyError):
            view.dispatch(request)

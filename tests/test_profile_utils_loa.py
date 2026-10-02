# -*- coding: utf-8 -*-
"""Tests for LoA/MFA-related fields in website.profile.utils.serialize_user().

Covers:
  - _aal / _ial badge classification
  - mfa_url construction and content
  - is_mfa flag based on LoA settings
  - Behaviour when no idp_attr / no LoA record exists
"""
import mock
import pytest
from urllib.parse import parse_qs, urlparse

from osf.models.loa import LoA
from osf.models import UserExtendedData
from osf_tests.factories import AuthUserFactory, InstitutionFactory
from tests.base import OsfTestCase
from website import settings
from website.profile.utils import serialize_user
from website.util import web_url_for

pytestmark = pytest.mark.django_db


def _make_user_with_idp_attr(institution=None, ial=None, aal=None, idp='https://idp.example.ac.jp'):
    """Helper: create a user with idp_attr set on UserExtendedData."""
    user = AuthUserFactory()
    user.ial = ial
    user.aal = aal
    user.save()

    if institution is None:
        institution = InstitutionFactory()
    user.affiliated_institutions.add(institution)

    ext, _ = UserExtendedData.objects.get_or_create(user=user)
    ext.set_idp_attr({
        'id': institution.id,
        'idp': idp,
        'eppn': user.username,
        'username': user.username,
        'fullname': user.fullname,
        'email': user.username,
    })

    return user, institution


def _query_param(url, name):
    """Return a single query parameter value from a URL."""
    return parse_qs(urlparse(url).query)[name][0]


def _unwrap_mfa_url(mfa_url):
    """Peel the nested layers of the MFA URL built by serialize_user().

    Structure::

        CAS_SERVER_URL/logout?service=
            OSF_MFA_URL?entityID=<entity_id>&target=
                CAS_SERVER_URL/login?service=<return_url>

    Returns a dict with the ``ds_url``, ``entity_id``, ``login_url`` and
    ``return_url`` parts, so tests can assert on each layer exactly rather
    than relying on substring matching against a multiply-encoded string.
    """
    ds_url = _query_param(mfa_url, 'service')
    login_url = _query_param(ds_url, 'target')
    return {
        'ds_url': ds_url,
        'entity_id': _query_param(ds_url, 'entityID'),
        'login_url': login_url,
        'return_url': _query_param(login_url, 'service'),
    }


class TestSerializeUserAalBadge(OsfTestCase):
    """Tests for _aal classification in serialize_user()."""

    def test_aal_null_when_no_aal(self):
        user, _ = _make_user_with_idp_attr(aal=None)
        result = serialize_user(user)
        assert result['_aal'] == 'NULL'

    def test_aal_null_when_empty_string(self):
        user, _ = _make_user_with_idp_attr(aal='')
        result = serialize_user(user)
        assert result['_aal'] == 'NULL'

    def test_aal2_when_aal_contains_aal2_url(self):
        user, _ = _make_user_with_idp_attr(
            aal='https://www.gakunin.jp/profile/AAL2',
        )
        result = serialize_user(user)
        assert result['_aal'] == 'AAL2'

    def test_aal1_when_aal_contains_aal1_url(self):
        user, _ = _make_user_with_idp_attr(
            aal='https://www.gakunin.jp/profile/AAL1',
        )
        result = serialize_user(user)
        assert result['_aal'] == 'AAL1'

    def test_aal1_when_aal_is_other_value(self):
        """Any non-AAL2 truthy value should classify as AAL1."""
        user, _ = _make_user_with_idp_attr(
            aal='urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport',
        )
        result = serialize_user(user)
        assert result['_aal'] == 'AAL1'

    def test_raw_aal_value_is_preserved(self):
        aal_value = 'https://www.gakunin.jp/profile/AAL2'
        user, _ = _make_user_with_idp_attr(aal=aal_value)
        result = serialize_user(user)
        assert result['aal'] == aal_value


class TestSerializeUserIalBadge(OsfTestCase):
    """Tests for _ial classification in serialize_user()."""

    def test_ial1_when_no_ial(self):
        """When ial is None or empty, _ial should be IAL1 (default)."""
        user, _ = _make_user_with_idp_attr(ial=None)
        result = serialize_user(user)
        assert result['_ial'] == 'IAL1'

    def test_ial2_when_ial_contains_ial2_url(self):
        user, _ = _make_user_with_idp_attr(
            ial='https://www.gakunin.jp/profile/IAL2',
        )
        result = serialize_user(user)
        assert result['_ial'] == 'IAL2'

    def test_ial1_when_ial_is_other_value(self):
        """Values other than IAL2 are equivalent to IAL1."""
        user, _ = _make_user_with_idp_attr(ial='some_other_ial_value')
        result = serialize_user(user)
        assert result['_ial'] == 'IAL1'

    def test_raw_ial_value_is_preserved(self):
        ial_value = 'https://www.gakunin.jp/profile/IAL2'
        user, _ = _make_user_with_idp_attr(ial=ial_value)
        result = serialize_user(user)
        assert result['ial'] == ial_value


class TestSerializeUserMfaUrl(OsfTestCase):
    """Tests for mfa_url construction in serialize_user()."""

    @mock.patch.object(settings, 'OSF_MFA_URL', 'https://mfa.example.com/ds')
    @mock.patch.object(settings, 'CAS_SERVER_URL', 'https://cas.example.com')
    def test_mfa_url_constructed_when_entity_id_present(self):
        """When idp_attr has entity_id (idp), mfa_url should be constructed."""
        user, institution = _make_user_with_idp_attr(
            idp='https://idp.example.ac.jp',
        )
        result = serialize_user(user)
        mfa_url = result['mfa_url']
        assert mfa_url != ''
        # Should contain CAS logout redirect pattern
        assert 'cas.example.com/logout' in mfa_url
        # Should contain mfa.example.com/ds in the service param
        assert 'mfa.example.com' in mfa_url

    @mock.patch.object(settings, 'OSF_MFA_URL', 'https://mfa.example.com/ds')
    @mock.patch.object(settings, 'CAS_SERVER_URL', 'https://cas.example.com')
    def test_mfa_url_contains_entity_id(self):
        entity_id = 'https://idp.specific.ac.jp'
        user, institution = _make_user_with_idp_attr(idp=entity_id)
        result = serialize_user(user)
        parts = _unwrap_mfa_url(result['mfa_url'])
        assert parts['entity_id'] == entity_id

    @mock.patch.object(settings, 'OSF_MFA_URL', 'https://mfa.example.com/ds')
    @mock.patch.object(settings, 'CAS_SERVER_URL', 'https://cas.example.com')
    def test_mfa_url_layers(self):
        """Each nested layer of the MFA URL points at the expected endpoint."""
        user, institution = _make_user_with_idp_attr()
        result = serialize_user(user)
        parts = _unwrap_mfa_url(result['mfa_url'])
        assert parts['ds_url'].startswith('https://mfa.example.com/ds?')
        assert parts['login_url'].startswith('https://cas.example.com/login?')

    @mock.patch.object(settings, 'OSF_MFA_URL', 'https://mfa.example.com/ds')
    @mock.patch.object(settings, 'CAS_SERVER_URL', 'https://cas.example.com')
    def test_mfa_url_returns_user_to_dashboard(self):
        """After MFA re-login CAS sends the user back to the dashboard.

        This used to be the profile/settings page ('user_profile'); guard the
        current target so a change back is not silently reintroduced.
        """
        user, institution = _make_user_with_idp_attr()
        result = serialize_user(user)
        parts = _unwrap_mfa_url(result['mfa_url'])
        assert parts['return_url'] == web_url_for('dashboard', _absolute=True)
        assert parts['return_url'] != web_url_for('user_profile', _absolute=True)

    def test_mfa_url_empty_when_no_entity_id(self):
        """When idp_attr has no 'idp' key, mfa_url should be empty."""
        user = AuthUserFactory()
        user.aal = None
        user.ial = None
        user.save()

        # Set idp_attr without 'idp' key
        ext, _ = UserExtendedData.objects.get_or_create(user=user)
        ext.set_idp_attr({
            'id': None,
            'username': user.username,
        })

        result = serialize_user(user)
        assert result['mfa_url'] == ''

    def test_mfa_url_empty_when_no_idp_attr(self):
        """When user has no UserExtendedData, mfa_url should be empty."""
        user = AuthUserFactory()
        user.aal = None
        user.ial = None
        user.save()

        result = serialize_user(user)
        assert result['mfa_url'] == ''


class TestSerializeUserIsMfa(OsfTestCase):
    """Tests for is_mfa flag based on LoA settings."""

    def test_is_mfa_true_when_loa_has_mfa_enabled(self):
        user, institution = _make_user_with_idp_attr()
        modifier = AuthUserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        result = serialize_user(user)
        assert result['is_mfa'] is True

    def test_is_mfa_false_when_loa_has_mfa_disabled(self):
        user, institution = _make_user_with_idp_attr()
        modifier = AuthUserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=False, modifier=modifier,
        )
        result = serialize_user(user)
        assert result['is_mfa'] is False

    def test_is_mfa_false_when_no_loa_record(self):
        user, institution = _make_user_with_idp_attr()
        # No LoA record created
        result = serialize_user(user)
        assert result['is_mfa'] is False

    def test_is_mfa_false_when_no_institution_id_in_idp_attr(self):
        """When idp_attr has id=None, LoA lookup returns None -> is_mfa=False."""
        user = AuthUserFactory()
        user.aal = None
        user.ial = None
        user.save()

        ext, _ = UserExtendedData.objects.get_or_create(user=user)
        ext.set_idp_attr({
            'id': None,
            'idp': 'https://idp.example.ac.jp',
        })

        result = serialize_user(user)
        assert result['is_mfa'] is False


class TestSerializeUserReturnedKeys(OsfTestCase):
    """Verify that all LoA-related keys are present in the serialized output."""

    def test_loa_keys_present(self):
        user, _ = _make_user_with_idp_attr()
        result = serialize_user(user)
        for key in ('ial', 'aal', '_ial', '_aal', 'mfa_url', 'is_mfa'):
            assert key in result, 'Missing key: {}'.format(key)

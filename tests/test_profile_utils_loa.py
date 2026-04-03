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

from osf.models.loa import LoA
from osf.models import UserExtendedData
from osf_tests.factories import AuthUserFactory, InstitutionFactory
from tests.base import OsfTestCase
from website import settings
from website.profile.utils import serialize_user

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
        mfa_url = result['mfa_url']
        # The entityID should be URL-encoded within the mfa_url
        assert 'idp.specific.ac.jp' in mfa_url

    @mock.patch.object(settings, 'OSF_MFA_URL', 'https://mfa.example.com/ds')
    @mock.patch.object(settings, 'CAS_SERVER_URL', 'https://cas.example.com')
    def test_mfa_url_contains_login_service_url(self):
        user, institution = _make_user_with_idp_attr()
        result = serialize_user(user)
        mfa_url = result['mfa_url']
        # The CAS login URL is nested inside multiple urlencode layers,
        # so slashes and colons are percent-encoded repeatedly.
        # Fully decode the URL and then check for the expected substring.
        from urllib.parse import unquote
        decoded = mfa_url
        for _ in range(5):
            decoded = unquote(decoded)
        assert 'cas.example.com/login' in decoded

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

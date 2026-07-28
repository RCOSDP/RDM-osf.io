# -*- coding: utf-8 -*-
"""Tests for LoA (Level of Assurance) validation in institution authentication.

Covers:
  - IAL / AAL extraction from eduPersonAssurance
  - IAL1 is the baseline: ial falls back to OSF_IAL1_VAR when IAL2 is absent
  - LoA validation logic (AAL2 required → MFA redirect, AAL1 required → ValidationError,
    IAL2 required → ValidationError, IAL1 required → always satisfied)
  - MFA URL construction with urlencode()
  - user.context containing mfa_url in response
  - ValidationError raised when LoA requirements are not met
  - user.ial / user.aal are persisted after successful authentication
"""
import json

import jwe
import jwt
import mock
import pytest

from api.base import settings
from api.base.settings.defaults import API_BASE

from osf.models import OSFUser
from osf.models.loa import LoA
from osf_tests.factories import InstitutionFactory, UserFactory
from website.settings import (
    OSF_AAL2_VAR,
    OSF_AAL1_VAR,
    OSF_IAL1_VAR,
    OSF_IAL2_VAR,
)

def make_payload(
        institution,
        username,
        fullname='Fake User',
        given_name='',
        family_name='',
        middle_names='',
        department='',
        edu_person_assurance='',
        shib_authn_context_class='',
        idp=None,
        **extra_user_fields,
):
    """Build a JWE/JWT payload for institution auth.

    Accepts ``edu_person_assurance`` and ``shib_authn_context_class``
    as explicit keyword arguments so that LoA-related tests can easily
    set them.  Any additional user fields can be passed via **extra_user_fields.

    ``idp`` can be set to a string (e.g. an entityID URL) to make the
    authentication code treat the IdP value as a string, which is required
    for MFA URL generation (``type(p_idp) is str`` check).  When *None*
    the default ``institution.email_domains`` (a list) is used.
    """
    user_dict = {
        'middleNames': middle_names,
        'familyName': family_name,
        'givenName': given_name,
        'fullname': fullname,
        'suffix': '',
        'username': username,
        'department': department,
        'eduPersonAssurance': edu_person_assurance,
        'Shib-AuthnContext-Class': shib_authn_context_class,
        # defaults for other fields expected by authentication
        'jaGivenName': '',
        'jaSurname': '',
        'jaDisplayName': '',
        'jaFullname': '',
        'jaMiddleNames': '',
        'jaOrganizationalUnitName': '',
        'organizationalUnitName': '',
        'organizationName': '',
        'eduPersonAffiliation': '',
        'eduPersonScopedAffiliation': '',
        'eduPersonTargetedID': '',
        'eduPersonUniqueId': '',
        'eduPersonOrcid': '',
        'isMemberOf': '',
        'gakuninScopedPersonalUniqueCode': '',
        'gakuninIdentityAssuranceOrganization': '',
        'gakuninIdentityAssuranceMethodReference': '',
    }
    user_dict.update(extra_user_fields)

    data = {
        'provider': {
            'idp': idp if idp is not None else institution.email_domains,
            'id': institution._id,
            'user': user_dict,
        }
    }

    return jwe.encrypt(
        jwt.encode(
            {
                'sub': username,
                'data': json.dumps(data),
            },
            settings.JWT_SECRET,
            algorithm='HS256',
        ),
        settings.JWE_SECRET,
    )


@pytest.mark.django_db
class TestInstitutionAuthLoA:
    """Tests for LoA validation during institution authentication."""

    @pytest.fixture()
    def institution(self):
        return InstitutionFactory()

    @pytest.fixture()
    def url_auth_institution(self):
        return '/{0}institutions/auth/'.format(API_BASE)

    @pytest.fixture()
    def app(self):
        from tests.json_api_test_app import JSONAPITestApp
        return JSONAPITestApp()

    # ---------------------------------------------------------------
    # IAL / AAL extraction from eduPersonAssurance
    # ---------------------------------------------------------------

    def test_aal2_extracted_from_edu_person_assurance(
        self, app, institution, url_auth_institution,
    ):
        """When eduPersonAssurance contains AAL2 URL, user.aal should be set."""
        username = 'user_aal2@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL2',
            ),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.aal == OSF_AAL2_VAR

    def test_aal1_extracted_from_edu_person_assurance(
        self, app, institution, url_auth_institution,
    ):
        username = 'user_aal1@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL1',
            ),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.aal == OSF_AAL1_VAR

    def test_ial2_extracted_from_edu_person_assurance(
        self, app, institution, url_auth_institution,
    ):
        username = 'user_ial2@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/IAL2',
            ),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.ial == OSF_IAL2_VAR

    def test_ial1_is_assigned_when_edu_person_assurance_is_empty(
        self, app, institution, url_auth_institution,
    ):
        """IAL1 is the baseline: ial falls back to OSF_IAL1_VAR when the IdP
        sends no eduPersonAssurance at all.
        """
        username = 'user_ial1_default@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.ial == OSF_IAL1_VAR

    def test_ial1_is_assigned_when_edu_person_assurance_has_no_ial2(
        self, app, institution, url_auth_institution,
    ):
        """eduPersonAssurance carrying only AAL values still yields IAL1."""
        username = 'user_ial1_from_aal_only@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL2',
            ),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.ial == OSF_IAL1_VAR

    def test_aal_falls_back_to_shib_authn_context_class(
        self, app, institution, url_auth_institution,
    ):
        """When eduPersonAssurance has no AAL, Shib-AuthnContext-Class is used."""
        username = 'user_shib@inst.edu'
        shib_value = 'urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='',
                shib_authn_context_class=shib_value,
            ),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.aal == shib_value

    def test_both_aal2_and_ial2_in_edu_person_assurance(
        self, app, institution, url_auth_institution,
    ):
        """Multi-value eduPersonAssurance containing both AAL2 and IAL2."""
        username = 'user_both@inst.edu'
        combined = (
            'https://www.gakunin.jp/profile/AAL2;'
            'https://www.gakunin.jp/profile/IAL2'
        )
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance=combined,
            ),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.aal == OSF_AAL2_VAR
        assert user.ial == OSF_IAL2_VAR

    # ---------------------------------------------------------------
    # LoA validation — no LoA record → pass through
    # ---------------------------------------------------------------

    def test_no_loa_record_allows_login(
        self, app, institution, url_auth_institution,
    ):
        """If no LoA is configured for the institution, login should succeed."""
        username = 'user_noloa@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
        )
        assert res.status_code == 200

    # ---------------------------------------------------------------
    # LoA validation — AAL2 required
    # ---------------------------------------------------------------

    def test_aal2_required_user_has_aal2_passes(
        self, app, institution, url_auth_institution,
    ):
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_aal2_ok@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL2',
            ),
        )
        assert res.status_code == 200
        # mfa_url should be empty because AAL2 requirement is met
        assert res.json.get('mfa_url', '') == ''

    @mock.patch('api.institutions.authentication.OSF_MFA_URL', 'https://mfa.example.com/ds')
    def test_aal2_required_user_has_aal1_returns_mfa_url(
        self, app, institution, url_auth_institution,
    ):
        """When AAL2 is required but user only has AAL1, mfa_url should be set."""
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_aal2_fail@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL1',
                idp='https://idp.example.ac.jp',
            ),
        )
        assert res.status_code == 200
        mfa_url = res.json.get('mfa_url', '')
        assert mfa_url != ''
        # MFA URL should contain expected components
        assert 'entityID=' in mfa_url or 'entityID' in mfa_url

    @mock.patch('api.institutions.authentication.OSF_MFA_URL', 'https://mfa.example.com/ds')
    def test_aal2_required_user_has_no_aal_returns_mfa_url(
        self, app, institution, url_auth_institution,
    ):
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_aal2_none@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                idp='https://idp.example.ac.jp',
            ),
        )
        assert res.status_code == 200
        mfa_url = res.json.get('mfa_url', '')
        assert mfa_url != ''

    # ---------------------------------------------------------------
    # LoA validation — AAL2 required but MFA URL unavailable
    # ---------------------------------------------------------------

    def test_aal2_required_no_mfa_url_available_raises_error(
        self, app, institution, url_auth_institution,
    ):
        """AAL2 required, AAL2 not met, and p_idp is a list (not str) so
        mfa_url_tmp is empty.  Login must be rejected instead of silently
        bypassing the AAL2 requirement.
        """
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_aal2_no_mfa@inst.edu'
        # idp is NOT passed, so institution.email_domains (a list) is used.
        # type(p_idp) is str -> False -> mfa_url_tmp remains empty.
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL1',
            ),
            expect_errors=True,
        )
        assert res.status_code == 400

    def test_aal2_required_no_aal_no_mfa_url_available_raises_error(
        self, app, institution, url_auth_institution,
    ):
        """AAL2 required, no AAL at all, p_idp is a list -> must be rejected."""
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_aal2_no_mfa_none@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
            expect_errors=True,
        )
        assert res.status_code == 400

    def test_aal2_required_user_has_aal2_passes_regardless_of_idp_type(
        self, app, institution, url_auth_institution,
    ):
        """AAL2 required and met - login should pass even if p_idp is a list."""
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_aal2_ok_list_idp@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL2',
            ),
        )
        assert res.status_code == 200

    # ---------------------------------------------------------------
    # LoA validation — AAL1 required
    # ---------------------------------------------------------------

    def test_aal1_required_user_has_aal1_passes(
        self, app, institution, url_auth_institution,
    ):
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=1, ial=0, modifier=modifier,
        )
        username = 'user_aal1_ok@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL1',
            ),
        )
        assert res.status_code == 200

    def test_aal1_required_user_has_no_aal_raises_error(
        self, app, institution, url_auth_institution,
    ):
        """AAL1 required but no AAL provided → ValidationError (400)."""
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=1, ial=0, modifier=modifier,
        )
        username = 'user_aal1_fail@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
            expect_errors=True,
        )
        assert res.status_code == 400

    # ---------------------------------------------------------------
    # LoA validation — IAL2 required
    # ---------------------------------------------------------------

    def test_ial2_required_user_has_ial2_passes(
        self, app, institution, url_auth_institution,
    ):
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=0, ial=2, modifier=modifier,
        )
        username = 'user_ial2_ok@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/IAL2',
            ),
        )
        assert res.status_code == 200

    def test_ial2_required_user_has_no_ial_raises_error(
        self, app, institution, url_auth_institution,
    ):
        """IAL2 required but not provided → ValidationError (400).

        The IAL1 fallback must NOT satisfy an IAL2 requirement.
        """
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=0, ial=2, modifier=modifier,
        )
        username = 'user_ial2_fail@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
            expect_errors=True,
        )
        assert res.status_code == 400

    # ---------------------------------------------------------------
    # LoA validation — IAL1 required
    #
    # IAL1 is the baseline assurance level: ial is always populated with
    # either OSF_IAL2_VAR or OSF_IAL1_VAR, so an IAL1 requirement is
    # satisfied by every authenticated user.
    # ---------------------------------------------------------------

    def test_ial1_required_user_has_ial2_passes(
        self, app, institution, url_auth_institution,
    ):
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=0, ial=1, modifier=modifier,
        )
        username = 'user_ial1_ok@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/IAL2',
            ),
        )
        assert res.status_code == 200

    def test_ial1_required_user_without_ial2_passes(
        self, app, institution, url_auth_institution,
    ):
        """A user with no IAL attribute still meets an IAL1 requirement,
        because ial falls back to OSF_IAL1_VAR.
        """
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=0, ial=1, modifier=modifier,
        )
        username = 'user_ial1_baseline@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        assert user.ial == OSF_IAL1_VAR

    # ---------------------------------------------------------------
    # Combined AAL + IAL requirements
    # ---------------------------------------------------------------

    def test_both_aal2_and_ial2_required_both_met(
        self, app, institution, url_auth_institution,
    ):
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=2, is_mfa=True, modifier=modifier,
        )
        username = 'user_combo_ok@inst.edu'
        combined = (
            'https://www.gakunin.jp/profile/AAL2;'
            'https://www.gakunin.jp/profile/IAL2'
        )
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance=combined,
            ),
        )
        assert res.status_code == 200
        assert res.json.get('mfa_url', '') == ''

    def test_aal2_met_but_ial2_not_met_raises_error(
        self, app, institution, url_auth_institution,
    ):
        """AAL2 met + IAL2 not met → ValidationError (IAL check is independent)."""
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=2, is_mfa=True, modifier=modifier,
        )
        username = 'user_combo_ial_fail@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL2',
            ),
            expect_errors=True,
        )
        assert res.status_code == 400

    # ---------------------------------------------------------------
    # Response contains mfa_url in user.context
    # ---------------------------------------------------------------

    def test_response_body_contains_mfa_url_key(
        self, app, institution, url_auth_institution,
    ):
        """InstitutionAuth.post() returns request.user.context with mfa_url."""
        username = 'user_ctx@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
        )
        assert res.status_code == 200
        assert 'mfa_url' in res.json

    # ---------------------------------------------------------------
    # MFA URL structure validation
    # ---------------------------------------------------------------

    @mock.patch('api.institutions.authentication.OSF_MFA_URL', 'https://mfa.example.com/ds')
    @mock.patch('api.institutions.authentication.CAS_SERVER_URL', 'https://cas.example.com')
    @mock.patch('api.institutions.authentication.DOMAIN', 'https://osf.example.com/')
    def test_mfa_url_structure(
        self, app, institution, url_auth_institution,
    ):
        """Verify MFA URL is constructed correctly with urlencode."""
        modifier = UserFactory()
        LoA.objects.create(
            institution=institution, aal=2, ial=0, is_mfa=True, modifier=modifier,
        )
        username = 'user_mfa_url@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(
                institution, username,
                edu_person_assurance='https://www.gakunin.jp/profile/AAL1',
                idp='https://idp.example.ac.jp',
            ),
        )
        assert res.status_code == 200
        mfa_url = res.json.get('mfa_url', '')
        assert mfa_url != ''
        # MFA URL should start with OSF_MFA_URL (after urlencode wrapping via CAS logout)
        # The overall structure: OSF_MFA_URL?entityID=...&target=CAS/login?service=profile
        assert 'mfa.example.com' in mfa_url or 'cas.example.com' in mfa_url

    # ---------------------------------------------------------------
    # idp_attr stores institution.id
    # ---------------------------------------------------------------

    def test_idp_attr_stores_institution_id(
        self, app, institution, url_auth_institution,
    ):
        """ext.set_idp_attr should include institution.id under key 'id'."""
        from osf.models import UserExtendedData

        username = 'user_idp_id@inst.edu'
        res = app.post(
            url_auth_institution,
            make_payload(institution, username),
        )
        assert res.status_code == 200
        user = OSFUser.objects.get(username=username)
        ext = UserExtendedData.objects.get(user=user)
        assert ext.data.get('idp_attr', {}).get('id') == institution.id

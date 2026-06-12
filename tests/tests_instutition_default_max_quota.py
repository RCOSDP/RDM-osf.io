# -*- coding: utf-8 -*-
from nose import tools as nt

from osf.models import InstitutionDefaultMaxQuota
from osf_tests.factories import AuthUserFactory, InstitutionFactory
from tests.base import OsfTestCase


class TestInstitutionDefaultMaxQuota(OsfTestCase):

    def test_get_quota_by_user_has_institution(self):
        user = AuthUserFactory()
        institution = InstitutionFactory()

        user.affiliated_institutions.add(institution)

        InstitutionDefaultMaxQuota.objects.create(
            institution=institution,
            default_max_quota=500
        )

        result = InstitutionDefaultMaxQuota.get_quota_by_user(user.id)

        nt.assert_equal(result, 500)

    def test_get_quota_by_user_no_institution(self):
        user = AuthUserFactory()

        result = InstitutionDefaultMaxQuota.get_quota_by_user(user.id)

        nt.assert_equal(result, None)

    def test_get_quota_by_user_multiple_institutions(self):
        user = AuthUserFactory()

        inst1 = InstitutionFactory()
        inst2 = InstitutionFactory()

        user.affiliated_institutions.add(inst1)
        user.affiliated_institutions.add(inst2)

        InstitutionDefaultMaxQuota.objects.create(
            institution=inst1,
            default_max_quota=100
        )

        InstitutionDefaultMaxQuota.objects.create(
            institution=inst2,
            default_max_quota=200
        )

        result = InstitutionDefaultMaxQuota.get_quota_by_user(user.id)

        nt.assert_true(result in [100, 200])

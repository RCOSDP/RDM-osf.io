# -*- coding: utf-8 -*-
import mock
from openpyxl import Workbook

from addons.base.tests.base import OAuthAddonTestCaseMixin, AddonTestCase
from addons.onedrivebusiness import utils
import pytest

from framework.auth import Auth
from osf_tests.factories import ProjectFactory, AuthUserFactory, InstitutionFactory, RegionFactory, UserQuotaFactory
from unittest import mock


@pytest.mark.django_db
class TestOneDriveBusinessAddonTestCase(OAuthAddonTestCaseMixin, AddonTestCase):

    def test_get_region_external_account(self):
        user = AuthUserFactory()
        node = ProjectFactory(creator=user)
        institution = InstitutionFactory()
        region = RegionFactory(_id=institution._id, name='Storage')
        user.affiliated_institutions.add(institution)

        with mock.patch('osf.models.rdm_addons.RdmAddonOption.objects.filter', return_value=user.affiliated_institutions):
            with mock.patch('addons.osfstorage.models.Region.objects.filter', return_value=user.affiliated_institutions):
                with mock.patch('osf.models.region_external_account.RegionExternalAccount.objects.get', return_value=region):
                    res = utils.get_region_external_account(node)
                    assert res.id == region.id
                    assert res.name == region.name

    def test_get_region_external_account_with_region_not_exists(self):
        user = AuthUserFactory()
        node = ProjectFactory(creator=user)
        institution = InstitutionFactory()
        region = RegionFactory(_id=institution._id, name='Storage')
        user.affiliated_institutions.add(institution)

        with mock.patch('addons.osfstorage.models.Region.objects.filter', return_value=user.affiliated_institutions):
            with mock.patch('osf.models.region_external_account.RegionExternalAccount.objects.get', return_value=region):
                res = utils.get_region_external_account(node)
                assert res is None

    def test_get_region_external_account_with_user_no_institution(self):
        user = AuthUserFactory()
        node = ProjectFactory(creator=user)
        res = utils.get_region_external_account(node)
        assert res is None

    def test_get_region_external_account_with_addon_option_none(self):
        user = AuthUserFactory()
        node = ProjectFactory(creator=user)
        institution = InstitutionFactory()
        region = RegionFactory(_id=institution._id, name='Storage')
        user.affiliated_institutions.add(institution)

        with mock.patch('osf.models.rdm_addons.RdmAddonOption.objects.filter', return_value=user.affiliated_institutions):
            with mock.patch('osf.models.region_external_account.RegionExternalAccount.objects.get', return_value=region):
                res = utils.get_region_external_account(node)
                assert res is None

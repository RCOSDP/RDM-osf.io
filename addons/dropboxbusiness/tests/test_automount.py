import unittest

from mock import patch, Mock
import pytest
from nose.tools import *  # noqa (PEP8 asserts)
from framework.auth.core import Auth
from addons.dropboxbusiness.apps import dropboxbusiness_root
from tests.base import OsfTestCase
from admin.rdm_addons.utils import get_rdm_addon_option

from osf_tests.factories import (
    fake_email,
    AuthUserFactory,
    InstitutionFactory,
    ExternalAccountFactory,
    UserFactory,
    ProjectFactory,
    RegionFactory
)
from addons.dropboxbusiness.models import NodeSettings
from admin_tests.rdm_addons import factories as rdm_addon_factories

pytestmark = pytest.mark.django_db

class DropboxBusinessAccountFactory(ExternalAccountFactory):
    provider = 'dropboxbusiness'

FILEACCESS_NAME = 'dropboxbusiness'
MANAGEMENT_NAME = 'dropboxbusiness_manage'
DBXBIZ = 'addons.dropboxbusiness'

class TestDropboxBusiness(unittest.TestCase):

    def setUp(self):

        super(TestDropboxBusiness, self).setUp()

        self.institution = InstitutionFactory()

        self.user = UserFactory()
        self.user.eppn = fake_email()
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

        self.f_option = get_rdm_addon_option(self.institution.id,
                                             FILEACCESS_NAME)
        self.m_option = get_rdm_addon_option(self.institution.id,
                                             MANAGEMENT_NAME)

        f_account = ExternalAccountFactory(provider=FILEACCESS_NAME)
        m_account = ExternalAccountFactory(provider=MANAGEMENT_NAME)

        self.f_option.external_accounts.add(f_account)
        self.m_option.external_accounts.add(m_account)

    def _new_project(self):
        with patch(DBXBIZ + '.utils.TeamInfo') as mock1, \
             patch(DBXBIZ + '.utils.get_current_admin_group_and_sync') as mock2, \
             patch(DBXBIZ + '.utils.get_current_admin_dbmid') as mock3, \
             patch(DBXBIZ + '.utils.create_team_folder') as mock4:
            mock2.return_value = (Mock(), Mock())
            mock3.return_value = 'dbmid:dummy'
            mock4.return_value = ('dbtid:dummy', 'g:dummy')
            self.project = ProjectFactory(creator=self.user)

    def _allowed(self):
        self.f_option.is_allowed = True
        self.f_option.save()

    def test_dropboxbusiness_default_is_not_allowed(self):
        assert_false(self.f_option.is_allowed)
        self._new_project()
        result = self.project.get_addon('dropboxbusiness')
        assert_equal(result, None)

    def test_dropboxbusiness_no_eppn(self):
        self.user.eppn = None
        self.user.save()
        self._allowed()
        self._new_project()
        result = self.project.get_addon('dropboxbusiness')
        assert_equal(result, None)

    def test_dropboxbusiness_no_institution(self):
        self.user.affiliated_institutions.clear()
        self._allowed()
        self._new_project()
        result = self.project.get_addon('dropboxbusiness')
        assert_equal(result, None)

    def test_dropboxbusiness_no_addon_option(self):
        self.f_option.delete()
        self._allowed()
        self._new_project()
        result = self.project.get_addon('dropboxbusiness')
        assert_equal(result, None)

    def test_dropboxbusiness_automount(self):
        self.f_option.is_allowed = True
        self.f_option.save()
        self._new_project()
        result = self.project.get_addon('dropboxbusiness')
        assert_true(isinstance(result, NodeSettings))
        assert_equal(result.admin_dbmid, 'dbmid:dummy')
        assert_equal(result.team_folder_id, 'dbtid:dummy')
        assert_equal(result.group_id, 'g:dummy')

class TestAppDropboxbussiness(OsfTestCase):
    def setUp(self):
        super(TestAppDropboxbussiness, self).setUp()
        self.user = AuthUserFactory()
        self.user.save()
        self.consolidated_auth = Auth(user=self.user)
        self.project = ProjectFactory(creator=self.user)
        self.auth = Auth(user=self.project.creator)
        self.project.add_addon('dropboxbusiness', auth=self.consolidated_auth)
        self.node_settings = self.project.get_addon('dropboxbusiness')
        self.ADDON_SHORT_NAME = 'dropboxbusiness'
        self.node_settings.save()

    @patch('admin.institutions.views.Region.objects')
    def test_dropboxbusiness_root(self, mock_region_objects_filter):
        institution = InstitutionFactory(_id=123456)
        region = RegionFactory()
        region._id = institution._id
        region.waterbutler_settings__storage__provider = self.ADDON_SHORT_NAME
        self.node_settings.fileaccess_option = get_rdm_addon_option(institution.id, FILEACCESS_NAME)
        region.save()
        mock_region_objects_filter.return_value = region
        mock_region_objects_filter.return_value.exists.return_value = True
        result = dropboxbusiness_root(addon_config='', node_settings=self.node_settings, auth=self.auth)
        assert isinstance(result, list)



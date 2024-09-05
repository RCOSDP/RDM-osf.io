import unittest

from mock import patch, Mock, MagicMock
import pytest
from nose.tools import (
    assert_true, assert_false,
    assert_equal,
)

from addons.osfstorage.models import Region, NodeSettings as osfNodeSettings
from admin.rdm_addons.utils import get_rdm_addon_option
from framework.auth.core import Auth
from osf.models.files import BaseFileNode
from osf_tests.factories import (
    fake_email,
    AuthUserFactory,
    InstitutionFactory,
    ExternalAccountFactory,
    UserFactory,
    ProjectFactory,
    RegionFactory
)
from addons.dropboxbusiness.apps import dropboxbusiness_root
from addons.dropboxbusiness.models import NodeSettings
from tests.base import OsfTestCase
from tests.test_websitefiles import TestFile

pytestmark = pytest.mark.django_db

class DropboxBusinessAccountFactory(ExternalAccountFactory):
    provider = 'dropboxbusiness'

SHORT_NAME = 'dropboxbusiness'
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
                                             FILEACCESS_NAME).first()
        self.m_option = get_rdm_addon_option(self.institution.id,
                                             MANAGEMENT_NAME).first()

        f_account = ExternalAccountFactory(provider=FILEACCESS_NAME)
        m_account = ExternalAccountFactory(provider=MANAGEMENT_NAME)

        self.f_option.external_accounts.add(f_account)
        self.m_option.external_accounts.add(m_account)

    def _new_project(self):
        with patch(DBXBIZ + '.utils.TeamInfo') as mock1, \
                patch(DBXBIZ + '.utils.get_current_admin_group_and_sync') as mock2, \
                patch(DBXBIZ + '.utils.get_current_admin_dbmid') as mock3, \
                patch(DBXBIZ + '.utils.create_team_folder') as mock4, \
                patch('admin.institutions.views.Region.objects.filter') as mock5, \
                patch('admin.institutions.views.Region.objects.get') as mock6, \
                patch('addons.osfstorage.models.NodeSettings.objects.filter') as mock7:
            team_info = Mock()
            team_info.group_name_to_id = {'dropboxbusiness': 'g:dummy'}
            mock1.return_value = team_info
            mock2.return_value = (Mock(), Mock())
            mock3.return_value = 'dbmid:dummy'
            mock4.return_value = ('dbtid:dummy', 'g:dummy')
            region = RegionFactory()
            region_filter = MagicMock()
            region_filter.order_by.return_value = [region]
            mock5.return_value = region_filter
            mock6.return_value = region
            node = osfNodeSettings()
            node.root_node = TestFile.get_or_create(ProjectFactory(), 'folder/path')
            node_filter = MagicMock()
            node_filter.first.return_value = node
            mock7.return_value = node_filter
            self.project = ProjectFactory(creator=self.user)
            self.osfstorage = self.project.get_addon('osfstorage')
            new_region = RegionFactory(
                _id=self.institution._id,
                name='Institutional Storage',
                waterbutler_settings={
                    'storage': {
                        'provider': SHORT_NAME,
                    },
                }
            )
            self.osfstorage.region = new_region
            self.osfstorage.save()
            self.project.save()

    def _allowed(self):
        self.f_option.is_allowed = True
        self.f_option.save()

    def test_dropboxbusiness_default_is_allowed(self):
        assert_true(self.f_option.is_allowed)
        self._new_project()
        result = self.project.get_addon('dropboxbusiness')
        assert_true(isinstance(result, NodeSettings))

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


class TestAppDropboxBusiness(OsfTestCase):
    def setUp(self):
        super(TestAppDropboxBusiness, self).setUp()
        self.ADDON_SHORT_NAME = 'dropboxbusiness'

        self.user = AuthUserFactory()
        self.auth = Auth(user=self.user)

        self.project = ProjectFactory(creator=self.user)
        self.project.add_addon('dropboxbusiness', auth=self.auth)

        self.node_settings = self.project.get_addon('dropboxbusiness')
        self.node_settings.save()

    def test_dropbox_business_root(self):
        institution = InstitutionFactory(_id=123456)
        region = Region()
        region._id = institution._id
        region.waterbutler_settings__storage__provider = self.ADDON_SHORT_NAME
        region.save()

        self.node_settings.fileaccess_option = get_rdm_addon_option(institution.id, FILEACCESS_NAME).first()
        self.node_settings.region = region
        self.node_settings.root_node = BaseFileNode()
        result = dropboxbusiness_root(addon_config='', node_settings=self.node_settings, auth=self.auth)

        assert isinstance(result, list)

from nose.tools import assert_is_not_none, assert_equal
import pytest
import unittest

from unittest import mock
from addons.base.tests.models import (OAuthAddonNodeSettingsTestSuiteMixin,
                                      OAuthAddonUserSettingTestSuiteMixin)

from addons.nextcloud.models import NodeSettings
from osf_tests.test_archiver import MockAddon
from addons.nextcloud.tests.factories import (
    NextcloudAccountFactory, NextcloudNodeSettingsFactory,
    NextcloudUserSettingsFactory, NextcloudFileFactory
)
from addons.nextcloud.settings import USE_SSL
from admin.rdm_addons.utils import get_rdm_addon_option
from osf_tests.factories import (
    ExternalAccountFactory,
    UserFactory, InstitutionFactory
)

pytestmark = pytest.mark.django_db

class TestUserSettings(OAuthAddonUserSettingTestSuiteMixin, unittest.TestCase):

    short_name = 'nextcloud'
    full_name = 'Nextcloud'
    UserSettingsFactory = NextcloudUserSettingsFactory
    ExternalAccountFactory = NextcloudAccountFactory


class TestNodeSettings(OAuthAddonNodeSettingsTestSuiteMixin, unittest.TestCase):

    short_name = 'nextcloud'
    full_name = 'Nextcloud'
    ExternalAccountFactory = NextcloudAccountFactory
    NodeSettingsFactory = NextcloudNodeSettingsFactory
    NodeSettingsClass = NodeSettings
    UserSettingsFactory = NextcloudUserSettingsFactory

    def _node_settings_class_kwargs(self, node, user_settings):
        return {
            'user_settings': self.user_settings,
            'folder_id': '/Documents',
            'owner': self.node
        }

    def test_serialize_credentials(self):
        credentials = self.node_settings.serialize_waterbutler_credentials()

        assert_is_not_none(self.node_settings.external_account.oauth_secret)
        expected = {
            'host': self.node_settings.external_account.oauth_secret,
            'password': 'meoword',
            'username': 'catname'
        }

        assert_equal(credentials, expected)

    def test_serialize_settings(self):
        settings = self.node_settings.serialize_waterbutler_settings()
        expected = {
            'folder': self.node_settings.folder_id,
            'verify_ssl': USE_SSL
        }
        assert_equal(settings, expected)


class TestNextcloudFile(unittest.TestCase):
    def setUp(self):
        super(TestNextcloudFile, self).setUp()

    def test_get_hash_for_timestamp_return_none(self):
        # UT code for the get_hash_for_timestamp method of the NextcloudFile class in case hash not contain sha512
        test_obj = NextcloudFileFactory()
        res = test_obj.get_hash_for_timestamp()
        # Assert result
        assert res == (None, None)

    def test_my_node_settings(self):
        # UT code for the _my_node_settings method of the NextcloudFile class
        # Define mock object for the rename_folder method of the IQBRIMSClient class
        mock_rename_folder = mock.MagicMock()
        mock_rename_folder.return_value = None

        # Define mock object for the get_folder_info method of the IQBRIMSClient class
        mock_get_folder_info = mock.MagicMock()
        mock_get_folder_info.return_value = {'title': 'test_title'}

        with mock.patch('addons.iqbrims.client.IQBRIMSClient.rename_folder', mock_rename_folder):
            with mock.patch('addons.iqbrims.client.IQBRIMSClient.get_folder_info', mock_get_folder_info):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon') as mock_get_addon:
                    test_obj = NextcloudFileFactory()
                    mock_addon = MockAddon()
                    mock_get_addon.return_value = mock_addon
                    res = test_obj._my_node_settings()
                    # Assert result
                    assert res != None

    def test_my_node_settings_return_none(self):
        # UT code for the _my_node_settings method in case project is None
        test_obj = NextcloudFileFactory()
        res = test_obj._my_node_settings()
        # Assert result
        assert res == None

    def test_get_timestamp(self):
        # UT code for the get_timestamp method of the NextcloudFile class
        # Define mock object for the get_timestamp function
        mock_utils = mock.MagicMock()
        mock_utils.return_value = 'abc'

        # Define mock object for the rename_folder method of the IQBRIMSClient class
        mock_rename_folder = mock.MagicMock()
        mock_rename_folder.return_value = None

        # Define mock object for the get_folder_info method of the IQBRIMSClient class
        mock_get_folder_info = mock.MagicMock()
        mock_get_folder_info.return_value = {'title': 'test_title'}

        with mock.patch('addons.iqbrims.client.IQBRIMSClient.rename_folder', mock_rename_folder):
            with mock.patch('addons.iqbrims.client.IQBRIMSClient.get_folder_info', mock_get_folder_info):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon') as mock_get_addon:
                    with mock.patch('addons.nextcloudinstitutions.utils.get_timestamp', mock_utils):
                        test_obj = NextcloudFileFactory()
                        mock_addon = MockAddon()
                        mock_get_addon.return_value = mock_addon
                        res = test_obj.get_timestamp()
                        # Assert result
                        assert res == 'abc'

    def test_get_timestamp_return_none(self):
        # UT code for the get_timestamp method in case get nodesettings return None
        test_obj = NextcloudFileFactory()
        res = test_obj.get_timestamp()
        # Assert result
        assert res == (None, None, None)

    def test_set_timestamp(self):
        # UT code for the set_timestamp method of the NextcloudFile class
        # Define mock object for the set_timestamp function
        mock_utils = mock.MagicMock()
        mock_utils.return_value = 'abc'

        # Define mock object for the rename_folder method of the IQBRIMSClient class
        mock_rename_folder = mock.MagicMock()
        mock_rename_folder.return_value = None

        # Define mock object for the get_folder_info method of the IQBRIMSClient class
        mock_get_folder_info = mock.MagicMock()
        mock_get_folder_info.return_value = {'title': 'test_title'}

        with mock.patch('addons.iqbrims.client.IQBRIMSClient.rename_folder', mock_rename_folder):
            with mock.patch('addons.iqbrims.client.IQBRIMSClient.get_folder_info', mock_get_folder_info):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon') as mock_get_addon:
                    with mock.patch('addons.nextcloudinstitutions.utils.set_timestamp', mock_utils):
                        test_obj = NextcloudFileFactory()
                        mock_addon = MockAddon()
                        mock_get_addon.return_value = mock_addon
                        test_obj.set_timestamp('timestamp_data', 'timestamp_status', 'context')

    def test_get_hash_for_timestamp(self):
        # UT code for the get_hash_for_timestamp method of the NextcloudFile class in case hash contain sha512
        # Define mock object for the _hashes property of the NextcloudFile class
        mock_hash = mock.MagicMock()
        mock_hash = {'sha512': 'data_sha512'}

        # Define mock object for the rename_folder method of the IQBRIMSClient class
        mock_rename_folder = mock.MagicMock()
        mock_rename_folder.return_value = None

        # Define mock object for the get_folder_info method of the IQBRIMSClient class
        mock_get_folder_info = mock.MagicMock()
        mock_get_folder_info.return_value = {'title': 'test_title'}

        with mock.patch('addons.iqbrims.client.IQBRIMSClient.rename_folder', mock_rename_folder):
            with mock.patch('addons.iqbrims.client.IQBRIMSClient.get_folder_info', mock_get_folder_info):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon') as mock_get_addon:
                    with mock.patch('addons.nextcloud.models.NextcloudFile._hashes', mock_hash):
                        test_obj = NextcloudFileFactory()
                        mock_addon = MockAddon()
                        mock_get_addon.return_value = mock_addon
                        res = test_obj.get_hash_for_timestamp()
                        # Assert result
                        assert res == ('sha512', 'data_sha512')

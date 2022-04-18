# -*- coding: utf-8 -*-

from base64 import decode
import jwt
import mock
import pytest
import unittest

from framework.auth import Auth

from nose.tools import (
    assert_equal,assert_true
)

from addons.base.tests.models import OAuthAddonNodeSettingsTestSuiteMixin

from addons.rushfiles.models import NodeSettings, RushFilesProvider, UserSettings
from addons.rushfiles.tests.factories import RushfilesAccountFactory,RushfilesNodeSettingFactory,RushfilesUserSettingFactory
from addons.rushfiles.client import RushFilesAuthClient, RushFilesClient

pytestmark = pytest.mark.django_db


class TestProvider(unittest.TestCase):
    def setUp(self):
        super(TestProvider, self).setUp()
        self.provider = RushFilesProvider()

    @mock.patch.object(RushFilesAuthClient, 'userinfo')
    def test_handle_callback(self, mock_client):
        fake_response = {'access_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJwcmltYXJ5X2RvbWFpbiI6ImZha2VAZmFrZS5uZXQifQ._CTx5dIZ0piHbqnF63NV-G6nuFs9uN-9q-pnR0X5HYE'}

        fake_info = {
            'User': {
                'UserId': 'fake@fake.net',
                'Email': 'kkitazawa@tsukaeru.net',
                'Name': 'fake fake'
            }
        }

        mock_client.return_value = fake_info

        res = self.provider.handle_callback(fake_response)

        assert_equal(res['provider_id'], 'fake@fake.net')
        assert_equal(res['display_name'], 'fake fake')
        assert_equal(res['profile_url'], None)

class TestNodeSettings(OAuthAddonNodeSettingsTestSuiteMixin,unittest.TestCase):
    short_name = 'rushfiles'
    full_name = 'Rushfiles'
    ExternalAccountFactory = RushfilesAccountFactory

    NodeSettingsFactory = RushfilesNodeSettingFactory
    NodeSettingsClass = NodeSettings
    UserSettingsFactory = RushfilesUserSettingFactory

    def _node_settings_class_kwargs(self, node, user_settings):
        return {
            'user_settings': self.user_settings,
            'share_id': 'fakemock',
            'share_name': 'fake_share',
            'domain': 'fake.com',
            'owner': self.node
        }

    # def setUp(self):
    #     super(TestNodeSettings, self).setUp()
    #     self.node_setting = NodeSettings()

    #     self.external_account = RushfilesAccountFactory()
    #     self.node_setting.external_account = self.external_account

    @mock.patch.object(RushFilesClient, 'shares')
    @mock.patch('addons.rushfiles.models.NodeSettings.fetch_access_token')
    def test_get_folder(self,mock_access_token, mock_share):
        fake_share_list = [
            {
                'Id': 'fakeId',
                'Name': 'fake share'
            }
        ]
        mock_share.return_value = fake_share_list
        mock_access_token.return_value = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJwcmltYXJ5X2RvbWFpbiI6ImZha2VAZmFrZS5uZXQifQ._CTx5dIZ0piHbqnF63NV-G6nuFs9uN-9q-pnR0X5HYE'

        res = self.node_settings.get_folders()
        assert_equal(res[0]['id'], fake_share_list[0]['Id'])
        assert_equal(res[0]['name'], fake_share_list[0]['Name'])
        assert_equal(res[0]['path'], fake_share_list[0]['Name'])

    def test_set_folder(self):
        folderId = 'fakeFolderId'
        domain = 'fake.net'
        folder = {
            'id': folderId + '@' + domain,
            'name': 'fake-folder-name',
            'path': 'fake-folder-name'
        }
        self.node_settings.set_folder(folder, auth=Auth(self.user))
        self.node_settings.save()

        assert_equal(self.node_settings.folder_id, folderId)
        assert_equal(self.node_settings.domain, domain)

        assert_equal(self.node_settings.folder_name, folder['name'])
        assert_equal(self.node_settings.folder_path, folder['path'])

    def test_serialize_settings(self):
        settings = self.node_settings.serialize_waterbutler_settings()
        expected = {
            'share':
            {
                'id': self.node_settings.folder_id,
                'name': self.node_settings.folder_name,
                'domain': self.node_settings.domain,
            }
        }

        assert_equal(expected, settings)

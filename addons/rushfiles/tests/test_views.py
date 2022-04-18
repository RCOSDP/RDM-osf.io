# -*- coding: utf-8 -*-
import mock

from addons.base.tests.views import (
    OAuthAddonAuthViewsTestCaseMixin, OAuthAddonConfigViewsTestCaseMixin
)
from tests.base import OsfTestCase
from addons.rushfiles.tests.utils import RushfilesAddonTestCase
from addons.rushfiles.client import RushFilesClient
from addons.rushfiles.serializer import RushFilesSerializer
from nose.tools import assert_equal
assert_equal.__self__.maxDiff = None

class TestRushfilesAuthView(RushfilesAddonTestCase, OAuthAddonAuthViewsTestCaseMixin, OsfTestCase):
    def setUp(self):
        super(TestRushfilesAuthView, self).setUp()

class TestRushfilesConfigViews(RushfilesAddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
    folder = {
        'path': 'fake_share',
        'id': 'abcdef@fake.net',
        'name':'fake_share'
    }
    Serializer = RushFilesSerializer
    client = RushFilesClient

    def setUp(self):
        super(TestRushfilesConfigViews, self).setUp()

    @mock.patch('addons.rushfiles.models.NodeSettings.fetch_access_token')
    def test_get_config(self, mock_access_token):
        mock_access_token.return_value = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJwcmltYXJ5X2RvbWFpbiI6ImZha2VAZmFrZS5uZXQifQ._CTx5dIZ0piHbqnF63NV-G6nuFs9uN-9q-pnR0X5HYE'
        super(TestRushfilesConfigViews, self).test_get_config()



    @mock.patch.object(RushFilesClient, 'shares')
    @mock.patch('addons.rushfiles.models.NodeSettings.fetch_access_token')
    def test_folder_list(self,mock_access_token, mock_share):
        fake_share_list = [
            {
                'Id': 'fakeId',
                'Name': 'fake share'
            }
        ]
        mock_share.return_value = fake_share_list
        mock_access_token.return_value = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJwcmltYXJ5X2RvbWFpbiI6ImZha2VAZmFrZS5uZXQifQ._CTx5dIZ0piHbqnF63NV-G6nuFs9uN-9q-pnR0X5HYE'

        super(TestRushfilesConfigViews, self).test_folder_list()

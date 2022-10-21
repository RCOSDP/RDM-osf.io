# -*- coding: utf-8 -*-
import pytest
import mock

from tests.base import OsfTestCase

from addons.rushfiles.serializer import RushFilesSerializer

from addons.base.tests.serializers import StorageAddonSerializerTestSuiteMixin
from addons.rushfiles.tests.factories import RushfilesAccountFactory
from addons.rushfiles.client import RushFilesClient


pytestmark = pytest.mark.django_db

class TestRushfilesSerializer(StorageAddonSerializerTestSuiteMixin, OsfTestCase):
    addon_short_name = 'rushfiles'

    ExternalAccountFactory = RushfilesAccountFactory
    Serializer = RushFilesSerializer
    client = RushFilesClient()

    def set_provider_id(self, pid):
        self.node_settings.share_id = pid

    @mock.patch('addons.rushfiles.models.NodeSettings.fetch_access_token')
    def test_serialize_settings_authorized_folder_is_set(self, mock_access_token):
        mock_access_token.return_value = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJwcmltYXJ5X2RvbWFpbiI6ImZha2VAZmFrZS5uZXQifQ._CTx5dIZ0piHbqnF63NV-G6nuFs9uN-9q-pnR0X5HYE'
        super(TestRushfilesSerializer, self).test_serialize_settings_authorized_folder_is_set()

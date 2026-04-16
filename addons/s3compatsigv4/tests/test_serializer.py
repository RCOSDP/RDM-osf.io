# -*- coding: utf-8 -*-
"""Serializer tests for the S3 Compatible Storage (SigV4) addon."""
import mock
import pytest

from addons.base.tests.serializers import StorageAddonSerializerTestSuiteMixin
from addons.s3compatsigv4.tests.factories import S3CompatSigV4AccountFactory
from addons.s3compatsigv4.serializer import S3CompatSigV4Serializer

from tests.base import OsfTestCase

pytestmark = pytest.mark.django_db

class Tests3compatsigv4Serializer(StorageAddonSerializerTestSuiteMixin, OsfTestCase):
    addon_short_name = 's3compatsigv4'
    Serializer = S3CompatSigV4Serializer
    ExternalAccountFactory = S3CompatSigV4AccountFactory
    client = None

    def set_provider_id(self, pid):
        self.node_settings.folder_id = pid

    def setUp(self):
        self.mock_can_list = mock.patch('addons.s3compatsigv4.serializer.utils.can_list')
        self.mock_can_list.return_value = True
        self.mock_can_list.start()
        super(Tests3compatsigv4Serializer, self).setUp()

    def tearDown(self):
        self.mock_can_list.stop()
        super(Tests3compatsigv4Serializer, self).tearDown()

# -*- coding: utf-8 -*-
"""Serializer tests for the My MinIO addon."""
import mock
import pytest

from addons.base.tests.serializers import StorageAddonSerializerTestSuiteMixin
from addons.webexmeetings.tests.factories import WebexMeetingsAccountFactory
from addons.webexmeetings.serializer import WebexMeetingsSerializer

from tests.base import OsfTestCase

pytestmark = pytest.mark.django_db

class TestWebexMeetingsSerializer(StorageAddonSerializerTestSuiteMixin, OsfTestCase):
    addon_short_name = 'webexmeetings'
    Serializer = WebexMeetingsSerializer
    ExternalAccountFactory = WebexMeetingsAccountFactory

    def set_provider_id(self, pid):
        self.node_settings.folder_id = pid

    def setUp(self):
        super(TestWebexMeetingsSerializer, self).setUp()

    def tearDown(self):
        super(TestWebexMeetingsSerializer, self).tearDown()

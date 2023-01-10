# -*- coding: utf-8 -*-
"""Serializer tests for the My MinIO addon."""
import mock
import pytest

from addons.base.tests.serializers import StorageAddonSerializerTestSuiteMixin
from addons.zoommeetings.tests.factories import ZoomMeetingsAccountFactory
from addons.zoommeetings.serializer import ZoomMeetingsSerializer

from tests.base import OsfTestCase

pytestmark = pytest.mark.django_db

class TestZoomMeetingsSerializer(StorageAddonSerializerTestSuiteMixin, OsfTestCase):
    addon_short_name = 'zoommeetings'
    Serializer = ZoomMeetingsSerializer
    ExternalAccountFactory = ZoomMeetingsAccountFactory

    def set_provider_id(self, pid):
        self.node_settings.folder_id = pid

    def setUp(self):
        super(TestZoomMeetingsSerializer, self).setUp()

    def tearDown(self):
        super(TestZoomMeetingsSerializer, self).tearDown()

# -*- coding: utf-8 -*-
"""Serializer tests for the My MinIO addon."""
import mock
import pytest

from addons.base.tests.serializers import StorageAddonSerializerTestSuiteMixin
from addons.microsoftteams.tests.factories import MicrosoftTeamsAccountFactory
from addons.microsoftteams.serializer import MicrosoftTeamsSerializer

from tests.base import OsfTestCase

pytestmark = pytest.mark.django_db

class TestMicrosoftTeamsSerializer(StorageAddonSerializerTestSuiteMixin, OsfTestCase):
    addon_short_name = 'microsoftteams'
    Serializer = MicrosoftTeamsSerializer
    ExternalAccountFactory = MicrosoftTeamsAccountFactory

    def set_provider_id(self, pid):
        self.node_settings.folder_id = pid

    def setUp(self):
        super(TestMicrosoftTeamsSerializer, self).setUp()

    def tearDown(self):
        super(TestMicrosoftTeamsSerializer, self).tearDown()

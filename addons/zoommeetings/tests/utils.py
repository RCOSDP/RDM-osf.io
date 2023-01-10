# -*- coding: utf-8 -*-
import json
from addons.base.tests.base import OAuthAddonTestCaseMixin, AddonTestCase
from addons.zoommeetings.tests.factories import ZoomMeetingsAccountFactory
from addons.zoommeetings.provider import ZoomMeetingsProvider
from addons.zoommeetings.serializer import ZoomMeetingsSerializer

class ZoomMeetingsAddonTestCase(OAuthAddonTestCaseMixin, AddonTestCase):

    ADDON_SHORT_NAME = 'zoommeetings'
    ExternalAccountFactory = ZoomMeetingsAccountFactory
    Provider = ZoomMeetingsProvider
    Serializer = ZoomMeetingsSerializer
    client = None
    folder = {
        'path': 'bucket',
        'name': 'bucket',
        'id': 'bucket'
    }

class MockResponse:
    def __init__(self, content, status_code):
        self.content = content
        self.status_code = status_code

    def json(self):
        return json.loads(self.content)

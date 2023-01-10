# -*- coding: utf-8 -*-
import json
from addons.base.tests.base import OAuthAddonTestCaseMixin, AddonTestCase
from addons.webexmeetings.tests.factories import WebexMeetingsAccountFactory
from addons.webexmeetings.provider import WebexMeetingsProvider
from addons.webexmeetings.serializer import WebexMeetingsSerializer

class WebexMeetingsAddonTestCase(OAuthAddonTestCaseMixin, AddonTestCase):

    ADDON_SHORT_NAME = 'webexmeetings'
    ExternalAccountFactory = WebexMeetingsAccountFactory
    Provider = WebexMeetingsProvider
    Serializer = WebexMeetingsSerializer
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

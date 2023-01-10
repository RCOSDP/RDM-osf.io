# -*- coding: utf-8 -*-
import json
from addons.base.tests.base import OAuthAddonTestCaseMixin, AddonTestCase
from addons.microsoftteams.tests.factories import MicrosoftTeamsAccountFactory
from addons.microsoftteams.provider import MicrosoftTeamsProvider
from addons.microsoftteams.serializer import MicrosoftTeamsSerializer

class MicrosoftTeamsAddonTestCase(OAuthAddonTestCaseMixin, AddonTestCase):

    ADDON_SHORT_NAME = 'microsoftteams'
    ExternalAccountFactory = MicrosoftTeamsAccountFactory
    Provider = MicrosoftTeamsProvider
    Serializer = MicrosoftTeamsSerializer
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

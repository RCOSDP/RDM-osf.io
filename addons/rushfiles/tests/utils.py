from addons.base.tests.base import OAuthAddonTestCaseMixin, AddonTestCase
from addons.rushfiles.tests.factories import RushfilesAccountFactory
from addons.rushfiles.models import RushFilesProvider

class RushfilesAddonTestCase(OAuthAddonTestCaseMixin, AddonTestCase):
    ADDON_SHORT_NAME = 'rushfiles'
    ExternalAccountFactory = RushfilesAccountFactory
    Provider = RushFilesProvider

    def set_node_settings(self, settings):
        super(RushfilesAddonTestCase, self).set_node_settings(settings)
        settings.share_id = '1234567890'
        settings.share_name = 'test_rushfiles'
from addons.base.tests.base import AddonTestCase
from addons.datasteward.models import DataStewardProvider

class DataStewardAddonTestCase(AddonTestCase):
    ADDON_SHORT_NAME = 'datasteward'
    Provider = DataStewardProvider
    OWNERS = ['user']

    def set_node_settings(self, settings):
        pass

    def set_user_settings(self, settings):
        pass

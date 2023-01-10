import os
from addons.base.apps import BaseAddonAppConfig
from addons.webexmeetings import SHORT_NAME, FULL_NAME

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(
    HERE,
    'templates'
)

class WebexMeetingsAddonConfig(BaseAddonAppConfig):

    name = 'addons.{}'.format(SHORT_NAME)
    label = 'addons_{}'.format(SHORT_NAME)
    short_name = SHORT_NAME
    full_name = FULL_NAME
    views = ['widget']
    categories = ['other']
    owners = ['user', 'node']
    configs = ['accounts', 'node']
    has_page_icon = False

    node_settings_template = os.path.join(TEMPLATE_PATH, 'webexmeetings_node_settings.mako')
    user_settings_template = os.path.join(TEMPLATE_PATH, 'webexmeetings_user_settings.mako')

    # default value for RdmAddonOption.is_allowed for GRDM Admin
    is_allowed_default = False

    @property
    def routes(self):
        from . import routes
        return [routes.api_routes]

    @property
    def user_settings(self):
        return self.get_model('UserSettings')

    @property
    def node_settings(self):
        return self.get_model('NodeSettings')

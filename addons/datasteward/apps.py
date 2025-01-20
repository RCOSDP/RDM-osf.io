import os

from addons.base.apps import BaseAddonAppConfig

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(
    HERE,
    'templates'
)


class DataStewardAddonAppConfig(BaseAddonAppConfig):
    name = 'addons.datasteward'
    label = 'addons_datasteward'
    full_name = 'DataSteward'
    short_name = 'datasteward'
    owners = ['user']
    configs = ['accounts']
    user_settings_template = os.path.join(TEMPLATE_PATH, 'datasteward_user_settings.mako')

    @property
    def routes(self):
        from .routes import api_routes
        return [api_routes]

    @property
    def user_settings(self):
        return self.get_model('UserSettings')

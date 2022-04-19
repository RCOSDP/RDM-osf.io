import os
from addons.base.apps import BaseAddonAppConfig, generic_root_folder

rushfiles_root_folder = generic_root_folder('rushfiles')

HERE = os.path.dirname(os.path.abspath(__file__))

class RushFilesAddonConfig(BaseAddonAppConfig):

    name = 'addons.rushfiles'
    label = 'addons_rushfiles'
    full_name = 'FileBako'
    short_name = 'rushfiles'
    owners = ['user', 'node']
    configs = ['accounts', 'node']
    categories = ['storage']
    has_hgrid_files = True

    @property
    def get_hgrid_data(self):
        return rushfiles_root_folder

    SHARE_SELECTED = 'rushfiles_folder_selected'
    NODE_AUTHORIZED = 'rushfiles_node_authorized'
    NODE_DEAUTHORIZED = 'rushfiles_node_deauthorized'

    actions = (SHARE_SELECTED, NODE_AUTHORIZED, NODE_DEAUTHORIZED, )

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

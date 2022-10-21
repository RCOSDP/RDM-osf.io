from oauthlib.oauth2 import InvalidGrantError
from addons.base.serializer import StorageAddonSerializer
from website.util import api_url_for

class RushFilesSerializer(StorageAddonSerializer):

    addon_short_name = 'rushfiles'

    def credentials_are_valid(self, user_settings, client):
        try:
            self.node_settings.fetch_access_token()
        except (InvalidGrantError, AttributeError):
            return False
        return True

    def serialized_folder(self, node_settings):
        return {
            'name': node_settings.folder_name,
            'path': node_settings.folder_path
        }

    @property
    def addon_serialized_urls(self):
        node = self.node_settings.owner
        return {
            'auth': api_url_for('oauth_connect', service_name='rushfiles'),
            'files': node.web_url_for('collect_file_trees'),
            'config': node.api_url_for('rushfiles_set_config'),
            'deauthorize': node.api_url_for('rushfiles_deauthorize_node'),
            'importAuth': node.api_url_for('rushfiles_import_auth'),
            'folders': node.api_url_for('rushfiles_folder_list'),
            'accounts': node.api_url_for('rushfiles_account_list'),
        }

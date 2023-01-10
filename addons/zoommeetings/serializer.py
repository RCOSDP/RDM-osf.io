from addons.base.serializer import StorageAddonSerializer
from addons.zoommeetings import SHORT_NAME
from website.util import web_url_for

class ZoomMeetingsSerializer(StorageAddonSerializer):
    addon_short_name = SHORT_NAME

    REQUIRED_URLS = []

    @property
    def addon_serialized_urls(self):
        node = self.node_settings.owner
        user_settings = self.node_settings.user_settings or self.user_settings

        result = {
            'auth': node.api_url_for('{}_oauth_connect'.format(SHORT_NAME)),
            'accounts': node.api_url_for('{}_account_list'.format(SHORT_NAME)),
            'importAuth': node.api_url_for('{}_import_auth'.format(SHORT_NAME)),
            'deauthorize': node.api_url_for('{}_deauthorize_node'.format(SHORT_NAME)),
        }
        if user_settings:
            result['owner'] = web_url_for('profile_view_id',
                                          uid=user_settings.owner._id)

        return result

    def serialized_folder(self, node_settings):
        return {
            'path': node_settings.folder_id,
            'name': node_settings.folder_name
        }

    def credentials_are_valid(self, user_settings, client=None):
        if user_settings:
            return True

        return False

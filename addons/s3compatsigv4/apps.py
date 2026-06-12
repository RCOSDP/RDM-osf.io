import os
from addons.base.apps import BaseAddonAppConfig, generic_root_folder
from addons.s3compatsigv4.settings import MAX_UPLOAD_SIZE

s3compatsigv4_root_folder = generic_root_folder('s3compatsigv4')

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(
    HERE,
    'templates'
)

class S3CompatSigV4AddonAppConfig(BaseAddonAppConfig):

    name = 'addons.s3compatsigv4'
    label = 'addons_s3compatsigv4'
    owners = ['user', 'node']
    configs = ['accounts', 'node']
    categories = ['storage']
    has_hgrid_files = True
    max_file_size = MAX_UPLOAD_SIZE
    node_settings_template = os.path.join(TEMPLATE_PATH, 's3compatsigv4_node_settings.mako')
    user_settings_template = os.path.join(TEMPLATE_PATH, 's3compatsigv4_user_settings.mako')

    @property
    def full_name(self):
        return 'S3 Compatible Storage (SigV4)'

    @property
    def short_name(self):
        return 's3compatsigv4'

    @property
    def get_hgrid_data(self):
        return s3compatsigv4_root_folder

    BUCKET_LINKED = 's3compatsigv4_bucket_linked'
    BUCKET_UNLINKED = 's3compatsigv4_bucket_unlinked'
    FILE_ADDED = 's3compatsigv4_file_added'
    FILE_REMOVED = 's3compatsigv4_file_removed'
    FILE_UPDATED = 's3compatsigv4_file_updated'
    FOLDER_CREATED = 's3compatsigv4_folder_created'
    NODE_AUTHORIZED = 's3compatsigv4_node_authorized'
    NODE_DEAUTHORIZED = 's3compatsigv4_node_deauthorized'
    NODE_DEAUTHORIZED_NO_USER = 's3compatsigv4_node_deauthorized_no_user'

    actions = (BUCKET_LINKED,
        BUCKET_UNLINKED,
        FILE_ADDED,
        FILE_REMOVED,
        FILE_UPDATED,
        FOLDER_CREATED,
        NODE_AUTHORIZED,
        NODE_DEAUTHORIZED,
        NODE_DEAUTHORIZED_NO_USER)

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

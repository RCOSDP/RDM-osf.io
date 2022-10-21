# -*- coding: utf-8 -*-
from flask import request

from website.project.decorators import must_have_addon, must_be_addon_authorizer

from addons.base import generic_views
from addons.rushfiles.serializer import RushFilesSerializer

SHORT_NAME = 'rushfiles'
FULL_NAME = 'Tsukaeru FileBako'

rushfiles_account_list = generic_views.account_list(
    SHORT_NAME,
    RushFilesSerializer
)

rushfiles_get_config = generic_views.get_config(
    SHORT_NAME,
    RushFilesSerializer
)

def _set_folder(node_addon, folder, auth):
    node_addon.set_folder(folder, auth=auth)
    node_addon.save()

rushfiles_set_config = generic_views.set_config(
    SHORT_NAME,
    FULL_NAME,
    RushFilesSerializer,
    _set_folder
)

rushfiles_import_auth = generic_views.import_auth(
    SHORT_NAME,
    RushFilesSerializer
)

rushfiles_deauthorize_node = generic_views.deauthorize_node(
    SHORT_NAME
)

#TODO Consider switching to select (like in GitLab)
@must_have_addon(SHORT_NAME, 'node')
@must_be_addon_authorizer(SHORT_NAME)
def rushfiles_folder_list(node_addon, **kwargs):
    """ Returns all the subsequent folders under the folder id passed.
        Not easily generalizable due to `path` kwarg.
    """
    path = request.args.get('path', '')
    folder_id = request.args.get('folder_id', 'root')

    return node_addon.get_folders(folder_path=path, folder_id=folder_id)

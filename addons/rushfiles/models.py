# -*- coding: utf-8 -*-
"""Persistence layer for the google drive addon.
"""
from addons.base.models import (BaseOAuthNodeSettings, BaseOAuthUserSettings,
                                BaseStorageAddon)
from django.db import models

from framework.exceptions import HTTPError
from osf.models.external import ExternalProvider
from osf.models.files import File, Folder, BaseFileNode
from addons.base import exceptions
from addons.rushfiles import settings
from addons.rushfiles.serializer import RushFilesSerializer

import jwt

class RushFilesFileNode(BaseFileNode):
    _provider = 'rushfiles'


class RushFilesFolder(RushFilesFileNode, Folder):
    pass


class RushFilesFile(RushFilesFileNode, File):
    pass


class RushFilesProvider(ExternalProvider):
    name = 'RushFiles'
    short_name = 'rushfiles'

    client_id = settings.CLIENT_ID
    client_secret = settings.CLIENT_SECRET


    auth_url_base = '{}{}'.format(settings.OAUTH_BASE_URL, 'authorize')
    callback_url = '{}{}'.format(settings.OAUTH_BASE_URL, 'token')
    auto_refresh_url = callback_url
    refresh_time = 180
    expiry_time = 0

    default_scopes = settings.OAUTH_SCOPE

    def handle_callback(self, response):
        # Should we better verify?
        payload = jwt.decode(response['access_token'], verify=False)
        #TODO: get user name from RushFiles
        return {
            'provider_id': payload['sub'],
            'display_name': 'Wiktor Klonowski',
            'profile_url': None
        }

    def fetch_access_token(self, force_refresh=False):
        self.refresh_oauth_key(force=force_refresh)
        return self.account.oauth_key


class UserSettings(BaseOAuthUserSettings):
    oauth_provider = RushFilesProvider
    serializer = RushFilesSerializer


class NodeSettings(BaseOAuthNodeSettings, BaseStorageAddon):
    oauth_provider = RushFilesProvider
    serializer = RushFilesSerializer

    share_id = models.TextField(null=True, blank=True)
    share_name = models.TextField(null=True, blank=True)
    domain = models.TextField(null=True, blank=True)
    user_settings = models.ForeignKey(UserSettings, null=True, blank=True, on_delete=models.CASCADE)

    _provider = None

    @property
    def provider(self):
        """Authenticated ExternalProvider instance"""
        if self._provider is None:
            self._provider = RushFilesProvider(self.external_account)
        return self._provider

    @property
    def folder_id(self):
        return self.share_id or None

    @property
    def folder_name(self):
        return self.share_name or None

    @property
    def folder_path(self):
        return self.share_name or None

    def fetch_access_token(self):
        return self.provider.fetch_access_token()

    def get_folders(self, **kwargs):
        node = self.owner

        try:
            access_token = self.fetch_access_token()
        except exceptions.InvalidAuthError:
            raise HTTPError(403)

        #TODO Return the list of shares available to the authenticated user
        # https://clientgateway.rushfiles.com/swagger/ui/index#!/User/User_GetUserShares
        # Get main user domain from access token (JWT)

        return [{
            'addon': self.config.short_name,
            'path': '開発',
            'kind': 'folder',
            'id': 'd0c475011bd24b6dae8a6f890f6b4a93',
            'name': '開発',
            'urls': {}
        }]

    def set_folder(self, folder, auth):
        """Configure this addon to point to a Google Drive folder

        :param dict folder:
        :param User user:
        """
        self.share_id = folder['id']
        self.share_name = folder['name']

        # Tell the user's addon settings that this node is connecting
        self.user_settings.grant_oauth_access(
            node=self.owner,
            external_account=self.external_account,
            metadata={'folder': self.share_id}
        )  # Performs a save on self.user_settings
        self.save()

        self.nodelogger.log('folder_selected', save=True)
    
    # Match with RDM-waterbutler/waterbutler/providers/rushfiles/provider.py:RushFilesProvider::__init__
    def serialize_waterbutler_credentials(self):
        if not self.has_auth:
            raise exceptions.AddonError('Addon is not authorized')
        return {'token': self.fetch_access_token()}

    # Match with RDM-waterbutler/waterbutler/providers/rushfiles/provider.py:RushFilesProvider::__init__
    def serialize_waterbutler_settings(self):
        if not self.folder_id:
            raise exceptions.AddonError('Folder is not configured')

        return {
            'share': {
                'id': self.folder_id,
                'name': self.folder_name,
            }
        }
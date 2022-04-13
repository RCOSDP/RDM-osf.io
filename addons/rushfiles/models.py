# -*- coding: utf-8 -*-
"""Persistence layer for the google drive addon.
"""
import sys
from addons.base.models import (BaseOAuthNodeSettings, BaseOAuthUserSettings,
                                BaseStorageAddon)
from django.db import models

from framework.auth import Auth

from framework.exceptions import HTTPError
from osf.models.external import ExternalProvider
from osf.models.files import File, Folder, BaseFileNode
from addons.base import exceptions
from addons.rushfiles import settings
from addons.rushfiles.serializer import RushFilesSerializer
from addons.rushfiles.utils import get_os
from addons.rushfiles.client import RushFilesClient, RushFilesAuthClient

import socket
import jwt

class RushFilesFileNode(BaseFileNode):
    _provider = 'rushfiles'


class RushFilesFolder(RushFilesFileNode, Folder):
    pass


class RushFilesFile(RushFilesFileNode, File):
    pass


class RushFilesProvider(ExternalProvider):
    name = 'FileBako'
    short_name = 'filebako'

    client_id = settings.CLIENT_ID
    client_secret = settings.CLIENT_SECRET

    auth_url_base = '{}authorize?acr_values=deviceName:OSF@{} deviceOs:{} deviceType:9'.format(settings.OAUTH_BASE_URL, socket.gethostname(), get_os())
    callback_url = '{}{}'.format(settings.OAUTH_BASE_URL, 'token')
    auto_refresh_url = callback_url
    refresh_time = settings.REFRESH_TIME
    expiry_time = settings.EXPIRY_TIME

    default_scopes = settings.OAUTH_SCOPE

    _auth_client = RushFilesAuthClient()

    def handle_callback(self, response):
        payload = jwt.decode(response['access_token'], verify=False)
        client = self._auth_client
        info = client.userinfo(response['access_token'], payload['primary_domain'])

        return {
            'provider_id': info['User']['UserId'],
            'display_name': info['User']['Name'],
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

    def clear_settings(self):
        self.share_id = None
        self.share_name = None
        self.domain = None

    def get_folders(self, **kwargs):
        node = self.owner

        try:
            access_token = self.fetch_access_token()
        except exceptions.InvalidAuthError:
            raise HTTPError(403)

        #TODO Return the list of shares available to the authenticated user
        # https://clientgateway.rushfiles.com/swagger/ui/index#!/User/User_GetUserShares
        # Get main user domain from access token (JWT)

        # I think handling only one level (shares) is enough. Permissions are configurable
        # on per-share basis and user can create sub-shares if they want different folder structure.
        # Question: How should we handle read-only shares?

        payload = jwt.decode(access_token, verify=False)

        client = RushFilesClient(access_token=access_token)

        share_list = client.shares(self.external_account.provider_id)

        return [{
            'addon': self.config.short_name,
            'path': share['Name'],
            'kind': 'folder',
            'id': share['Id'],
            'name': share['Name'],
            'urls': {
                'folders':''
            }
        } for share in share_list ]

    def set_folder(self, folder, auth):
        """
        """
        share_id, domain = folder['id'].split("@")
        self.share_id = share_id
        self.share_name = folder['name']
        self.domain = domain

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
                'domain': self.domain
            }
        }

    def create_waterbutler_log(self, auth, action, metadata):
        url = self.owner.web_url_for('addon_view_or_download_file', path=metadata['path'], provider='rushfiles')

        self.owner.add_log(
            'rushfiles_{0}'.format(action),
            auth=auth,
            params={
                'project': self.owner.parent_id,
                'node': self.owner._id,
                'path': metadata['materialized'],
                'bucket': self.folder_id,
                'urls': {
                    'view': url,
                    'download': url + '?action=download'
                }
            },
        )


    def deauthorize(self, auth=None, add_log=True, save=False):
        if add_log:
            extra = {'folder_id': self.folder_id}
            self.nodelogger.log(action='node_deauthorized', extra=extra, save=True)

        self.clear_settings()
        self.clear_auth()

        if save:
            self.save()

    def after_delete(self, user):
        self.deauthorize(Auth(user=user), add_log=True, save=True)

    def on_delete(self):
        self.deauthorize(add_log=False)
        self.save()

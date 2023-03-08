# -*- coding: utf-8 -*-
from datetime import timedelta
import logging
from addons.base import exceptions
from addons.base.models import (BaseOAuthNodeSettings, BaseOAuthUserSettings,
                                BaseStorageAddon)
from django.db import models
from django.utils import timezone

from framework.auth.decorators import Auth

from osf.models.base import BaseModel
from osf.models.files import File, Folder, BaseFileNode
from osf.models.metaschema import RegistrationSchema
from osf.utils.fields import NonNaiveDateTimeField

from .serializer import WEKOSerializer
from .provider import WEKOProvider
from .client import Client
from .apps import SHORT_NAME
from . import settings


logger = logging.getLogger(__name__)


class WEKOFileNode(BaseFileNode):
    _provider = 'weko'


class WEKOFolder(WEKOFileNode, Folder):
    pass


class WEKOFile(WEKOFileNode, File):
    version_identifier = 'version'

class UserSettings(BaseOAuthUserSettings):
    oauth_provider = WEKOProvider
    serializer = WEKOSerializer


class NodeSettings(BaseOAuthNodeSettings, BaseStorageAddon):
    oauth_provider = WEKOProvider
    serializer = WEKOSerializer

    index_title = models.TextField(blank=True, null=True)
    index_id = models.TextField(blank=True, null=True)
    user_settings = models.ForeignKey(UserSettings, null=True, blank=True, on_delete=models.CASCADE)

    _api = None

    @property
    def api(self):
        """authenticated ExternalProvider instance"""
        if self._api is None:
            self._api = WEKOProvider(self.external_account)
        return self._api

    @property
    def folder_name(self):
        return self.index_title

    @property
    def complete(self):
        return bool(self.has_auth and self.index_id is not None)

    @property
    def folder_id(self):
        return self.index_id

    @property
    def folder_path(self):
        pass

    @property
    def has_metadata(self):
        return self.complete

    def fetch_access_token(self):
        return self.api.fetch_access_token()

    def create_client(self):
        if not self.external_account:
            return None
        provider = WEKOProvider(self.external_account)

        if provider.repoid is None:
            # Basic authentication - for compatibility
            return Client(provider.sword_url, username=provider.userid,
                          password=provider.password)
        token = provider.fetch_access_token()
        return Client(provider.sword_url, token=token)

    def set_folder(self, index, auth=None):
        self.index_id = index.identifier
        self.index_title = index.title

        self.save()

        if auth:
            self.owner.add_log(
                action='weko_index_linked',
                params={
                    'project': self.owner.parent_id,
                    'node': self.owner._id,
                    'dataset': index.title,
                },
                auth=auth,
            )

    def set_publish_task_id(self, path, task_id):
        q = self.publish_task.filter(path=path).order_by('-updated')
        if not q.exists():
            PublishTask.objects.create(
                project=self,
                path=path,
                updated=timezone.now(),
                last_task_id=task_id
            )
            return
        m = q.first()
        m.updated = timezone.now()
        m.last_task_id = task_id
        m.save()

    def get_publish_task_id(self, path):
        q = self.publish_task.filter(path=path).order_by('-updated')
        if not q.exists():
            return None
        m = q.first()
        if timezone.now() - m.updated > timedelta(days=1):
            return None
        return {
            'task_id': m.last_task_id,
            'updated': m.updated.timestamp(),
        }

    def clear_settings(self):
        """Clear selected index"""
        self.index_id = None
        self.index_title = None

    def deauthorize(self, auth=None, add_log=True):
        """Remove user authorization from this node and log the event."""
        self.clear_settings()
        self.clear_auth()  # Also performs a save

        # Log can't be added without auth
        if add_log and auth:
            node = self.owner
            self.owner.add_log(
                action='weko_node_deauthorized',
                params={
                    'project': node.parent_id,
                    'node': node._id,
                },
                auth=auth,
            )

    def serialize_waterbutler_credentials(self):
        if not self.has_auth:
            raise exceptions.AddonError('Addon is not authorized')
        provider = WEKOProvider(self.external_account)
        default_provider = self.owner.get_addon('osfstorage')
        r = {
            'default_storage': default_provider.serialize_waterbutler_credentials(),
        }
        if provider.repoid is not None:
            r.update({
                'token': self.fetch_access_token(),
                'user_id': provider.userid,
            })
        else:
            r.update({
                'password': provider.password,
                'user_id': provider.userid,
            })
        return r

    def serialize_waterbutler_settings(self):
        if not self.folder_id:
            raise exceptions.AddonError('WEKO is not configured')
        provider = WEKOProvider(self.external_account)
        default_provider = self.owner.get_addon('osfstorage')
        schema_id = RegistrationSchema.objects.get(name=settings.REGISTRATION_SCHEMA_NAME)._id
        return {
            'nid': self.owner._id,
            'url': provider.sword_url,
            'index_id': self.index_id,
            'index_title': self.index_title,
            'default_storage': default_provider.serialize_waterbutler_settings(),
            'metadata_schema_id': schema_id,
        }

    def create_waterbutler_log(self, auth, action, metadata):
        url = self.owner.web_url_for('addon_view_or_download_file', path=metadata['path'], provider='weko')
        self.owner.add_log(
            'weko_{0}'.format(action),
            auth=auth,
            params={
                'project': self.owner.parent_id,
                'node': self.owner._id,
                'dataset': self.index_title,
                'filename': metadata['materialized'].strip('/'),
                'urls': {
                    'view': url,
                    'download': url + '?action=download'
                },
            },
        )

    def validate_index_id(self, index_id):
        if self.index_id == index_id:
            return True
        try:
            index = self.create_client().get_index_by_id(self.index_id)
            return self._validate_index_id(index, index_id)
        except:
            logger.exception('Index validation failed')
            return False

    def get_metadata_repository(self):
        c = self.create_client()
        try:
            index = c.get_index_by_id(self.index_id)
        except ValueError:
            logger.warn(f'WEKO3 Index is not found. Ignored: {self.index_id}')
            return []
        schema_id = RegistrationSchema.objects.get(name=settings.REGISTRATION_SCHEMA_NAME)._id
        return {
            'metadata': {
                'provider': SHORT_NAME,
                'urls': {
                    'get': self.owner.api_url_for('weko_get_file_metadata'),
                },
                'permissions': {
                    'provider': False,
                },
            },
            'registries': self._as_destinations(schema_id, index, ''),
        }

    def _validate_index_id(self, index, index_id):
        if index.identifier == index_id:
            return True
        for child in index.children:
            if self._validate_index_id(child, index_id):
                return True
        return False

    def _as_destinations(self, schema_id, index, parent):
        url = self.owner.api_url_for(
            'weko_publish_file',
            index_id=index.identifier,
            mnode='<mnode>',
            filepath='<filepath>'
        )
        url = url[:url.index('/%3Cmnode%3E/')]
        r = [
            {
                'id': 'weko-' + index.identifier,
                'name': parent + index.title,
                'url': url,
                'schema': schema_id,
            },
        ]
        for child in index.children:
            r += self._as_destinations(schema_id, child, parent + index.title + ' > ')
        return r

    ##### Callback overrides #####

    def after_delete(self, user):
        self.deauthorize(Auth(user=user), add_log=True)
        self.save()

    def on_delete(self):
        self.deauthorize(add_log=False)
        self.save()


class PublishTask(BaseModel):
    project = models.ForeignKey(NodeSettings, related_name='publish_task',
                                db_index=True, null=True, blank=True,
                                on_delete=models.CASCADE)

    path = models.TextField()

    updated = NonNaiveDateTimeField(blank=True, null=True)

    last_task_id = models.CharField(max_length=128, blank=True, null=True)

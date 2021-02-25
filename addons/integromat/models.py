# -*- coding: utf-8 -*-
import logging

from django.db import models
from django.contrib.postgres.fields import ArrayField
from osf.models.base import BaseModel
from osf.models.rdm_integromat import RdmWorkflows, RdmWebMeetingApps
from addons.base import exceptions
from addons.base.models import (BaseOAuthNodeSettings, BaseOAuthUserSettings,
                                BaseStorageAddon)
from addons.integromat.serializer import IntegromatSerializer
from addons.integromat.provider import IntegromatProvider
from addons.integromat import SHORT_NAME, FULL_NAME
import addons.integromat.settings as settings

from addons.integromat.utils import bucket_exists, get_bucket_names
from framework.auth.core import Auth
from osf.models.files import File, Folder, BaseFileNode

logger = logging.getLogger(__name__)


class IntegromatProvider(object):
    name = FULL_NAME
    short_name = SHORT_NAME
    serializer = IntegromatSerializer

    def __init__(self, account=None):
        super(IntegromatProvider, self).__init__()  # this does exactly nothing...
        # provide an unauthenticated session by default
        self.account = account

    def __repr__(self):
        return '<{name}: {status}>'.format(
            name=self.__class__.__name__,
            status=self.account.display_name if self.account else 'anonymous'
        )

class UserSettings(BaseOAuthUserSettings):
    oauth_provider = IntegromatProvider
    serializer = IntegromatSerializer

class NodeSettings(BaseOAuthNodeSettings):
    oauth_provider = IntegromatProvider
    serializer = IntegromatSerializer
    user_settings = models.ForeignKey(UserSettings, null=True, blank=True)
    folder_id = models.TextField(blank=True, null=True)
    folder_name = models.TextField(blank=True, null=True)
    folder_location = models.TextField(blank=True, null=True)

    @property
    def folder_path(self):
        return self.folder_name

    @property
    def display_name(self):
        return u'{0}: {1}'.format(self.config.full_name, self.folder_id)

    def set_folder(self, folder_id, auth):
        host = settings.HOST
        if not bucket_exists(host,
                             self.external_account.oauth_key,
                             self.external_account.oauth_secret, folder_id):
            error_message = ('We are having trouble connecting to that bucket. '
                             'Try a different one.')
            raise exceptions.InvalidFolderError(error_message)

        self.folder_id = str(folder_id)
        self.folder_name = folder_id
        self.save()

        self.nodelogger.log(action='bucket_linked', extra={'bucket': str(folder_id)}, save=True)

    def get_folders(self, **kwargs):
        # This really gets only buckets, not subfolders,
        # as that's all we want to be linkable on a node.
        try:
            buckets = get_bucket_names(self)
        except Exception:
            raise exceptions.InvalidAuthError()

        return [
            {
                'addon': SHORT_NAME,
                'kind': 'folder',
                'id': bucket,
                'name': bucket,
                'path': bucket,
                'urls': {
                    'folders': ''
                }
            }
            for bucket in buckets
        ]

    @property
    def complete(self):
        return self.has_auth and self.folder_id is not None

    def authorize(self, user_settings, save=False):
        self.user_settings = user_settings
        self.nodelogger.log(action='node_authorized', save=save)

    def clear_settings(self):
        self.folder_id = None
        self.folder_name = None
        self.folder_location = None

    def deauthorize(self, auth=None, log=True):
        """Remove user authorization from this node and log the event."""
        self.clear_settings()
        self.clear_auth()  # Also performs a save

        if log:
            self.nodelogger.log(action='node_deauthorized', save=True)

    def delete(self, save=True):
        self.deauthorize(log=False)
        super(NodeSettings, self).delete(save=save)

    def serialize_waterbutler_credentials(self):
        if not self.has_auth:
            raise exceptions.AddonError('Cannot serialize credentials for {} addon'.format(FULL_NAME))
        return {
            'host': settings.HOST,
            'access_key': self.external_account.oauth_key,
            'secret_key': self.external_account.oauth_secret,
        }

    def serialize_waterbutler_settings(self):
        if not self.folder_id:
            raise exceptions.AddonError('Cannot serialize settings for {} addon'.format(FULL_NAME))
        return {
            'bucket': self.folder_id
        }

    def create_waterbutler_log(self, auth, action, metadata):
        url = self.owner.web_url_for('addon_view_or_download_file', path=metadata['path'], provider=SHORT_NAME)

        self.owner.add_log(
            '{0}_{1}'.format(SHORT_NAME, action),
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

    def after_delete(self, user):
        self.deauthorize(Auth(user=user), log=True)

class Attendees(BaseModel):
    id = models.AutoField(primary_key=True)
    user_guid = models.CharField(max_length=128)
    microsoft_teams_user_object = models.CharField(max_length=256)
    microsoft_teams_mail = models.CharField(max_length=256)
    node_settings = models.ForeignKey(NodeSettings, null=False, blank=False, default=None)

class AllMeetingInformation(BaseModel):
    id = models.AutoField(primary_key=True)
    subject = models.CharField(blank=True, null=True, max_length=128)
    organizer = models.CharField(max_length=128)
    attendees = models.ManyToManyField(Attendees, blank=True, null=True)
    start_datetime = models.DateTimeField(blank=True, null=True)
    end_datetime = models.DateTimeField(blank=True, null=True)
    location = models.CharField(blank=True, null=True, max_length=128)
    content = models.CharField(blank=True, null=True, max_length=128)
    join_url = models.CharField(max_length=512)
    meetingid = models.CharField(max_length=512)
    app = models.ForeignKey(RdmWebMeetingApps, to_field='id', on_delete=models.CASCADE)
    node_settings = models.ForeignKey(NodeSettings, null=False, blank=False, default=None)

class workflowExecutionMessages(BaseModel):

    id = models.AutoField(primary_key=True)
    notified = models.BooleanField(default=False)
    integromat_msg = models.CharField(blank=True, null=True, max_length=128)
    timestamp = models.CharField(blank=True, null=True, max_length=128)
    node_settings = models.ForeignKey(NodeSettings, null=False, blank=False, default=None)

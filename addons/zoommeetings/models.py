# -*- coding: utf-8 -*-
import logging

from django.db import models
from osf.models.base import BaseModel, ObjectIDMixin
from osf.models.external import ExternalAccount
from addons.base.models import (BaseOAuthNodeSettings, BaseOAuthUserSettings,
                                BaseStorageAddon)
from addons.zoommeetings.serializer import ZoomMeetingsSerializer
from addons.zoommeetings.provider import ZoomMeetingsProvider
from addons.zoommeetings import settings
from framework.auth.core import Auth
logger = logging.getLogger(__name__)

class UserSettings(BaseOAuthUserSettings):
    oauth_provider = ZoomMeetingsProvider
    serializer = ZoomMeetingsSerializer


class NodeSettings(BaseOAuthNodeSettings, BaseStorageAddon):
    oauth_provider = ZoomMeetingsProvider
    serializer = ZoomMeetingsSerializer
    user_settings = models.ForeignKey(UserSettings, null=True, blank=True)
    folder_id = models.TextField(blank=True, null=True)
    folder_name = models.TextField(blank=True, null=True)
    folder_location = models.TextField(blank=True, null=True)

    _api = None

    @property
    def api(self):
        """Authenticated ExternalProvider instance"""
        if self._api is None:
            self._api = ZoomMeetingsProvider(self.external_account)
        return self._api

    @property
    def folder_path(self):
        return self.folder_name

    @property
    def display_name(self):
        return u'{0}: {1}'.format(self.config.full_name, self.folder_id)

    def set_folder(self, folder_id, auth):
        # required by superclass, not actually used
        pass

    @property
    def complete(self):
        return bool(self.has_auth and self.user_settings.verify_oauth_access(
            node=self.owner,
            external_account=self.external_account,
        ))

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
        # required by superclass, not actually used
        pass

    def serialize_waterbutler_settings(self):
        # required by superclass, not actually used
        pass

    def create_waterbutler_log(self, auth, action, metadata):
        # required by superclass, not actually used
        pass

    def after_delete(self, user):
        self.deauthorize(Auth(user=user), log=True)

    def fetch_access_token(self):
        return self.api.fetch_access_token()


class Meetings(ObjectIDMixin, BaseModel):
    subject = models.CharField(max_length=255)
    organizer = models.CharField(max_length=255)
    organizer_fullname = models.CharField(max_length=255)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    content = models.TextField(blank=True, null=True, max_length=10000)
    join_url = models.TextField(max_length=512)
    meetingid = models.TextField(max_length=512)
    app_name = models.CharField(max_length=128, default=settings.ZOOM_MEETINGS)
    external_account = models.ForeignKey(ExternalAccount, null=True, blank=True, default=None)
    node_settings = models.ForeignKey(NodeSettings, null=False, blank=False, default=None)

# -*- coding: utf-8 -*-
"""Factories for the ZoomMeetings addon."""
import factory
from datetime import date, datetime, timedelta
from factory.django import DjangoModelFactory
from osf.models.user import OSFUser
from addons.zoommeetings import settings
from addons.zoommeetings import SHORT_NAME
from addons.zoommeetings.models import (
    UserSettings,
    NodeSettings,
    Meetings
)

from osf_tests.factories import UserFactory, ProjectFactory, ExternalAccountFactory

class ZoomMeetingsAccountFactory(ExternalAccountFactory):
    provider = SHORT_NAME
    provider_id = factory.Sequence(lambda n: 'id-{0}'.format(n))
    oauth_key = factory.Sequence(lambda n: 'key-{0}'.format(n))
    display_name = 'zoomtestuser1@test.zoom.com(ZoomMeetings Fake User)'


class ZoomMeetingsUserSettingsFactory(DjangoModelFactory):
    class Meta:
        model = UserSettings

    owner = factory.SubFactory(UserFactory)


class ZoomMeetingsNodeSettingsFactory(DjangoModelFactory):
    class Meta:
        model = NodeSettings

    _id = 'qwe'
    owner = factory.SubFactory(ProjectFactory)
    user_settings = factory.SubFactory(ZoomMeetingsUserSettingsFactory)

class ZoomMeetingsMeetingsFactory(DjangoModelFactory):
    class Meta:
        model = Meetings


    subject = 'My Test Meeting'
    organizer = 'zoomtestuser1@test.zoom.com'
    organizer_fullname = 'ZoomMeetings Fake User'
    start_datetime = datetime.now().isoformat()
    end_datetime = (datetime.now() + timedelta(hours=1)).isoformat()
    content = 'My Meeting Content'
    join_url = 'zoom/zoom.com/321'
    meetingid = 'qwertyuiopasdfghjklzxcvbnm'
    app_name = settings.ZOOM_MEETINGS
    external_account = factory.SubFactory(ZoomMeetingsAccountFactory)
    node_settings = factory.SubFactory(ZoomMeetingsNodeSettingsFactory)

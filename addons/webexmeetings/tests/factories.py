# -*- coding: utf-8 -*-
"""Factories for the WebexMeetings addon."""
import factory
from datetime import date, datetime, timedelta
from factory.django import DjangoModelFactory
from osf.models.user import OSFUser
from addons.webexmeetings import settings
from addons.webexmeetings import SHORT_NAME
from addons.webexmeetings.models import (
    UserSettings,
    NodeSettings,
    Attendees,
    Meetings
)

from osf_tests.factories import UserFactory, ProjectFactory, ExternalAccountFactory

class WebexMeetingsAccountFactory(ExternalAccountFactory):
    provider = SHORT_NAME
    provider_id = factory.Sequence(lambda n: 'id-{0}'.format(n))
    oauth_key = factory.Sequence(lambda n: 'key-{0}'.format(n))
    display_name = 'webextestuser1@test.webex.com(WebexMeetings Fake User)'


class WebexMeetingsUserSettingsFactory(DjangoModelFactory):
    class Meta:
        model = UserSettings

    owner = factory.SubFactory(UserFactory)


class WebexMeetingsNodeSettingsFactory(DjangoModelFactory):
    class Meta:
        model = NodeSettings

    _id = 'qwe'
    owner = factory.SubFactory(ProjectFactory)
    user_settings = factory.SubFactory(WebexMeetingsUserSettingsFactory)

class WebexMeetingsAttendeesFactory(DjangoModelFactory):
    class Meta:
        model = Attendees

    user_guid = 'webextestuser'
    fullname = 'WebexMeetings Fake User'
    email_address = 'webextestuser1@test.webex.com'
    display_name = 'Webex Test User1'
    is_guest = False
    is_active = True
    has_grdm_account = True
    external_account = factory.SubFactory(WebexMeetingsAccountFactory)
    node_settings = factory.SubFactory(WebexMeetingsNodeSettingsFactory)

class WebexMeetingsMeetingsFactory(DjangoModelFactory):
    class Meta:
        model = Meetings


    subject = 'My Test Meeting'
    organizer = 'webextestuser1@test.webex.com'
    organizer_fullname = 'WebexMeetings Fake User'
    start_datetime = datetime.now().isoformat()
    end_datetime = (datetime.now() + timedelta(hours=1)).isoformat()
    content = 'My Meeting Content'
    join_url = 'webex/webex.com/321'
    meetingid = 'qwertyuiopasdfghjklzxcvbnm'
    meeting_password = 'qwer12345'
    app_name = settings.WEBEX_MEETINGS
    external_account = factory.SubFactory(WebexMeetingsAccountFactory)
    node_settings = factory.SubFactory(WebexMeetingsNodeSettingsFactory)


    @factory.post_generation
    def attendees(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            for attendee in extracted:
                self.attendees.add(attendee)

class WebexMeetingsMeetingsAttendeesRelationFactory(DjangoModelFactory):

    meeting = factory.SubFactory(WebexMeetingsMeetingsFactory)
    attendee = factory.SubFactory(WebexMeetingsAttendeesFactory)
    webex_meetings_invitee_id = 'zxcvbnmasdfghjkl'
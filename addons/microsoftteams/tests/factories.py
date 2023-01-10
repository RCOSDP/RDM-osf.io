# -*- coding: utf-8 -*-
"""Factories for the MicrosoftTeams addon."""
import factory
from datetime import date, datetime, timedelta
from factory.django import DjangoModelFactory
from osf.models.user import OSFUser
from addons.microsoftteams import settings
from addons.microsoftteams import SHORT_NAME
from addons.microsoftteams.models import (
    UserSettings,
    NodeSettings,
    Attendees,
    Meetings
)

from osf_tests.factories import UserFactory, ProjectFactory, ExternalAccountFactory

class MicrosoftTeamsAccountFactory(ExternalAccountFactory):
    provider = SHORT_NAME
    provider_id = factory.Sequence(lambda n: 'id-{0}'.format(n))
    oauth_key = factory.Sequence(lambda n: 'key-{0}'.format(n))
    display_name = 'teamstestuser1@test.onmicrosoft.com(MicrosoftTeams Fake User)'


class MicrosoftTeamsUserSettingsFactory(DjangoModelFactory):
    class Meta:
        model = UserSettings

    owner = factory.SubFactory(UserFactory)


class MicrosoftTeamsNodeSettingsFactory(DjangoModelFactory):
    class Meta:
        model = NodeSettings

    _id = 'qwe'
    owner = factory.SubFactory(ProjectFactory)
    user_settings = factory.SubFactory(MicrosoftTeamsUserSettingsFactory)

class MicrosoftTeamsAttendeesFactory(DjangoModelFactory):
    class Meta:
        model = Attendees

    user_guid = 'teamstestuser'
    fullname = 'MicrosoftTeams Fake User'
    email_address = 'teamstestuser1@test.onmicrosoft.com'
    display_name = 'Teams Test User1'
    is_guest = False
    is_active = True
    has_grdm_account = True
    external_account = factory.SubFactory(MicrosoftTeamsAccountFactory)
    node_settings = factory.SubFactory(MicrosoftTeamsNodeSettingsFactory)

class MicrosoftTeamsMeetingsFactory(DjangoModelFactory):
    class Meta:
        model = Meetings


    subject = 'My Test Meeting'
    organizer = 'teamstestuser1@test.onmicrosoft.com'
    organizer_fullname = 'MicrosoftTeams Fake User'
    start_datetime = datetime.now().isoformat()
    end_datetime = (datetime.now() + timedelta(hours=1)).isoformat()
    content = 'My Meeting Content'
    join_url = 'teams/microsoft.com/321'
    meetingid = 'qwertyuiopasdfghjklzxcvbnm'
    app_name = settings.MICROSOFT_TEAMS
    external_account = factory.SubFactory(MicrosoftTeamsAccountFactory)
    node_settings = factory.SubFactory(MicrosoftTeamsNodeSettingsFactory)


    @factory.post_generation
    def attendees(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            for attendee in extracted:
                self.attendees.add(attendee)

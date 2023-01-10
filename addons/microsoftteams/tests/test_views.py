# -*- coding: utf-8 -*-
import mock
import pytest
import json
import addons.microsoftteams.settings as microsoftteams_settings
import pytz
from nose.tools import (assert_equal, assert_equals,
    assert_true, assert_in, assert_false)
from rest_framework import status as http_status
from django.core import serializers
import requests
from framework.auth import Auth
from tests.base import OsfTestCase
from osf_tests.factories import ProjectFactory, AuthUserFactory, InstitutionFactory, CommentFactory
from addons.base.tests.views import (
    OAuthAddonConfigViewsTestCaseMixin
)
from addons.microsoftteams.tests.utils import MicrosoftTeamsAddonTestCase, MockResponse
from website.util import api_url_for
from admin.rdm_addons.utils import get_rdm_addon_option
from datetime import date, datetime, timedelta
from dateutil import parser as date_parse
from dateutil.tz import gettz
from addons.microsoftteams.models import (
    UserSettings,
    NodeSettings,
    Attendees,
    Meetings
)
from osf.models import ExternalAccount, OSFUser, RdmAddonOption, BaseFileNode, AbstractNode, Comment
from addons.microsoftteams.tests.factories import (
    MicrosoftTeamsUserSettingsFactory,
    MicrosoftTeamsNodeSettingsFactory,
    MicrosoftTeamsAccountFactory,
    MicrosoftTeamsAttendeesFactory,
    MicrosoftTeamsMeetingsFactory
)
from api_tests import utils as api_utils
from requests.exceptions import HTTPError
import logging
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db

class TestMicrosoftTeamsViews(MicrosoftTeamsAddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
    def setUp(self):
        super(TestMicrosoftTeamsViews, self).setUp()

    def tearDown(self):
        super(TestMicrosoftTeamsViews, self).tearDown()

    def test_microsoftteams_remove_node_settings_owner(self):
        url = self.node_settings.owner.api_url_for('microsoftteams_deauthorize_node')
        self.app.delete(url, auth=self.user.auth)
        result = self.Serializer().serialize_settings(node_settings=self.node_settings, current_user=self.user)
        assert_equal(result['nodeHasAuth'], False)

    def test_microsoftteams_remove_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('microsoftteams_deauthorize_node')
        ret = self.app.delete(url, auth=None, expect_errors=True)

        assert_equal(ret.status_code, 401)

    def test_microsoftteams_get_node_settings_owner(self):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.node_settings.owner.api_url_for('microsoftteams_get_config')
        res = self.app.get(url, auth=self.user.auth)

        result = res.json['result']
        assert_equal(result['nodeHasAuth'], True)
        assert_equal(result['userIsOwner'], True)

    def test_microsoftteams_get_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('microsoftteams_get_config')
        unauthorized = AuthUserFactory()
        ret = self.app.get(url, auth=unauthorized.auth, expect_errors=True)

        assert_equal(ret.status_code, 403)

    @mock.patch('addons.microsoftteams.utils.api_create_teams_meeting')
    def test_microsoftteams_request_api_create(self, mock_api_create_teams_meeting):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        url = self.project.api_url_for('microsoftteams_request_api')

        expected_action = 'create'
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = ''

        expected_subject = 'My Test Meeting'
        expected_organizer = 'teamstestuser1@test.onmicrosoft.com'
        expected_organizer_fullname = 'MicrosoftTeams Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='teamstestuser').id
        expected_attendees = {
                    'emailAddress': {
                        'address': 'teamstestuser1@test.onmicrosoft.com',
                        'name': 'Teams Test User1'
                    }
                }
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content'
        expected_contentExtract = expected_content
        expected_joinUrl = 'teams/microsoft.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_body = {
                'subject': expected_subject,
                'start': {
                    'dateTime': expected_startDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': expected_endDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'body': {
                    'contentType': 'HTML',
                    'content': expected_content,
                },
                'attendees': expected_attendees,
                'isOnlineMeeting': True,
            };

        mock_api_create_teams_meeting.return_value = {
            'id': expected_meetingId,
            'subject': expected_subject,
            'start': {
                'dateTime': expected_startDatetime,
                'timeZone': 'Asia/Tokyo'
            },
            'end': {
                'dateTime': expected_endDatetime,
                'timeZone': 'Asia/Tokyo'
            },
            'attendees': [expected_attendees],
            'bodyPreview': expected_content,
            'organizer': {
                'emailAddress': {
                    'name': 'Teams Test User1',
                    'address': 'teamstestuser1@test.onmicrosoft.com',
                }
            },
            'onlineMeeting': {
                'joinUrl': expected_joinUrl
            }
        }

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'contentExtract': expected_contentExtract,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.get(meetingid=expected_meetingId)

        tz = pytz.timezone('Asia/Tokyo')
        expected_startDatetime = date_parse.parse(expected_startDatetime)
        expected_startDatetime = tz.localize(expected_startDatetime)
        expected_startDatetime = expected_startDatetime.astimezone(gettz('UTC'))
        expected_endDatetime = date_parse.parse(expected_endDatetime)
        expected_endDatetime = tz.localize(expected_endDatetime)
        expected_endDatetime = expected_endDatetime.astimezone(gettz('UTC'))
        expected_startDatetime_format = expected_startDatetime.strftime('%Y/%m/%d %H:%M:%S')
        expected_endDatetime_format = expected_endDatetime.strftime('%Y/%m/%d %H:%M:%S')

        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.start_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_startDatetime_format)
        assert_equals(result.end_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_endDatetime_format)

        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_meetingId)
        assert_equals(result.app_name, microsoftteams_settings.MICROSOFT_TEAMS)
        assert_equals(result.external_account.id, self.external_account.id)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson, {})
        assert_equals(result.attendees.all()[0].id, expected_attendees_id)

        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_create_teams_meeting')
    def test_microsoftteams_request_api_create_401(self, mock_api_create_teams_meeting):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        url = self.project.api_url_for('microsoftteams_request_api')
        expected_action = 'create'
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = ''
        expected_subject = 'My Test Meeting'
        expected_organizer = 'teamstestuser1@test.onmicrosoft.com'
        expected_organizer_fullname = 'MicrosoftTeams Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='teamstestuser').id
        expected_attendees = {
                    'emailAddress': {
                        'address': 'teamstestuser1@test.onmicrosoft.com',
                        'name': 'Teams Test User1'
                    }
                }
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content'
        expected_contentExtract = expected_content
        expected_joinUrl = 'teams/microsoft.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_body = {
                'subject': expected_subject,
                'start': {
                    'dateTime': expected_startDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': expected_endDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'body': {
                    'contentType': 'HTML',
                    'content': expected_content,
                },
                'attendees': expected_attendees,
                'isOnlineMeeting': True,
            };
        mock_api_create_teams_meeting.side_effect = HTTPError(401)
        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'contentExtract': expected_contentExtract,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')
        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_update_teams_meeting')
    def test_microsoftteams_request_api_update(self, mock_api_update_teams_meeting):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        updateEmailAddress = 'teamstestuser2@test.onmicrosoft.com'
        updateDisplayName = 'Teams Test User2'

        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        AttendeesFactory2 = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account, user_guid='teamstestuser2', fullname='TEAMS TEST USER 2', email_address=updateEmailAddress, display_name=updateDisplayName)
        MeetingsFactory = MicrosoftTeamsMeetingsFactory(node_settings=self.node_settings)

        qsMeetings = Meetings.objects.all()
        meetingsJson = json.loads(serializers.serialize('json', qsMeetings, ensure_ascii=False))
        expected_external_id = meetingsJson[0]['fields']['external_account']

        url = self.project.api_url_for('microsoftteams_request_api')

        expected_action = 'update'
        expected_UpdateMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_DeleteMeetinId = ''

        expected_subject = 'My Test Meeting EDIT'
        expected_organizer = 'teamstestuser1@test.onmicrosoft.com'
        expected_organizer_fullname = 'MicrosoftTeams Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='teamstestuser2').id
        expected_attendees = {
                    'emailAddress': {
                        'address': updateEmailAddress,
                        'name': updateDisplayName
                    }
                }
        expected_startDatetime = str(datetime.now().isoformat())
        expected_endDatetime = str((datetime.now() + timedelta(hours=1)).isoformat())
        expected_content = 'My Test Content EDIT'
        expected_contentExtract = expected_content
        expected_joinUrl = 'teams/microsoft.com/321'
        expected_body = {
                'subject': expected_subject,
                'start': {
                    'dateTime': expected_startDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': expected_endDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'body': {
                    'contentType': 'HTML',
                    'content': expected_content,
                },
                'attendees': expected_attendees,
                'isOnlineMeeting': True,
            };

        mock_api_update_teams_meeting.return_value = {
            'id': expected_UpdateMeetinId,
            'subject': expected_subject,
            'start': {
                'dateTime': expected_startDatetime,
                'timeZone': 'Asia/Tokyo'
            },
            'end': {
                'dateTime': expected_endDatetime,
                'timeZone': 'Asia/Tokyo'
            },
            'attendees': [expected_attendees],
            'bodyPreview': expected_content,
            'organizer': {
                'emailAddress': {
                    'name': 'Teams Test User1',
                    'address': 'teamstestorganizer@test.onmicrosoft.com',
                },
                'emailAddress': {
                    'name': updateDisplayName,
                    'address': updateEmailAddress,
                }
            },
            'onlineMeeting': {
                'joinUrl': expected_joinUrl
            }
        }

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'contentExtract': expected_contentExtract,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.get(meetingid=expected_UpdateMeetinId)

        tz = pytz.timezone('Asia/Tokyo')
        expected_startDatetime = date_parse.parse(expected_startDatetime)
        expected_startDatetime = tz.localize(expected_startDatetime)
        expected_startDatetime = expected_startDatetime.astimezone(gettz('UTC'))
        expected_endDatetime = date_parse.parse(expected_endDatetime)
        expected_endDatetime = tz.localize(expected_endDatetime)
        expected_endDatetime = expected_endDatetime.astimezone(gettz('UTC'))
        expected_startDatetime_format = expected_startDatetime.strftime('%Y/%m/%d %H:%M:%S')
        expected_endDatetime_format = expected_endDatetime.strftime('%Y/%m/%d %H:%M:%S')

        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.start_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_startDatetime_format)
        assert_equals(result.end_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_endDatetime_format)
        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_UpdateMeetinId)
        assert_equals(result.app_name, microsoftteams_settings.MICROSOFT_TEAMS)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson, {})
        assert_equals(len(result.attendees.all()), 1)
        assert_equals(result.attendees.all()[0].id, expected_attendees_id)
        assert_equals(result.external_account.id, expected_external_id)

        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_update_teams_meeting')
    def test_microsoftteams_request_api_update_401(self, mock_api_update_teams_meeting):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        updateEmailAddress = 'teamstestuser2@test.onmicrosoft.com'
        updateDisplayName = 'Teams Test User2'
        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings)
        AttendeesFactory2 = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, user_guid='teamstestuser2', fullname='TEAMS TEST USER 2', email_address=updateEmailAddress, display_name=updateDisplayName)
        MeetingsFactory = MicrosoftTeamsMeetingsFactory(node_settings=self.node_settings)
        qsMeetings = Meetings.objects.all()
        meetingsJson = json.loads(serializers.serialize('json', qsMeetings, ensure_ascii=False))
        expected_external_id = meetingsJson[0]['fields']['external_account']
        url = self.project.api_url_for('microsoftteams_request_api')
        expected_action = 'update'
        expected_UpdateMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_DeleteMeetinId = ''
        expected_subject = 'My Test Meeting EDIT'
        expected_organizer = 'teamstestuser1@test.onmicrosoft.com'
        expected_organizer_fullname = 'MicrosoftTeams Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='teamstestuser2').id
        expected_attendees = {
                    'emailAddress': {
                        'address': updateEmailAddress,
                        'name': updateDisplayName
                    }
                }
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content EDIT'
        expected_contentExtract = expected_content
        expected_joinUrl = 'teams/microsoft.com/321'
        expected_body = {
                'subject': expected_subject,
                'start': {
                    'dateTime': expected_startDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': expected_endDatetime,
                    'timeZone': 'Asia/Tokyo',
                },
                'body': {
                    'contentType': 'HTML',
                    'content': expected_content,
                },
                'attendees': expected_attendees,
                'isOnlineMeeting': True,
            };
        mock_api_update_teams_meeting.side_effect = HTTPError(401)
        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'contentExtract': expected_contentExtract,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')
        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_delete_teams_meeting')
    def test_microsoftteams_request_api_delete(self, mock_api_delete_teams_meeting):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        mock_api_delete_teams_meeting.return_value = {}

        expected_action = 'delete'
        MeetingsFactory = MicrosoftTeamsMeetingsFactory(node_settings=self.node_settings)

        url = self.project.api_url_for('microsoftteams_request_api')

        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = 'qwertyuiopasdfghjklzxcvbnm'

        expected_body = {
                'subject': '',
                'start': {
                    'dateTime': '',
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': '',
                    'timeZone': 'Asia/Tokyo',
                },
                'body': {
                    'contentType': 'HTML',
                    'content': '',
                },
                'attendees': [],
                'isOnlineMeeting': True,
            };

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.filter(meetingid=expected_DeleteMeetinId)

        assert_equals(result.count(), 0)
        assert_equals(rvBodyJson, {})

        Meetings.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_delete_teams_meeting')
    def test_microsoftteams_request_api_delete_401(self, mock_api_delete_teams_meeting):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        mock_api_delete_teams_meeting.return_value = {}
        expected_action = 'delete'
        MeetingsFactory = MicrosoftTeamsMeetingsFactory(node_settings=self.node_settings)
        url = self.project.api_url_for('microsoftteams_request_api')
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_body = {
                'subject': '',
                'start': {
                    'dateTime': '',
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': '',
                    'timeZone': 'Asia/Tokyo',
                },
                'body': {
                    'contentType': 'HTML',
                    'content': '',
                },
                'attendees': [],
                'isOnlineMeeting': True,
            };
        mock_api_delete_teams_meeting.side_effect = HTTPError(401)
        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')
        Meetings.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_get_microsoft_username')
    def test_microsoftteams_register_email_create(self, mock_api_get_microsoft_username):
        mock_api_get_microsoft_username.return_value = 'Teams Test User A'
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']
        url = self.project.api_url_for('microsoftteams_register_email')

        _id = None
        expected_guid = osfUserGuid
        expected_email = 'teamstestusera@test.onmicrosoft.com'
        expected_username = mock_api_get_microsoft_username.return_value
        expected_is_guest = False
        expected_has_grdm_account = True
        expected_fullname = osfUser.fullname
        expected_actionType = 'create'
        expected_emailType = True
        expected_regAuto = True

        rv = self.app.post_json(url, {
            '_id': _id,
            'guid': expected_guid,
            'email': expected_email,
            'fullname': expected_fullname,
            'is_guest': expected_is_guest,
            'has_grdm_account': expected_has_grdm_account,
            'actionType': expected_actionType,
            'emailType': expected_emailType,
            'regAuto': expected_regAuto
        }, auth=self.user.auth)

        expected_newAttendee = {
            'guid': expected_guid,
            'dispName': expected_fullname,
            'fullname': expected_fullname,
            'email': expected_email,
            'institution': '',
            'appUsername': expected_username,
            'appEmail': expected_email,
            'profile': '',
            '_id': '',
            'is_guest': expected_is_guest,
        }

        rvBodyJson = json.loads(rv.body)

        result = Attendees.objects.get(user_guid=osfUserGuid)

        assert_equals(result.user_guid, expected_guid)
        assert_equals(result.fullname, expected_fullname)
        assert_equals(result.email_address, expected_email)
        assert_equals(result.display_name, expected_username)
        assert_equals(result.is_guest, expected_is_guest)
        assert_equals(result.is_active, True)
        assert_equals(result.has_grdm_account, expected_has_grdm_account)
        assert_equals(result.external_account.id, self.external_account.id)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson['result'], '')
        assert_equals(rvBodyJson['regAuto'], True)
        assert_equals(rvBodyJson['newAttendee'], expected_newAttendee)

        #clear
        Attendees.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_get_microsoft_username')
    def test_microsoftteams_register_email_create_outside(self, mock_api_get_microsoft_username):
        mock_api_get_microsoft_username.return_value = ''
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']
        url = self.project.api_url_for('microsoftteams_register_email')
        _id = None
        expected_guid = osfUserGuid
        expected_email = 'teamstestusera@test.onmicrosoft.com'
        expected_is_guest = False
        expected_has_grdm_account = True
        expected_fullname = osfUser.fullname
        expected_actionType = 'create'
        expected_emailType = True
        expected_regAuto = True

        result = Attendees.objects.all()
        resultJson = json.loads(serializers.serialize('json', result, ensure_ascii=False))

        rv = self.app.post_json(url, {
            '_id': _id,
            'guid': expected_guid,
            'email': expected_email,
            'fullname': expected_fullname,
            'is_guest': expected_is_guest,
            'has_grdm_account': expected_has_grdm_account,
            'actionType': expected_actionType,
            'emailType': expected_emailType,
            'regAuto': expected_regAuto
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        result = Attendees.objects.all()
        resultJson = json.loads(serializers.serialize('json', result, ensure_ascii=False))
        assert_equals(rvBodyJson['result'], 'outside_email')
        assert_equals(rvBodyJson['regAuto'], True)
        assert_equals(result.count(), 0)

    @mock.patch('addons.microsoftteams.utils.api_get_microsoft_username')
    def test_microsoftteams_register_email_update(self, mock_api_get_microsoft_username):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']
        expected_fullname = osfUser.fullname
        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, user_guid=osfUserGuid)
        mock_api_get_microsoft_username.return_value = 'Teams Test User B EDIT'
        url = self.project.api_url_for('microsoftteams_register_email')

        qsAttendees = Attendees.objects.all()
        attendeesJson = json.loads(serializers.serialize('json', qsAttendees, ensure_ascii=False))
        expected_external_id = attendeesJson[0]['fields']['external_account']
        expected_id = AttendeesFactory._id
        expected_guid = AttendeesFactory.user_guid
        expected_email = 'teamstestuserbedit@test.onmicrosoft.com'
        expected_username = mock_api_get_microsoft_username.return_value
        expected_is_guest = False
        expected_has_grdm_account = True
        expected_actionType = 'update'
        expected_emailType = True
        expected_regAuto = False

        rv = self.app.post_json(url, {
            '_id': expected_id,
            'guid': expected_guid,
            'fullname': expected_fullname,
            'email': expected_email,
            'is_guest': expected_is_guest,
            'has_grdm_account': expected_has_grdm_account,
            'actionType': expected_actionType,
            'emailType': expected_emailType,
            'regAuto': expected_regAuto
        }, auth=self.user.auth)

        expected_newAttendee = {
            'guid': expected_guid,
            'dispName': expected_fullname,
            'fullname': expected_fullname,
            'email': expected_email,
            'institution': '',
            'appUsername': expected_username,
            'appEmail': expected_email,
            'profile': '',
            '_id': '',
            'is_guest': expected_is_guest,
        }

        rvBodyJson = json.loads(rv.body)
        result = Attendees.objects.get(_id=expected_id)

        assert_equals(result.user_guid, expected_guid)
        assert_equals(result.fullname, expected_fullname)
        assert_equals(result.email_address, expected_email)
        assert_equals(result.display_name, expected_username)
        assert_equals(result.is_guest, expected_is_guest)
        assert_equals(result.is_active, True)
        assert_equals(result.has_grdm_account, expected_has_grdm_account)
        assert_equals(result.external_account.id, expected_external_id)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson['result'], '')
        assert_equals(rvBodyJson['regAuto'], False)
        assert_equals(rvBodyJson['newAttendee'], {})

        #clear
        Attendees.objects.all().delete()

    @mock.patch('addons.microsoftteams.utils.api_get_microsoft_username')
    def test_microsoftteams_register_email_update_outside(self, mock_api_get_microsoft_username):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']

        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings, user_guid=osfUserGuid)
        mock_api_get_microsoft_username.return_value = ''
        url = self.project.api_url_for('microsoftteams_register_email')

        qsAttendees = Attendees.objects.all()
        attendeesJson = json.loads(serializers.serialize('json', qsAttendees, ensure_ascii=False))
        expected_external_id = attendeesJson[0]['fields']['external_account']

        result = Attendees.objects.all()
        resultJson = json.loads(serializers.serialize('json', result, ensure_ascii=False))

        expected_id = AttendeesFactory._id
        expected_guid = AttendeesFactory.user_guid
        expected_email = AttendeesFactory.email_address
        expected_username = AttendeesFactory.display_name
        expected_is_guest = False
        expected_has_grdm_account = True
        expected_fullname = AttendeesFactory.fullname
        expected_actionType = 'update'
        expected_emailType = True
        expected_regAuto = False

        rv = self.app.post_json(url, {
            '_id': expected_id,
            'guid': expected_guid,
            'fullname': expected_username,
            'email': expected_email,
            'is_guest': expected_is_guest,
            'has_grdm_account': expected_has_grdm_account,
            'actionType': expected_actionType,
            'emailType': expected_emailType,
            'regAuto': expected_regAuto
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        result = Attendees.objects.get(_id=expected_id)

        assert_equals(rvBodyJson['result'], 'outside_email')
        assert_equals(rvBodyJson['regAuto'], expected_regAuto)
        assert_equals(result.user_guid, expected_guid)
        assert_equals(result.fullname, expected_fullname)
        assert_equals(result.email_address, expected_email)
        assert_equals(result.display_name, expected_username)
        assert_equals(result.is_guest, expected_is_guest)
        assert_equals(result.external_account.id, expected_external_id)
        assert_equals(result.node_settings.id, self.node_settings.id)

        #clear
        Attendees.objects.all().delete()

    def test_microsoftteams_register_email_delete(self):
        AttendeesFactory = MicrosoftTeamsAttendeesFactory(node_settings=self.node_settings)
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.project.api_url_for('microsoftteams_register_email')

        expected_id = AttendeesFactory._id
        expected_actionType = 'delete'

        rv = self.app.post_json(url, {
            '_id': expected_id,
            'actionType': expected_actionType,
        }, auth=self.user.auth)

        rvBodyJson = json.loads(rv.body)

        result = Attendees.objects.get(node_settings_id=self.node_settings.id, _id=expected_id)

        assert_equals(result.is_active, False)
        assert_equals(rvBodyJson['result'], '')

    ## Overrides ##

    def test_folder_list(self):
        pass

    def test_set_config(self):
        pass

    def test_import_auth(self):

        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        rdm_addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = True
        rdm_addon_option.save()

        ea = self.ExternalAccountFactory()
        self.user.external_accounts.add(ea)
        self.user.save()

        node = ProjectFactory(creator=self.user)
        node_settings = node.get_or_add_addon(self.ADDON_SHORT_NAME, auth=Auth(self.user))
        node.save()
        url = node.api_url_for('{0}_import_auth'.format(self.ADDON_SHORT_NAME))
        res = self.app.put_json(url, {
            'external_account_id': ea._id
        }, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        node_settings.reload()
        assert_equal(node_settings.external_account._id, ea._id)

        node.reload()
        last_log = node.logs.latest()
        assert_equal(last_log.action, '{0}_node_authorized'.format(self.ADDON_SHORT_NAME))

# -*- coding: utf-8 -*-
import mock
import pytest
import json
import addons.webexmeetings.settings as webexmeetings_settings

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
from addons.webexmeetings.tests.utils import WebexMeetingsAddonTestCase, MockResponse
from website.util import api_url_for
from admin.rdm_addons.utils import get_rdm_addon_option
from datetime import date, datetime, timedelta
from dateutil import parser as date_parse
from addons.webexmeetings.models import (
    UserSettings,
    NodeSettings,
    Attendees,
    Meetings,
    MeetingsAttendeesRelation
)
from osf.models import ExternalAccount, OSFUser, RdmAddonOption, BaseFileNode, AbstractNode, Comment
from addons.webexmeetings.tests.factories import (
    WebexMeetingsUserSettingsFactory,
    WebexMeetingsNodeSettingsFactory,
    WebexMeetingsAccountFactory,
    WebexMeetingsAttendeesFactory,
    WebexMeetingsMeetingsFactory
)
from api_tests import utils as api_utils
from requests.exceptions import HTTPError
import logging
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db

class TestWebexMeetingsViews(WebexMeetingsAddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
    def setUp(self):
        super(TestWebexMeetingsViews, self).setUp()

    def tearDown(self):
        super(TestWebexMeetingsViews, self).tearDown()

    def test_webexmeetings_remove_node_settings_owner(self):
        url = self.node_settings.owner.api_url_for('webexmeetings_deauthorize_node')
        self.app.delete(url, auth=self.user.auth)
        result = self.Serializer().serialize_settings(node_settings=self.node_settings, current_user=self.user)
        assert_equal(result['nodeHasAuth'], False)

    def test_webexmeetings_remove_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('webexmeetings_deauthorize_node')
        ret = self.app.delete(url, auth=None, expect_errors=True)

        assert_equal(ret.status_code, 401)

    def test_webexmeetings_get_node_settings_owner(self):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.node_settings.owner.api_url_for('webexmeetings_get_config')
        res = self.app.get(url, auth=self.user.auth)

        result = res.json['result']
        assert_equal(result['nodeHasAuth'], True)
        assert_equal(result['userIsOwner'], True)

    def test_webexmeetings_get_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('webexmeetings_get_config')
        unauthorized = AuthUserFactory()
        ret = self.app.get(url, auth=unauthorized.auth, expect_errors=True)

        assert_equal(ret.status_code, 403)

    @mock.patch('addons.webexmeetings.utils.get_invitees')
    @mock.patch('addons.webexmeetings.utils.api_create_webex_meeting')
    def test_webexmeetings_request_api_create(self, mock_api_create_webex_meeting, mock_get_invitees):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        url = self.project.api_url_for('webexmeetings_request_api')

        expected_action = 'create'
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = ''

        expected_subject = 'My Test Meeting'
        expected_organizer = 'webextestuser1@test.webex.com'
        expected_organizer_fullname = 'WebexMeetings Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='webextestuser').id
        expected_attendee_email = 'webextestuser1@test.webex.com'
        expected_attendees = [{'email': expected_attendee_email}]
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content'
        expected_joinUrl = 'webex/webex.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_passowrd = 'qwer12345'
        expected_invitee_id = 'zxcvbnmasdfghjkl'
        expected_body = {
                'title': expected_subject,
                'start': expected_startDatetime,
                'end': expected_endDatetime,
                'agenda': expected_content,
                'invitees': expected_attendees,
            }

        mock_api_create_webex_meeting.return_value = {
            'id': expected_meetingId,
            'title': expected_subject,
            'start': expected_startDatetime,
            'end': expected_endDatetime,
            'agenda': expected_content,
            'hostEmail': expected_organizer,
            'webLink': expected_joinUrl,
            'password': expected_passowrd
        }
        mock_get_invitees.return_value = [{
                    'email': expected_attendee_email,
                    'id': expected_invitee_id
                }]

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.get(meetingid=expected_meetingId)
        relationResult = MeetingsAttendeesRelation.objects.get(webex_meetings_invitee_id=expected_invitee_id)

        expected_startDatetime_format = date_parse.parse(expected_startDatetime).strftime('%Y/%m/%d %H:%M:%S')
        expected_endDatetime_format = date_parse.parse(expected_endDatetime).strftime('%Y/%m/%d %H:%M:%S')

        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.start_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_startDatetime_format)
        assert_equals(result.end_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_endDatetime_format)

        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_meetingId)
        assert_equals(result.meeting_password, expected_passowrd)
        assert_equals(result.app_name, webexmeetings_settings.WEBEX_MEETINGS)
        assert_equals(result.external_account.id, self.external_account.id)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson, {})
        assert_equals(result.attendees.all()[0].id, expected_attendees_id)
        assert_equals(relationResult.meeting_id, result.id)
        assert_equals(relationResult.attendee_id, expected_attendees_id)
        assert_equals(relationResult.webex_meetings_invitee_id, expected_invitee_id)

        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()
        MeetingsAttendeesRelation.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.get_invitees')
    @mock.patch('addons.webexmeetings.utils.api_create_webex_meeting')
    def test_webexmeetings_request_api_create_401(self, mock_api_create_webex_meeting, mock_get_invitees):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        url = self.project.api_url_for('webexmeetings_request_api')

        expected_action = 'create'
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = ''

        expected_subject = 'My Test Meeting'
        expected_organizer = 'webextestuser1@test.webex.com'
        expected_organizer_fullname = 'WebexMeetings Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='webextestuser').id
        expected_attendee_email = 'webextestuser1@test.webex.com'
        expected_attendees = [{'email': expected_attendee_email}]
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content'
        expected_joinUrl = 'webex/webex.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_passowrd = 'qwer12345'
        expected_invitee_id = 'zxcvbnmasdfghjkl'
        expected_body = {
                'title': expected_subject,
                'start': expected_startDatetime,
                'end': expected_endDatetime,
                'agenda': expected_content,
                'invitees': expected_attendees,
            }
        mock_api_create_webex_meeting.side_effect = HTTPError(401)
        mock_get_invitees.return_value = [{
                    'email': expected_attendee_email,
                    'id': expected_invitee_id
                }]

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')

        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()
        MeetingsAttendeesRelation.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.api_update_webex_meeting_attendees')
    @mock.patch('addons.webexmeetings.utils.api_update_webex_meeting')
    def test_webexmeetings_request_api_update(self, mock_api_update_webex_meeting, mock_api_update_webex_meeting_attendees):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        createEmailAddress = 'webextestuser2@test.webex.com'
        createDisplayName = 'Webex Test User2'
        expected_action = 'update'
        expected_UpdateMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_DeleteMeetinId = ''

        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        AttendeesFactory2 = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account, user_guid='webextestuser2', fullname='WEBEX TEST USER 2', email_address=createEmailAddress, display_name=createDisplayName)
        MeetingsFactory = WebexMeetingsMeetingsFactory(node_settings=self.node_settings, external_account=self.external_account)

        deleteInviteeId = 'zxcvbnmasdfghjkl'

        meeting = Meetings.objects.get(meetingid=expected_UpdateMeetinId)
        attendeeId = Attendees.objects.get(user_guid='webextestuser').id
        meeting.attendees = [attendeeId]
        meeting.save()

        rel = MeetingsAttendeesRelation(
            attendee_id=attendeeId,
            meeting_id=meeting.id,
            webex_meetings_invitee_id=deleteInviteeId
        )
        rel.save()

        qsMeetings = Meetings.objects.all()
        meetingsJson = json.loads(serializers.serialize('json', qsMeetings, ensure_ascii=False))
        expected_external_id = meetingsJson[0]['fields']['external_account']

        url = self.project.api_url_for('webexmeetings_request_api')

        expected_subject = 'My Test Meeting EDIT'
        expected_organizer = 'webextestuser1@test.webex.com'
        expected_organizer_fullname = 'WebexMeetings Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='webextestuser2').id
        deleteEmailAddress = 'webextestuser1@test.webex.com'


        expected_attendees = [{'email': createEmailAddress}]
        createInviteeId = '1234565678'
        createdInvitees = [{'email': createEmailAddress, 'id': createInviteeId}]

        deletedInvitees = [deleteInviteeId]
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content EDIT'
        expected_joinUrl = 'webex/webex.com/321'
        expected_passowrd = 'qwer12345'
        expected_body = {
                'title': expected_subject,
                'start': expected_startDatetime,
                'end': expected_endDatetime,
                'agenda': expected_content,
                'invitees': expected_attendees,
            }

        mock_api_update_webex_meeting.return_value = {
            'id': expected_UpdateMeetinId,
            'title': expected_subject,
            'start': expected_startDatetime,
            'end': expected_endDatetime,
            'agenda': expected_content,
            'hostMail': 'webextestorganizer@test.webex.com',
            'webLink': expected_joinUrl,
            'password': expected_passowrd
        }

        mock_api_update_webex_meeting_attendees.return_value = {
            'created': [{'email': createEmailAddress, 'id': createInviteeId}],
            'deleted': [deleteInviteeId]
        }

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
            'created': createdInvitees,
            'deleted': deletedInvitees,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.get(meetingid=expected_UpdateMeetinId)
        relationResult = MeetingsAttendeesRelation.objects.get(webex_meetings_invitee_id=createInviteeId)

        expected_startDatetime_format = date_parse.parse(expected_startDatetime).strftime('%Y/%m/%d %H:%M:%S')
        expected_endDatetime_format = date_parse.parse(expected_endDatetime).strftime('%Y/%m/%d %H:%M:%S')

        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.start_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_startDatetime_format)
        assert_equals(result.end_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_endDatetime_format)
        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_UpdateMeetinId)
        assert_equals(result.meeting_password, expected_passowrd)
        assert_equals(result.app_name, webexmeetings_settings.WEBEX_MEETINGS)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson, {})
        assert_equals(len(result.attendees.all()), 1)
        assert_equals(result.attendees.all()[0].id, expected_attendees_id)
        assert_equals(result.external_account.id, expected_external_id)
        assert_equals(relationResult.meeting_id, result.id)
        assert_equals(relationResult.attendee_id, expected_attendees_id)
        assert_equals(relationResult.webex_meetings_invitee_id, createInviteeId)

        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.api_update_webex_meeting_attendees')
    @mock.patch('addons.webexmeetings.utils.api_update_webex_meeting')
    def test_webexmeetings_request_api_update_401(self, mock_api_update_webex_meeting, mock_api_update_webex_meeting_attendees):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        createEmailAddress = 'webextestuser2@test.webex.com'
        createDisplayName = 'Webex Test User2'
        expected_action = 'update'
        expected_UpdateMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_DeleteMeetinId = ''

        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account)
        AttendeesFactory2 = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, external_account=self.external_account, user_guid='webextestuser2', fullname='WEBEX TEST USER 2', email_address=createEmailAddress, display_name=createDisplayName)
        MeetingsFactory = WebexMeetingsMeetingsFactory(node_settings=self.node_settings, external_account=self.external_account)

        deleteInviteeId = 'zxcvbnmasdfghjkl'

        meeting = Meetings.objects.get(meetingid=expected_UpdateMeetinId)
        attendeeId = Attendees.objects.get(user_guid='webextestuser').id
        meeting.attendees = [attendeeId]
        meeting.save()

        rel = MeetingsAttendeesRelation(
            attendee_id=attendeeId,
            meeting_id=meeting.id,
            webex_meetings_invitee_id=deleteInviteeId
        )
        rel.save()

        qsMeetings = Meetings.objects.all()
        meetingsJson = json.loads(serializers.serialize('json', qsMeetings, ensure_ascii=False))
        expected_external_id = meetingsJson[0]['fields']['external_account']

        url = self.project.api_url_for('webexmeetings_request_api')

        expected_subject = 'My Test Meeting EDIT'
        expected_organizer = 'webextestuser1@test.webex.com'
        expected_organizer_fullname = 'WebexMeetings Fake User'
        expected_attendees_id = Attendees.objects.get(user_guid='webextestuser2').id
        deleteEmailAddress = 'webextestuser1@test.webex.com'


        expected_attendees = [{'email': createEmailAddress}]
        createInviteeId = '1234565678'
        createdInvitees = [{'email': createEmailAddress, 'id': createInviteeId}]

        deletedInvitees = [deleteInviteeId]
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = (datetime.now() + timedelta(hours=1)).isoformat()
        expected_content = 'My Test Content EDIT'
        expected_joinUrl = 'webex/webex.com/321'
        expected_passowrd = 'qwer12345'
        expected_body = {
                'title': expected_subject,
                'start': expected_startDatetime,
                'end': expected_endDatetime,
                'agenda': expected_content,
                'invitees': expected_attendees,
            }

        mock_api_update_webex_meeting.side_effect = HTTPError(401)
        mock_api_update_webex_meeting_attendees.return_value = {
            'created': [{'email': createEmailAddress, 'id': createInviteeId}],
            'deleted': [deleteInviteeId]
        }

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
            'created': createdInvitees,
            'deleted': deletedInvitees,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')
        #clear
        Attendees.objects.all().delete()
        Meetings.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.api_delete_webex_meeting')
    def test_webexmeetings_request_api_delete(self, mock_api_delete_webex_meeting):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        mock_api_delete_webex_meeting.return_value = {}

        expected_action = 'delete'
        MeetingsFactory = WebexMeetingsMeetingsFactory(node_settings=self.node_settings)

        url = self.project.api_url_for('webexmeetings_request_api')

        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = 'qwertyuiopasdfghjklzxcvbnm'

        expected_body = {
                'title': '',
                'start': '',
                'end': '',
                'agenda': '',
                'invitees': [],
            }

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

        #clear
        Meetings.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.api_delete_webex_meeting')
    def test_webexmeetings_request_api_delete_401(self, mock_api_delete_webex_meeting):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        mock_api_delete_webex_meeting.side_effect = HTTPError(401)
        expected_action = 'delete'
        MeetingsFactory = WebexMeetingsMeetingsFactory(node_settings=self.node_settings)

        url = self.project.api_url_for('webexmeetings_request_api')

        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = 'qwertyuiopasdfghjklzxcvbnm'

        expected_body = {
                'title': '',
                'start': '',
                'end': '',
                'agenda': '',
                'invitees': [],
            }

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')

        #clear
        Meetings.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.api_get_webex_meetings_username')
    def test_webexmeetings_register_email_create(self, mock_api_get_webex_meetings_username):
        mock_api_get_webex_meetings_username.return_value = 'Webex Test User A'
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']
        url = self.project.api_url_for('webexmeetings_register_email')

        _id = None
        expected_guid = osfUserGuid
        expected_email = 'webextestusera@test.webex.com'
        expected_username = mock_api_get_webex_meetings_username.return_value
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

        rvBodyJson = json.loads(rv.body)

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

    @mock.patch('addons.webexmeetings.utils.api_get_webex_meetings_username')
    def test_webexmeetings_register_email_create_outside(self, mock_api_get_webex_meetings_username):
        mock_api_get_webex_meetings_username.return_value = ''
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']
        url = self.project.api_url_for('webexmeetings_register_email')
        _id = None
        expected_guid = osfUserGuid
        expected_email = 'webextestusera@test.webex.com'
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
        rvBodyJson = json.loads(rv.body)
        result = Attendees.objects.all()
        assert_equals(len(result), 0)
        assert_equals(rvBodyJson['result'], 'outside_email')
        assert_equals(rvBodyJson['regAuto'], True)

    @mock.patch('addons.webexmeetings.utils.api_get_webex_meetings_username')
    def test_webexmeetings_register_email_update(self, mock_api_get_webex_meetings_username):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']

        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, user_guid=osfUserGuid)
        mock_api_get_webex_meetings_username.return_value = 'Webex Test User B EDIT'
        url = self.project.api_url_for('webexmeetings_register_email')

        qsAttendees = Attendees.objects.all()
        attendeesJson = json.loads(serializers.serialize('json', qsAttendees, ensure_ascii=False))
        expected_external_id = attendeesJson[0]['fields']['external_account']

        expected_id = AttendeesFactory._id
        expected_guid = AttendeesFactory.user_guid
        expected_email = 'webextestuserbedit@test.webex.com'
        expected_username = mock_api_get_webex_meetings_username.return_value
        expected_is_guest = False
        expected_has_grdm_account = True
        expected_fullname = osfUser.fullname
        expected_actionType = 'update'
        expected_emailType = True
        expected_regAuto = False

        rv = self.app.post_json(url, {
            '_id': expected_id,
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

        expected_newAttendee = {
            'guid': expected_guid,
            'dispName': expected_fullname,
            'fullname': expected_fullname,
            'email': '',
            'institution': '',
            'appUsername': expected_username,
            'appEmail': expected_email,
            'profile': '',
            '_id': '',
            'is_guest': expected_is_guest,
        }

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
        assert_equals(rvBodyJson['regAuto'], expected_regAuto)
        assert_equals(rvBodyJson['newAttendee'], {})

        #clear
        Attendees.objects.all().delete()

    @mock.patch('addons.webexmeetings.utils.api_get_webex_meetings_username')
    def test_webexmeetings_register_email_update_outside(self, mock_api_get_webex_meetings_username):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        osfUser = OSFUser.objects.get(username=self.user.username)
        osfGuids = osfUser._prefetched_objects_cache['guids'].only()
        osfGuidsSerializer = serializers.serialize('json', osfGuids, ensure_ascii=False)
        osfGuidsJson = json.loads(osfGuidsSerializer)
        osfUserGuid = osfGuidsJson[0]['fields']['_id']

        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings, user_guid=osfUserGuid)
        mock_api_get_webex_meetings_username.return_value = ''
        url = self.project.api_url_for('webexmeetings_register_email')

        qsAttendees = Attendees.objects.all()
        attendeesJson = json.loads(serializers.serialize('json', qsAttendees, ensure_ascii=False))
        expected_external_id = attendeesJson[0]['fields']['external_account']

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
            'email': expected_email,
            'is_guest': expected_is_guest,
            'has_grdm_account': expected_has_grdm_account,
            'actionType': expected_actionType,
            'emailType': expected_emailType,
            'regAuto': expected_regAuto
        }, auth=self.user.auth)

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
        assert_equals(rvBodyJson['result'], 'outside_email')
        assert_equals(rvBodyJson['regAuto'], expected_regAuto)

        #clear
        Attendees.objects.all().delete()

    def test_webexmeetings_register_email_delete(self):
        AttendeesFactory = WebexMeetingsAttendeesFactory(node_settings=self.node_settings)
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.project.api_url_for('webexmeetings_register_email')

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

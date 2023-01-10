# -*- coding: utf-8 -*-
import mock
import pytest
import json
import addons.zoommeetings.settings as zoommeetings_settings
from requests.exceptions import HTTPError
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
from addons.zoommeetings.tests.utils import ZoomMeetingsAddonTestCase, MockResponse
from website.util import api_url_for
from admin.rdm_addons.utils import get_rdm_addon_option
from datetime import date, datetime, timedelta
from dateutil import parser as date_parse
from addons.zoommeetings.models import (
    UserSettings,
    NodeSettings,
    Meetings
)
from osf.models import ExternalAccount, OSFUser, RdmAddonOption, BaseFileNode, AbstractNode, Comment
from addons.zoommeetings.tests.factories import (
    ZoomMeetingsUserSettingsFactory,
    ZoomMeetingsNodeSettingsFactory,
    ZoomMeetingsAccountFactory,
    ZoomMeetingsMeetingsFactory
)
from api_tests import utils as api_utils

import logging
logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db

class TestZoomMeetingsViews(ZoomMeetingsAddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
    def setUp(self):
        super(TestZoomMeetingsViews, self).setUp()

    def tearDown(self):
        super(TestZoomMeetingsViews, self).tearDown()

    def test_zoommeetings_remove_node_settings_owner(self):
        url = self.node_settings.owner.api_url_for('zoommeetings_deauthorize_node')
        self.app.delete(url, auth=self.user.auth)
        result = self.Serializer().serialize_settings(node_settings=self.node_settings, current_user=self.user)
        assert_equal(result['nodeHasAuth'], False)

    def test_zoommeetings_remove_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('zoommeetings_deauthorize_node')
        ret = self.app.delete(url, auth=None, expect_errors=True)

        assert_equal(ret.status_code, 401)

    def test_zoommeetings_get_node_settings_owner(self):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.node_settings.owner.api_url_for('zoommeetings_get_config')
        res = self.app.get(url, auth=self.user.auth)

        result = res.json['result']
        assert_equal(result['nodeHasAuth'], True)
        assert_equal(result['userIsOwner'], True)

    def test_zoommeetings_get_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('zoommeetings_get_config')
        unauthorized = AuthUserFactory()
        ret = self.app.get(url, auth=unauthorized.auth, expect_errors=True)

        assert_equal(ret.status_code, 403)

    @mock.patch('addons.zoommeetings.utils.api_create_zoom_meeting')
    def test_zoommeetings_request_api_create(self, mock_api_create_zoom_meeting):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        url = self.project.api_url_for('zoommeetings_request_api')

        expected_action = 'create'
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = ''

        expected_subject = 'My Test Meeting'
        expected_organizer = 'zoomtestuser1@test.zoom.com'
        expected_organizer_fullname = 'ZoomMeetings Fake User'
        expected_startDatetime = date_parse.parse(datetime.now().isoformat())
        expected_duration = 60
        expected_endDatetime = expected_startDatetime + timedelta(minutes=expected_duration)
        expected_content = 'My Test Content'
        expected_contentExtract = expected_content
        expected_joinUrl = 'zoom/zoom.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_body = {
                'topic': expected_subject,
                'start_time': str(expected_startDatetime),
                'duration': expected_duration,
                'agenda': expected_content,
                'timezone': 'UTC',
                'type':2
            };

        mock_api_create_zoom_meeting.return_value = {
            'id': expected_meetingId,
            'topic': expected_subject,
            'host_email': expected_organizer,
            'start_time': str(expected_startDatetime),
            'duration': expected_duration,
            'agenda': expected_content,
            'bodyPreview': expected_content,
            'host_email': 'zoomtestuser1@test.zoom.com',
            'join_url': expected_joinUrl
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

        expected_startDatetime_format = date_parse.parse(expected_startDatetime.isoformat()).strftime('%Y/%m/%d %H:%M:%S')
        expected_endDatetime_format = date_parse.parse(expected_endDatetime.isoformat()).strftime('%Y/%m/%d %H:%M:%S')

        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.start_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_startDatetime_format)
        assert_equals(result.end_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_endDatetime_format)
        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_meetingId)
        assert_equals(result.app_name, zoommeetings_settings.ZOOM_MEETINGS)
        assert_equals(result.external_account.id, self.external_account.id)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson, {})

        #clear
        Meetings.objects.all().delete()

    @mock.patch('addons.zoommeetings.utils.api_create_zoom_meeting')
    def test_zoommeetings_request_api_create_401(self, mock_api_create_zoom_meeting):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.project.api_url_for('zoommeetings_request_api')
        expected_action = 'create'
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = ''
        expected_subject = 'My Test Meeting'
        expected_organizer = 'zoomtestuser1@test.zoom.com'
        expected_organizer_fullname = 'ZoomMeetings Fake User'
        expected_startDatetime = date_parse.parse(datetime.now().isoformat())
        expected_duration = 60
        expected_endDatetime = expected_startDatetime + timedelta(minutes=expected_duration)
        expected_content = 'My Test Content'
        expected_contentExtract = expected_content
        expected_joinUrl = 'zoom/zoom.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_body = {
                'topic': expected_subject,
                'start_time': str(expected_startDatetime),
                'duration': expected_duration,
                'agenda': expected_content,
                'timezone': 'UTC',
                'type':2
            };
        mock_api_create_zoom_meeting.side_effect = HTTPError(401)
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
        Meetings.objects.all().delete()

    @mock.patch('addons.zoommeetings.utils.api_update_zoom_meeting')
    def test_zoommeetings_request_api_update(self, mock_api_update_zoom_meeting):

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        MeetingsFactory = ZoomMeetingsMeetingsFactory(node_settings=self.node_settings)

        url = self.project.api_url_for('zoommeetings_request_api')

        qsMeetings = Meetings.objects.all()
        meetingsJson = json.loads(serializers.serialize('json', qsMeetings, ensure_ascii=False))
        expected_external_id = meetingsJson[0]['fields']['external_account']
        expected_action = 'update'
        expected_UpdateMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_DeleteMeetinId = ''

        expected_subject = 'My Test Meeting EDIT'
        expected_organizer = 'zoomtestuser1@test.zoom.com'
        expected_organizer_fullname = 'ZoomMeetings Fake User'

        expected_startDatetime = date_parse.parse(datetime.now().isoformat())
        expected_duration = 60
        expected_endDatetime = expected_startDatetime + timedelta(minutes=expected_duration)
        expected_content = 'My Test Content EDIT'
        expected_contentExtract = expected_content
        expected_joinUrl = 'zoom/zoom.com/321'
        expected_body = {
                'topic': expected_subject,
                'start_time': str(expected_startDatetime),
                'duration': expected_duration,
                'agenda': expected_content,
                'timezone': 'UTC',
                'type':2
            };

        mock_api_update_zoom_meeting.return_value = {}

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'updateMeetingId': expected_UpdateMeetinId,
            'deleteMeetingId': expected_DeleteMeetinId,
            'contentExtract': expected_contentExtract,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.get(meetingid=expected_UpdateMeetinId)

        expected_startDatetime_format = date_parse.parse(expected_startDatetime.isoformat()).strftime('%Y/%m/%d %H:%M:%S')
        expected_endDatetime_format = date_parse.parse(expected_endDatetime.isoformat()).strftime('%Y/%m/%d %H:%M:%S')

        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.start_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_startDatetime_format)
        assert_equals(result.end_datetime.strftime('%Y/%m/%d %H:%M:%S'), expected_endDatetime_format)
        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_UpdateMeetinId)
        assert_equals(result.node_settings.id, self.node_settings.id)
        assert_equals(rvBodyJson, {})
        assert_equals(result.external_account.id, expected_external_id)
        #clear
        Meetings.objects.all().delete()


    @mock.patch('addons.zoommeetings.utils.api_update_zoom_meeting')
    def test_zoommeetings_request_api_update_401(self, mock_api_update_zoom_meeting):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        MeetingsFactory = ZoomMeetingsMeetingsFactory(node_settings=self.node_settings)
        url = self.project.api_url_for('zoommeetings_request_api')
        qsMeetings = Meetings.objects.all()
        meetingsJson = json.loads(serializers.serialize('json', qsMeetings, ensure_ascii=False))
        expected_external_id = meetingsJson[0]['fields']['external_account']
        expected_action = 'update'
        expected_UpdateMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_DeleteMeetinId = ''
        expected_subject = 'My Test Meeting EDIT'
        expected_organizer = 'zoomtestuser1@test.zoom.com'
        expected_organizer_fullname = 'ZoomMeetings Fake User'
        expected_startDatetime = date_parse.parse(datetime.now().isoformat())
        expected_duration = 60
        expected_endDatetime = expected_startDatetime + timedelta(minutes=expected_duration)
        expected_content = 'My Test Content EDIT'
        expected_contentExtract = expected_content
        expected_joinUrl = 'zoom/zoom.com/321'
        expected_body = {
                'topic': expected_subject,
                'start_time': str(expected_startDatetime),
                'duration': expected_duration,
                'agenda': expected_content,
                'timezone': 'UTC',
                'type':2
            };
        mock_api_update_zoom_meeting.side_effect = HTTPError(401)
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
        Meetings.objects.all().delete()

    @mock.patch('addons.zoommeetings.utils.api_delete_zoom_meeting')
    def test_zoommeetings_request_api_delete(self, mock_api_delete_zoom_meeting):

        mock_api_delete_zoom_meeting.return_value = {}

        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()

        expected_action = 'delete'
        MeetingsFactory = ZoomMeetingsMeetingsFactory(node_settings=self.node_settings)

        url = self.project.api_url_for('zoommeetings_request_api')

        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_body = {
                'topic': '',
                'start_time': '',
                'duration': '',
                'agenda': '',
                'timezone': 'UTC',
                'type': 2,
            };

        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'deleteMeetingId': expected_DeleteMeetinId,
            'updateMeetingId': expected_UpdateMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)

        result = Meetings.objects.filter(meetingid=expected_DeleteMeetinId)

        assert_equals(result.count(), 0)
        assert_equals(rvBodyJson, {})

        #clear
        Meetings.objects.all().delete()

    @mock.patch('addons.zoommeetings.utils.api_delete_zoom_meeting')
    def test_zoommeetings_request_api_delete_401(self, mock_api_delete_zoom_meeting):
        mock_api_delete_zoom_meeting.return_value = {}
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        expected_action = 'delete'
        MeetingsFactory = ZoomMeetingsMeetingsFactory(node_settings=self.node_settings)
        url = self.project.api_url_for('zoommeetings_request_api')
        expected_UpdateMeetinId = ''
        expected_DeleteMeetinId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_body = {
                'topic': '',
                'start_time': '',
                'duration': '',
                'agenda': '',
                'timezone': 'UTC',
                'type': 2,
            };
        mock_api_delete_zoom_meeting.side_effect = HTTPError(401)
        rv = self.app.post_json(url, {
            'actionType': expected_action,
            'deleteMeetingId': expected_DeleteMeetinId,
            'updateMeetingId': expected_UpdateMeetinId,
            'body': expected_body,
        }, auth=self.user.auth)
        rvBodyJson = json.loads(rv.body)
        assert_equals(rvBodyJson['errCode'], '401')
        #clear
        Meetings.objects.all().delete()

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

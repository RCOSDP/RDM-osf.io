# -*- coding: utf-8 -*-
from rest_framework import status as http_status

from boto.exception import S3ResponseError
import mock
from nose.tools import (assert_equal, assert_equals,
    assert_true, assert_in, assert_false)
import pytest

from framework.auth import Auth
from tests.base import OsfTestCase, get_default_metaschema
from osf_tests.factories import ProjectFactory, AuthUserFactory, DraftRegistrationFactory, InstitutionFactory

from addons.base.tests.views import (
    OAuthAddonConfigViewsTestCaseMixin
)
from addons.integromat.tests.utils import IntegromatAddonTestCase
import addons.integromat.settings as integromat_settings
from website.util import api_url_for
from admin.rdm_addons.utils import get_rdm_addon_option
from datetime import date, datetime, timedelta
from osf.models.rdm_grdmapps import (
    RdmWebMeetingApps,
    RdmWorkflows
)
from addons.integromat.models import (
    UserSettings,
    NodeSettings,
    WorkflowExecutionMessages,
    Attendees,
    AllMeetingInformation,
    AllMeetingInformationAttendeesRelation,
    NodeWorkflows
)
from addons.integromat.tests.factories import (
    IntegromatUserSettingsFactory,
    IntegromatNodeSettingsFactory,
    IntegromatAccountFactory,
    IntegromatAttendeesFactory,
    IntegromatWorkflowExecutionMessagesFactory
)
from django.core import serializers

pytestmark = pytest.mark.django_db

class TestIntegromatViews(IntegromatAddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
    def setUp(self):
        self.mock_uid = mock.patch('addons.integromat.views.authIntegromat')
        self.mock_uid.return_value = {'id': '1234567890', 'name': 'integromat.user'}
        self.mock_uid.start()
        super(TestIntegromatViews, self).setUp()

    def tearDown(self):
        self.mock_uid.stop()
        super(TestIntegromatViews, self).tearDown()

    def test_integromat_settings_input_empty_access_key(self):
        url = self.project.api_url_for('integromat_add_user_account')
        rv = self.app.post_json(url, {
            'access_token': '',
        }, auth=self.user.auth, expect_errors=True)
        assert_equals(rv.status_int, http_status.HTTP_400_BAD_REQUEST)
        assert_in('All the fields above are required.', rv.body.decode())

    def test_integromat_settings_rdm_addons_denied(self):
        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        rdm_addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = False
        rdm_addon_option.save()
        url = self.project.api_url_for('integromat_add_user_account')
        rv = self.app.post_json(url,{
            'access_token': 'aldkjf',
        }, auth=self.user.auth, expect_errors=True)
        assert_equal(rv.status_int, http_status.HTTP_403_FORBIDDEN)
        assert_in('You are prohibited from using this add-on.', rv.body.decode())

    def test_integromat_remove_node_settings_owner(self):
        url = self.node_settings.owner.api_url_for('integromat_deauthorize_node')
        self.app.delete(url, auth=self.user.auth)
        result = self.Serializer().serialize_settings(node_settings=self.node_settings, current_user=self.user)
        assert_equal(result['nodeHasAuth'], False)

    def test_integromat_remove_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('integromat_deauthorize_node')
        ret = self.app.delete(url, auth=None, expect_errors=True)

        assert_equal(ret.status_code, 401)

    def test_integromat_get_node_settings_owner(self):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.node_settings.owner.api_url_for('integromat_get_config')
        res = self.app.get(url, auth=self.user.auth)

        result = res.json['result']
        assert_equal(result['nodeHasAuth'], True)
        assert_equal(result['userIsOwner'], True)

    def test_integromat_get_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('integromat_get_config')
        unauthorized = AuthUserFactory()
        ret = self.app.get(url, auth=unauthorized.auth, expect_errors=True)

        assert_equal(ret.status_code, 403)

    def test_integromat_api_call(self):
        url = self.project.api_url_for('integromat_api_call')

        res = self.app.get(url, auth=self.user.auth)

        assert_equals(self.user, res.body.email)

    def test_integromat_register_meeting_microsoft_teams(self):
        url = self.project.api_url_for('integromat_register_meeting')

        node_id = 'qwe'
        app_name = 'MicrosoftTeams'

        expected_subject = 'Subject Test'
        expected_organizer = 'testUser3@test.onmicrosoft.com'
        expected_organizer_fullname = 'TEST USER3'
        expected_attendees = ['testUser1@test.onmicrosoft.com']
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = expected_startDatetime + timedelta(hours=1)
        expected_location = 'Location Test'
        expected_content = 'Content Test'
        expected_joinUrl = 'teams/microsoft.com/asd'
        expected_meetingId = '1234567890qwertyuiopasdfghjkl'
        expected_password = ''

        rv = self.app.post_json(url, {
            'nodeId': node_id,
            'appName': app_name,
            'subject': expected_subject,
            'organizer': expected_organizer,
            'attendees': expected_attendees,
            'startDatetime': expected_startDatetime,
            'endDatetime': expected_endDatetime,
            'location': expected_location,
            'content': expected_content,
            'joinUrl': expected_joinUrl,
            'meetingId': expected_meetingId,
            'password': expected_password,
            'meetingInviteesInfo': expected_meetingInviteesInfo,
        }, auth=self.user.auth)

        result = AllMeetingInformation.objects.get(meetingId='1234567890qwertyuiopasdfghjkl')
        expected_attendees_id = Attendees.objects.get(microsoft_teams_mail=expected_attendees[0])
        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.attendees, expected_attendees_id)
        assert_equals(result.start_datetime, expected_startDatetime)
        assert_equals(result.end_datetime, expected_endDatetime)
        assert_equals(result.location, expected_location)
        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_meetingId)
        assert_equals(result.password, expected_password)

        expected_appId = RdmWebMeetingApps.objects.get(app_name=app_name).id
        expected_nodeId = NodeSettings.objects.get(_id=node_id).id

        assert_equals(result.app_id, expected_appId)
        assert_equals(result.node_settings_id, expected_nodeId)

        rResult = AllMeetingInformationAttendeesRelation.objects.all()
        assert_equals(rResult.len, 0)

    def test_integromat_update_meeting_registration_microsoft_teams(self):
        url = self.project.api_url_for('integromat_update_meeting_registration')

        node_id = 'qwe'
        app_name = 'MicrosoftTeams'

        expected_subject = 'Subject Test Update'
        expected_organizer = 'testUser1@test.onmicrosoft.com'
        expected_organizer_fullname = 'TEST USER'
        expected_attendees = []
        expected_startDatetime = datetime.now().isoformat()
        expected_endDatetime = expected_startDatetime + timedelta(hours=1)
        expected_location = 'Location Test Update'
        expected_content = 'Content Test Update'
        expected_meetingId = 'qwertyuiopasdfghjklzxcvbnm'
        expected_meetingCreatedInviteesInfo = ''
        expected_meetingDeletedInviteesInfo = ''

        rv = self.app.post_json(url, {
            'nodeId': node_id,
            'appName': app_name,
            'subject': expected_subject,
            'attendees': expected_attendees,
            'startDatetime': expected_startDatetime,
            'endDatetime': expected_endDatetime,
            'location': expected_location,
            'content': expected_content,
            'meetingId': expected_meetingId,
            'password': expected_password,
            'meetingCreatedInviteesInfo': expected_meetingCreatedInviteesInfo,
            'meetingDeletedInviteesInfo': expected_meetingDeletedInviteesInfo,
        }, auth=self.user.auth)

        result = AllMeetingInformation.objects.get(meetingId='qwertyuiopasdfghjklzxcvbnm')
        assert_equals(result.subject, expected_subject)
        assert_equals(result.organizer, expected_organizer)
        assert_equals(result.organizer_fullname, expected_organizer_fullname)
        assert_equals(result.attendees, expected_attendees)
        assert_equals(result.start_datetime, expected_startDatetime)
        assert_equals(result.end_datetime, expected_endDatetime)
        assert_equals(result.location, expected_location)
        assert_equals(result.content, expected_content)
        assert_equals(result.join_url, expected_joinUrl)
        assert_equals(result.meetingid, expected_meetingId)
        assert_equals(result.password, expected_password)

        expected_appId = RdmWebMeetingApps.objects.get(app_name=app_name).id
        expected_nodeId = NodeSettings.objects.get(_id=node_id).id

        assert_equals(result.app_id, expected_appId)
        assert_equals(result.node_settings_id, expected_nodeId)

        rResult = AllMeetingInformationAttendeesRelation.objects.all()
        assert_equals(rResult.len, 0)

    def test_integromat_delete_meeting_registration(self):
        url = self.project.api_url_for('integromat_delete_meeting_registration')

        expected_meetingId = 'qwertyuiopasdfghjklzxcvbnm'

        rv = self.app.post_json(url, {
            'meetingId': expected_meetingId,
        }, auth=self.user.auth)

        result = AllMeetingInformation.objects.filter(meetingId='qwertyuiopasdfghjklzxcvbnm')

        assert_equals(result.count(), 0)

    def test_integromat_get_meetings(self):
        url = self.project.api_url_for('integromat_get_meetings')

        resJson = self.app.get(url, auth=self.user.auth)
        expectedQuery = AllMeetingInformation.objects.all()
        expectedJson = serializers.serialize('json', expectedQuery, ensure_ascii=False)

        assert_equals(resJson.recentMeetings, expectedJson)

    def test_integromat_register_web_meeting_apps_email_register(self):
        url = self.project.api_url_for('integromat_register_web_meeting_apps_email')

        expected_guid = '123as'
        appName = 'MicrosoftTeams'
        expected_email = 'testUser4@test.onmicrosoft.com'
        expected_username = 'Teams User4'
        expected_is_guest = False

        rv = self.app.post_json(url, {
            'appName': appName,
            'guid': expected_guid,
            'email': expected_email,
            'username': expected_username,
            'is_guest': expected_is_guest,
        }, auth=self.user.auth)

        result = Attendees.objects.get(user_guid='123as')
        expected_fullname = Attendees.objects.get(user_guid='123as').fullname

        assert_equals(result.fullname, expected_fullname)
        assert_equals(result.microsoft_teams_mail, expected_email)
        assert_equals(result.microsoft_teams_user_name, expected_username)
        assert_equals(result.webex_meetings_mail, None)
        assert_equals(result.webex_meetings_display_name, None)
        assert_equals(result.is_guest, expected_is_guest)

    def test_integromat_register_web_meeting_apps_email_update(self):
        url = self.project.api_url_for('integromat_register_web_meeting_apps_email')

        _id = '1234567890qwertyuiop'
        expected_guid = 'testuser'
        appName = 'MicrosoftTeams'
        expected_email = 'testUser4update@test.onmicrosoft.com'
        expected_username = 'Teams User4 update'
        expected_is_guest = False

        rv = self.app.post_json(url, {
            '_id': _id,
            'appName': appName,
            'guid': expected_guid,
            'email': expected_email,
            'username': expected_username,
            'is_guest': expected_is_guest,
        }, auth=self.user.auth)

        result = Attendees.objects.get(user_guid='testuser')
        expected_fullname = Attendees.objects.get(user_guid='testuser').fullname

        assert_equals(result.fullname, expected_fullname)
        assert_equals(result.microsoft_teams_mail, expected_email)
        assert_equals(result.microsoft_teams_user_name, expected_username)
        assert_equals(result.webex_meetings_mail, None)
        assert_equals(result.webex_meetings_display_name, None)
        assert_equals(result.is_guest, expected_is_guest)

    def test_integromat_register_web_meeting_apps_email_guest_update(self):
        url = self.project.api_url_for('integromat_register_web_meeting_apps_email')

        _id = '0987654321poiuytrewq'
        appName = 'MicrosoftTeams'
        fullname = 'Guest User2'
        origin_email = 'testUser5@guest.com'
        origin_username = 'Teams Guest User5'
        origin_is_guest = True

        IntegromatAttendeesFactory(_id='0987654321poiuytrewq', fullname=fullname, microsoft_teams_mail=origin_email, microsoft_teams_user_name=origin_username, is_guest=is_guest)

        expected_email = 'testUser5Update@guest.com'
        expected_username = 'Teams Guest User5 Update'
        expected_is_guest = True

        rv = self.app.post_json(url, {
            '_id': _id,
            'appName': appName,
            'guid': None,
            'email': expected_email,
            'username': expected_username,
            'is_guest': expected_is_guest,
        }, auth=self.user.auth)

        result = Attendees.objects.get(_id=_id)
        expected_fullname = Attendees.objects.get(_id=_id).fullname

        assert_equals(result.fullname, expected_fullname)
        assert_equals(result.microsoft_teams_mail, expected_email)
        assert_equals(result.microsoft_teams_user_name, expected_username)
        assert_equals(result.webex_meetings_mail, None)
        assert_equals(result.webex_meetings_display_name, None)
        assert_equals(result.is_guest, expected_is_guest)

    def test_integromat_start_scenario(self):
        url = self.project.api_url_for('integromat_start_scenario')

        node_id = 'qwe'
        expected_timestamp = '1234567890123'
        expected_webhook_url = 'https://hook.integromat.com/xyz'

        rv = self.app.post_json(url, {
            'node_id': 'qwe',
            'timestamp': expected_timestamp,
            'webhook_url': expected_webhook_url,
        }, auth=self.user.auth)

        assert_equals(rv.timestamp, expected_timestamp)

    def test_integromat_req_next_msg(self):
        url = self.project.api_url_for('integromat_req_next_msg')

        expected_timestamp = '1234567890123'
        count = 1
        expected_integromatMsg = 'integromat.info.message'

        rv = self.app.post_json(url, {
            'timestamp': expected_timestamp,
            'count': count,
        }, auth=self.user.auth)

        assert_equals(rv.integromatMsg, expected_integromatMsg)
        assert_equals(rv.timestamp, expected_timestamp)
        assert_equals(rv.notify, True)
        assert_equals(rv.count, count)

    def test_integromat_req_next_msg_scenario_did_not_start(self):
        url = self.project.api_url_for('integromat_req_next_msg')

        expected_timestamp = '1234567890123'
        count = 15
        expected_integromatMsg = 'integromat.error.didNotStart'

        rv = self.app.post_json(url, {
            'timestamp': expected_timestamp,
            'count': count,
        }, auth=self.user.auth)

        assert_equals(rv.integromatMsg, expected_integromatMsg)
        assert_equals(rv.timestamp, expected_timestamp)
        assert_equals(rv.notify, True)
        assert_equals(rv.count, count)

    def test_integromat_info_msg(self):
        url = self.project.api_url_for('integromat_info_msg')

        expected_notifyType = 'integromat.info.notify'
        expected_timestamp = '0987654321098'

        rv = self.app.post_json(url, {
            'notifyType': expected_notifyType,
            'timestamp': expected_timestamp,
        }, auth=self.user.auth)

        result = workflowExecutionMessages.objects.get(timestamp='0987654321098')

        assert_equals(result.integromat_msg, expected_notifyType)
        assert_equals(result.timestamp, expected_timestamp)

    def test_integromat_error_msg(self):
        url = self.project.api_url_for('integromat_error_msg')

        expected_notifyType = 'integromat.error.notify'
        expected_timestamp = '6789012345678'

        rv = self.app.post_json(url, {
            'notifyType': expected_notifyType,
            'timestamp': expected_timestamp,
        }, auth=self.user.auth)

        result = workflowExecutionMessages.objects.get(timestamp='6789012345678')

        assert_equals(result.integromat_msg, expected_notifyType)
        assert_equals(result.timestamp, expected_timestamp)

    def test_integromat_register_alternative_webhook_url(self):
        url = self.project.api_url_for('integromat_register_alternative_webhook_url')

        workflowDescription = 'integromat.test.workflows.web_meeting.description'
        expected_alternativeWebhookUrl = 'hook/integromat/com/test'

        rv = self.app.post_json(url, {
            'workflowDescription': workflowDescription,
            'alternativeWebhookUrl': expected_alternativeWebhookUrl,
        }, auth=self.user.auth)
        workflow = RdmWorkflows.objects.get(workflow_description=workflowDescription)
        result = workflowExecutionMessages.objects.get(node_settings_id=nodeId, workflow_id=workflow.id)

        assert_equals(result.alternative_webhook_url, expected_alternativeWebhookUrl)
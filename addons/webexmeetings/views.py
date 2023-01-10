# -*- coding: utf-8 -*-
from flask import request
import logging
import json
import time
from addons.webexmeetings import SHORT_NAME
from addons.base import generic_views
from framework.auth.decorators import must_be_logged_in
from addons.webexmeetings.serializer import WebexMeetingsSerializer
from addons.webexmeetings import settings
from osf.models import ExternalAccount, OSFUser
from osf.utils.permissions import WRITE
from website.project.decorators import (
    must_have_addon,
    must_be_valid_project,
    must_have_permission,
)
from admin.rdm_addons.decorators import must_be_rdm_addons_allowed
from addons.webexmeetings import models
from addons.webexmeetings import utils
from website.oauth.utils import get_service
from requests.exceptions import HTTPError
from django.db import transaction
logger = logging.getLogger(__name__)

webexmeetings_account_list = generic_views.account_list(
    SHORT_NAME,
    WebexMeetingsSerializer
)

webexmeetings_get_config = generic_views.get_config(
    SHORT_NAME,
    WebexMeetingsSerializer
)

webexmeetings_import_auth = generic_views.import_auth(
    SHORT_NAME,
    WebexMeetingsSerializer
)

webexmeetings_deauthorize_node = generic_views.deauthorize_node(
    SHORT_NAME
)

# Overrides oauth_connect
@must_be_logged_in
@must_be_rdm_addons_allowed(SHORT_NAME)
def webexmeetings_oauth_connect(auth, **kwargs):
    provider = get_service(SHORT_NAME)
    authorization_url = provider.get_authorization_url(provider.client_id)

    return authorization_url

@must_be_valid_project
@must_have_permission(WRITE)
@must_have_addon(SHORT_NAME, 'node')
def webexmeetings_request_api(**kwargs):
    auth = kwargs['auth']
    user = auth.user
    requestData = request.get_data()
    requestDataJsonLoads = json.loads(requestData)
    logger.info('{} API will be requested with following attribute by {}=> '.format(settings.WEBEX_MEETINGS, str(user)) + str(requestDataJsonLoads))

    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    account_id = addon.external_account_id
    action = requestDataJsonLoads['actionType']
    updateMeetingId = requestDataJsonLoads['updateMeetingId']
    deleteMeetingId = requestDataJsonLoads['deleteMeetingId']
    requestBody = requestDataJsonLoads['body']

    account = ExternalAccount.objects.get(
        provider='webexmeetings', id=account_id
    )

    if action == 'create':
        try:
            createdMeeting = utils.api_create_webex_meeting(requestBody, account)
            #synchronize data
            utils.grdm_create_webex_meeting(addon, account, createdMeeting)
        except HTTPError as e1:
            logger.info(str(e1))
            errCode = str(e1) if e1.response is None else e1.response.status_code
            return {
                'errCode': errCode,
            }

    if action == 'update':
        try:
            updatedMeeting = utils.api_update_webex_meeting(updateMeetingId, requestBody, account)
            updatedAttendees = utils.api_update_webex_meeting_attendees(requestDataJsonLoads, account)
            #synchronize data
            utils.grdm_update_webex_meeting(updatedAttendees, updatedMeeting, addon)
        except HTTPError as e1:
            logger.info(str(e1))
            errCode = str(e1) if e1.response is None else e1.response.status_code
            return {
                'errCode': errCode,
            }

    if action == 'delete':
        try:
            utils.api_delete_webex_meeting(deleteMeetingId, account)
            #synchronize data
            utils.grdm_delete_webex_meeting(deleteMeetingId)
        except HTTPError as e1:
            logger.info(str(e1))
            errCode = str(e1) if e1.response is None else e1.response.status_code
            return {
                'errCode': errCode,
            }

    return {}

@must_be_valid_project
@must_have_permission(WRITE)
@must_have_addon(SHORT_NAME, 'node')
def webexmeetings_register_email(**kwargs):
    auth = kwargs['auth']
    user = auth.user
    requestData = request.get_data()
    requestDataJson = json.loads(requestData)
    actionType = requestDataJson.get('actionType', '')
    logger.info('{} Email will be {}d with following attribute by {} => '.format(settings.WEBEX_MEETINGS, str(actionType), str(user)) + str(requestDataJson))

    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    account_id = addon.external_account_id
    account = ExternalAccount.objects.get(
        provider=SHORT_NAME, id=account_id
    )
    _id = requestDataJson.get('_id', '')
    guid = requestDataJson.get('guid', '')
    fullname = requestDataJson.get('fullname', '')
    email = requestDataJson.get('email', '')
    is_guest = requestDataJson.get('is_guest', True)
    has_grdm_account = requestDataJson.get('has_grdm_account', False)
    regAuto = requestDataJson.get('regAuto', False)
    displayName = ''
    result = ''
    nodeSettings = models.NodeSettings.objects.get(_id=addon._id)
    newAttendee = {}

    if actionType == 'create':
        if regAuto:
            if models.Attendees.objects.filter(node_settings_id=nodeSettings.id, external_account_id=account_id, email_address=email, is_active=True).exists():
                logger.info('{} Email({}) was duplicated when {} in node:{}, external:{}'.format(settings.WEBEX_MEETINGS, str(email), str(actionType), str(nodeSettings.id), str(account_id)))
                return {
                    'result': 'duplicated_email',
                    'regAuto': regAuto,
                }
        if is_guest:
            displayName = utils.api_get_webex_meetings_username(account, email)
            if not displayName:
                displayName = fullname
            else:
                is_guest = False
        else:
            displayName = utils.api_get_webex_meetings_username(account, email)
            if not displayName:
                logger.info('{} Email({}) was outside when {}. '.format(settings.WEBEX_MEETINGS, str(email), str(actionType)))
                return {
                    'result': 'outside_email',
                    'regAuto': regAuto,
                }

        attendee = models.Attendees(
            user_guid=guid,
            fullname=fullname,
            is_guest=is_guest,
            has_grdm_account=has_grdm_account,
            email_address=email,
            display_name=displayName,
            external_account=account,
            node_settings=nodeSettings,
        )
        attendee.save()

        newAttendee = {
            'guid': guid,
            'dispName': fullname,
            'fullname': fullname,
            'email': email,
            'institution': '',
            'appUsername': displayName,
            'appEmail': email,
            'profile': '',
            '_id': '',
            'is_guest': is_guest,
        }

    elif actionType == 'update':
        if models.Attendees.objects.filter(node_settings_id=nodeSettings.id, _id=_id).exists():
            attendee = models.Attendees.objects.get(node_settings_id=nodeSettings.id, _id=_id)

        if is_guest:
            displayName = utils.api_get_webex_meetings_username(account, email)
            if not displayName:
                displayName = fullname
            else:
                is_guest = False
        else:
            displayName = utils.api_get_webex_meetings_username(account, email)
            if not displayName:
                logger.info('{} Email({}) was outside when {}.'.format(settings.WEBEX_MEETINGS, str(email), str(actionType)))
                return {
                    'result': 'outside_email',
                    'regAuto': regAuto,
                }
        if has_grdm_account:
            fullname = OSFUser.objects.get(guids___id=attendee.user_guid).fullname

        attendee.fullname = fullname
        attendee.email_address = email
        attendee.display_name = displayName
        attendee.is_guest = is_guest
        attendee.save()

    elif actionType == 'delete':
        attendee = models.Attendees.objects.get(node_settings_id=nodeSettings.id, _id=_id)
        timestamp = int(time.time())
        attendee.is_active = False
        attendee.email_address = '{}{}{}'.format(attendee.email_address, '_', timestamp)
        attendee.save()

    logger.info('{} Email was {}d with following attribute by {} => '.format(settings.WEBEX_MEETINGS, str(actionType), str(user)) + str(vars(attendee)))

    return {
        'result': result,
        'regAuto': regAuto,
        'newAttendee': newAttendee,
    }

@must_be_valid_project
@must_have_permission(WRITE)
@must_have_addon(SHORT_NAME, 'node')
def webexmeetings_register_contributors_email(**kwargs):
    auth = kwargs['auth']
    user = auth.user
    requestData = request.get_data()
    unregisteredContribs = json.loads(requestData)
    logger.info('{} Email will be created with following attribute by {} => '.format(settings.WEBEX_MEETINGS, str(user)) + str(unregisteredContribs))

    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    account_id = addon.external_account_id
    account = ExternalAccount.objects.get(
        provider=SHORT_NAME, id=account_id
    )

    nodeSettings = models.NodeSettings.objects.get(_id=addon._id)
    canNotRegister = ''
    registered = []

    for unregisteredContrib in unregisteredContribs:
        guid = unregisteredContrib.get('guid', '')
        email = unregisteredContrib.get('email', '')
        fullname = unregisteredContrib.get('fullname', '')
        try:
            with transaction.atomic():
                attendee = models.Attendees(
                    user_guid=guid,
                    fullname=fullname,
                    is_guest=True,
                    has_grdm_account=True,
                    email_address=email,
                    display_name=fullname,
                    external_account=account,
                    node_settings=nodeSettings,
                )
                attendee.save()
                newAttendee = {
                    'guid': guid,
                    'dispName': fullname,
                    'fullname': fullname,
                    'email': email,
                    'institution': '',
                    'appUsername': fullname,
                    'appEmail': email,
                    'profile': '',
                    '_id': '',
                    'is_guest': True,
                }
                registered.append(newAttendee)
                logger.info('{} Email was created with following attribute by {} => '.format(settings.WEBEX_MEETINGS, str(user)) + str(vars(attendee)))
        except Exception as e:
            logger.info(str(e))
            canNotRegister += fullname
            canNotRegister += ','
    return {
        'result': registered,
        'canNotRegister': canNotRegister[:-1],
    }

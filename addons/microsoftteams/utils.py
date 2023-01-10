# -*- coding: utf-8 -*-
import json
import requests
import pytz
import dateutil.parser
from addons.microsoftteams import models
from addons.microsoftteams import settings
import logging
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
logger = logging.getLogger(__name__)

# widget: ここから
def serialize_microsoftteams_widget(node):
    microsoftteams = node.get_addon('microsoftteams')
    ret = {
        # if True, show widget body, otherwise show addon configuration page link.
        'complete': microsoftteams.complete,
        'include': False,
        'can_expand': True,
    }
    ret.update(microsoftteams.config.to_json())
    return ret
# widget: ここまで

def makeInstitutionUserList(users):
    institutionUsers = []
    userInfo = {}
    for user in users:
        userInfo = {}
        userInfo['guid'] = user._id
        userInfo['fullname'] = user.fullname
        userInfo['username'] = user.username
        institutionUsers.append(userInfo)

    ret = json.dumps(institutionUsers)

    return ret

def api_get_microsoft_username(account, email):
    token = account.oauth_key
    url = '{}{}{}'.format(settings.MICROSOFT_GRAPH_API_BASE_URL, 'v1.0/users/', email)
    requestToken = 'Bearer ' + token
    requestHeaders = {
        'Authorization': requestToken,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=requestHeaders, timeout=60)
    responseData = response.json()
    logger.info('Get the following user => {}'.format(str(responseData)))
    logger.info('StatusCode: {}'.format(str(response.status_code)))
    username = responseData.get('displayName', '')
    return username

def api_create_teams_meeting(requestData, account):
    token = account.oauth_key
    url = '{}{}'.format(settings.MICROSOFT_GRAPH_API_BASE_URL, 'v1.0/me/events')
    requestToken = 'Bearer ' + token
    requestHeaders = {
        'Authorization': requestToken,
        'Content-Type': 'application/json'
    }
    requestBody = json.dumps(requestData)
    response = requests.post(url, data=requestBody, headers=requestHeaders, timeout=60)
    response.raise_for_status()
    responseData = response.json()
    logger.info('StatusCode:{} . A {} meeting was created with following attributes => '.format(str(response.status_code), settings.MICROSOFT_TEAMS) + str(responseData))
    return responseData

def grdm_create_teams_meeting(addon, account, requestData, createdData):
    subject = createdData['subject']
    organizer = createdData['organizer']['emailAddress']['address']
    timeZone = createdData['start']['timeZone']
    tz = pytz.timezone(timeZone)
    startDatetime = createdData['start']['dateTime']
    startDatetime = dateutil.parser.parse(startDatetime)
    startDatetime = tz.localize(startDatetime)
    endDatetime = createdData['end']['dateTime']
    endDatetime = dateutil.parser.parse(endDatetime)
    endDatetime = tz.localize(endDatetime)
    attendees = createdData['attendees']
    attendeeIds = []
    content = createdData['bodyPreview']
    joinUrl = createdData['onlineMeeting']['joinUrl']
    meetingId = createdData['id']
    organizer_fullname = account.display_name
    target = '('
    idx = organizer_fullname.find(target)
    organizer_fullname = organizer_fullname[idx + 1: len(organizer_fullname) - 1]
    contentExtract = requestData['contentExtract']

    for attendeeMail in attendees:
        address = attendeeMail['emailAddress']['address']

        try:
            attendeeObj = models.Attendees.objects.get(node_settings_id=addon.id, email_address=address, external_account=addon.external_account_id, is_active=True)
        except ObjectDoesNotExist:
            continue
        attendeeId = attendeeObj.id
        attendeeIds.append(attendeeId)

    if contentExtract in content:
        content = contentExtract

    with transaction.atomic():

        createData = models.Meetings(
            subject=subject,
            organizer=organizer,
            organizer_fullname=organizer_fullname,
            start_datetime=startDatetime,
            end_datetime=endDatetime,
            content=content,
            join_url=joinUrl,
            meetingid=meetingId,
            external_account_id=addon.external_account_id,
            node_settings_id=addon.id,
        )
        createData.save()
        createData.attendees = attendeeIds
        createData.save()
    logger.info(' A {} meeting on GRDM was created with following attributes => '.format(settings.MICROSOFT_TEAMS) + str(vars(createData)))
    return {}

def api_update_teams_meeting(meetingId, requestData, account):
    token = account.oauth_key
    url = '{}{}{}'.format(settings.MICROSOFT_GRAPH_API_BASE_URL, 'v1.0/me/events/', meetingId)
    requestToken = 'Bearer ' + token
    requestHeaders = {
        'Authorization': requestToken,
        'Content-Type': 'application/json'
    }
    requestBody = json.dumps(requestData)
    response = requests.patch(url, data=requestBody, headers=requestHeaders, timeout=60)
    response.raise_for_status()
    responseData = response.json()
    logger.info('StatusCode:{} . A {} meeting was updated with following attributes => '.format(str(response.status_code), settings.MICROSOFT_TEAMS) + str(responseData))
    return responseData

def grdm_update_teams_meeting(addon, requestData, updatedData):
    meetingId = updatedData['id']
    subject = updatedData['subject']
    timeZone = updatedData['start']['timeZone']
    tz = pytz.timezone(timeZone)
    startDatetime = updatedData['start']['dateTime']
    startDatetime = dateutil.parser.parse(startDatetime)
    startDatetime = tz.localize(startDatetime)
    endDatetime = updatedData['end']['dateTime']
    endDatetime = dateutil.parser.parse(endDatetime)
    endDatetime = tz.localize(endDatetime)
    attendees = updatedData['attendees']
    attendeeIds = []
    content = updatedData['bodyPreview']
    contentExtract = requestData['contentExtract']

    if contentExtract in content:
        content = contentExtract

    for attendeeMail in attendees:
        address = attendeeMail['emailAddress']['address']

        try:
            attendeeObj = models.Attendees.objects.get(node_settings_id=addon.id, email_address=address, external_account=addon.external_account_id, is_active=True)
        except ObjectDoesNotExist:
            continue
        attendeeId = attendeeObj.id
        attendeeIds.append(attendeeId)

    updateData = models.Meetings.objects.get(meetingid=meetingId)

    updateData.subject = subject
    updateData.start_datetime = startDatetime
    updateData.end_datetime = endDatetime
    updateData.attendees = attendeeIds
    updateData.content = content
    updateData.save()
    logger.info('A {} meeting information on GRDM was updated with following attributes => '.format(settings.MICROSOFT_TEAMS) + str(vars(updateData)))
    return {}

def api_delete_teams_meeting(meetingId, account):
    token = account.oauth_key
    url = '{}{}{}'.format(settings.MICROSOFT_GRAPH_API_BASE_URL, 'v1.0/me/events/', meetingId)
    requestToken = 'Bearer ' + token
    requestHeaders = {
        'Authorization': requestToken,
        'Content-Type': 'application/json'
    }
    response = requests.delete(url, headers=requestHeaders, timeout=60)
    if response.status_code != 404:
        response.raise_for_status()

    logger.info('A {} meeting was deleted or has been already deleted. StatusCode : {}'.format(settings.MICROSOFT_TEAMS, str(response.status_code)))
    return {}

def grdm_delete_teams_meeting(meetingId):
    deleteData = models.Meetings.objects.get(meetingid=meetingId)
    deleteData.delete()
    logger.info('A {} meeting information on GRDM was deleted. meetingId => '.format(settings.MICROSOFT_TEAMS) + str(meetingId))
    return {}

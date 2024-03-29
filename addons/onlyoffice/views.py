# -*- coding: utf-8 -*-
from flask import request, Response
import logging

import requests
import os
import time
from osf.models import BaseFileNode

from . import util as onlyoffice_util
from . import settings
from website import settings as websettings

logger = logging.getLogger(__name__)

#  wopi CheckFileInfo endpoint

# Do not add decorator, or else online editor will not open.
def onlyoffice_check_file_info(**kwargs):
    file_id = kwargs['file_id']
    file_version = onlyoffice_util.get_file_version(file_id)
    # logger.info('check_file_info : file_id = {}, file_version = {}'.format(file_id, file_version))

    file_node = BaseFileNode.load(file_id)
    if file_node is None:
        logger.error('BaseFileNode None')
        return

    access_token = request.args.get('access_token', '')
    cookies = {websettings.COOKIE_NAME: access_token}
    user_info = onlyoffice_util.get_user_info(access_token)
    file_info = onlyoffice_util.get_file_info(file_node, file_version, cookies)

    logger.info('ONLYOFFICE file opened : user id = {}, fullname = {}, file_name = {}'
                .format(user_info['user_id'], user_info['full_name'], file_info['name']))

    res = {
        'BaseFileName': file_info['name'],
        'Version': file_version,
        #'ReadOnly': True,
        'UserCanReview': True,
        'UserCanWrite': True,
        'SupportsRename': True,
        'SupportsReviewing': True,
        'UserId': user_info['user_id'],
        'UserFriendlyName': user_info['display_name'],
    }
    return res

    '''
    Available response parameters and examples for ONLYOFFICE.
        'BaseFileName': 'Word.docx',
        'Version': 'Khirz6zTPdfd7',
        'BrandcrumbBrandName': "NII",
        'BrandcrumbBrandUrl': "https://www.nii.ac.jp",
        'BrandcrumbDocName': "barnd_doc.docx",
        'BrandcrumbFolderName': "Example Folder Name",
        'BrandcrumbFolderUrl': "https://www.nii.ac.jp/foler/",
        'ClosePostMessage': True,
        'EditModulePostMessages': True,
        'EditNotificationPostMessage': True,
        'FileShareingPostMessage': True,
        'FileVersionPostMessages': True,
        'PostMessageOrigin': "http://192.168.1.141",
        'CloseUrl': '',
        'FileShareingUrl': '',
        'FileVersionUrl': '',
        'HostEditUrl': '',
        'DisablePrint': True,
        'FileExension': '.docx',
        'FileNameMaxLength': 32,
        'LastModifiedTime': isomtime,
        'isAnonymousUser': True,
        'UserFriendlyName': 'Friendly name',
        'UserId': '1',
        'ReadOnly': True,
        'UserCanRename': True,
        'UserCanReview': True,
        'UserCanWrite': True,
        'SuuportsRename': True,
        'SupportsReviewing': True,
        'HidePrintOption': False
    '''


#  file content view endpoint

# Do not add decorator, or else online editor will not open.
def onlyoffice_file_content_view(**kwargs):
    file_id = kwargs['file_id']
    file_version = onlyoffice_util.get_file_version(file_id)

    file_node = BaseFileNode.load(file_id)
    access_token = request.args.get('access_token', '')
    cookies = {websettings.COOKIE_NAME: access_token}

    user_info = onlyoffice_util.get_user_info(access_token)
    file_info = onlyoffice_util.get_file_info(file_node, file_version, cookies)

    # logger.info('file_content_view: method, file_id, access_token = {} {} {}'.format(request.method, file_id, access_token))
    # logger.info('waterbutler url = {}'.format(websettings.WATERBUTLER_URL))

    if request.method == 'GET':
        #  wopi GetFile endpoint
        content = ''
        try:
            wburl = file_node.generate_waterbutler_url(version=file_version, action='download', direct=None, _internal=True)
            # logger.info('wburl, cookies = {}  {}'.format(wburl, cookies))
            response = requests.get(
                wburl,
                cookies=cookies,
                stream=True
            )
            content = response.raw
        except Exception as err:
            logger.error(err)
            return

        return Response(response=content, status=200)

    if request.method == 'POST':
        #  wopi PutFile endpoint
        logger.info('ONLYOFFICE file saved  : user id = {}, fullname = {}, file_name = {}'
                    .format(user_info['user_id'], user_info['full_name'], file_info['name']))
        if not request.data:
            return Response(response='Not possible to get the file content.', status=401)

        data = request.data
        wburl = file_node.generate_waterbutler_url(direct=None, _internal=True) + '?kind=file'
        logger.debug('wburl = {}'.format(wburl))
        response = requests.put(
            wburl,
            cookies=cookies,
            data=data,
        )

        return Response(status=200)  # status 200


# Do not add decorator, or else online editor will not open.
def onlyoffice_lock_file(**kwargs):
    file_id = kwargs['file_id']
    logger.info('lock_file: file_id = {}'.format(file_id))

    if request.method == 'POST':
        operation = request.META.get('X-WOPI-Override', None)
        if operation == 'LOCK':
            lockId = request.META.get('X-WOPI-Lock', None)
            logger.debug(f"Lock: file id: {file_id}, access token: {request.args.get['access_token']}, lock id: {lockId}")
        elif operation == 'UNLOCK':
            lockId = request.META.get('X-WOPI-Lock', None)
            logger.debug(f"UnLock: file id: {file_id}, access token: {request.args.get['access_token']}, lock id: {lockId}")
        elif operation == 'REFRESH_LOCK':
            lockId = request.META.get('X-WOPI-Lock', None)
            logger.debug(f"RefreshLock: file id: {file_id}, access token: {request.args.get['access_token']}, lock id: {lockId}")
        elif operation == 'RENAME':
            toName = request.META.get('X-WOPI-RequestedName', None)
            logger.debug(f"Rename: file id: {file_id}, access token: {request.args.get['access_token']}, toName: {toName}")

    return Response(status=200)   # Status 200


# Do not add decorator, or else online editor will not open.
def onlyoffice_edit_by_onlyoffice(**kwargs):
    file_id = kwargs['file_id']
    cookie = request.cookies.get(websettings.COOKIE_NAME)
    logger.debug('cookie = {}'.format(cookie))

    # file_id -> fileinfo
    file_node = BaseFileNode.load(file_id)
    if file_node is None:
        logger.error('BaseFileNode None')
        return

    ext = os.path.splitext(file_node.name)[1][1:]
    access_token = cookie
    # access_token ttl (ms).  Arrange this parameter suitable value.
    token_ttl = (time.time() + settings.WOPI_TOKEN_TTL) * 1000

    wopi_client_host = settings.WOPI_CLIENT_ONLYOFFICE
    logger.debug('edit_online.index_view wopi_client_host = {}'.format(wopi_client_host))

    wopi_url = ''
    wopi_client_url = onlyoffice_util.get_onlyoffice_url(wopi_client_host, 'edit', ext)
    if wopi_client_url:
        wopi_src_host = settings.WOPI_SRC_HOST
        wopi_src = f'{wopi_src_host}/wopi/files/{file_id}'
        # logger.info('edit_by_onlyoffice.index_view wopi_src = {}'.format(wopi_src))
        wopi_url = wopi_client_url \
            + 'rs=ja-jp&ui=ja-jp'  \
            + '&wopisrc=' + wopi_src

    # logger.info('edit_by_online.index_view wopi_url = {}'.format(wopi_url))

    context = {
        'wopi_url': wopi_url,
        'access_token': access_token,
        'access_token_ttl': token_ttl,
    }
    return context

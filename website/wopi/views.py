# -*- coding: utf-8 -*-
import logging
import requests
from flask import request, Response
from website import settings
from website.edit_online.util import parse_file_info
from osf.models import BaseFileNode, OSFUser

logger = logging.getLogger(__name__)

#  wopi CheckFileInfo endpoint

def _get_user_info(cookie):
    user = OSFUser.from_cookie(cookie)
    user_info = None
    if user:
        # summary = user.get_summary()
        user_info = {
            'user_id': user._id,
            'full_name': user.display_full_name(),
            'display_name': user.get_summary().get('user_display_name')
        }
        logger.info('check_file_info : user id = {}, fullname = {}, display_name = {}'
                    .format(user._id, user_info['full_name'], user_info['display_name']))
    return user_info


def _get_file_info(file_node, file_version, cookies):
    wburl = file_node.generate_waterbutler_url(version=file_version, meta='', _internal=True)
    logger.debug('wburl = {}'.format(wburl))
    response = requests.get(
        wburl,
        headers={'content-type': 'application/json'},
        cookies=cookies
    )
    if response.status_code != 200:
        return None

    file_data = response.json().get('data')
    file_info = {
        'file_name': file_node.name,
        'file_size': file_data['attributes'].get('size'),
        'file_mtime': file_data['attributes'].get('modified_utc')
    }
    return file_info


def check_file_info(**kwargs):
    file_id_ver = kwargs['file_id_ver']
    file_id, file_version = parse_file_info(file_id_ver)
    logger.info('check_file_info : file_id = {}, file_version = {}'.format(file_id, file_version))

    file_node = BaseFileNode.load(file_id)
    if file_node is None:
        logger.info('BaseFileNode None')
        return

    access_token = request.args.get('access_token', '')
    cookies = {settings.COOKIE_NAME: access_token}
    user_agent = str(request.user_agent)
    # Collabora user_agent is 'COOLWSD HTTP Agent 22.05.8.2'
    # ONLYOFFICE user_agent is 'Node.js/6.13'

    # logger.info('check_file_info_onlyoffice request.host : {}'.format(request.host))
    # logger.info('check_file_info_onlyoffice request.user_agent : {}'.format(user_agent))
    # logger.info('check_file_info_onlyoffice request.referrer : {}'.format(request.referrer))
    # logger.info('check_file_info_onlyoffice request.remote_addr : {}'.format(request.remote_addr))

    user_info = _get_user_info(access_token)
    file_info = _get_file_info(file_node, file_version, cookies)

    if user_agent.startswith('Node.js'):
        res = {
            'BaseFileName': file_info['file_name'],
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

    if user_agent.startswith('COOLWSD'):
        res = {
            'BaseFileName': file_info['file_name'],
            'Size': file_info['file_size'],
            #'Version': file_version,
            'UserCanWrite': True,
            #'LastModifiedTime': file_info['file_mtime'],
            'UserId': user_info['user_id'],
            'UserFriendlyName': user_info['display_name'],
        }
        return res


def file_content_view(**kwargs):
    file_id_ver = kwargs['file_id_ver']
    file_id, file_version = parse_file_info(file_id_ver)

    file_node = BaseFileNode.load(file_id)
    access_token = request.args.get('access_token', '')
    cookies = {settings.COOKIE_NAME: access_token}

    logger.info('file_content_view: method, file_id, access_token = {} {} {}'.format(request.method, file_id, access_token))
    logger.info('waterbutler url = {}'.format(settings.WATERBUTLER_URL))

    if request.method == 'GET':
        #  wopi GetFile endpoint
        content = ''
        try:
            wburl = file_node.generate_waterbutler_url(version=file_version, action='download', direct=None, _internal=True)
            logger.info('wburl, cookies = {}  {}'.format(wburl, cookies))
            response = requests.get(
                wburl,
                cookies=cookies,
                stream=True
            )
            content = response.raw
        except Exception as err:
            logger.error(err)
            return None

        return Response(response=content, status=200)

    if request.method == 'POST':
        #  wopi PutFile endpoint
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


def lock_file(**kwargs):
    file_id_ver = kwargs['file_id_ver']
    file_id, file_version = parse_file_info(file_id_ver)
    logger.info('lock_file: file_id = {}, file_version = {}'.format(file_id, file_version))

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

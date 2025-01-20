# -*- coding: utf-8 -*-
import logging
import requests
from lxml import etree
from osf.models import BaseFileNode, OSFUser

logger = logging.getLogger(__name__)


def get_user_info(cookie):
    user = OSFUser.from_cookie(cookie)
    user_info = None
    if user:
        # summary = user.get_summary()
        user_info = {
            'user_id': user._id,
            'full_name': user.display_full_name(),
            'display_name': user.get_summary().get('user_display_name')
        }
        # logger.info('get_user_info : user id = {}, fullname = {}, display_name = {}'
        #             .format(user._id, user_info['full_name'], user_info['display_name']))
    return user_info


def get_file_info(file_node, file_version, cookies):
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


def parse_file_info(file_id_ver):
    # file_id_ver example : "0120394556fe24-3".
    #  '-' is separator.
    #  In this case, file_id is "0120394556fe24" and version is "3".

    file_id = ''
    file_version = ''
    if '-' in file_id_ver:
        file_id, file_version = file_id_ver.rsplit('-', 1)
    else:
        # If version not specified, get latest version number of this file.
        file_id = file_id_ver
        base_file_data = BaseFileNode.objects.filter(_id=file_id)
        base_file_data_exists = base_file_data.exists()
        if base_file_data_exists:
            base_file_data = base_file_data.get()
            file_versions = base_file_data.versions.all()
            file_version = file_versions.latest('id').identifier

    return file_id, file_version


def _ext_to_app_name_onlyoffice(ext):
    ext_app = {
        'txt': 'text/plain',
        'docx': 'Word',
        'xlsx': 'Excel',
        'pptx': 'PowerPoint'
    }

    app_name = ext_app[ext.lower()]
    return app_name


def get_onlyoffice_url(server, mode, ext):
    response = requests.get(server + '/hosting/discovery')
    discovery = response.text
    if not discovery:
        logger.error('No able to retrieve the discovery.xml for onlyoffice.')
        return None

    parsed = etree.fromstring(bytes(discovery, encoding='utf-8'))
    if parsed is None:
        logger.error('The retrieved discovery.xml file is not a valid XML file')
        return None

    app_name = _ext_to_app_name_onlyoffice(ext)
    if app_name is None:
        logger.error('Not supported file extension for editting.')
        return None

    result = parsed.xpath(f"/wopi-discovery/net-zone/app[@name='{app_name}']/action")

    online_url = ''
    for res in result:
        if res.get('name') == mode and res.get('ext') == ext:
            online_url = res.get('urlsrc')
            break
        if app_name == 'text/plain' and res.get('ext') == '':
            # In discoverry messae of app_name = 'text/plain', ext is ''
            online_url = res.get('urlsrc')
            break

    if online_url == '':
        logger.error('Supported url not found.')
        return None

    online_url = online_url[:online_url.index('?') + 1]
    return online_url

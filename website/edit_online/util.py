# -*- coding: utf-8 -*-
import logging
import requests
from lxml import etree
from osf.models import BaseFileNode

logger = logging.getLogger(__name__)


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
        'docx': 'Word',
        'xlsx': 'Excel',
        'pptx': 'PowerPoint'
    }

    app_name = ext_app[ext.lower()]
    return app_name

def _ext_to_app_name_collabora(ext):
    ext_app = {
        'doc': 'writer',
        'docx': 'writer',
        'xls': 'calc',
        'xlsx': 'calc',
        'ppt': 'impress',
        'pptx': 'impress'
    }

    app_name = ext_app[ext.lower()]
    return app_name


def get_onlyoffice_url(server, mode, ext):
    response = requests.get(server + '/hosting/discovery')
    discovery = response.text
    if not discovery:
        logger.error('No able to retrieve the discovery.xml for onlyoffice.')
        return

    parsed = etree.fromstring(bytes(discovery, encoding='utf-8'))
    if parsed is None:
        logger.error('The retrieved discovery.xml file is not a valid XML file')
        return

    app_name = _ext_to_app_name_onlyoffice(ext)
    if app_name is None:
        logger.error('Not supported file extension for editting.')
        return

    result = parsed.xpath(f"/wopi-discovery/net-zone/app[@name='{app_name}']/action")

    online_url = ''
    for res in result:
        if res.get('name') == mode and res.get('ext') == ext:
            online_url = res.get('urlsrc')
            # logger.debug('online url: ' + online_url)
            break

    if online_url == '':
        logger.error('Supported url not found.')
        return

    online_url = online_url[:online_url.index('&')]
    return online_url


def get_collabora_url(server, mode, ext):
    response = requests.get(server + '/hosting/discovery')
    discovery = response.text
    if not discovery:
        logger.error('No able to retrieve the discovery.xml for collabora.')
        return

    parsed = etree.fromstring(bytes(discovery, encoding='utf-8'))
    if parsed is None:
        logger.error('The retrieved discovery.xml file is not a valid XML file')
        return

    app_name = _ext_to_app_name_collabora(ext)
    if app_name is None:
        logger.error('Not supported file extension for editting.')
        return

    result = parsed.xpath(f"/wopi-discovery/net-zone/app[@name='{app_name}']/action[@ext='{ext}'][@name='{mode}']")

    if len(result) != 1:
        logger.error('The requested mime type is not handled')
        return

    online_url = result[0].get('urlsrc')
    return online_url

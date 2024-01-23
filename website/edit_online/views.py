# -*- coding: utf-8 -*-
import logging
from flask import request
import os
import time
from osf.models import BaseFileNode
from website import settings
from website.edit_online.util import parse_file_info, get_onlyoffice_url, get_collabora_url

logger = logging.getLogger(__name__)

def edit_by_onlyoffice(**kwargs):
    file_id_ver = kwargs['file_id_ver']
    file_id, file_version = parse_file_info(file_id_ver)

    cookie = request.cookies.get(settings.COOKIE_NAME)
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
    wopi_client_url = get_onlyoffice_url(wopi_client_host, 'edit', ext)
    if wopi_client_url:
        wopi_src_host = settings.WOPI_SRC_HOST
        wopi_src = f'{wopi_src_host}/wopi/files/{file_id}-{file_version}'
        logger.info('edit_online.index_view wopi_src = {}'.format(wopi_src))
        wopi_url = wopi_client_url \
            + 'rs=ja-jp&ui=ja-jp'  \
            + '&wopisrc=' + wopi_src

    logger.info('edit_online.index_view wopi_url = {}'.format(wopi_url))

    context = {
        'wopi_url': wopi_url,
        'access_token': access_token,
        'access_token_ttl': token_ttl,
    }
    return context


def edit_by_collabora(**kwargs):
    file_id_ver = kwargs['file_id_ver']
    file_id, file_version = parse_file_info(file_id_ver)

    cookie = request.cookies.get(settings.COOKIE_NAME)
    logger.info('cookie = {}'.format(cookie))

    # file_id -> fileinfo
    file_node = BaseFileNode.load(file_id)
    if file_node is None:
        logger.error('BaseFileNode None')
        return

    ext = os.path.splitext(file_node.name)[1][1:]
    access_token = cookie
    token_ttl = 0

    wopi_client_host = settings.WOPI_CLIENT_COLLABORA
    logger.info('edit_online.index_view wopi_client_host = {}'.format(wopi_client_host))

    wopi_url = ''
    wopi_client_url = get_collabora_url(wopi_client_host, 'edit', ext)

    if wopi_client_url:
        wopi_src_host = settings.WOPI_SRC_HOST
        wopi_src = f'{wopi_src_host}/wopi/files/{file_id}-{file_version}'
        logger.info('edit_online.index_view wopi_src = {}'.format(wopi_src))
        wopi_url = wopi_client_url + 'access_token=' + access_token + '&WOPISrc=' + wopi_src

    logger.info('edit_by_collabora wopi_url = {}'.format(wopi_url))

    context = {
        'wopi_url': wopi_url,
        'access_token': access_token,
        'access_token_ttl': token_ttl,
    }
    return context

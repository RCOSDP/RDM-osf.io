# -*- coding: utf-8 -*-
import os
import json
import requests
import sys
from bs4 import BeautifulSoup
from website import settings
from framework.status import pop_status_messages
from flask import send_from_directory, Response, stream_with_context
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core.models import http

from website.settings import EXTERNAL_EMBER_APPS, PROXY_EMBER_APPS, EXTERNAL_EMBER_SERVER_TIMEOUT

ember_osf_web_dir = os.path.abspath(os.path.join(os.getcwd(), EXTERNAL_EMBER_APPS['ember_osf_web']['path']))

routes = [
    '/quickfiles/',
    '/<uid>/quickfiles/',
    '/institutions/',
    '/support/',
]

def use_ember_app(**kwargs):
    subsegment = xray_recorder.current_subsegment()
    subsegment.put_http_meta(http.URL, EXTERNAL_EMBER_APPS['ember_osf_web']['server'])
    subsegment.put_http_meta(http.METHOD, 'GET')
    if PROXY_EMBER_APPS:
        resp = requests.get(EXTERNAL_EMBER_APPS['ember_osf_web']['server'], stream=True, timeout=EXTERNAL_EMBER_SERVER_TIMEOUT)
        # Add X-Amzn-Trace-Id variable to the HTML response
        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' in content_type:
            soup = BeautifulSoup(resp.content, 'html.parser')
            script_tag = soup.new_tag('script')
            script_tag.string = f"window.traceId = '{subsegment.trace_id}';"
            soup.head.append(script_tag)

            html_with_trace_id = soup.prettify()
            resp = Response(html_with_trace_id, resp.status_code)
        else:
            resp = Response(stream_with_context(resp.iter_content()), resp.status_code)
    else:
        resp = send_from_directory(ember_osf_web_dir, 'index.html')
    subsegment.put_http_meta(http.STATUS, resp.status_code)
    messages = pop_status_messages()
    if messages:
        try:
            status = [{'id': stat[5] if stat[5] else stat[0], 'class': stat[2], 'jumbo': stat[1], 'dismiss': stat[3], 'extra': stat[6]} for stat in messages]
            resp.set_cookie(settings.COOKIE_NAME + '_status', json.dumps(status))
        except IndexError:
            # Ignoring the error as it will only occur when statuses were created prior to merging the changes that add
            # extra and id, (patch to prevent breaking the app meanwhile)
            exc_type, exc_value, exc_traceback = sys.exc_info()
            subsegment.add_exception(exc_value, exc_traceback)
            pass
    return resp
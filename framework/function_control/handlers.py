# -*- coding: utf-8 -*-
import logging
import json
import os
import re

from django.http import JsonResponse
from flask import request, abort, Response
from rest_framework import status as http_status
from admin.base.schemas.utils import validate_config_schema
from admin.base.settings import BASE_DIR
from framework.flask import redirect

logger = logging.getLogger(__name__)


def check_api_service_access(request_url_path, request_method, user):
    """ Check if user has access to API """
    from admin.service_access_control_setting.views import CONFIG_PATH, CONFIG_SCHEMA_FILE_NAME
    from api.base.settings import ERROR_MESSAGE_API_LIST
    if user is None:
        # If there is no user information, return None
        return None

    try:
        # Load config data file
        with open(os.path.join(BASE_DIR, CONFIG_PATH), encoding='utf-8') as fp:
            function_config_json = json.load(fp)
        # Validate config data with the JSON schema
        validate_config_schema(function_config_json, CONFIG_SCHEMA_FILE_NAME)
    except Exception as e:
        # Fail to load or validate config data, return None
        logger.warning(f'Failed to load config schema with exception {e}')
        return None

    # Find a function_code in config data
    request_function_code = None
    for function_code, function_config in function_config_json.items():
        for api_item in function_config.get('api_group', []):
            try:
                api_pattern = re.compile(api_item.get('api'))
                api_method = api_item.get('method')
                if api_pattern.match(request_url_path) and api_method == request_method:
                    request_function_code = function_code
                    break
            except re.error:
                # If API string is not a regex, skip this item
                continue

    if not user.is_allowed_to_access_api(request_function_code):
        # If user is not allowed to access API, return HTTP 403 response
        # If error_type = 0: instruct client not to show error message
        # If error_type = 1: instruct client to show error message
        error_type = 0
        try:
            # Check if request URL and request method is in API group list that will return error_message
            for api_item in ERROR_MESSAGE_API_LIST:
                try:
                    api_pattern = re.compile(api_item.get('api'))
                    api_method = api_item.get('method')
                    if api_pattern.match(request_url_path) and api_method == request_method:
                        # If request URL is in API group list setting, set error_type to 1
                        error_type = 1
                        break
                except re.error:
                    # If API string is not a regex, skip this item
                    continue
        except Exception as e:
            # If other exception raised, stop checking
            logger.warning(f'Error occurred while checking request URL with error message API list setting: {e}')

        # Return HTTP 403 error response with correspond error_type
        return JsonResponse({
            'errors': [{
                'message': 'User is not allowed to access this API.',
                'type': error_type,
                'status': http_status.HTTP_403_FORBIDDEN
            }]
        }, status=http_status.HTTP_403_FORBIDDEN)
    return None


def function_control_before_request():
    """ Check function access control before request function """
    from osf.models import OSFUser
    from website.settings import COOKIE_NAME

    # Get user information from request
    cookie_value = request.cookies.get(COOKIE_NAME)
    user = OSFUser.from_cookie(cookie_value)
    # Check user's API permission
    error_response = check_api_service_access(request.path, request.method, user)
    if error_response:
        # If there is error response, handle that error response
        error_dict = json.loads(error_response.content.decode('utf-8'))
        error_type = error_dict.get('errors', [{}])[0].get('type')
        if request.accept_mimetypes['text/html'] > request.accept_mimetypes['application/json'] and error_type == 0:
            # If request want to get HTML response and error_type = 0, redirect to 403 page
            return redirect('/403')
        else:
            # Otherwise, return JSON response
            abort(Response(response=error_response.content, status=http_status.HTTP_403_FORBIDDEN, content_type='application/json'))


handlers = {
    'before_request': function_control_before_request,
}

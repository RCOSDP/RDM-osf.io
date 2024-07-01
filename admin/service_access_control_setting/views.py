import logging
import os
import json
from itertools import groupby

import jsonschema

from collections import OrderedDict

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import transaction
from django.db.models import Subquery, OuterRef
from django.http import JsonResponse
from django.template.defaultfilters import register
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from rest_framework import status as http_status

from osf.exceptions import ValidationError
from osf.models import Function, Institution
from osf.models.service_access_control_setting import ServiceAccessControlSetting
from admin.base.schemas.utils import validate_json_schema, validate_config_schema
from admin.base.settings import BASE_DIR
from admin.rdm.utils import RdmPermissionMixin

logger = logging.getLogger(__name__)

CONFIG_PATH = 'service_access_control_setting/settings/config_data.json'
CONFIG_SCHEMA_FILE_NAME = 'config-schema.json'
SERVICE_ACCESS_CONTROL_SCHEMA_FILE_NAME = 'service-access-control-setting-schema.json'
JSON_FILE_INVALID_RESPONSE = {
    'message': 'JSON file is invalid.'
}
CONFIG_DATA_INVALID_RESPONSE = {
    'message': 'Config data is invalid.'
}


@register.simple_tag
def get_rowspan(row_info_dict, filter_key):
    """ A Django simple tag that return rowspan value by filter_key """
    # Get value from dict based on filter key. If not found then return 1
    return row_info_dict.get(filter_key, 1)


class ServiceAccessControlSettingView(UserPassesTestMixin, RdmPermissionMixin, ListView):
    """ Allow an administrator to view service access control setting """
    paginate_by = 25
    template_name = 'service_access_control_setting/list.html'
    raise_exception = True
    model = ServiceAccessControlSetting

    def test_func(self):
        """check user permissions"""
        if not self.is_authenticated:
            self.raise_exception = False
            return False
        return self.is_super_admin or self.is_admin

    def get_queryset(self):
        # Create sub queryset to get institution name by institution guid
        institution_subquery = Institution.objects.filter(_id=OuterRef('institution_id')).values('name')
        # Create queryset
        queryset = ServiceAccessControlSetting.objects.filter(
            functions__is_deleted=False, is_deleted=False
        ).annotate(
            institution_name=Subquery(institution_subquery), function_codes=ArrayAgg('functions__function_code')
        ).order_by('institution_name', 'domain', 'is_ial2_or_aal2', 'user_domain')
        if self.is_super_admin:
            # Get settings for all institutions
            return queryset
        elif self.is_admin:
            # Get settings for administrator's institution
            user = self.request.user
            institution = user.affiliated_institutions.filter(is_deleted=False).first()
            return queryset.filter(institution_id=institution.guid)
        # Otherwise, return none queryset
        return ServiceAccessControlSetting.objects.none()

    def get_context_data(self, **kwargs):
        try:
            # Load JSON config data
            with open(os.path.join(BASE_DIR, CONFIG_PATH), encoding='utf-8') as fp:
                config_data = json.load(fp, object_pairs_hook=OrderedDict)
            # Validate config data with the JSON schema
            validate_config_schema(config_data, CONFIG_SCHEMA_FILE_NAME)
        except Exception:
            # Return no data
            return {
                'column_data': {},
                'row_data': [],
            }

        # Convert config data into dict of {"function_code": "function_name value"}
        function_data = {kv[0]: kv[1].get('function_name', '') for i, kv in enumerate(config_data.items())}

        # Paginate the queryset
        query_set = kwargs.pop('object_list', self.object_list)
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(
            query_set, page_size)

        # Get rowspan info for rendering table
        institution_id_rowspan_info = {}
        domain_rowspan_info = {}
        ial2_aal2_rowspan_info = {}
        if query_set.exists():
            # institution_id_rowspan_info example value: {'gakunin': 3}
            for k, v in groupby(query_set, key=lambda x: (x.institution_id,)):
                institution_id_rowspan_info['__'.join(map(str, k))] = len(list(v))
            # domain_rowspan_info example value: {'gakunin__default': 2, 'gakunin__test.com': 1}
            for k, v in groupby(query_set, key=lambda x: (x.institution_id, x.domain,)):
                domain_rowspan_info['__'.join(map(str, k))] = len(list(v))
            # ial2_aal2_rowspan_info example value: {'gakunin__default__True': 1, 'gakunin__default__False': 1}
            for k, v in groupby(query_set, key=lambda x: (x.institution_id, x.domain, x.is_ial2_or_aal2,)):
                ial2_aal2_rowspan_info['__'.join(map(str, k))] = len(list(v))

        return {
            'column_data': function_data,
            'row_data': query_set,
            'page': page,
            'institution_id_rowspan_info': institution_id_rowspan_info,
            'domain_rowspan_info': domain_rowspan_info,
            'ial2_aal2_rowspan_info': ial2_aal2_rowspan_info,
        }


class ServiceAccessControlSettingCreateView(UserPassesTestMixin, RdmPermissionMixin, View):
    """ Allow an integrated administrator to update service access control setting """
    raise_exception = True

    def test_func(self):
        """check user permissions"""
        if not self.is_authenticated:
            self.raise_exception = False
            return False
        return self.is_super_admin

    def post(self, request):
        """Handle upload setting file request"""
        # Default response is HTTP 200 OK
        response_body = {}
        status_code = http_status.HTTP_200_OK

        # If there is error, raise and catch exception, then return response later
        try:
            try:
                # Load setting data from uploaded JSON file
                file = self.parse_file(request.FILES['file'])
                setting_json = json.loads(file)
            except json.decoder.JSONDecodeError as e:
                # Fail to decode JSON file, return HTTP 400
                logger.error(f'JSON file is invalid: {e}')
                response_body = JSON_FILE_INVALID_RESPONSE
                status_code = http_status.HTTP_400_BAD_REQUEST
                raise e
            except Exception as e:
                # Fail to load setting data, return HTTP 500
                logger.error(f'Fail to load setting data with error {e}')
                raise e

            try:
                # Validate setting data with the JSON schema
                validate_json_schema(setting_json, SERVICE_ACCESS_CONTROL_SCHEMA_FILE_NAME)
            except (jsonschema.ValidationError, jsonschema.SchemaError) as e:
                logger.error(f'JSON file is invalid: {e}')
                response_body = JSON_FILE_INVALID_RESPONSE
                status_code = http_status.HTTP_400_BAD_REQUEST
                raise e

            try:
                # Load config data file
                with open(os.path.join(BASE_DIR, CONFIG_PATH), encoding='utf-8') as fp:
                    function_config_json = json.load(fp)
                # Validate config data with the JSON schema
                validate_config_schema(function_config_json, CONFIG_SCHEMA_FILE_NAME)
            except Exception as e:
                logger.error(f'Config data is invalid: {e}')
                response_body = CONFIG_DATA_INVALID_RESPONSE
                status_code = http_status.HTTP_400_BAD_REQUEST
                raise e

            function_config_codes = {item[0] for item in function_config_json.items()}
            service_access_control_settings = []
            function_settings = []
            validation_list = []
            for setting_data_item in setting_json.get('data', []):
                institution_id = setting_data_item.get('institution_id')
                domain = setting_data_item.get('domain')
                is_ial2_or_aal2 = setting_data_item.get('is_ial2_or_aal2')
                user_domain = setting_data_item.get('user_domain')
                function_codes = setting_data_item.get('function_codes', [])
                is_whitelist = setting_data_item.get('is_whitelist')
                project_limit_number = setting_data_item.get('project_limit_number')

                if not Institution.objects.filter(_id=institution_id).exists():
                    # If institution guid does not exist, return HTTP 400
                    logger.error('JSON file is invalid: institution_id not found.')
                    response_body = JSON_FILE_INVALID_RESPONSE
                    status_code = http_status.HTTP_400_BAD_REQUEST
                    raise ValidationError('JSON file is invalid: institution_id not found.')

                function_codes_set = set(function_codes)
                if not function_codes_set.issubset(function_config_codes):
                    # If there are some function codes that are not in config file, return HTTP 400
                    logger.error('JSON file is invalid: some function codes are not in config file.')
                    response_body = JSON_FILE_INVALID_RESPONSE
                    status_code = http_status.HTTP_400_BAD_REQUEST
                    raise ValidationError('JSON file is invalid: some function codes are not in config file.')

                # Prepare data for later duplication validation
                validation_list.append((institution_id, domain, is_ial2_or_aal2, user_domain,))

                # Prepare data for bulk-insert
                new_setting = ServiceAccessControlSetting(
                    institution_id=institution_id,
                    domain=domain,
                    is_ial2_or_aal2=is_ial2_or_aal2,
                    user_domain=user_domain,
                    is_whitelist=is_whitelist,
                    project_limit_number=project_limit_number
                )
                service_access_control_settings.append(new_setting)
                function_settings.extend([
                    Function(function_code=item, service_access_control_setting=new_setting) for item in function_codes_set]
                )

            if len(validation_list) != len(set(validation_list)):
                # If settings has duplicate information, return HTTP 400
                logger.error('JSON file is invalid: upload settings has duplicate information')
                response_body = JSON_FILE_INVALID_RESPONSE
                status_code = http_status.HTTP_400_BAD_REQUEST
                raise ValidationError('JSON file is invalid: upload settings has duplicate information')

            try:
                # Begin transaction
                with transaction.atomic():
                    # Set is_deleted to True for current osf_service_access_control_setting and osf_function records
                    ServiceAccessControlSetting.objects.filter(is_deleted=False).update(is_deleted=True, modified=timezone.now())
                    Function.objects.filter(is_deleted=False).update(is_deleted=True, modified=timezone.now())
                    # Bulk insert osf_service_access_control_setting
                    ServiceAccessControlSetting.objects.bulk_create(service_access_control_settings)
                    # Bulk insert osf_function
                    for function_setting_item in function_settings:
                        # Assign now created osf_service_access_control_setting.id to osf_function.service_access_control_setting_id
                        function_setting_item.service_access_control_setting_id = function_setting_item.service_access_control_setting.id
                    Function.objects.bulk_create(function_settings)
            except Exception as e:
                logger.error(f'Exception raised in the create setting transaction: {e}')
                # Raise HTTP 500
                raise e
        except Exception as e:
            if status_code != http_status.HTTP_400_BAD_REQUEST:
                # If request does not plan to return HTTP 400 then return HTTP 500 by raising the exception
                raise e

        return JsonResponse(response_body, status=status_code)

    def parse_file(self, f):
        """Parse file data"""
        parsed_file = ''
        for chunk in f.chunks():
            if isinstance(chunk, bytes):
                chunk = chunk.decode()
            parsed_file += chunk
        return parsed_file

from __future__ import unicode_literals

import json
import logging
import re

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.generic import ListView, View
from rest_framework import status as http_status

from admin.base.settings import ATTRIBUTE_NAME_LIST
from admin.base.utils import render_bad_request_response
from admin.login_access_control import utils
from admin.rdm.utils import RdmPermissionMixin
from osf.models import Institution, LoginControlAuthenticationAttribute, LoginControlMailAddress
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import Http404

logger = logging.getLogger(__name__)


class LoginAccessControlListView(RdmPermissionMixin, UserPassesTestMixin, ListView):
    """ Login Access Control page """
    paginate_by = 10
    template_name = 'login_access_control/list.html'
    raise_exception = True
    ordering = '-id'

    def test_func(self):
        """check user permissions"""
        # login check
        if not self.is_authenticated:
            self.raise_exception = False
            return False

        # Superuser or institutional admin has permission
        return self.is_super_admin or self.is_institutional_admin

    def get_queryset(self):
        # Return None queryset as get_context_data function already has querysets
        return LoginControlAuthenticationAttribute.objects.none()

    def get(self, request, *args, **kwargs):
        institution_id = self.request.GET.get('institution_id')
        if institution_id is not None:
            # If institution_id query param has value, validate institution_id
            try:
                institution_id = int(institution_id)
                if not Institution.objects.filter(id=institution_id, is_deleted=False).exists():
                    # institution not found, redirect to 404 page
                    raise Http404(f'Institution with id "{institution_id}" not found.')
            except (ValueError, TypeError):
                # Invalid institution_id, redirect to 404 page
                return render_bad_request_response(self.request, 'institution_id is invalid.')

        return super(LoginAccessControlListView, self).get(request, args, kwargs)

    def get_context_data(self, **kwargs):
        institution_id = int(self.request.GET.get('institution_id'))
        user = self.request.user
        # Get institution list
        institutions = Institution.objects.filter(is_deleted=False).order_by('name')
        if not self.is_super_admin and self.is_institutional_admin:
            # If user is an institution administrator, get institution list that user is affiliated
            institutions = user.affiliated_institutions.filter(is_deleted=False)
            if institution_id is not None and not institutions.filter(id=institution_id).exists():
                # If user is not affiliated with institution with institution_id query params, return HTTP 403 page
                raise PermissionDenied()

        if institution_id is None:
            # If the url does not have institution_id param, select the first institution
            selected_institution = institutions.first()
        else:
            # Otherwise, select the institution with institution_id
            selected_institution = institutions.filter(id=institution_id).first()

        if not selected_institution:
            raise Http404()

        # Get login control authentication attribute and login control mail address lists
        login_control_authentication_attribute_list = LoginControlAuthenticationAttribute.objects.filter(
            institution=selected_institution, is_deleted=False
        ).order_by('attribute_name', '-id')
        login_control_mail_address_list = LoginControlMailAddress.objects.filter(
            institution=selected_institution, is_deleted=False
        ).order_by('-id')

        # Pagination
        self.page_kwarg = 'attribute_page_number'
        attribute_page_size = self.get_paginate_by(login_control_authentication_attribute_list)
        _, attribute_page, attribute_query_set, _ = self.paginate_queryset(login_control_authentication_attribute_list, attribute_page_size)
        attribute_list = list(attribute_query_set)

        self.page_kwarg = 'mail_address_page_number'
        mail_address_page_size = self.get_paginate_by(login_control_mail_address_list)
        _, mail_address_page, mail_address_query_set, _ = self.paginate_queryset(login_control_mail_address_list, mail_address_page_size)
        mail_address_list = list(mail_address_query_set)

        # Return data
        return {
            'is_admin': self.is_institutional_admin,
            'institutions': institutions,
            'selected_institution': selected_institution,
            'attributes': ATTRIBUTE_NAME_LIST,
            'login_control_authentication_attribute_list': attribute_list,
            'login_control_authentication_attribute_page': attribute_page,
            'login_control_mail_address_list': mail_address_list,
            'login_control_mail_address_page': mail_address_page,
        }


class BaseLogicAccessControlUpdateView(RdmPermissionMixin, UserPassesTestMixin, View):
    """ Base view for create/update/delete API views in logic access control page """
    raise_exception = True

    def test_func(self):
        """check user permissions"""
        # login check
        if not self.is_authenticated:
            self.raise_exception = False
            return False

        # superuser or institutional admin has permission
        return self.is_super_admin or self.is_institutional_admin

    def parse_json_request(self, request):
        """ Parse JSON request body """
        try:
            data = json.loads(request.body)
        except Exception:
            return None, JsonResponse({'error_message': 'The request body data is invalid'}, status=http_status.HTTP_400_BAD_REQUEST)

        if not data:
            return None, JsonResponse({'error_message': 'The request body data is required'}, status=http_status.HTTP_400_BAD_REQUEST)

        return data, None

    def is_affiliated_with_not_deleted_institution(self, institution_id):
        """ Check if user is an institution administrator that is affiliated with institution_id """
        return self.request.user.affiliated_institutions.filter(pk=institution_id, is_deleted=False).exists()


class UpdateLoginAvailabilityDefaultView(BaseLogicAccessControlUpdateView):
    """ Update institution's login availability default view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        login_availability_default = request_body.get('login_availability_default')

        # Validate request data
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        login_availability_default_error_message = utils.validate_boolean(login_availability_default, 'login_availability_default')
        if login_availability_default_error_message is not None:
            return JsonResponse({'error_message': login_availability_default_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Update institution's login_availability default
        institution = Institution.objects.filter(id=institution_id, is_deleted=False).first()
        if institution:
            institution.login_availability_default = login_availability_default
            institution.save()

        return JsonResponse({}, status=http_status.HTTP_204_NO_CONTENT)


class SaveAuthenticationAttributeListView(BaseLogicAccessControlUpdateView):
    """ Add institution's login authentication attributes view """
    def post(self, request):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        attribute_data_list = request_body.get('attribute_data', [])

        # Validate institution_id
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        # Validate list of attribute name, value pair
        if not attribute_data_list:
            return JsonResponse({'error_message': 'Group (attribute name, attribute value) is required.'}, status=http_status.HTTP_400_BAD_REQUEST)

        current_attribute_list = LoginControlAuthenticationAttribute.objects.filter(institution_id=institution_id, is_deleted=False).values_list(
            'attribute_name', 'attribute_value')
        validation_list = list(current_attribute_list)
        new_attribute_list = []

        for attribute_data in attribute_data_list:
            attribute_name = (attribute_data.get('attribute_name') or '').strip()
            attribute_value = (attribute_data.get('attribute_value') or '').strip()

            # Validate attribute name
            if not attribute_name:
                return JsonResponse({'error_message': 'Attribute name is required.'}, status=http_status.HTTP_400_BAD_REQUEST)

            if attribute_name not in ATTRIBUTE_NAME_LIST:
                return JsonResponse({'error_message': 'Attribute name is not exist in config.'}, status=http_status.HTTP_400_BAD_REQUEST)

            # Validate attribute value
            if not attribute_value:
                return JsonResponse({'error_message': 'Attribute value is required.'}, status=http_status.HTTP_400_BAD_REQUEST)

            if len(attribute_value) > 255:
                return JsonResponse({'error_message': 'Length of attribute value > 255 characters.'}, status=http_status.HTTP_400_BAD_REQUEST)

            validation_list.append((attribute_name, attribute_value,))

            # Add name, value pair to bulk insert queryset
            new_attribute = LoginControlAuthenticationAttribute(institution_id=institution_id, attribute_name=attribute_name, attribute_value=attribute_value)
            new_attribute_list.append(new_attribute)

        if len(validation_list) != len(set(validation_list)):
            # If there are duplicate records, return not unique error message
            return JsonResponse({'error_message': 'Group (attribute name, attribute value) MUST be unique.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Insert new attribute data into DB
        LoginControlAuthenticationAttribute.objects.bulk_create(new_attribute_list)

        return JsonResponse({}, status=http_status.HTTP_201_CREATED)


class UpdateAuthenticationAttributeView(BaseLogicAccessControlUpdateView):
    """ Update is_availability of a login authentication attribute view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        attribute_id = request_body.get('attribute_id')
        is_availability = request_body.get('is_availability')

        # Validate data
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        attribute_id_error_message = utils.validate_integer(attribute_id, 'attribute_id')
        if attribute_id_error_message is not None:
            return JsonResponse({'error_message': attribute_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        attribute_queryset = LoginControlAuthenticationAttribute.objects.filter(id=attribute_id, is_deleted=False)
        if not attribute_queryset.exists():
            return JsonResponse({'error_message': 'attribute_id is invalid.'}, status=http_status.HTTP_400_BAD_REQUEST)

        is_availability_error_message = utils.validate_boolean(is_availability, 'is_availability')
        if is_availability_error_message is not None:
            return JsonResponse({'error_message': is_availability_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Get login control authentication attribute by institution_id
        attribute = attribute_queryset.filter(institution_id=institution_id).first()
        if not attribute:
            return JsonResponse({'error_message': 'Can not setting login access control of the institution into the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Check if attribute is set in institution's login_logic_condition
        institution = Institution.objects.filter(id=institution_id, is_deleted=False).first()
        if institution.login_logic_condition:
            logic_condition_attribute_id_list = map(int, re.findall('\\d+', institution.login_logic_condition))
            if attribute_id in logic_condition_attribute_id_list:
                return JsonResponse({'error_message': 'Can not switch toggle the attribute element due to it is using in the logic condition.'},
                                    status=http_status.HTTP_400_BAD_REQUEST)

        # Update authentication attribute's is_availability
        attribute.is_availability = is_availability
        attribute.save()

        return JsonResponse({}, status=http_status.HTTP_204_NO_CONTENT)


class DeleteAuthenticationAttributeView(BaseLogicAccessControlUpdateView):
    """ Delete a login authentication attribute view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        attribute_id = request_body.get('attribute_id')

        # Validate data
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        attribute_id_error_message = utils.validate_integer(attribute_id, 'attribute_id')
        if attribute_id_error_message is not None:
            return JsonResponse({'error_message': attribute_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        attribute_queryset = LoginControlAuthenticationAttribute.objects.filter(id=attribute_id, is_deleted=False)
        if not attribute_queryset.exists():
            return JsonResponse({'error_message': 'attribute_id is invalid.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Get login control authentication attribute by institution_id
        attribute = attribute_queryset.filter(institution_id=institution_id).first()
        if not attribute:
            return JsonResponse({'error_message': 'Can not setting login access control of the institution into the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Check if attribute is set in institution's login_logic_condition
        institution = Institution.objects.filter(id=institution_id, is_deleted=False).first()
        if institution.login_logic_condition:
            logic_condition_attribute_id_list = map(int, re.findall('\\d+', institution.login_logic_condition))
            if attribute_id in logic_condition_attribute_id_list:
                return JsonResponse({'error_message': 'Can not delete the attribute element due to it is using in the logic condition.'},
                                    status=http_status.HTTP_400_BAD_REQUEST)

        # Update authentication attribute's is_deleted to True
        attribute.is_deleted = True
        attribute.save()

        return JsonResponse({}, status=http_status.HTTP_204_NO_CONTENT)


class UpdateLoginLogicConditionView(BaseLogicAccessControlUpdateView):
    """ Update institution's login logic condition expression view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        logic_condition = (request_body.get('logic_condition') or '').strip()

        # Validate data
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        if not utils.validate_logic_condition(logic_condition):
            return JsonResponse({'error_message': 'Logic condition is invalid.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        institution = Institution.objects.filter(id=institution_id, is_deleted=False).first()
        # Check if there is a index that does not exist for institution
        logic_condition_attribute_id_list = re.findall('\\d+', logic_condition)
        logic_condition_attribute_unique_id_list = set(logic_condition_attribute_id_list)
        current_attribute_list = LoginControlAuthenticationAttribute.objects.filter(
            institution=institution, id__in=logic_condition_attribute_unique_id_list, is_availability=True, is_deleted=False)
        if len(logic_condition_attribute_unique_id_list) != current_attribute_list.count():
            return JsonResponse({'error_message': 'Index number does not exist.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # Update institution's login logic condition
        institution.login_logic_condition = logic_condition
        institution.save()

        return JsonResponse({}, status=http_status.HTTP_204_NO_CONTENT)


class SaveMailAddressListView(BaseLogicAccessControlUpdateView):
    """ Add institution's logic mail addresses view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        mail_address_list = request_body.get('mail_address_list', [])

        # Validate institution_id
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        # Validate mail address list
        if not mail_address_list:
            return JsonResponse({'error_message': 'Mail address is required.'}, status=http_status.HTTP_400_BAD_REQUEST)

        mail_address_regex = r'^([\w\-\.]+@|@|\.|)(?!\d+\.)+(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]{0,62}[a-z0-9]$'
        current_mail_address_list = LoginControlMailAddress.objects.filter(institution_id=institution_id, is_deleted=False).values_list('mail_address', flat=True)
        validation_list = list(current_mail_address_list)
        new_mail_list = []

        for mail_address in mail_address_list:
            # Trim mail address input
            mail_address = (mail_address or '').strip()
            # Validate mail_address
            if not mail_address:
                return JsonResponse({'error_message': 'Mail address is required.'}, status=http_status.HTTP_400_BAD_REQUEST)

            if len(mail_address) > 320:
                return JsonResponse({'error_message': 'Length of mail address > 320 characters.'}, status=http_status.HTTP_400_BAD_REQUEST)

            if not re.match(mail_address_regex, mail_address):
                return JsonResponse({'error_message': 'Mail address format is invalid.'}, status=http_status.HTTP_400_BAD_REQUEST)

            validation_list.append(mail_address)

            # Add mail address to bulk insert queryset
            new_mail_address = LoginControlMailAddress(institution_id=institution_id, mail_address=mail_address)
            new_mail_list.append(new_mail_address)

        if len(validation_list) != len(set(validation_list)):
            # If there are duplicate records, return not unique error message
            return JsonResponse({'error_message': 'Mail address MUST be unique.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Insert new attribute data into DB
        LoginControlMailAddress.objects.bulk_create(new_mail_list)

        return JsonResponse({}, status=http_status.HTTP_201_CREATED)


class UpdateMailAddressView(BaseLogicAccessControlUpdateView):
    """ Update is_availability of a logic mail address view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        mail_address_id = request_body.get('mail_address_id')
        is_availability = request_body.get('is_availability')

        # Validate data
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        mail_address_id_error_message = utils.validate_integer(mail_address_id, 'mail_address_id')
        if mail_address_id_error_message is not None:
            return JsonResponse({'error_message': mail_address_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        mail_address_control_query = LoginControlMailAddress.objects.filter(id=mail_address_id, is_deleted=False)
        if not mail_address_control_query.exists():
            return JsonResponse({'error_message': 'mail_address_id is invalid.'}, status=http_status.HTTP_400_BAD_REQUEST)

        is_availability_error_message = utils.validate_boolean(is_availability, 'is_availability')
        if is_availability_error_message is not None:
            return JsonResponse({'error_message': is_availability_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Get login control mail address by institution_id
        mail_address_control = mail_address_control_query.filter(institution_id=institution_id).first()
        if not mail_address_control:
            return JsonResponse({'error_message': 'Can not setting login access control of the institution into the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Update login control mail address's is_availability
        mail_address_control.is_availability = is_availability
        mail_address_control.save()

        return JsonResponse({}, status=http_status.HTTP_204_NO_CONTENT)


class DeleteMailAddressView(BaseLogicAccessControlUpdateView):
    """ Delete a logic mail address view """
    def post(self, request, *args, **kwargs):
        # Get request body
        request_body, error_response = self.parse_json_request(request)
        if error_response:
            return error_response
        institution_id = request_body.get('institution_id')
        mail_address_id = request_body.get('mail_address_id')

        # Validate data
        institution_id_error_message = utils.validate_institution_id(institution_id)
        if institution_id_error_message is not None:
            return JsonResponse({'error_message': institution_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        mail_address_id_error_message = utils.validate_integer(mail_address_id, 'mail_address_id')
        if mail_address_id_error_message is not None:
            return JsonResponse({'error_message': mail_address_id_error_message}, status=http_status.HTTP_400_BAD_REQUEST)

        mail_address_control_query = LoginControlMailAddress.objects.filter(id=mail_address_id, is_deleted=False)
        if not mail_address_control_query.exists():
            return JsonResponse({'error_message': 'mail_address_id is invalid.'}, status=http_status.HTTP_400_BAD_REQUEST)

        # If user is institution administrator and not affiliated with institution_id, return 403 response
        if self.is_admin and not self.is_affiliated_with_not_deleted_institution(institution_id):
            return JsonResponse({'error_message': 'You do not have permission to setting login access control of the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Get login control mail address by institution_id
        mail_address_control = mail_address_control_query.filter(institution_id=institution_id).first()
        if not mail_address_control:
            return JsonResponse({'error_message': 'Can not setting login access control of the institution into the other institution.'},
                                status=http_status.HTTP_403_FORBIDDEN)

        # Update login control mail address's is_deleted to True
        mail_address_control.is_deleted = True
        mail_address_control.save()

        return JsonResponse({}, status=http_status.HTTP_204_NO_CONTENT)

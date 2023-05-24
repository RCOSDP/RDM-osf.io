import os
from operator import itemgetter
from mimetypes import MimeTypes
from django.db import connection

from admin.institutions.views import QuotaUserStorageList
from osf.models import Institution, OSFUser
from admin.base import settings
from addons.osfstorage.models import Region
from django.views.generic import ListView, View
from django.shortcuts import redirect
from admin.rdm.utils import RdmPermissionMixin
from django.core.urlresolvers import reverse
from django.http import HttpResponse, Http404
from rest_framework import status as http_status
from admin.base.utils import reverse_qs
from admin.rdm_custom_storage_location import utils
from framework.exceptions import HTTPError
from website.util.quota import update_institutional_storage_max_quota


class IconView(View):
    raise_exception = True

    def get(self, request, *args, **kwargs):
        addon_name = kwargs['addon_name']
        addon = utils.get_addon_by_name(addon_name)
        if addon:
            # get addon's icon
            image_path = os.path.join('addons', addon_name, 'static', addon.icon)
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                    content_type = MimeTypes().guess_type(addon.icon)[0]
                    return HttpResponse(image_data, content_type=content_type)
        raise Http404


class ProviderListByInstitution(RdmPermissionMixin, ListView):
    paginate_by = 25
    template_name = 'institutional_storage_quota_control/' \
                    'list_provider_of_institution.html'
    raise_exception = True
    model = Institution

    def get_order_by(self):
        order_by = self.request.GET.get('order_by', 'order_id')
        if order_by not in ['provider', 'name']:
            return 'order_id'
        return order_by

    def get_direction(self):
        direction = self.request.GET.get('status', 'desc')
        if direction not in ['asc', 'desc']:
            return 'desc'
        return direction

    def get_institution(self):
        institution_id = self.kwargs.get('institution_id')
        institution = Institution.objects.filter(id=institution_id).first()
        if institution is None:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST)
        return institution

    def get(self, request, *args, **kwargs):
        query_set = self.get_queryset()
        self.object_list = query_set
        ctx = self.get_context_data()

        if len(query_set) == 1:
            institution = self.get_institution()
            return redirect(
                reverse_qs(
                    'institutional_storage_quota_control:institution_user_list',
                    kwargs={'institution_id': institution.id},
                    query_kwargs={'region_id': query_set[0]['region_id']}
                )
            )

        return self.render_to_response(ctx)

    def get_queryset(self):
        list_provider = []
        number_id = 0

        institution_id = self.kwargs.get('institution_id')
        inst_obj = Institution.objects.filter(id=institution_id).first()
        if inst_obj is None:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST)
        list_region = Region.objects.filter(_id=inst_obj._id)

        for region in list_region:
            list_provider.append({
                'order_id': number_id,
                'region_id': region.id,
                'institution_id': institution_id,
                'name': region.name,
                'provider': region.provider_full_name,
                'icon_url_admin': reverse('institutional_storage_quota_control:icon',
                                          kwargs={'addon_name': region.provider_short_name,
                                                  'icon_filename': 'comicon.png'}),
            })

        order_by = self.get_order_by()
        direction = self.get_direction() != 'asc'
        list_provider.sort(key=itemgetter(order_by), reverse=direction)
        for provider in list_provider:
            number_id = number_id + 1
            provider['order_id'] = number_id
        return list_provider

    def get_context_data(self, **kwargs):
        query_set = self.get_queryset()
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(query_set, page_size)
        kwargs.setdefault('page', page)

        inst_obj = self.get_institution()
        kwargs['institution'] = inst_obj
        kwargs['list_storage'] = query_set
        kwargs['order_by'] = self.get_order_by()
        kwargs['direction'] = self.get_direction()
        return super(ProviderListByInstitution, self).get_context_data(**kwargs)


class InstitutionStorageList(RdmPermissionMixin, ListView):
    paginate_by = 25
    template_name = 'institutional_storage_quota_control/' \
                    'list_institution_storage.html'
    ordering = 'name'
    raise_exception = True
    model = Institution

    def merge_data(self, institutions):
        """ merge all institution storage names into the list of organization names

        :param list institutions: List of institution
        :return list: List of merged institution

        """
        _merged_inst = []
        for inst in institutions:
            # check institution is not merged
            if not [item for item in _merged_inst if item.institution_id == inst.institution_id]:
                # name attr to list of string
                inst.name = [inst.name]
                # add to merged list
                _merged_inst.append(inst)
            else:
                # get existing institution
                _inst = [item for item in _merged_inst if item.institution_id == inst.institution_id][0]
                _inst.name.append(inst.name)
        return _merged_inst

    def get(self, request, *args, **kwargs):
        count = 0
        query_set = self.get_queryset()
        self.object_list = query_set

        for item in query_set:
            if item.institution_id:
                count += 1
            else:
                self.object_list = self.object_list.exclude(id=item.id)

        ctx = self.get_context_data()

        if self.is_super_admin:
            return self.render_to_response(ctx)
        elif self.is_admin:
            # if count == 1:
            #     return redirect(reverse(
            #         'institutional_storage_quota_control:'
            #         'institutional_storages',
            #         kwargs={'institution_id': institution_id}
            #     ))
            return self.render_to_response(ctx)

    def get_queryset(self):
        if self.is_super_admin:
            query = 'select {} ' \
                    'from osf_institution ' \
                    'where addons_osfstorage_region._id = osf_institution._id'
            return Region.objects.extra(select={'institution_id': query.format('id'),
                                                'institution_name': query.format('name'),
                                                'institution_logo_name': query.format(
                                                    'logo_name'),
                                                }).order_by('institution_name', self.ordering)
        elif self.is_admin:
            user_id = self.request.user.id
            query = 'select {} ' \
                    'from osf_institution ' \
                    'where addons_osfstorage_region._id = _id ' \
                    'and id in (' \
                    '    select institution_id ' \
                    '    from osf_osfuser_affiliated_institutions ' \
                    '    where osfuser_id = {}' \
                    ')'
            return Region.objects.extra(select={'institution_id': query.format('id', user_id),
                                                'institution_name': query.format(
                                                    'name',
                                                    user_id),
                                                'institution_logo_name': query.format(
                                                    'logo_name',
                                                    user_id),
                                                })

    def get_context_data(self, **kwargs):
        object_list = self.merge_data(self.object_list)
        query_set = kwargs.pop('object_list', object_list)
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(
            query_set,
            page_size
        )
        kwargs.setdefault('institutions', query_set)
        kwargs.setdefault('page', page)
        kwargs.setdefault('logohost', settings.OSF_URL)
        return super(InstitutionStorageList, self).get_context_data(**kwargs)


class UserListByInstitutionStorageID(RdmPermissionMixin, QuotaUserStorageList):
    template_name = 'institutional_storage_quota_control/list_institute.html'
    raise_exception = True
    paginate_by = 25

    def get_institution(self):
        region = self.get_region()
        query = 'select name ' \
                'from addons_osfstorage_region ' \
                'where addons_osfstorage_region._id = osf_institution._id ' \
                'and addons_osfstorage_region.id = {region_id}'.format(region_id=region.id)
        institution = Institution.objects.filter(
            id=self.kwargs['institution_id']
        ).extra(
            select={
                'storage_name': query,
            }
        )
        return institution.first()

    def get_userlist(self):
        user_list = []
        for user in OSFUser.objects.filter(
                affiliated_institutions=self.kwargs['institution_id']
        ):
            user_list.append(self.get_user_storage_quota_info(user))
        return user_list

    def get_region(self):
        region_id = self.request.GET.get('region_id', None)
        institution_id = self.kwargs['institution_id']
        region = Region.objects.filter(id=region_id).first()
        institution = Institution.objects.filter(id=institution_id).first()
        if not region or not institution or institution._id != region._id:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST)
        return region


class UpdateQuotaUserListByInstitutionStorageID(RdmPermissionMixin, View):
    raise_exception = True

    def post(self, request, *args, **kwargs):
        institution_id = self.kwargs['institution_id']
        min_value, max_value = connection.ops.integer_field_range('IntegerField')
        max_quota = min(int(self.request.POST.get('maxQuota')), max_value)

        region_id = self.request.POST.get('region_id', None)
        region = Region.objects.filter(id=region_id).first()
        institution = Institution.objects.filter(id=institution_id).first()
        if not region or not institution or institution._id != region._id:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST)

        for user in OSFUser.objects.filter(
                affiliated_institutions=institution_id):
            update_institutional_storage_max_quota(user, region, max_quota)

        return redirect(
            reverse_qs(
                'institutional_storage_quota_control:institution_user_list',
                kwargs={'institution_id': institution_id},
                query_kwargs={'region_id': region.id}
            )
        )

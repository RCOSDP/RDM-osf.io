from __future__ import unicode_literals

import json

from django.core import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.forms.models import model_to_dict
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponse, JsonResponse
from django.views.generic import ListView, DetailView, View, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import PermissionRequiredMixin

from admin.base import settings
from admin.base.forms import ImportFileForm
from admin.institutions.forms import InstitutionForm
from api.base import settings as api_settings
from osf.models import Institution, Node, OSFUser
from website.util import quota

class InstitutionList(PermissionRequiredMixin, ListView):
    paginate_by = 25
    template_name = 'institutions/list.html'
    ordering = 'name'
    permission_required = 'osf.view_institution'
    raise_exception = True
    model = Institution

    def get_queryset(self):
        return Institution.objects.all().order_by(self.ordering)

    def get_context_data(self, **kwargs):
        query_set = kwargs.pop('object_list', self.object_list)
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(query_set, page_size)
        kwargs.setdefault('institutions', query_set)
        kwargs.setdefault('page', page)
        kwargs.setdefault('logohost', settings.OSF_URL)
        return super(InstitutionList, self).get_context_data(**kwargs)

class InstitutionUserList(PermissionRequiredMixin, ListView):
    paginate_by = 25
    template_name = 'institutions/institution_list.html'
    ordering = 'name'
    permission_required = 'osf.view_institution'
    raise_exception = True
    model = Institution

    def get_queryset(self):
        return Institution.objects.all().order_by(self.ordering)

    def get_context_data(self, **kwargs):
        query_set = kwargs.pop('object_list', self.object_list)
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(query_set, page_size)
        kwargs.setdefault('institutions', query_set)
        kwargs.setdefault('page', page)
        kwargs.setdefault('logohost', settings.OSF_URL)
        return super(InstitutionUserList, self).get_context_data(**kwargs)


class InstitutionDisplay(PermissionRequiredMixin, DetailView):
    model = Institution
    template_name = 'institutions/detail.html'
    permission_required = 'osf.view_institution'
    raise_exception = True

    def get_object(self, queryset=None):
        return Institution.objects.get(id=self.kwargs.get('institution_id'))

    def get_context_data(self, *args, **kwargs):
        institution = self.get_object()
        institution_dict = model_to_dict(institution)
        kwargs.setdefault('page_number', self.request.GET.get('page', '1'))
        kwargs['institution'] = institution_dict
        kwargs['logohost'] = settings.OSF_URL
        fields = institution_dict
        kwargs['change_form'] = InstitutionForm(initial=fields)
        kwargs['import_form'] = ImportFileForm()
        kwargs['node_count'] = institution.nodes.count()

        return kwargs


class InstitutionDetail(PermissionRequiredMixin, View):
    permission_required = 'osf.view_institution'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        view = InstitutionDisplay.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = InstitutionChangeForm.as_view()
        return view(request, *args, **kwargs)


class ImportInstitution(PermissionRequiredMixin, View):
    permission_required = 'osf.change_institution'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        form = ImportFileForm(request.POST, request.FILES)
        if form.is_valid():
            file_str = self.parse_file(request.FILES['file'])
            file_json = json.loads(file_str)
            return JsonResponse(file_json[0]['fields'])

    def parse_file(self, f):
        parsed_file = ''
        for chunk in f.chunks():
            parsed_file += str(chunk)
        return parsed_file


class InstitutionChangeForm(PermissionRequiredMixin, UpdateView):
    permission_required = 'osf.change_institution'
    raise_exception = True
    model = Institution
    form_class = InstitutionForm

    def get_object(self, queryset=None):
        provider_id = self.kwargs.get('institution_id')
        return Institution.objects.get(id=provider_id)

    def get_context_data(self, *args, **kwargs):
        kwargs['import_form'] = ImportFileForm()
        return super(InstitutionChangeForm, self).get_context_data(*args, **kwargs)

    def get_success_url(self, *args, **kwargs):
        return reverse_lazy('institutions:detail', kwargs={'institution_id': self.kwargs.get('institution_id')})


class InstitutionExport(PermissionRequiredMixin, View):
    permission_required = 'osf.view_institution'
    raise_exception = True

    def get(self, request, *args, **kwargs):
        institution = Institution.objects.get(id=self.kwargs['institution_id'])
        data = serializers.serialize('json', [institution])

        filename = '{}_export.json'.format(institution.name)

        response = HttpResponse(data, content_type='text/json')
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        return response


class CreateInstitution(PermissionRequiredMixin, CreateView):
    permission_required = 'osf.change_institution'
    raise_exception = True
    template_name = 'institutions/create.html'
    success_url = reverse_lazy('institutions:list')
    model = Institution
    form_class = InstitutionForm

    def get_context_data(self, *args, **kwargs):
        kwargs['import_form'] = ImportFileForm()
        return super(CreateInstitution, self).get_context_data(*args, **kwargs)


class InstitutionNodeList(PermissionRequiredMixin, ListView):
    template_name = 'institutions/node_list.html'
    paginate_by = 25
    ordering = 'modified'
    permission_required = 'osf.view_node'
    raise_exception = True
    model = Node

    def get_queryset(self):
        inst = self.kwargs['institution_id']
        return Node.objects.filter(affiliated_institutions=inst).order_by(self.ordering)

    def get_context_data(self, **kwargs):
        query_set = kwargs.pop('object_list', self.object_list)
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(query_set, page_size)
        kwargs.setdefault('nodes', query_set)
        kwargs.setdefault('institution', Institution.objects.get(id=self.kwargs['institution_id']))
        kwargs.setdefault('page', page)
        kwargs.setdefault('logohost', settings.OSF_URL)
        return super(InstitutionNodeList, self).get_context_data(**kwargs)


class DeleteInstitution(PermissionRequiredMixin, DeleteView):
    permission_required = 'osf.delete_institution'
    raise_exception = True
    template_name = 'institutions/confirm_delete.html'
    success_url = reverse_lazy('institutions:list')

    def delete(self, request, *args, **kwargs):
        institution = Institution.objects.get(id=self.kwargs['institution_id'])
        if institution.nodes.count() > 0:
            return redirect('institutions:cannot_delete', institution_id=institution.pk)
        return super(DeleteInstitution, self).delete(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        institution = Institution.objects.get(id=self.kwargs['institution_id'])
        if institution.nodes.count() > 0:
            return redirect('institutions:cannot_delete', institution_id=institution.pk)
        return super(DeleteInstitution, self).get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        institution = Institution.objects.get(id=self.kwargs['institution_id'])
        return institution


class CannotDeleteInstitution(TemplateView):
    template_name = 'institutions/cannot_delete.html'

    def get_context_data(self, **kwargs):
        context = super(CannotDeleteInstitution, self).get_context_data(**kwargs)
        context['institution'] = Institution.objects.get(id=self.kwargs['institution_id'])
        return context

SORT_BY = {
    'fullname': 'fullname',
    'n_fullname': '-fullname',
    'username': 'username',
    'n_username': '-username',
    'id': '_id',
    'n_id':'-_id'
}

class UserListByInstitutionID(PermissionRequiredMixin, ListView):
    template_name = 'institutions/list_institute.html'
    permission_required = 'osf.view_osfuser'
    raise_exception = True
    paginate_by = 10
    ordering = 'fullname'
    context_object_name = 'users'
    def get_user_list_institute_id(self):
        if 'institution_id'in self.kwargs:
            self.institution_id = self.kwargs['institution_id']
        else:
            self.institution_id = self.request.GET.get('institution_id','0')
        user_query_set = OSFUser.objects.filter(affiliated_institutions=self.institution_id).order_by(self.get_ordering())
        dict_of_list = []
        for user in user_query_set:
            try:
                max_quota = user.userquota.max_quota
            except ObjectDoesNotExist:
                max_quota = api_settings.DEFAULT_MAX_QUOTA
            used_quota = quota.used_quota(user.guids.first()._id)
            used_quota_abbr = quota.abbreviate_size(used_quota)
            if used_quota_abbr[1] == 'B':
                used_quota_abbr = '{:.0f} {}'.format(used_quota_abbr[0], used_quota_abbr[1])
            else:
                used_quota_abbr = '{:.1f} {}'.format(used_quota_abbr[0], used_quota_abbr[1])
            dict_of_list.append({
                'id': user.guids.first()._id,
                'name': user.fullname,
                'username': user.username,
                'ratio_to_quota': '{:.1f}%'.format(float(used_quota) / (max_quota * 1024 ** 3) * 100),
                'usage': used_quota_abbr,
                'limit_value': str(max_quota) + ' GB'
            })
        return dict_of_list

    def get_queryset(self):
        return self.get_user_list_institute_id()

    def get_context_data(self, **kwargs):
        self.users = self.get_queryset()
        kwargs['users'] = self.users
        self.page_size = self.get_paginate_by(self.users)
        self.paginator, self.page, self.query_set, self.is_paginated = self.paginate_queryset(self.users, self.page_size)
        kwargs['page'] = self.page
        kwargs['users_for_page']= self.query_set
        self.y = {
            'users': self.query_set,
            'page': self.page,
            'p': self.get_paginate_by(self.users),
            'SORT_BY': SORT_BY,
            'order': self.get_ordering(),
            'status': self.request.GET.get('status', 'all'),
        }
        kwargs['p'] =self.y['p']
        kwargs['SORT_BY'] =self.y['SORT_BY']
        kwargs['order'] =self.y['order']
        kwargs['institution_id'] = self.institution_id
        return super(UserListByInstitutionID, self).get_context_data(**kwargs)

    def get_ordering(self):
        return self.request.GET.get('order_by', self.ordering)

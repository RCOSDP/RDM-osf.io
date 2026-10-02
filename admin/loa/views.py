from __future__ import unicode_literals
from urllib.parse import urlencode
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import View, TemplateView
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from admin.rdm.utils import RdmPermissionMixin
from admin.loa.forms import LoAForm
from osf.models import Institution, LoA
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import Http404
from admin.base.utils import render_bad_request_response
import logging

logger = logging.getLogger(__name__)


class ListLoA(RdmPermissionMixin, UserPassesTestMixin, TemplateView):
    template_name = 'loa/list.html'
    raise_exception = True
    institution_id = None
    model = LoA

    form_class = LoAForm

    def dispatch(self, request, *args, **kwargs):

        # login check
        if not self.is_authenticated:
            return self.handle_no_permission()
        try:
            self.institution_id = self.request.GET.get('institution_id')
            if self.institution_id:
                self.institution_id = int(self.institution_id)
            return super(ListLoA, self).dispatch(request, *args, **kwargs)
        except ValueError:
            return render_bad_request_response(request=request, error_msgs='institution_id must be a integer')

    def test_func(self):
        """check user permissions"""
        if not self.institution_id:
            # superuser or admin has an institution
            return self.is_super_admin or self.is_institutional_admin
        else:
            # institution not exist
            if not Institution.objects.filter(id=self.institution_id).exists():
                raise Http404(
                    'Institution with id "{}" not found.'.format(
                        self.institution_id
                    ))
            # superuser or institutional admin has permission
            return self.is_super_admin or \
                (self.is_admin and self.is_affiliated_institution(self.institution_id))

    def get_context_data(self, **kwargs):
        user = self.request.user
        # superuser
        if self.is_super_admin:
            institutions = Institution.objects.all().order_by('name')
        # institution administrator
        elif self.is_admin and user.affiliated_institutions.first():
            institutions = Institution.objects.filter(pk__in=user.affiliated_institutions.all()).order_by('name')
        else:
            raise PermissionDenied('Not authorized to view the LoA.')

        selected_id = institutions.first().id

        institution_id = int(self.kwargs.get('institution_id', self.request.GET.get('institution_id', selected_id)))

        formset_loa = LoAForm(instance=LoA.objects.get_or_none(institution_id=institution_id))
        logger.info(formset_loa)
        kwargs.setdefault('institutions', institutions)
        kwargs.setdefault('institution_id', institution_id)
        kwargs.setdefault('selected_id', institution_id)
        kwargs.setdefault('formset_loa', formset_loa)

        return super(ListLoA, self).get_context_data(**kwargs)


class BulkAddLoA(RdmPermissionMixin, UserPassesTestMixin, View):
    raise_exception = True
    institution_id = None

    def dispatch(self, request, *args, **kwargs):
        """Initialize attributes shared by all view methods."""
        # login check
        if not self.is_authenticated:
            return self.handle_no_permission()
        try:
            self.institution_id = self.request.POST.get('institution_id')
            if self.institution_id:
                self.institution_id = int(self.institution_id)
            else:
                return render_bad_request_response(request=request, error_msgs='institution_id is required')
            return super(BulkAddLoA, self).dispatch(request, *args, **kwargs)
        except ValueError:
            return render_bad_request_response(request=request, error_msgs='institution_id must be a integer')

    def test_func(self):
        """check user permissions"""
        # institution not exist
        if not Institution.objects.filter(id=self.institution_id, is_deleted=False).exists():
            raise Http404(
                'Institution with id "{}" not found.'.format(
                    self.institution_id
                ))
        # superuser or institutional admin has permission
        return self.is_super_admin or \
            (self.is_admin and self.is_affiliated_institution(self.institution_id))

    def post(self, request):
        institution_id = request.POST.get('institution_id')
        aal = request.POST.get('aal')
        ial = request.POST.get('ial')
        is_mfa = request.POST.get('is_mfa')
        existing_set = LoA.objects.get_or_none(institution_id=institution_id)
        if not existing_set:
            LoA.objects.create(institution_id=institution_id, aal=aal, ial=ial, is_mfa=is_mfa, modifier=request.user)
        else:
            existing_set.aal = aal
            existing_set.ial = ial
            existing_set.is_mfa = is_mfa
            existing_set.modifier = request.user
            existing_set.save()

        base_url = reverse('loa:list')
        query_string = urlencode({'institution_id': institution_id})
        ctx = _('LoA update successful.')
        messages.success(self.request, ctx)
        return redirect('{}?{}'.format(base_url, query_string))

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
import logging
logger = logging.getLogger(__name__)


class ListLoA(RdmPermissionMixin, TemplateView):
    template_name = 'loa/list.html'
    raise_exception = True
    model = LoA

    form_class = LoAForm

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


class BulkAddLoA(RdmPermissionMixin, View):
    raise_exception = True

    def post(self, request):
        institution_id = request.POST.get('institution_id')
        aal = request.POST.get('aal')
        ial = request.POST.get('ial')
        existing_set = LoA.objects.get_or_none(institution_id=institution_id)
        if not existing_set:
            LoA.objects.create(institution_id=institution_id,
                                                  aal=aal,
                                                  ial=ial,
                                                  modifier=request.user)
        else:
            existing_set.aal = aal
            existing_set.ial = ial
            existing_set.modifier = request.user
            existing_set.save()

        base_url = reverse('loa:list')
        query_string = urlencode({'institution_id': institution_id})
        ctx = _('LoA update successful.')
        messages.success(self.request, ctx)
        return redirect('{}?{}'.format(base_url, query_string))

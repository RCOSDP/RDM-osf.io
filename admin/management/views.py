from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import PermissionRequiredMixin
from osf.management.commands.manage_switch_flags import manage_waffle
from django.core.urlresolvers import reverse
from django.shortcuts import redirect

class ManagementCommands(PermissionRequiredMixin, TemplateView):
    """ Basic form to trigger various management commands
    """
    template_name = 'management/commands.html'
    object_type = 'management'
    permission_required = 'osf.view_management'
    raise_exception = True

class ManagementCommandPermissionView(PermissionRequiredMixin, View):

    permission_required = 'osf.view_management'
    raise_exception = True

class WaffleFlag(ManagementCommandPermissionView):

    def post(self, request, *args, **kwargs):
        manage_waffle()
        return redirect(reverse('management:commands'))

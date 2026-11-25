from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView, View
from osf.management.commands.manage_switch_flags import manage_waffle
from django.core.urlresolvers import reverse
from django.shortcuts import redirect

from admin.rdm.utils import RdmPermissionMixin

class ManagementCommands(RdmPermissionMixin, UserPassesTestMixin, TemplateView):
    """ Basic form to trigger various management commands
    """
    template_name = 'management/commands.html'
    object_type = 'management'
    raise_exception = True

    def test_func(self):
        """check user permissions"""
        return self.is_super_admin


class WaffleFlag(RdmPermissionMixin, UserPassesTestMixin, View):
    raise_exception = True

    def test_func(self):
        """check user permissions"""
        return self.is_super_admin

    def post(self, request, *args, **kwargs):
        manage_waffle()
        return redirect(reverse('management:commands'))

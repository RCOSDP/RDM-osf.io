from django import forms
from osf.models import Institution
from django.utils.translation import ugettext_lazy as _


class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution

        labels = {
            'last_logged': _('Last logged'),
            'name': _('Name'),
            'description': _('Description'),
            'banner_name': _('Banner name'),
            'logo_name': _('Logo name'),
            'delegation_protocol': _('Delegation protocol'),
            'login_url': _('Login url'),
            'logout_url': _('Logout url'),
            'domains': _('Domains'),
            'email_domains': _('Email domains'),
        }

        exclude = [
            'is_deleted', 'contributors',
            '_id',
            'last_logged', 'delegation_protocol', 
            'login_url', 'logout_url',
            'domains', 'email_domains',
            'login_url', 'banner_name',
        ]

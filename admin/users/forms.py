from django import forms
from django.utils.translation import ugettext_lazy as _
from osf.models.user import AuthControl

class EmailResetForm(forms.Form):
    emails = forms.ChoiceField(label='Email')

    def __init__(self, *args, **kwargs):
        choices = kwargs.get('initial', {}).get('emails', [])
        self.base_fields['emails'] = forms.ChoiceField(choices=choices)
        super(EmailResetForm, self).__init__(*args, **kwargs)


class WorkshopForm(forms.Form):
    document = forms.FileField(
        label=_('Select a file')
    )


class UserSearchForm(forms.Form):
    guid = forms.CharField(label='guid', min_length=5, max_length=5, required=False)  # TODO: Move max to 6 when needed
    name = forms.CharField(label=_('name'), required=False)
    email = forms.EmailField(label=_('email'), required=False)

class MergeUserForm(forms.Form):
    user_guid_to_be_merged = forms.CharField(label='user_guid_to_be_merged', min_length=5, max_length=5, required=True)  # TODO: Move max to 6 when needed

class AddSystemTagForm(forms.Form):
    system_tag_to_add = forms.CharField(label='system_tag_to_add', min_length=1, max_length=1024, required=True)

class UserAuthenticationControlForm(forms.ModelForm):
    class Meta:
        model = AuthControl
        fields = ('eduPersonEntilement', 'permission')

    eduPersonEntilement  = forms.CharField(label='eduPersonEntilement', required=False)
    permission = forms.NullBooleanField(required=True)

    permission.widget = forms.widgets.RadioSelect(
        choices = [
            (True, '許可'),
            (False, '拒否'),
        ]
    )

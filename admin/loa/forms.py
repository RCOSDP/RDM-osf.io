from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from osf.models import LoA
import logging

class LoAForm(forms.ModelForm):

    CHOICES_AAL = [('', _('NULL')),(1, _('AAL1')),(2, _('AAL2'))]
    CHOICES_IAL = [('', _('NULL')),(1, _('IAL1')),(2, _('IAL2'))]
    aal = forms.ChoiceField(choices=CHOICES_AAL,required=False,)
    ial = forms.ChoiceField(choices=CHOICES_IAL,required=False,)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control form-control-sm'

    class Meta:
        model = LoA
        fields = ('aal','ial',)
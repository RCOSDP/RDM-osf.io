# -*- coding: utf-8 -*-

from django import forms
from django.utils.translation import gettext_lazy as _

from addons.workflow import settings as workflow_settings
from addons.workflow.models import WorkflowEngine, WorkflowEngineKey


ALGORITHM_CHOICES = (
    ('RS256', 'RS256'),
    ('RS384', 'RS384'),
    ('RS512', 'RS512'),
    ('ES256', 'ES256'),
    ('ES384', 'ES384'),
    ('ES512', 'ES512'),
)


class WorkflowEngineForm(forms.ModelForm):
    label = forms.CharField(
        label=_('Name'),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False,
    )
    gateway_base_url = forms.URLField(
        label=_('Gateway URL'),
        widget=forms.URLInput(attrs={'class': 'form-control'}),
    )
    signing_kid = forms.CharField(
        label=_('Signing kid'),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    verify_ssl = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Verify SSL certificate'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    request_timeout = forms.IntegerField(
        label=_('Request timeout (seconds)'),
        min_value=1,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    keyset_url = forms.CharField(widget=forms.HiddenInput(), required=False)
    upload_whitelist_node_ids_input = forms.CharField(
        required=False,
        label=_('Upload whitelist node IDs'),
        help_text=_('Enter node IDs separated by commas or newlines (e.g., "abc12, def34" or one per line). Only listed projects can upload workflow ZIPs.'),
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
    )

    class Meta:
        model = WorkflowEngine
        fields = [
            'label',
            'gateway_base_url',
            'signing_kid',
            'verify_ssl',
            'request_timeout',
            'keyset_url',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_signing_kid_field()
        self._initialize_upload_whitelist()

    def clean_upload_whitelist_node_ids_input(self):
        raw_input = self.cleaned_data.get('upload_whitelist_node_ids_input', '')
        if not raw_input or not raw_input.strip():
            return []

        node_ids = []
        for line in raw_input.replace(',', '\n').split('\n'):
            node_id = line.strip()
            if node_id:
                node_ids.append(node_id)
        return node_ids

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.upload_whitelist_node_ids = self.cleaned_data.get('upload_whitelist_node_ids_input', [])
        if commit:
            instance.save()
        return instance

    def _configure_signing_kid_field(self) -> None:
        specs = workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS or []
        choices = []
        for spec in specs:
            kid = spec.get('kid') if isinstance(spec, dict) else None
            if kid:
                choices.append((kid, kid))

        if choices:
            initial = self.initial.get('signing_kid') or self.fields['signing_kid'].initial
            self.fields['signing_kid'] = forms.ChoiceField(
                choices=choices,
                label=_('Signing kid'),
                required=True,
                initial=initial,
                widget=forms.Select(attrs={'class': 'form-control'}),
                help_text=_('Select the signing key that RDM will use when calling the gateway.'),
            )

    def _initialize_upload_whitelist(self) -> None:
        if not (self.instance and self.instance.pk):
            return
        node_ids = self.instance.upload_whitelist_node_ids
        self.fields['upload_whitelist_node_ids_input'].initial = '\n'.join(node_ids)

class WorkflowEngineKeyForm(forms.ModelForm):
    kid = forms.CharField(
        label=_('Key ID (kid)'),
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    algorithm = forms.ChoiceField(
        choices=ALGORITHM_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Algorithm'),
    )
    public_key = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        label=_('Public key'),
    )

    class Meta:
        model = WorkflowEngineKey
        fields = ['kid', 'algorithm', 'public_key']

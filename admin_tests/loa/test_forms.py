# -*- coding: utf-8 -*-
"""Tests for admin.loa.forms.LoAForm."""
import pytest

from admin.loa.forms import LoAForm
from osf.models.loa import LoA
from osf_tests.factories import InstitutionFactory, AuthUserFactory

pytestmark = pytest.mark.django_db


class TestLoAForm:
    """Tests for LoAForm."""

    def test_form_fields(self):
        form = LoAForm()
        assert 'aal' in form.fields
        assert 'ial' in form.fields
        assert 'is_mfa' in form.fields

    def test_form_valid_with_all_fields(self):
        form = LoAForm(data={'aal': '2', 'ial': '2', 'is_mfa': 'True'})
        assert form.is_valid(), form.errors

    def test_form_valid_with_zero_values(self):
        """aal=0 and ial=0 represent the NULL choice."""
        form = LoAForm(data={'aal': '0', 'ial': '0', 'is_mfa': 'False'})
        assert form.is_valid(), form.errors

    def test_form_valid_with_empty_fields(self):
        """All fields are not required, so empty strings should be accepted."""
        form = LoAForm(data={'aal': '', 'ial': '', 'is_mfa': ''})
        assert form.is_valid(), form.errors

    def test_form_aal_choices(self):
        form = LoAForm()
        aal_values = [c[0] for c in form.fields['aal'].choices]
        assert 0 in aal_values
        assert 1 in aal_values
        assert 2 in aal_values

    def test_form_ial_choices(self):
        form = LoAForm()
        ial_values = [c[0] for c in form.fields['ial'].choices]
        assert 0 in ial_values
        assert 1 in ial_values
        assert 2 in ial_values

    def test_form_is_mfa_choices(self):
        form = LoAForm()
        mfa_values = [c[0] for c in form.fields['is_mfa'].choices]
        assert False in mfa_values
        assert True in mfa_values

    def test_form_widget_css_class(self):
        """All field widgets should have 'form-control form-control-sm' CSS class."""
        form = LoAForm()
        for field in form.fields.values():
            assert 'form-control form-control-sm' in field.widget.attrs.get('class', '')

    def test_form_with_instance(self):
        """Form should populate correctly from an existing LoA instance."""
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=2, ial=1, is_mfa=True, modifier=modifier,
        )
        form = LoAForm(instance=loa)
        assert form.initial['aal'] == 2
        assert form.initial['ial'] == 1
        assert form.initial['is_mfa'] is True

    def test_form_meta_model(self):
        assert LoAForm.Meta.model is LoA

    def test_form_meta_fields(self):
        assert LoAForm.Meta.fields == ('aal', 'ial', 'is_mfa')

    def test_form_invalid_aal_choice(self):
        form = LoAForm(data={'aal': '99', 'ial': '1', 'is_mfa': 'False'})
        assert not form.is_valid()
        assert 'aal' in form.errors

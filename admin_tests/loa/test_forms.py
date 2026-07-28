# -*- coding: utf-8 -*-
"""Tests for admin.loa.forms.LoAForm."""
import pytest
from django.utils.translation import ugettext_lazy as _

from admin.loa.forms import LoAForm
from osf.models.loa import LoA
from osf_tests.factories import InstitutionFactory, AuthUserFactory

pytestmark = pytest.mark.django_db


class TestLoAForm:
    """Tests for LoAForm."""

    # ---------------------------------------------------------------
    # Fields and declaration order
    # ---------------------------------------------------------------

    def test_form_fields(self):
        form = LoAForm()
        assert 'ial' in form.fields
        assert 'aal' in form.fields
        assert 'is_mfa' in form.fields

    def test_form_field_order(self):
        """Fields are declared in IAL -> AAL -> MFA order and rendered as such."""
        form = LoAForm()
        assert list(form.fields.keys()) == ['ial', 'aal', 'is_mfa']

    def test_form_meta_model(self):
        assert LoAForm.Meta.model is LoA

    def test_form_meta_fields(self):
        assert LoAForm.Meta.fields == ('ial', 'aal', 'is_mfa')

    # ---------------------------------------------------------------
    # Labels
    # ---------------------------------------------------------------

    def test_form_ial_label(self):
        """ial has an explicit label instead of the auto-generated 'Ial'."""
        form = LoAForm()
        assert str(form.fields['ial'].label) == str(_('Required IAL level'))

    def test_form_aal_label(self):
        """aal has an explicit label instead of the auto-generated 'Aal'."""
        form = LoAForm()
        assert str(form.fields['aal'].label) == str(_('Required AAL level'))

    def test_form_is_mfa_label(self):
        form = LoAForm()
        assert str(form.fields['is_mfa'].label) == str(_('Display MFA link button'))

    # ---------------------------------------------------------------
    # Choices
    # ---------------------------------------------------------------

    def test_form_ial_choices(self):
        form = LoAForm()
        ial_values = [c[0] for c in form.fields['ial'].choices]
        assert ial_values == [0, 1, 2]

    def test_form_aal_choices(self):
        form = LoAForm()
        aal_values = [c[0] for c in form.fields['aal'].choices]
        assert aal_values == [0, 1, 2]

    def test_form_is_mfa_choices(self):
        form = LoAForm()
        mfa_values = [c[0] for c in form.fields['is_mfa'].choices]
        assert False in mfa_values
        assert True in mfa_values

    def test_form_is_mfa_initial_is_false(self):
        form = LoAForm()
        assert form.fields['is_mfa'].initial is False

    def test_form_fields_are_not_required(self):
        form = LoAForm()
        for name, field in form.fields.items():
            assert field.required is False, '{} should not be required'.format(name)

    # ---------------------------------------------------------------
    # Validation
    # ---------------------------------------------------------------

    def test_form_valid_with_all_fields(self):
        form = LoAForm(data={'ial': '2', 'aal': '2', 'is_mfa': 'True'})
        assert form.is_valid(), form.errors

    def test_form_valid_with_zero_values(self):
        """ial=0 and aal=0 represent the NULL choice."""
        form = LoAForm(data={'ial': '0', 'aal': '0', 'is_mfa': 'False'})
        assert form.is_valid(), form.errors

    def test_form_valid_with_empty_fields(self):
        """All fields are not required, so empty strings should be accepted."""
        form = LoAForm(data={'ial': '', 'aal': '', 'is_mfa': ''})
        assert form.is_valid(), form.errors

    def test_form_invalid_ial_choice(self):
        form = LoAForm(data={'ial': '99', 'aal': '1', 'is_mfa': 'False'})
        assert not form.is_valid()
        assert 'ial' in form.errors

    def test_form_invalid_aal_choice(self):
        form = LoAForm(data={'ial': '1', 'aal': '99', 'is_mfa': 'False'})
        assert not form.is_valid()
        assert 'aal' in form.errors

    # ---------------------------------------------------------------
    # Widget / instance
    # ---------------------------------------------------------------

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
            institution=institution, ial=1, aal=2, is_mfa=True, modifier=modifier,
        )
        form = LoAForm(instance=loa)
        assert form.initial['ial'] == 1
        assert form.initial['aal'] == 2
        assert form.initial['is_mfa'] is True

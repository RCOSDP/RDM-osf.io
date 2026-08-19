# -*- coding: utf-8 -*-
"""Tests for the LoA (Level of Assurance) model."""
import pytest

from osf.models.loa import LoA
from osf_tests.factories import InstitutionFactory, AuthUserFactory

pytestmark = pytest.mark.django_db


class TestBaseManager:
    """Tests for BaseManager.get_or_none()."""

    def test_get_or_none_returns_object_when_exists(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=1, ial=1, is_mfa=False, modifier=modifier,
        )
        result = LoA.objects.get_or_none(institution_id=institution.id)
        assert result is not None
        assert result.pk == loa.pk

    def test_get_or_none_returns_none_when_not_exists(self):
        result = LoA.objects.get_or_none(institution_id=99999)
        assert result is None


class TestLoAModel:
    """Tests for the LoA model fields and behaviour."""

    def test_create_loa_with_all_fields(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=2, ial=2, is_mfa=True, modifier=modifier,
        )
        assert loa.pk is not None
        assert loa.institution == institution
        assert loa.aal == 2
        assert loa.ial == 2
        assert loa.is_mfa is True
        assert loa.modifier == modifier

    def test_create_loa_with_null_aal_ial(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=None, ial=None, is_mfa=False, modifier=modifier,
        )
        assert loa.aal is None
        assert loa.ial is None

    def test_create_loa_with_zero_values(self):
        """aal=0 and ial=0 represent NULL choice."""
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=0, ial=0, is_mfa=False, modifier=modifier,
        )
        assert loa.aal == 0
        assert loa.ial == 0

    def test_is_mfa_defaults_to_false(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, modifier=modifier,
        )
        assert loa.is_mfa is False

    def test_loa_timestamps(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=1, ial=1, modifier=modifier,
        )
        assert loa.created is not None
        assert loa.modified is not None

    def test_cascade_delete_on_institution(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        LoA.objects.create(
            institution=institution, aal=1, ial=1, modifier=modifier,
        )
        institution_id = institution.id
        institution.delete()
        assert LoA.objects.filter(institution_id=institution_id).count() == 0

    def test_cascade_delete_on_modifier(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        LoA.objects.create(
            institution=institution, aal=1, ial=1, modifier=modifier,
        )
        modifier_pk = modifier.pk
        modifier.delete()
        assert LoA.objects.filter(modifier_id=modifier_pk).count() == 0

    def test_unicode_representation(self):
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        loa = LoA.objects.create(
            institution=institution, aal=2, ial=1, is_mfa=True, modifier=modifier,
        )
        expected = u'institution_{}:{}:{}:{}'.format(
            institution._id, 2, 1, True,
        )
        # LoA defines __unicode__ (not __str__), so call it directly
        assert loa.__unicode__() == expected

    def test_init_pops_node_kwarg(self):
        """__init__ should silently pop 'node' from kwargs."""
        institution = InstitutionFactory()
        modifier = AuthUserFactory()
        # Should not raise
        loa = LoA(
            institution=institution, aal=1, ial=1, modifier=modifier, node='anything',
        )
        assert loa.aal == 1

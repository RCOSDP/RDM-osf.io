import pytest
from django.db import IntegrityError

from osf.models import ServiceAccessControlSetting


@pytest.mark.django_db
class TestServiceAccessControlSetting:
    def test_has_an_integer_pk(self):
        setting = ServiceAccessControlSetting(
            institution_id='gakunin',
            domain='test.com',
            is_ial2_or_aal2=True,
            user_domain='example.com',
            is_whitelist=True
        )
        setting.save()
        assert type(setting.pk) is int

    def test_validation__no_values(self):
        setting = ServiceAccessControlSetting()
        with pytest.raises(IntegrityError):
            setting.save()

    def test_validation__no_institution_id(self):
        setting = ServiceAccessControlSetting(
            institution_id=None,
            domain='test.com',
            is_ial2_or_aal2=True,
            user_domain='example.com',
            is_whitelist=True

        )
        with pytest.raises(IntegrityError):
            setting.save()

    def test_validation__no_domain(self):
        setting = ServiceAccessControlSetting(
            institution_id='gakunin',
            domain=None,
            is_ial2_or_aal2=True,
            user_domain='example.com',
            is_whitelist=True
        )
        with pytest.raises(IntegrityError):
            setting.save()

    def test_validation__no_is_ial2_or_aal2(self):
        # Null is_ial2_or_aal2
        setting = ServiceAccessControlSetting(
            institution_id='gakunin',
            domain='test.com',
            is_ial2_or_aal2=None,
            user_domain='example.com',
            is_whitelist=True
        )
        with pytest.raises(IntegrityError):
            setting.save()

    def test_validation__no_user_domain(self):
        setting = ServiceAccessControlSetting(
            institution_id='gakunin',
            domain='test.com',
            is_ial2_or_aal2=True,
            user_domain=None,
            is_whitelist=True
        )
        with pytest.raises(IntegrityError):
            setting.save()

    def test_validation__no_is_whitelist(self):
        setting = ServiceAccessControlSetting(
            institution_id='gakunin',
            domain='test.com',
            is_ial2_or_aal2=True,
            user_domain='example.com',
            is_whitelist=None
        )
        with pytest.raises(IntegrityError):
            setting.save()

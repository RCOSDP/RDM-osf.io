import pytest
from django.db import IntegrityError

from osf.models import Function
from osf_tests.factories import ServiceAccessControlSettingFactory


@pytest.mark.django_db
class TestFunction:
    def test_has_an_integer_pk(self):
        service_access_control_setting = ServiceAccessControlSettingFactory()
        function = Function(function_code='test', service_access_control_setting=service_access_control_setting)
        function.save()
        assert type(function.pk) is int

    def test_validation__no_values(self):
        function = Function()
        with pytest.raises(IntegrityError):
            function.save()

    def test_validation__no_related_service_acccess_control_setting(self):
        function = Function(function_code='test')
        with pytest.raises(IntegrityError):
            function.save()

    def test_validation__no_function_code(self):
        service_access_control_setting = ServiceAccessControlSettingFactory()
        function = Function(function_code=None, service_access_control_setting=service_access_control_setting)
        with pytest.raises(IntegrityError):
            function.save()

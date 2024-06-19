from admin.base.settings import ATTRIBUTE_NAME_LIST
from osf.models.login_control import LoginControlAuthenticationAttribute, LoginControlMailAddress
from nose import tools as nt
from .factories import InstitutionFactory, LoginControlAuthenticationAttributeFactory, LoginControlMailAddressFactory
import pytest


class TestLoginControlAuthenticationAttributeModel:

    @pytest.mark.django_db
    def test_factory(self):
        institution = InstitutionFactory()
        authentication_attribute = LoginControlAuthenticationAttributeFactory(institution=institution)
        nt.assert_equal(authentication_attribute.institution, institution)
        nt.assert_equal(authentication_attribute.is_availability, True)
        nt.assert_in(authentication_attribute.attribute_name, ATTRIBUTE_NAME_LIST)

    @pytest.mark.django_db
    def test__init__(self):
        institution = InstitutionFactory()
        authentication_attribute = LoginControlAuthenticationAttribute(institution=institution, attribute_name='ou', attribute_value='test')
        nt.assert_equal(authentication_attribute.institution, institution)
        nt.assert_equal(authentication_attribute.is_availability, True)
        nt.assert_in(authentication_attribute.attribute_name, ATTRIBUTE_NAME_LIST)


class TestLoginControlMailAddressModel:
    @pytest.mark.django_db
    def test_factory(self):
        institution = InstitutionFactory()
        mail_address = LoginControlMailAddressFactory(institution=institution)
        nt.assert_equal(mail_address.institution, institution)
        nt.assert_equal(mail_address.is_availability, True)

    @pytest.mark.django_db
    def test__init__(self):
        institution = InstitutionFactory()
        mail_address = LoginControlMailAddress(institution=institution)
        nt.assert_equal(mail_address.institution, institution)
        nt.assert_equal(mail_address.is_availability, True)

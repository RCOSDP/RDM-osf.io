import pytest
from api.base.settings.defaults import API_BASE
from nose import tools as nt

from api.institutions.views import LoginAvailability
from osf_tests.factories import InstitutionFactory, AuthUserFactory, LoginControlAuthenticationAttributeFactory
from tests.base import ApiTestCase


@pytest.mark.django_db
class TestLoginAvailability(ApiTestCase):
    def setUp(self):
        super(TestLoginAvailability, self).setUp()
        self.institution = InstitutionFactory()
        self.institution.save()

        self.attribute1 = LoginControlAuthenticationAttributeFactory(institution=self.institution, attribute_name='mail', attribute_value='test.com')
        self.attribute2 = LoginControlAuthenticationAttributeFactory(institution=self.institution, attribute_name='o', attribute_value='test_o')
        self.attribute3 = LoginControlAuthenticationAttributeFactory(institution=self.institution, attribute_name='sn', attribute_value='test_sn')

        self.user = AuthUserFactory()
        self.user.save()

        self.url = '/{0}institutions/login_availability/'.format(API_BASE)
        self.view = LoginAvailability()

    def test_get_serializer_class(self):
        nt.assert_is_none(self.view.get_serializer_class())

    def test__get_embed_partial(self):
        nt.assert_is_none(self.view._get_embed_partial())

    def test_post__invalid_institution_guid(self):
        payload = {
            'institution_id': '',
        }

        res = self.app.simple_post_api(self.url, payload, expect_errors=True)
        nt.assert_equal(res.status_code, 403)

    def test_post__institution_no_logic_condition(self):
        payload = {
            'institution_id': self.institution.guid,
        }

        res = self.app.simple_post_api(self.url, payload)
        res_data = res.json['login_availability']
        nt.assert_equal(res.status_code, 200)
        nt.assert_equal(res_data, 'check mail address')

    def test_post__match_logic_condition_and_login_availability_default(self):
        self.institution.login_logic_condition = f'{self.attribute1.id}&&{self.attribute2.id}&&{self.attribute3.id}'
        self.institution.save()
        payload = {
            'institution_id': self.institution.guid,
            'mail': 'test.com',
            'o': [
                'test_o',
                'test_o_2',
            ],
            'sn': 'test_sn',
        }

        res = self.app.simple_post_api(self.url, payload, expect_errors=True)
        nt.assert_equal(res.status_code, 403)

    def test_post__match_logic_condition_and_not_login_availability_default(self):
        self.institution.login_logic_condition = f'{self.attribute1.id}&&{self.attribute2.id}&&{self.attribute3.id}'
        self.institution.login_availability_default = False
        self.institution.save()
        payload = {
            'institution_id': self.institution.guid,
            'mail': 'test.com',
            'o': [
                'test_o',
                'test_o_2',
            ],
            'sn': 'test_sn',
        }

        res = self.app.simple_post_api(self.url, payload)
        res_data = res.json['login_availability']
        nt.assert_equal(res.status_code, 200)
        nt.assert_equal(res_data, 'can login')

    def test_post__not_match_logic_condition(self):
        self.institution.login_logic_condition = f'{self.attribute1.id}&&{self.attribute2.id}&&{self.attribute3.id}'
        self.institution.save()
        payload = {
            'institution_id': self.institution.guid,
            'o': [
                'test_o_1',
                'test_o_2',
            ],
            'sn': 'test_sn_wrong',
        }

        res = self.app.simple_post_api(self.url, payload)
        res_data = res.json['login_availability']
        nt.assert_equal(res.status_code, 200)
        nt.assert_equal(res_data, 'check mail address')

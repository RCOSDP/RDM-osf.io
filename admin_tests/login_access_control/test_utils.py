import pytest
from nose import tools as nt
from admin.login_access_control import utils
from osf_tests.factories import InstitutionFactory


class TestValidateValue:
    def test_validate_integer(self):
        name = 'attribute_id'
        nt.assert_is_none(utils.validate_integer(1, name))
        nt.assert_is_not_none(utils.validate_integer(None, name))
        nt.assert_is_not_none(utils.validate_integer('test', name))

    def test_validate_boolean(self):
        name = 'is_availability'
        nt.assert_is_none(utils.validate_boolean(True, name))
        nt.assert_is_none(utils.validate_boolean(False, name))
        nt.assert_is_not_none(utils.validate_boolean(None, name))
        nt.assert_is_not_none(utils.validate_boolean('test', name))

    @pytest.mark.django_db
    def test_validate_institution_id(self):
        institution = InstitutionFactory()
        nt.assert_is_none(utils.validate_institution_id(institution.id))
        nt.assert_is_not_none(utils.validate_institution_id(None))
        nt.assert_is_not_none(utils.validate_institution_id('test'))
        nt.assert_is_not_none(utils.validate_institution_id(0))

    def test_validate_logic_condition(self):
        nt.assert_true(utils.validate_logic_condition('1&&(2||!3)'))
        nt.assert_true(utils.validate_logic_condition(''))
        nt.assert_true(utils.validate_logic_condition(None))
        nt.assert_true(utils.validate_logic_condition('12'))
        nt.assert_true(utils.validate_logic_condition('!((2))'))

        nt.assert_false(utils.validate_logic_condition(1234))
        nt.assert_false(utils.validate_logic_condition('!a'))
        nt.assert_false(utils.validate_logic_condition('1@@2++3--4<5?6>'))
        nt.assert_false(utils.validate_logic_condition('1&&&&2'))
        nt.assert_false(utils.validate_logic_condition('1|||2'))
        nt.assert_false(utils.validate_logic_condition('!((2)'))
        nt.assert_false(utils.validate_logic_condition('()'))

    def test_has_invalid_character(self):
        nt.assert_true(utils.has_invalid_character('1@@2++3--4<5?6>'))
        nt.assert_true(utils.has_invalid_character('a||b'))
        nt.assert_false(utils.has_invalid_character('1&&(2||!3)'))
        nt.assert_false(utils.has_invalid_character(''))
        nt.assert_false(utils.has_invalid_character('12'))

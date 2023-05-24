from osf.models import AuthenticationAttribute
from api.base import settings as api_settings
from .factories import AuthenticationAttributeFactory
import pytest


@pytest.mark.django_db
def test_factory():
    attribute = AuthenticationAttributeFactory()
    assert attribute.index_number == api_settings.DEFAULT_INDEX_NUMBER
    assert attribute.attribute_name is None
    assert attribute.attribute_value is None


@pytest.mark.django_db
def test_factory_with_params():
    attribute = AuthenticationAttributeFactory(
        index_number=2,
        attribute_name='mail',
        attribute_value='test'
    )
    attribute_test = AuthenticationAttribute.objects.get(id=attribute.id)
    assert attribute_test.index_number == 2
    assert attribute_test.attribute_name == 'mail'
    assert attribute_test.attribute_value == 'test'


@pytest.mark.django_db
def test_factory_delete():
    attribute = AuthenticationAttributeFactory()
    attribute.delete()
    attribute_test = AuthenticationAttribute.objects.get(id=attribute.id)
    assert attribute_test.attribute_name is None
    assert attribute_test.attribute_value is None
    assert attribute_test.is_deleted is True


@pytest.mark.django_db
def test_factory_restore():
    attribute = AuthenticationAttributeFactory(is_deleted=True)
    attribute.restore()
    attribute_test = AuthenticationAttribute.objects.get(id=attribute.id)
    assert attribute_test.is_deleted is False

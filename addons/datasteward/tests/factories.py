import factory
from factory.django import DjangoModelFactory
from osf_tests.factories import UserFactory

from ..models import UserSettings


class UserSettingsFactory(DjangoModelFactory):
    class Meta:
        model = UserSettings

    owner = factory.SubFactory(UserFactory)

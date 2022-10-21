# -*- coding: utf-8 -*-
from django.db import models
from factory import Sequence, SubFactory
from factory.django import DjangoModelFactory
from osf_tests.factories import ExternalAccountFactory

from addons.rushfiles.models import NodeSettings, UserSettings
from osf_tests.factories import UserFactory,ProjectFactory


class RushfilesUserSettingFactory(DjangoModelFactory):
    class Meta:
        model = UserSettings
    owner = SubFactory(UserFactory)

class RushfilesNodeSettingFactory(DjangoModelFactory):
    class Meta:
        model = NodeSettings
    owner = SubFactory(ProjectFactory)
    user_settings = SubFactory(RushfilesUserSettingFactory)


class RushfilesAccountFactory(ExternalAccountFactory):
    provider = 'rushfiles'
    provider_id = Sequence(lambda n: 'id-{0}'.format(n))
    oauth_key = Sequence(lambda n: 'key-{0}'.format(n))
    display_name = 'fake rushfiles'

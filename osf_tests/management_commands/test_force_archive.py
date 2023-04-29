# -*- coding: utf-8 -*-
import mock  # noqa
import pytest

from addons.osfstorage.tests import factories
from osf.management.commands.force_archive import archive
from osf_tests.factories import RegionFactory, NodeFactory, RegistrationFactory
from tests.base import OsfTestCase


@pytest.mark.django_db
class TestArchiveUtils(OsfTestCase):

    def setUp(self):
        super(TestArchiveUtils, self).setUp()
        self.config = {
            'storage': {
                'provider': 'osfstorage',
                'container': 'osf_storage',
                'use_public': True,
            }
        }
        self.user = factories.AuthUserFactory()
        self.region = RegionFactory(waterbutler_settings=self.config)

    def test_archive_exception(self):
        proj = NodeFactory()
        NodeFactory(parent=proj)
        comp2 = NodeFactory(parent=proj)
        NodeFactory(parent=comp2)
        reg = RegistrationFactory(project=proj)
        archive(reg, self.region.id)

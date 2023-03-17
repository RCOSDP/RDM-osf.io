# -*- coding: utf-8 -*-
import mock  # noqa
import pytest

from addons.osfstorage.tests import factories
from osf_tests.factories import ProjectFactory, RegionFactory, NodeFactory
from tests.base import OsfTestCase
from website.archiver.utils import archive_provider_for, link_archive_provider


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
        self.project = ProjectFactory(creator=self.user)
        self.region = RegionFactory(waterbutler_settings=self.config)
        self.new_component = NodeFactory(parent=self.project)
        self.component_node_settings = self.new_component.get_addon('osfstorage')
        self.component_node_settings.region = self.region
        self.component_node_settings.full_name = self.config['storage']['provider']
        self.component_node_settings.save()

    def test_archive_provider_for(self):
        res = archive_provider_for(self.new_component, self.user)
        assert res.region_id == self.new_component.get_addon('osfstorage').region_id

    def test_archive_provider_for_excpetion(self):
        with mock.patch('osf.models.mixins.AddonModelMixin.get_addon', side_effect=Exception('mocked error')):
            res = archive_provider_for(self.new_component, self.user)
            assert res.region_id == self.new_component.get_first_addon('osfstorage').region_id

    def test_link_archive_provider(self):
        with mock.patch('osf.models.node.AbstractNode.get_addon', return_value=None):
            with mock.patch('osf.models.node.AbstractNode.add_addon', return_value=self.component_node_settings):
                link_archive_provider(self.new_component, self.user)

    def test_link_archive_provider_exception(self):
        with mock.patch('osf.models.node.AbstractNode.get_addon', return_value=None):
            with mock.patch('osf.models.node.AbstractNode.add_addon', side_effect=Exception('mocked error')):
                with mock.patch('osf.models.node.AbstractNode.get_first_addon', return_value=self.component_node_settings):
                    link_archive_provider(self.new_component, self.user)

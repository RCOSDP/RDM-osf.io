# -*- coding: utf-8 -*-
import pytest
from nose import tools as nt
from addons.osfstorage.tests import factories
from osf_tests.factories import ProjectFactory, RegionFactory, NodeFactory
from tests.base import OsfTestCase
from unittest import mock
from addons.osfstorage.models import NodeSettings


@pytest.mark.django_db
class TestAddonModelMixin(OsfTestCase):

    def setUp(self):
        super(TestAddonModelMixin, self).setUp()
        self.config = {
            'storage': {
                'provider': 'osfstorage',
                'container': 'osf_storage',
                'use_public': True,
            }
        }
        self.user = factories.AuthUserFactory()
        self.region = RegionFactory(waterbutler_settings=self.config)
        self.project = ProjectFactory(creator=self.user)
        self.project.save()

        self.new_component = NodeFactory(parent=self.project, creator=self.user)
        self.new_component.save()
    def test_get_addon_region(self):
        root_id = 1
        res = self.new_component.get_addon('osfstorage', False, self.region.id, root_id)
        nt.assert_is_instance(res, NodeSettings)

    def test_get_addon_settings_obj_not_exist(self):
        root_id = 1
        res = self.new_component.get_addon('osfstorage', False, self.region.id, root_id)
        nt.assert_is_instance(res, NodeSettings)

    def test_get_addon_exception_lookuperror(self):
        with mock.patch('osf.models.mixins.AddonModelMixin._settings_model', side_effect=LookupError()):
            self.new_component.get_addon(None)

    def test_get_addon_except_mutiple(self):
        project = ProjectFactory(creator=self.user)
        region_1 = RegionFactory()
        region_2 = RegionFactory()
        project.add_addon('osfstorage', auth=None, region_id=region_1.id)
        project.add_addon('osfstorage', auth=None, region_id=region_2.id)
        project.save()
        addon = project.get_addon('osfstorage', region_id=region_1.id)

        assert addon.region.id == region_1.id

        root_id = project.get_addon('osfstorage', region_id=region_2.id).get_root().id
        addon_1 = project.get_addon('osfstorage', root_id=root_id)

        assert addon_1.region.id == region_2.id

    def test_get_addon_not_settings_model(self):
        with mock.patch('osf.models.mixins.AddonModelMixin._settings_model', return_value=None):
            res = self.new_component.get_addon('osfstorage')
            assert res is None

    def test_get_addon_settings_multiple_objects_returned(self):
        self.new_component.get_addon('osfstorage')

    def test_get_first_addon(self):
        res = self.new_component.get_first_addon('osfstorage', is_deleted=False)
        assert res is not None

    def test_get_first_addon_key_error(self):
        res = self.new_component.get_first_addon('osfstorage')
        assert res is not None

    def test_get_first_addon_exception(self):
        res = self.new_component.get_first_addon(None)
        assert res is None

    def test_get_first_addon_return_none(self):
        with mock.patch('osf.models.mixins.AddonModelMixin._settings_model', return_value=None):
            res = self.new_component.get_first_addon('osfstorage')
            assert res is None

    @mock.patch('osf.models.mixins.AddonModelMixin._settings_model')
    def test_add_addon_not_settings_model(self, mock_settings_model):
        mock_settings_model.return_value = None
        temp_region = RegionFactory(name='Frankfort', _id='eu-central-1')

        res = self.new_component.add_addon('osfstorage', None, False, temp_region.id)
        assert res is None

    @mock.patch('osf.models.mixins.AddonModelMixin._settings_model')
    def test_add_addon_not_raise_lookup_error(self, mock_settings_model):
        mock_settings_model.side_effect = LookupError('mock error')
        temp_region = RegionFactory(name='Frankfort', _id='eu-central-1')

        res = self.new_component.add_addon('osfstorage', None, False, temp_region.id)
        assert res is None

    def test_delete_addon(self):
        with mock.patch('osf.models.mixins.AddonModelMixin.get_addon', return_value=None):
            res = self.new_component.delete_addon('node', auth=self.user.auth)
            assert res is False

    def test_get_addons(self):
        res = self.new_component.get_addons()
        nt.assert_is_instance(res, list)
        nt.assert_is_instance(res[0], NodeSettings)

    def test_get_osfstorage_addons(self):
        res = self.new_component.get_osfstorage_addons()
        nt.assert_is_instance(res[0], NodeSettings)

    def test_get_osfstorage_addons_return_none(self):
        with mock.patch('osf.models.mixins.AddonModelMixin._settings_model', return_value=None):
            res = self.new_component.get_osfstorage_addons()
            assert len(res) == 0

    def test_get_osfstorage_addons_except(self):
        with mock.patch('osf.models.mixins.AddonModelMixin._settings_model', side_effect=LookupError()):
            res = self.new_component.get_osfstorage_addons()
            assert len(res) == 0

    def test_has_addon(self):
        res = self.new_component.has_addon('osfstorage', False)
        assert res is True

    def test_has_addon_except(self):
        res = self.new_component.has_addon('not_corect_name', False)
        assert res is False

    def test_has_addon_return_none(self):
        with mock.patch('osf.models.mixins.AddonModelMixin._settings_model', return_value=None):
            res = self.new_component.has_addon('not_corect_name', False)
            assert res is False

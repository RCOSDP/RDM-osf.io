# -*- coding: utf-8 -*-
import unittest
import six

from mock import patch, MagicMock
import pytest
from nose.tools import (
    assert_true, assert_false,
    assert_equal,
)

from addons.osfstorage.models import Region,NodeSettings as osfNodeSettings
from admin.rdm_addons.utils import get_rdm_addon_option
from framework.auth import Auth
from osf.models import BaseFileNode
from osf_tests.factories import (
    fake_email,
    AuthUserFactory,
    InstitutionFactory,
    ExternalAccountFactory,
    UserFactory,
    ProjectFactory,
    RegionFactory
)
from addons.s3compatinstitutions.apps import s3compatinstitutions_root, SHORT_NAME
from addons.s3compatinstitutions.models import NodeSettings
from tests.base import OsfTestCase

USE_MOCK = True  # False for DEBUG

pytestmark = pytest.mark.django_db

NAME = 's3compatinstitutions'
PACKAGE = 'addons.{}'.format(NAME)

DEFAULT_BASE_FOLDER = 'GRDM'
ROOT_FOLDER_FORMAT = '{guid}'

def filename_filter(name):
    return name.replace('/', '_')

class TestS3Compatinstitutions(unittest.TestCase):

    def setUp(self):

        super(TestS3Compatinstitutions, self).setUp()

        self.institution = InstitutionFactory()

        self.user = UserFactory()
        self.user.eppn = fake_email()
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

        # create
        self.option = get_rdm_addon_option(self.institution.id, NAME).first()

        account = ExternalAccountFactory(provider=NAME)
        self.option.external_accounts.add(account)

    def _patch1(self):
        return patch(PACKAGE + '.models.boto3.client')

    @property
    def _expected_folder_name(self):
        return six.u(ROOT_FOLDER_FORMAT.format(
            title=filename_filter(self.project.title),
            guid=self.project._id))

    def _new_project(self):
        if USE_MOCK:
            with self._patch1() as mock1, \
                    patch('admin.institutions.views.Region.objects.filter') as mock2, \
                    patch('admin.institutions.views.Region.objects.get') as mock3, \
                    patch('addons.osfstorage.models.NodeSettings.objects.filter') as mock4:
                mock1.return_value = MagicMock()
                mock1.list_objects.return_value = {'Contents': []}
                region = RegionFactory()
                region_filter = MagicMock()
                region_filter.order_by.return_value = [region]
                mock2.return_value = region_filter
                mock3.return_value = region
                node = osfNodeSettings()
                node.root_node = BaseFileNode()
                node_filter = MagicMock()
                node_filter.first.return_value = node
                mock4.return_value = node_filter
                # mock1.list_buckets.return_value = None
                self.project = ProjectFactory(creator=self.user)
        else:
            self.project = ProjectFactory(creator=self.user)
        self.project.add_addon('osfstorage', auth=Auth(user=self.user))
        self.osfstorage = self.project.get_addon('osfstorage')
        new_region = RegionFactory(
            _id=self.institution._id,
            name='Institutional Storage',
            waterbutler_settings={
                'storage': {
                    'provider': SHORT_NAME,
                },
            }
        )
        self.osfstorage.region = new_region
        self.osfstorage.save()

    def _allow(self, save=True):
        self.option.is_allowed = True
        if save:
            self.option.save()

    def test_s3compatinstitutions_default_is_allowed(self):
        assert_true(self.option.is_allowed)
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))

    def test_s3compatinstitutions_no_eppn(self):
        self.user.eppn = None
        self.user.save()
        self._allow()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_s3compatinstitutions_no_institution(self):
        self.user.affiliated_institutions.clear()
        self._allow()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_s3compatinstitutions_no_addon_option(self):
        self._allow()
        self.option.delete()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_s3compatinstitutions_automount(self):
        self._allow()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))
        assert_equal(result.folder_name, self._expected_folder_name)

    def test_s3compatinstitutions_automount_with_basefolder(self):
        base_folder = six.u('GRDM_project_bucket')
        self._allow(save=False)
        self.option.extended = {'base_folder': base_folder}
        self.option.save()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))
        assert_equal(result.folder_name, self._expected_folder_name)

    def test_s3compatinstitutions_rename(self):
        self._allow()
        self._new_project()
        with self._patch1() as mock1:
            self.project.title = self.project.title + '_new'
            self.project.save()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))
        # not changed
        assert_equal(result.folder_name, self._expected_folder_name)


class TestAppS3CompatInstitutions(OsfTestCase):
    def setUp(self):
        super(TestAppS3CompatInstitutions, self).setUp()
        self.ADDON_SHORT_NAME = 's3compatinstitutions'

        self.user = AuthUserFactory()
        self.auth = Auth(user=self.user)

        self.project = ProjectFactory(creator=self.user)
        self.node_settings = MagicMock()
        self.node_settings.complete = True

    def test_s3compat_institutions_root(self):
        institution = InstitutionFactory(_id=123456)
        region = Region()
        region._id = institution._id
        region.waterbutler_settings__storage__provider = self.ADDON_SHORT_NAME
        region.save()

        self.node_settings.addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME).first()
        self.node_settings.region = region
        self.node_settings.root_node = BaseFileNode()

        result = s3compatinstitutions_root(addon_config='', node_settings=self.node_settings, auth=self.auth)

        assert isinstance(result, list)

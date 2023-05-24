# -*- coding: utf-8 -*-
import unittest
import six

from mock import patch, Mock, MagicMock
import pytest
from nose.tools import *  # noqa (PEP8 asserts)

from admin.rdm_addons.utils import get_rdm_addon_option
from framework.auth.core import Auth
from tests.base import OsfTestCase
from addons.ociinstitutions.apps import ociinstitutions_root
from osf_tests.factories import (
    fake_email,
    AuthUserFactory,
    InstitutionFactory,
    ExternalAccountFactory,
    UserFactory,
    ProjectFactory,
    RegionFactory
)
from addons.ociinstitutions.models import NodeSettings
from admin_tests.rdm_addons import factories as rdm_addon_factories

USE_MOCK = True  # False for DEBUG

pytestmark = pytest.mark.django_db

NAME = 'ociinstitutions'
PACKAGE = 'addons.{}'.format(NAME)

DEFAULT_BASE_FOLDER = 'GRDM'
ROOT_FOLDER_FORMAT = '{guid}'

def filename_filter(name):
    return name.replace('/', '_')

class TestOCIinstitutions(unittest.TestCase):

    def setUp(self):

        super(TestOCIinstitutions, self).setUp()

        self.institution = InstitutionFactory()

        self.user = UserFactory()
        self.user.eppn = fake_email()
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

        # create
        self.option = get_rdm_addon_option(self.institution.id, NAME)

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
            with self._patch1() as mock1:
                mock1.return_value = MagicMock()
                mock1.list_objects.return_value = {'Contents': []}
                # mock1.list_buckets.return_value = None
                self.project = ProjectFactory(creator=self.user)
        else:
            self.project = ProjectFactory(creator=self.user)

    def _allow(self, save=True):
        self.option.is_allowed = True
        if save:
            self.option.save()

    def test_ociinstitutions_default_is_not_allowed(self):
        assert_false(self.option.is_allowed)
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_ociinstitutions_no_eppn(self):
        self.user.eppn = None
        self.user.save()
        self._allow()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_ociinstitutions_no_institution(self):
        self.user.affiliated_institutions.clear()
        self._allow()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_ociinstitutions_no_addon_option(self):
        self._allow()
        self.option.delete()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_equal(result, None)

    def test_ociinstitutions_automount(self):
        self._allow()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))
        assert_equal(result.folder_name, self._expected_folder_name)

    def test_ociinstitutions_automount_with_basefolder(self):
        base_folder = six.u('GRDM_project_bucket')
        self._allow(save=False)
        self.option.extended = {'base_folder': base_folder}
        self.option.save()
        self._new_project()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))
        assert_equal(result.folder_name, self._expected_folder_name)

    def test_ociinstitutions_rename(self):
        self._allow()
        self._new_project()
        with self._patch1() as mock1:
            self.project.title = self.project.title + '_new'
            self.project.save()
        result = self.project.get_addon(NAME)
        assert_true(isinstance(result, NodeSettings))
        # not changed
        assert_equal(result.folder_name, self._expected_folder_name)

class TestAppOCIinstitutions(OsfTestCase):
    def setUp(self):
        super(TestAppOCIinstitutions, self).setUp()
        self.user = AuthUserFactory()
        self.user.save()
        self.consolidated_auth = Auth(user=self.user)
        self.project = ProjectFactory(creator=self.user)
        self.auth = Auth(user=self.project.creator)
        self.project.add_addon('ociinstitutions', auth=self.consolidated_auth)
        self.node_settings = self.project.get_addon('ociinstitutions')
        self.ADDON_SHORT_NAME = 'ociinstitutions'
        self.node_settings.save()

    @patch('admin.institutions.views.Region.objects')
    def test_nextcloudinstitutions_root(self, mock_region_objects_filter):
        institution = InstitutionFactory(_id=123456)
        region = RegionFactory()
        region._id = institution._id
        region.waterbutler_settings__storage__provider = self.ADDON_SHORT_NAME
        self.node_settings.addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME)
        region.save()
        mock_region_objects_filter.return_value = region
        mock_region_objects_filter.return_value.exists.return_value = True
        result = ociinstitutions_root(addon_config='', node_settings=self.node_settings, auth=self.auth)
        assert isinstance(result, list)
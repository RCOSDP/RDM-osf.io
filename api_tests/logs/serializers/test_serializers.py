import pytest

from framework.auth import Auth
from osf.models import NodeLog
from api.logs.serializers import NodeLogSerializer, NodeLogParamsSerializer
from osf_tests.factories import ProjectFactory, UserFactory, AuthUserFactory, InstitutionFactory, RegionFactory, UserQuotaFactory
from tests.utils import make_drf_request_with_version
from unittest import mock
from osf.models import ProjectStorageType

pytestmark = pytest.mark.django_db

class TestNodeLogSerializer:

    # Regression test for https://openscience.atlassian.net/browse/PLAT-758
    def test_serializing_log_with_legacy_non_registered_contributor_data(self, fake):
        # Old logs store unregistered contributors in params as dictionaries of the form:
        # {
        #     'nr_email': <email>,
        #     'nr_name': <name>,
        # }
        # This test ensures that the NodeLogSerializer can handle this legacy data.
        project = ProjectFactory()
        user = UserFactory()
        request = make_drf_request_with_version()
        nr_data = {'nr_email': fake.email(), 'nr_name': fake.name()}
        log = project.add_log(
            action=NodeLog.CONTRIB_ADDED,
            auth=Auth(project.creator),
            params={
                'project': project._id,
                'node': project._id,
                'contributors': [user._id, nr_data],
            }
        )
        serialized = NodeLogSerializer(log, context={'request': request}).data
        contributor_data = serialized['data']['attributes']['params']['contributors']
        # contributor_data will have two dicts:
        # the first will be the registered contrib, 2nd will be non-reg contrib
        reg_contributor_data, unreg_contributor_data = contributor_data
        assert reg_contributor_data['id'] == user._id
        assert reg_contributor_data['full_name'] == user.fullname

        assert unreg_contributor_data['id'] is None
        assert unreg_contributor_data['full_name'] == nr_data['nr_name']


@pytest.mark.django_db
class TestNodeLogParamsSerializer:

    def test_get_storage_name(self):
        user = AuthUserFactory()
        user_quota = UserQuotaFactory(user_id=user.id, storage_type=2)
        node = ProjectFactory(creator=user)
        institution = InstitutionFactory()
        region = RegionFactory(_id=institution._id, name='Storage')
        user.affiliated_institutions.add(institution)
        obj_value = {
            'path': 'fake_path',
            'node': node,
            'region': region.id
        }
        mock_abstractnode = mock.MagicMock()
        mock_abstractnode.return_value = node
        with mock.patch('osf.models.project_storage_type.ProjectStorageType.objects.get', return_value=user_quota):
            with mock.patch('osf.models.node.AbstractNode.load', mock_abstractnode):
                res = NodeLogParamsSerializer.get_storage_name(None, obj_value)
                assert res == region.name

    def test_get_storage_name_with_nii_type(self):
        user = AuthUserFactory()
        user_quota = UserQuotaFactory(user_id=user.id, storage_type=1)
        node = ProjectFactory(creator=user)
        institution = InstitutionFactory()
        region = RegionFactory(_id=institution._id, name='Storage')
        user.affiliated_institutions.add(institution)
        obj_value = {
            'path': 'fake_path',
            'node': node,
            'region': region.id
        }
        mock_abstractnode = mock.MagicMock()
        mock_abstractnode.return_value = node
        with mock.patch('osf.models.project_storage_type.ProjectStorageType.objects.get', return_value=user_quota):
            with mock.patch('osf.models.node.AbstractNode.load', mock_abstractnode):
                res = NodeLogParamsSerializer.get_storage_name(None, obj_value)
                assert res == 'NII Storage'

    def test_get_storage_name_exception(self):
        user = AuthUserFactory()
        node = ProjectFactory(creator=user)
        institution = InstitutionFactory()
        region = RegionFactory(_id=institution._id, name='Storage')
        user.affiliated_institutions.add(institution)
        obj_value = {
            'path': 'fake_path',
            'node': node,
            'region': region.id
        }
        mock_abstractnode = mock.MagicMock()
        mock_abstractnode.return_value = node
        with mock.patch('osf.models.project_storage_type.ProjectStorageType.objects.get', side_effect=ProjectStorageType.DoesNotExist('mock error')):
            with mock.patch('osf.models.node.AbstractNode.load', mock_abstractnode):
                res = NodeLogParamsSerializer.get_storage_name(None, obj_value)
                assert res == 'NII Storage'

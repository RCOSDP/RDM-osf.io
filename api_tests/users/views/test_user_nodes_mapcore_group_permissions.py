import pytest

from api.base.settings.defaults import API_BASE
from framework.auth.core import Auth
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_node_group import MapCoreNodeGroup
from osf.models.mapcore_user_group import MapCoreUserGroup
from osf_tests.factories import (
    AuthUserFactory,
    ProjectFactory,
)
from osf.utils import permissions


@pytest.mark.django_db
class TestUserNodesMapCoreGroupPermissions:
    """current_user_permissions on the nodes list must reflect mAP core
    group membership, matching the node detail endpoint."""

    @pytest.fixture()
    def group_member(self):
        return AuthUserFactory()

    @pytest.fixture()
    def project(self, group_member):
        creator = AuthUserFactory()
        project = ProjectFactory(creator=creator, is_public=False)
        project.add_addon('groups', auth=Auth(creator))
        project.save()

        mapcore_group = MapCoreGroup.objects.create(_id='test-mapcore-group')
        MapCoreNodeGroup.objects.create(
            node=project,
            group=project.get_group(permissions.WRITE),
            mapcore_group=mapcore_group,
            creator=creator,
        )
        MapCoreUserGroup.objects.create(
            user=group_member,
            mapcore_group=mapcore_group,
        )
        return project

    def test_list_permissions_match_detail(self, app, group_member, project):
        list_url = '/{}users/me/nodes/'.format(API_BASE)
        res = app.get(list_url, auth=group_member.auth)
        assert res.status_code == 200
        nodes = {n['id']: n for n in res.json['data']}
        assert project._id in nodes

        detail_url = '/{}nodes/{}/'.format(API_BASE, project._id)
        detail = app.get(detail_url, auth=group_member.auth)
        assert detail.status_code == 200
        detail_perms = detail.json['data']['attributes']['current_user_permissions']
        assert permissions.WRITE in detail_perms

        list_perms = nodes[project._id]['attributes']['current_user_permissions']
        assert list_perms == detail_perms

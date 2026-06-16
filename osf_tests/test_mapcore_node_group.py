import pytest
from django.contrib.auth.models import Group as AuthGroup
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_node_group import MapCoreNodeGroup
from osf_tests.factories import UserFactory, NodeFactory

pytestmark = pytest.mark.django_db

def _make_mc_node_group(node, user, group_name):
    auth_group = AuthGroup.objects.create(name=group_name)
    mc_group = MapCoreGroup.objects.create(_id=f'mc-{group_name}')
    return MapCoreNodeGroup.objects.create(
        node=node,
        group=auth_group,
        mapcore_group=mc_group,
        creator=user,
    )

def test_get_permission_parses_admin_write_read():
    user = UserFactory()
    node = NodeFactory(is_public=False)

    mc_admin = _make_mc_node_group(node, user, f'node_{node._id}_admin')
    assert mc_admin.get_permission == 'admin'

    mc_write = _make_mc_node_group(node, user, f'node_{node._id}_write')
    assert mc_write.get_permission == 'write'

    mc_read = _make_mc_node_group(node, user, f'node_{node._id}_read')
    assert mc_read.get_permission == 'read'

def test_get_permission_returns_none_for_unmatched_name():
    user = UserFactory()
    node = NodeFactory(is_public=False)

    mc_other = _make_mc_node_group(node, user, 'some-random-group')
    assert mc_other.get_permission is None

    mc_empty = _make_mc_node_group(node, user, '')
    assert mc_empty.get_permission is None

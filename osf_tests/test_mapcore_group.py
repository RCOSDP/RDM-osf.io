import pytest
from django.contrib.auth.models import Group as AuthGroup, Permission
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_node_group import MapCoreNodeGroup
from osf.models.mapcore_user_group import MapCoreUserGroup
from osf.models.node import Node
from osf.models.node import NodeGroupObjectPermission
from osf_tests.factories import PrivateLinkFactory, UserFactory, NodeFactory

pytestmark = pytest.mark.django_db


class TestCanViewMapcoreGroups:

    def _make_node_group_permission(self, node, group, perm_codename='admin_node'):
        """
        Helper: create NodeGroupObjectPermission linking the auth group to a permission on the node.
        """
        # Get permission object id
        perm = Permission.objects.get(codename=perm_codename)
        # NodeGroupObjectPermission is defined in osf.models.node as a guardian-backed model
        # We can create via NodeGroupObjectPermission.objects.create
        return NodeGroupObjectPermission.objects.create(
            group_id=group.id,
            permission_id=perm.id,
            content_object_id=node.id
        )

    def test_can_view_via_mapcore_group_when_included(self):
        # Setup: node, user, mapcore group, auth group that follows 'node_<id>_admin' naming.
        user = UserFactory()
        node = NodeFactory(is_public=False)
        # Create the MapCoreGroup
        mc_group = MapCoreGroup.objects.create(_id='mc-1')

        # Create a Django Auth Group with name matching mapcore node group pattern
        auth_group = AuthGroup.objects.create(name=f'node_{node._id}_admin')

        # Create MapCoreNodeGroup linking node, auth group and mapcore group (not deleted)
        MapCoreNodeGroup.objects.create(node=node, group=auth_group, mapcore_group=mc_group, creator=user, is_deleted=False)

        # Create MapCoreUserGroup linking user to the MapCoreGroup (not deleted)
        MapCoreUserGroup.objects.create(mapcore_group=mc_group, user=user, is_deleted=False)

        # Create the NodeGroupObjectPermission that actually grants the admin_node perm to the auth_group on the node
        self._make_node_group_permission(node, auth_group, perm_codename='admin_node')

        # Now assert that with include_mapcore_groups True the node is visible to the user via Node.objects.can_view(...)
        qs = Node.objects.get_queryset().can_view(user=user, private_link=None, include_mapcore_groups=True)
        assert node in qs

    def test_can_view_with_private_link(self):
        node = NodeFactory(is_public=False)

        # Create a private link and attach it to the node
        pl = PrivateLinkFactory()
        pl.nodes.add(node)
        pl.save()

        # Passing the PrivateLink instance should return the node
        qs_obj = Node.objects.get_queryset().can_view(user=None, private_link=pl)
        assert node in qs_obj

        # Passing the key string should also return the node
        qs_key = Node.objects.get_queryset().can_view(user=None, private_link=pl.key)
        assert node in qs_key

        # Passing an invalid type should raise a TypeError
        with pytest.raises(TypeError):
            Node.objects.get_queryset().can_view(user=None, private_link=123)

    def test_cannot_view_via_mapcore_group_when_not_included(self):
        # Same setup but do NOT include mapcore groups in the queryset
        user = UserFactory()
        node = NodeFactory(is_public=False)
        mc_group = MapCoreGroup.objects.create(_id='mc-2')
        auth_group = AuthGroup.objects.create(name=f'node_{node._id}_admin')
        MapCoreNodeGroup.objects.create(node=node, group=auth_group, mapcore_group=mc_group, creator=user, is_deleted=False)
        MapCoreUserGroup.objects.create(mapcore_group=mc_group, user=user, is_deleted=False)
        self._make_node_group_permission(node, auth_group, perm_codename='admin_node')

        qs = Node.objects.get_queryset().can_view(user=user, private_link=None, include_mapcore_groups=False)
        assert node not in qs

    def test_deleted_mapcore_node_group_is_ignored(self):
        # If the MapCoreNodeGroup is marked is_deleted=True it should not grant visibility
        user = UserFactory()
        node = NodeFactory(is_public=False)
        mc_group = MapCoreGroup.objects.create(_id='mc-3')
        auth_group = AuthGroup.objects.create(name=f'node_{node._id}_admin')
        MapCoreNodeGroup.objects.create(node=node, group=auth_group, mapcore_group=mc_group, creator=user, is_deleted=True)
        MapCoreUserGroup.objects.create(mapcore_group=mc_group, user=user, is_deleted=False)
        self._make_node_group_permission(node, auth_group, perm_codename='admin_node')

        qs = Node.objects.get_queryset().can_view(user=user, private_link=None, include_mapcore_groups=True)
        assert node not in qs

    def test_get_nodes_for_user_include_mapcore_group(self):
        user = UserFactory()
        node = NodeFactory(is_public=False)
        mc_group = MapCoreGroup.objects.create(_id='mc-4')
        auth_group = AuthGroup.objects.create(name=f'node_{node._id}_admin')
        MapCoreNodeGroup.objects.create(node=node, group=auth_group, mapcore_group=mc_group, creator=user, is_deleted=False)
        MapCoreUserGroup.objects.create(mapcore_group=mc_group, user=user, is_deleted=False)
        self._make_node_group_permission(node, auth_group, perm_codename='admin_node')

        qs_included = Node.objects.get_nodes_for_user(user, permission='admin_node', include_mapcore_groups=True)
        assert node in qs_included

        qs_excluded = Node.objects.get_nodes_for_user(user, permission='admin_node', include_mapcore_groups=False)
        assert node not in qs_excluded

    def test_get_nodes_for_user_invalid_permission_raises(self):
        user = UserFactory()
        with pytest.raises(ValueError):
            Node.objects.get_nodes_for_user(user, permission='not_a_real_permission')

    def test_get_nodes_for_user_include_public(self):
        user = UserFactory()
        private_node = NodeFactory(is_public=False)
        public_node = NodeFactory(is_public=True)
        # Ensure public node is not returned when include_public=False
        qs_no_public = Node.objects.get_nodes_for_user(user, permission='read_node', include_public=False)
        assert public_node not in qs_no_public
        # Ensure public node is returned when include_public=True
        qs_with_public = Node.objects.get_nodes_for_user(user, permission='read_node', include_public=True)
        assert public_node in qs_with_public
        # Private node should still not be returned without explicit permission
        assert private_node not in qs_with_public

import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import Group as AuthGroup
from rest_framework import exceptions

from api.nodes.serializers import (
    NodeMapCoreGroupSerializer,
    NodeMapCoreGroupCreateSerializer,
    NodeMapCoreGroupUpdateSerializer,
    NodeSerializer
)
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_node_group import MapCoreNodeGroup
from osf_tests.factories import AuthUserFactory, NodeFactory
from tests.utils import make_drf_request_with_version
from website import settings as website_settings


@pytest.fixture()
def user():
    return AuthUserFactory()


@pytest.fixture()
def node(user):
    return NodeFactory(creator=user)


@pytest.fixture()
def mapcore_group():
    return MapCoreGroup.objects.create(_id='test-group-1')


@pytest.fixture()
def auth_group(node):
    return AuthGroup.objects.get_or_create(name=f'node_{node.id}_admin')[0]


@pytest.fixture()
def mapcore_node_group(node, mapcore_group, auth_group, user):
    return MapCoreNodeGroup.objects.create(
        node=node,
        group=auth_group,
        mapcore_group=mapcore_group,
        creator=user,
    )


@pytest.mark.django_db
class TestNodeMapCoreGroupSerializer:
    """Test cases for NodeMapCoreGroupSerializer"""

    def test_basic_serialization(self, mapcore_node_group, node):
        """Test basic serialization of MapCoreNodeGroup"""
        # Simulate permissions attached by view
        mapcore_node_group.permissions = ['admin']

        req = make_drf_request_with_version(version='2.0')
        result = NodeMapCoreGroupSerializer(
            mapcore_node_group,
            context={'request': req, 'node': node}
        ).data
        data = result['data']

        # Test top-level structure
        assert data['id'] == mapcore_node_group.id
        assert data['type'] == 'node-mapcore-group'

        # Test attributes
        attrs = data['attributes']
        assert attrs['node_group_id'] == mapcore_node_group.id
        assert attrs['creator_id'] == mapcore_node_group.creator.id
        assert attrs['creator'] == mapcore_node_group.creator.fullname
        assert attrs['permission'] == 'admin'
        assert attrs['mapcore_group_id'] == mapcore_node_group.mapcore_group.id
        assert attrs['name'] == mapcore_node_group.mapcore_group._id
        assert 'created' in attrs
        assert 'modified' in attrs

        # Test links
        expected_url = f'{website_settings.MAPCORE_GROUP_HOSTNAME}{website_settings.MAPCORE_GROUP_API_PATH}{mapcore_node_group.mapcore_group._id}'
        assert data['links']['self'] == expected_url

    def test_get_permission_with_multiple_permissions(self, mapcore_node_group, node):
        """Test that get_permission returns highest permission"""
        # Test admin priority
        mapcore_node_group.permissions = ['read', 'write', 'admin']

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupSerializer(
            mapcore_node_group,
            context={'request': req, 'node': node}
        )
        assert serializer.get_permission(mapcore_node_group) == 'admin'

        # Test write priority over read
        mapcore_node_group.permissions = ['read', 'write']
        assert serializer.get_permission(mapcore_node_group) == 'write'

        # Test read only
        mapcore_node_group.permissions = ['read']
        assert serializer.get_permission(mapcore_node_group) == 'read'

    def test_get_permission_no_permissions(self, mapcore_node_group, node):
        """Test get_permission returns None when no permissions"""
        mapcore_node_group.permissions = []

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupSerializer(
            mapcore_node_group,
            context={'request': req, 'node': node}
        )
        assert serializer.get_permission(mapcore_node_group) is None

    def test_get_permission_unknown_permissions(self, mapcore_node_group, node):
        """Test get_permission with unknown permissions"""
        mapcore_node_group.permissions = ['unknown', 'invalid']

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupSerializer(
            mapcore_node_group,
            context={'request': req, 'node': node}
        )
        assert serializer.get_permission(mapcore_node_group) is None

    def test_get_permission_missing_permissions_attribute(self, mapcore_node_group, node):
        """Test get_permission when permissions attribute is missing"""
        # Don't set permissions attribute at all

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupSerializer(
            mapcore_node_group,
            context={'request': req, 'node': node}
        )

        # Should default to empty list and return None
        assert serializer.get_permission(mapcore_node_group) is None


@pytest.mark.django_db
class TestNodeMapCoreGroupCreateSerializer:
    """Test cases for NodeMapCoreGroupCreateSerializer"""

    def setup_auth_groups(self, node):
        """Helper to create auth groups for a node"""
        groups = {}
        for perm in ['read', 'write', 'admin']:
            groups[perm] = AuthGroup.objects.get_or_create(name=f'node_{node.id}_{perm}')[0]
        return groups

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_basic(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test basic creation of MapCoreNodeGroup"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        mapcore_group = MapCoreGroup.objects.create(_id='test-group-create')

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group.id,
                    'permission': 'admin'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify
        assert len(result) == 1
        response_item = result[0]
        assert response_item['type'] == 'node-mapcore-group'
        assert response_item['attributes']['permission'] == 'admin'
        assert response_item['attributes']['mapcore_group_id'] == mapcore_group.id

        # Verify database
        mcng = MapCoreNodeGroup.objects.get(
            node=node,
            mapcore_group=mapcore_group,
            is_deleted=False
        )
        assert mcng.group == auth_groups['admin']
        assert mcng.creator == user

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_with_components(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test creation with component nodes"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        component1 = NodeFactory(creator=user, parent=node)
        component2 = NodeFactory(creator=user, parent=node)
        mapcore_group = MapCoreGroup.objects.create(_id='test-group-components')

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group.id,
                    'permission': 'write'
                }
            ],
            'component_ids': [component1._id, component2._id]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)
        # Verify
        assert len(result) == 1

        # Verify main node relationship created
        main_mcng = MapCoreNodeGroup.objects.get(
            node=node,
            mapcore_group=mapcore_group,
            is_deleted=False
        )
        assert main_mcng.group == auth_groups['write']

        # Verify component relationships created
        for component in [component1, component2]:
            comp_mcng = MapCoreNodeGroup.objects.get(
                node=component,
                mapcore_group=mapcore_group,
                is_deleted=False
            )
            assert comp_mcng.group == auth_groups['write']

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_with_existing_component_relationship(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test creation with existing component relationship (update scenario)"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        component = NodeFactory(creator=user, parent=node)
        mapcore_group = MapCoreGroup.objects.create(_id='test-group-update')

        # Create existing relationship with read permission
        existing_mcng = MapCoreNodeGroup.objects.create(
            node=component,
            mapcore_group=mapcore_group,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group.id,
                    'permission': 'admin'  # Upgrade to admin
                }
            ],
            'component_ids': [component._id]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)
        # Verify
        assert len(result) == 1

        # Verify component relationship was updated
        existing_mcng.refresh_from_db()
        assert existing_mcng.group == auth_groups['admin']

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_duplicate_mapcore_group_raises_error(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test that creating duplicate MapCoreNodeGroup raises ValidationError"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        mapcore_group = MapCoreGroup.objects.create(_id='test-group-duplicate')

        # Create existing relationship
        MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group,
            group=auth_groups['admin'],
            creator=user,
            is_deleted=False
        )

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group.id,
                    'permission': 'admin'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute and verify exception
        with pytest.raises(Exception) as exc_info:
            serializer.create(validated_data)

        assert 'MapCoreNodeGroup already exists' in str(exc_info.value)

    def test_load_mapcore_group_not_found(self, user, node):
        """Test load_mapcore_group raises NotFound for nonexistent group"""
        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        with pytest.raises(exceptions.NotFound) as exc_info:
            serializer.load_mapcore_group(99999)

        assert 'MapCore Group with id 99999 does not exist' in str(exc_info.value)

    def test_load_mapcore_group_success(self, user, node):
        """Test load_mapcore_group returns correct group"""
        mapcore_group = MapCoreGroup.objects.create(_id='test-load-group')

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        result = serializer.load_mapcore_group(mapcore_group.id)
        assert result == mapcore_group

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_multiple_node_groups(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test creating multiple MapCoreNodeGroups in single call"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        mapcore_group1 = MapCoreGroup.objects.create(_id='test-group-multi-1')
        mapcore_group2 = MapCoreGroup.objects.create(_id='test-group-multi-2')

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group1.id,
                    'permission': 'admin'
                },
                {
                    'mapcore_group_id': mapcore_group2.id,
                    'permission': 'write'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify
        assert len(result) == 2

        # Verify both relationships created with correct permissions
        mcng1 = MapCoreNodeGroup.objects.get(
            node=node,
            mapcore_group=mapcore_group1,
            is_deleted=False
        )
        assert mcng1.group == auth_groups['admin']

        mcng2 = MapCoreNodeGroup.objects.get(
            node=node,
            mapcore_group=mapcore_group2,
            is_deleted=False
        )
        assert mcng2.group == auth_groups['write']

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_component_two_groups_update_and_add_new(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Create for a component with two mapcore groups: one updates, one is added"""
        # Setup auth groups
        auth_groups = self.setup_auth_groups(node)

        # Create a component and two mapcore groups (one existing on component, one new)
        component = NodeFactory(creator=user, parent=node)
        existing_mapcore_group = MapCoreGroup.objects.create(_id='test-component-existing')
        new_mapcore_group = MapCoreGroup.objects.create(_id='test-component-new')

        # Existing relationship on the component (read)
        existing_mcng = MapCoreNodeGroup.objects.create(
            node=component,
            mapcore_group=existing_mapcore_group,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': existing_mapcore_group.id,
                    'permission': 'admin'  # upgrade existing on component
                },
                {
                    'mapcore_group_id': new_mapcore_group.id,
                    'permission': 'write'  # add new to component
                }
            ],
            'component_ids': [component._id]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify serializer response for two items
        assert len(result) == 2

        # Verify existing relationship was updated on the component
        existing_mcng.refresh_from_db()
        assert existing_mcng.group == auth_groups['admin']

        # Verify new relationship was created for the component
        new_mcng = MapCoreNodeGroup.objects.get(
            node=component,
            mapcore_group=new_mapcore_group,
            is_deleted=False
        )
        assert new_mcng.group == auth_groups['write']

        # Optionally verify main node relationships were also created/updated
        main_existing = MapCoreNodeGroup.objects.get(node=node, mapcore_group=existing_mapcore_group, is_deleted=False)
        assert main_existing.group == auth_groups['admin']
        main_new = MapCoreNodeGroup.objects.get(node=node, mapcore_group=new_mapcore_group, is_deleted=False)
        assert main_new.group == auth_groups['write']


@pytest.mark.django_db
class TestNodeMapCoreGroupUpdateSerializer:
    """Test cases for NodeMapCoreGroupUpdateSerializer"""

    def setup_auth_groups(self, node):
        """Helper to create auth groups for a node"""
        groups = {}
        for perm in ['read', 'write', 'admin']:
            groups[perm] = AuthGroup.objects.get_or_create(name=f'node_{node.id}_{perm}')[0]
        return groups

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_update_basic(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test basic update of MapCoreNodeGroup permissions"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        mapcore_group = MapCoreGroup.objects.create(_id='test-group-update')

        # Create existing relationship with read permission
        existing_mcng = MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'node_group_id': existing_mcng.id,
                    'permission': 'admin'  # Update to admin
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify response
        assert len(result) == 1
        response_item = result[0]
        assert response_item['attributes']['permission'] == 'admin'
        assert response_item['attributes']['node_group_id'] == existing_mcng.id

        # Verify database update
        existing_mcng.refresh_from_db()
        assert existing_mcng.group == auth_groups['admin']

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_update_multiple_node_groups(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test updating multiple MapCoreNodeGroups"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        mapcore_group1 = MapCoreGroup.objects.create(_id='test-group-update-1')
        mapcore_group2 = MapCoreGroup.objects.create(_id='test-group-update-2')

        # Create existing relationships
        mcng1 = MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group1,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )
        mcng2 = MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group2,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'node_group_id': mcng1.id,
                    'permission': 'admin'
                },
                {
                    'node_group_id': mcng2.id,
                    'permission': 'write'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify response
        assert len(result) == 2

        # Verify database updates
        mcng1.refresh_from_db()
        mcng2.refresh_from_db()
        assert mcng1.group == auth_groups['admin']
        assert mcng2.group == auth_groups['write']

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_update_no_permission_change(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test update with no permission provided (should skip)"""
        # Setup
        auth_groups = self.setup_auth_groups(node)
        mapcore_group = MapCoreGroup.objects.create(_id='test-group-no-change')

        existing_mcng = MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )
        original_modified = existing_mcng.modified

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'node_group_id': existing_mcng.id,
                    'permission': None  # No permission change
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify no changes made
        assert len(result) == 0
        existing_mcng.refresh_from_db()
        assert existing_mcng.group == auth_groups['read']  # Unchanged
        assert existing_mcng.modified == original_modified  # Unchanged

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_update_nonexistent_node_group_id(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test update with nonexistent node_group_id (should be ignored)"""
        auth_groups = self.setup_auth_groups(node)

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'node_group_id': 99999,  # Nonexistent ID
                    'permission': 'admin'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify no updates made
        assert len(result) == 0

    def test_load_mapcore_group_not_found(self, user, node):
        """Test load_mapcore_group raises NotFound for nonexistent group"""
        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        with pytest.raises(exceptions.NotFound) as exc_info:
            serializer.load_mapcore_group(99999)

        assert 'MapCore Group with id 99999 does not exist' in str(exc_info.value)

    def test_load_mapcore_group_success(self, user, node):
        """Test load_mapcore_group returns correct group"""
        mapcore_group = MapCoreGroup.objects.create(_id='test-load-group')

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        result = serializer.load_mapcore_group(mapcore_group.id)
        assert result == mapcore_group


@pytest.mark.django_db
class TestGetGroupByNode:
    """Test cases for the get_group_by_node helper function"""

    def test_get_group_by_node(self, node):
        """Test get_group_by_node returns correct mapping"""
        from api.nodes.serializers import get_group_by_node

        # Create auth groups for the node
        admin_group = AuthGroup.objects.get_or_create(name=f'node_{node.id}_admin')[0]
        write_group = AuthGroup.objects.get_or_create(name=f'node_{node.id}_write')[0]
        read_group = AuthGroup.objects.get_or_create(name=f'node_{node.id}_read')[0]

        # Also create some unrelated groups to ensure they're filtered out
        AuthGroup.objects.get_or_create(name='unrelated_group')[0]
        AuthGroup.objects.get_or_create(name=f'node_{node.id + 1}_admin')[0]  # Different node

        result = get_group_by_node(node.id)

        expected = {
            'admin': admin_group.id,
            'write': write_group.id,
            'read': read_group.id
        }
        assert result == expected

    def test_get_group_by_node_no_groups(self, node):
        """Test get_group_by_node with no matching groups"""
        from api.nodes.serializers import get_group_by_node

        # Ensure no leftover groups from other tests remain for this node
        AuthGroup.objects.filter(name__startswith=f'node_{node.id}_').delete()

        result = get_group_by_node(node.id)
        assert result == {}

    def test_get_group_by_node_partial_groups(self, node):
        """Test get_group_by_node with only some permission groups"""
        from api.nodes.serializers import get_group_by_node

        # Remove any leftover groups for this node to ensure test isolation
        AuthGroup.objects.filter(name__startswith=f'node_{node.id}_').delete()

        # Only create admin and read groups, no write
        admin_group = AuthGroup.objects.create(name=f'node_{node.id}_admin')
        read_group = AuthGroup.objects.create(name=f'node_{node.id}_read')

        result = get_group_by_node(node.id)

        expected = {
            'admin': admin_group.id,
            'read': read_group.id
        }
        assert result == expected


@pytest.mark.django_db
class TestNodeMapCoreGroupSerializerEdgeCases:
    """Additional edge case tests for complete coverage"""

    def test_get_permission_missing_permissions_attribute(self, user, node):
        """Test get_permission when permissions attribute is missing"""
        mapcore_group = MapCoreGroup.objects.create(_id='test-missing-perm')
        auth_group = AuthGroup.objects.get_or_create(name=f'node_{node.id}_admin')[0]
        mapcore_node_group = MapCoreNodeGroup.objects.create(
            node=node,
            group=auth_group,
            mapcore_group=mapcore_group,
            creator=user,
        )
        # Don't set permissions attribute at all

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupSerializer(
            mapcore_node_group,
            context={'request': req, 'node': node}
        )

        # Should default to empty list and return None
        assert serializer.get_permission(mapcore_node_group) is None

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_with_empty_component_ids(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test creation with empty component_ids list"""
        # Setup
        auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            auth_groups[perm] = AuthGroup.objects.get_or_create(name=f'node_{node.id}_{perm}')[0]

        mapcore_group = MapCoreGroup.objects.create(_id='test-group-empty-components')

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group.id,
                    'permission': 'admin'
                }
            ],
            'component_ids': []  # Empty list
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify only main node relationship created
        assert len(result) == 1
        mcng = MapCoreNodeGroup.objects.get(
            node=node,
            mapcore_group=mapcore_group,
            is_deleted=False
        )
        assert mcng.group == auth_groups['admin']

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_create_node_logging(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test that node logging occurs during creation"""
        # Setup
        auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            auth_groups[perm] = AuthGroup.objects.get_or_create(name=f'node_{node.id}_{perm}')[0]

        mapcore_group = MapCoreGroup.objects.create(_id='test-group-logging')

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'mapcore_group_id': mapcore_group.id,
                    'permission': 'admin'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupCreateSerializer(
            context={'request': req, 'node': node}
        )

        original_modified = node.modified

        # Execute
        result = serializer.create(validated_data)
        assert len(result) == 1

        # Verify node was modified (for logging)
        node.refresh_from_db()
        assert node.modified > original_modified

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_update_empty_permission_string(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test update with empty permission string"""
        # Setup
        auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            auth_groups[perm] = AuthGroup.objects.get_or_create(name=f'node_{node.id}_{perm}')[0]

        mapcore_group = MapCoreGroup.objects.create(_id='test-group-empty-perm')

        existing_mcng = MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )
        original_modified = existing_mcng.modified

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'node_group_id': existing_mcng.id,
                    'permission': ''  # Empty permission string
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        # Execute
        result = serializer.create(validated_data)

        # Verify no changes made (empty string is falsy)
        assert len(result) == 0
        existing_mcng.refresh_from_db()
        assert existing_mcng.group == auth_groups['read']  # Unchanged
        assert existing_mcng.modified == original_modified  # Unchanged

    @patch('api.nodes.serializers.get_group_by_node')
    @patch('api.nodes.serializers.get_user_auth')
    def test_update_node_logging(self, mock_get_user_auth, mock_get_group_by_node, user, node):
        """Test that node logging occurs during update"""
        # Setup
        auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            auth_groups[perm] = AuthGroup.objects.get_or_create(name=f'node_{node.id}_{perm}')[0]

        mapcore_group = MapCoreGroup.objects.create(_id='test-group-update-logging')

        existing_mcng = MapCoreNodeGroup.objects.create(
            node=node,
            mapcore_group=mapcore_group,
            group=auth_groups['read'],
            creator=user,
            is_deleted=False
        )

        mock_get_user_auth.return_value = MagicMock(user=user)
        mock_get_group_by_node.return_value = {
            'admin': auth_groups['admin'].id,
            'write': auth_groups['write'].id,
            'read': auth_groups['read'].id
        }

        validated_data = {
            'node_groups': [
                {
                    'node_group_id': existing_mcng.id,
                    'permission': 'admin'
                }
            ]
        }

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeMapCoreGroupUpdateSerializer(
            context={'request': req, 'node': node}
        )

        original_modified = node.modified

        # Execute
        result = serializer.create(validated_data)
        assert len(result) == 1

        # Verify node was modified (for logging)
        node.refresh_from_db()
        assert node.modified > original_modified


@pytest.mark.django_db
class TestNodeSerializerMapCoreIntegration:
    """Test NodeSerializer get_node_count and node creation with MapCore group"""

    def test_get_node_count(self, node):
        """Test get_node_count returns correct count"""
        NodeFactory(creator=node.creator, parent=node, is_deleted=False, is_public=True)
        NodeFactory(creator=node.creator, parent=node, is_deleted=False, is_public=True)

        req = make_drf_request_with_version(version='2.0')
        serializer = NodeSerializer(instance=node, context={'request': req})
        count = serializer.get_node_count(node)
        assert count == 2

    @pytest.mark.django_db
    def test_create_node_with_mapcore_group_parent_writable(self, user):
        # Create a MapCore group and parent node
        mapcore_group = MapCoreGroup.objects.create(_id='test-mapcore-create-parent-writable')
        parent_node = NodeFactory(creator=user)

        # Attach a MapCoreNodeGroup to the parent so it can be inherited
        auth_group = AuthGroup.objects.get_or_create(name=f'node_{parent_node.id}_admin')[0]
        MapCoreNodeGroup.objects.create(
            node=parent_node,
            group=auth_group,
            mapcore_group=mapcore_group,
            creator=user,
            is_deleted=False,
        )

        # Grant the test user write permission on the parent so has_permission(...) returns True
        parent_node.add_contributor(user, permissions='admin', save=True)
        assert parent_node.has_permission(user, 'write')
        user.is_registered = True
        user.save()
        # Prepare request that requests inheritance
        req = make_drf_request_with_version(version='2.0')
        req._request.GET = {'inherit_contributors': 'true'}
        req.user = user

        validated_data = {
            'title': 'Child Node inheriting MapCore',
            'category': 'project',
            'parent': parent_node,
            'creator': user,
        }

        serializer = NodeSerializer(context={'request': req})
        child_node = serializer.create(validated_data)

        # Verify a MapCoreNodeGroup was copied from parent to child
        assert MapCoreNodeGroup.objects.filter(node=child_node, mapcore_group=mapcore_group, is_deleted=False).exists()

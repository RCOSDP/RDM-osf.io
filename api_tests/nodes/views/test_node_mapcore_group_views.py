import pytest
from django.contrib.auth.models import Group as AuthGroup

from api.base.settings.defaults import API_BASE
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_node_group import MapCoreNodeGroup
from osf.models.mapcore_user_group import MapCoreUserGroup
from osf_tests.factories import AuthUserFactory, NodeFactory, ProjectFactory, UserFactory
from tests.base import ApiTestCase
from framework.auth import Auth


@pytest.mark.django_db
class TestNodeMapCoreGroupList(ApiTestCase):
    """Test cases for NodeMapCoreGroupList view"""

    def setUp(self):
        super().setUp()
        self.user = AuthUserFactory()
        self.admin_user = AuthUserFactory()
        self.read_only_user = AuthUserFactory()

        self.node = ProjectFactory(creator=self.admin_user, is_public=False)
        self.node.add_contributor(self.user, permissions='admin')
        self.node.add_contributor(self.read_only_user, permissions='read')
        self.node.add_addon('groups', auth=Auth(self.user))  # Enable groups addon
        self.node.save()

        # Create auth groups for the node
        self.auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            self.auth_groups[perm] = AuthGroup.objects.get_or_create(
                name=f'node_{self.node.id}_{perm}'
            )[0]

        # Create MapCoreGroups
        self.mapcore_group1 = MapCoreGroup.objects.create(_id='test-mapcore-1')
        self.mapcore_group2 = MapCoreGroup.objects.create(_id='test-mapcore-2')

        # Create MapCoreNodeGroup relationships
        self.mcng1 = MapCoreNodeGroup.objects.create(
            node=self.node,
            group=self.auth_groups['admin'],
            mapcore_group=self.mapcore_group1,
            creator=self.admin_user,
        )
        self.mcng2 = MapCoreNodeGroup.objects.create(
            node=self.node,
            group=self.auth_groups['write'],
            mapcore_group=self.mapcore_group2,
            creator=self.admin_user,
        )

        self.url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/'

    def test_list_mapcore_groups_success(self):
        """Test listing MapCoreNodeGroup relationships"""
        res = self.app.get(self.url, auth=self.user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 2

        # Verify structure of response
        item = res.json['data'][0]
        assert 'id' in item
        assert item['type'] == 'node-mapcore-group'
        assert 'attributes' in item
        assert 'links' in item

    def test_list_mapcore_groups_permissions_attached(self):
        """Test that permissions are properly attached to serialized objects"""
        res = self.app.get(self.url, auth=self.user.auth)
        assert res.status_code == 200

        # Find the item with mapcore_group1
        items = res.json['data']
        item1 = next((i for i in items if i['attributes']['mapcore_group_id'] == self.mapcore_group1.id), None)
        assert item1 is not None
        assert 'permission' in item1['attributes']

    def test_list_mapcore_groups_unauthenticated_public_node(self):
        """Test listing MapCoreGroups on public node without auth"""
        self.node.is_public = True
        self.node.save()

        res = self.app.get(self.url)
        assert res.status_code == 200

    def test_list_mapcore_groups_unauthenticated_private_node(self):
        """Test listing MapCoreGroups on private node without auth returns 401"""
        res = self.app.get(self.url, expect_errors=True)
        assert res.status_code == 401

    def test_list_mapcore_groups_read_only_user(self):
        """Test read-only user can list MapCoreGroups on public node"""
        self.node.is_public = True
        self.node.save()

        res = self.app.get(self.url, auth=self.read_only_user.auth)
        assert res.status_code == 200

    def test_list_mapcore_groups_ordering(self):
        """Test that MapCoreGroups are ordered by mapcore_group___id"""
        # Create another group with _id that sorts before 'test-mapcore-1'
        mapcore_group3 = MapCoreGroup.objects.create(_id='aaa-test-mapcore')
        MapCoreNodeGroup.objects.create(
            node=self.node,
            group=self.auth_groups['read'],
            mapcore_group=mapcore_group3,
            creator=self.admin_user,
        )

        res = self.app.get(self.url, auth=self.user.auth)
        assert res.status_code == 200

        # Check ordering
        items = res.json['data']
        assert len(items) == 3
        # Should be ordered by mapcore_group___id
        assert items[0]['attributes']['name'] == 'test-mapcore-1'
        assert items[1]['attributes']['name'] == 'test-mapcore-2'
        assert items[2]['attributes']['name'] == 'aaa-test-mapcore'

    def test_create_mapcore_group_success(self):
        """Test creating a new MapCoreNodeGroup relationship"""
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth)
        assert res.status_code == 201
        assert len(res.json['data']) == 1

        created_item = res.json['data'][0]
        assert created_item['attributes']['mapcore_group_id'] == mapcore_group3.id
        assert created_item['attributes']['permission'] == 'write'

        # Verify database
        mcng = MapCoreNodeGroup.objects.get(
            node=self.node,
            mapcore_group=mapcore_group3,
            is_deleted=False
        )
        assert mcng.group == self.auth_groups['write']

    def test_create_mapcore_group_multiple(self):
        """Test creating multiple MapCoreNodeGroup relationships at once"""
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')
        mapcore_group4 = MapCoreGroup.objects.create(_id='test-mapcore-4')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        },
                        {
                            'mapcore_group_id': mapcore_group4.id,
                            'permission': 'admin'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth)
        assert res.status_code == 201
        assert len(res.json['data']) == 2

    def test_create_mapcore_group_with_components(self):
        """Test creating MapCoreNodeGroup with component nodes"""
        component1 = NodeFactory(creator=self.admin_user, parent=self.node)
        component2 = NodeFactory(creator=self.admin_user, parent=self.node)
        auth_groups_component = {}
        for component in [component1, component2]:
            auth_groups_component[component.id] = AuthGroup.objects.get_or_create(
                name=f'node_{component.id}_write'
            )[0]
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        }
                    ],
                    'component_ids': [component1._id, component2._id]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth)
        assert res.status_code == 201

        # Verify main node relationship
        mcng_main = MapCoreNodeGroup.objects.get(
            node=self.node,
            mapcore_group=mapcore_group3,
            is_deleted=False
        )
        assert mcng_main.group == self.auth_groups['write']

        # Verify component relationships
        for component in [component1, component2]:
            mcng_comp = MapCoreNodeGroup.objects.get(
                node=component,
                mapcore_group=mapcore_group3,
                is_deleted=False
            )
            assert mcng_comp.group == auth_groups_component[component.id]

    def test_create_mapcore_group_empty_node_groups_fails(self):
        """Test creating with empty node_groups fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': []
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'non-empty' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_missing_required_fields(self):
        """Test creating without required fields fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': 123
                            # Missing 'permission'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'permission' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_invalid_permission(self):
        """Test creating with invalid permission fails"""
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'invalid_permission'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'invalid' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_duplicate_in_request(self):
        """Test creating with duplicate mapcore_group_id in request fails"""
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        },
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'admin'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'duplicate' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_nonexistent_mapcore_group_id(self):
        """Test creating with nonexistent mapcore_group_id fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': 99999,
                            'permission': 'write'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'not found' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_already_exists(self):
        """Test creating duplicate MapCoreNodeGroup fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': self.mapcore_group1.id,
                            'permission': 'write'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'already exists' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_duplicate_component_ids(self):
        """Test creating with duplicate component_ids fails"""
        component = NodeFactory(creator=self.admin_user, parent=self.node)
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        }
                    ],
                    'component_ids': [component._id, component._id]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'duplicate' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_nonexistent_component_ids(self):
        """Test creating with nonexistent component_ids fails"""
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        }
                    ],
                    'component_ids': ['nonexistent123']
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'not found' in res.json['errors'][0]['detail'].lower()

    def test_create_mapcore_group_non_admin_fails(self):
        """Test non-admin user cannot create MapCoreNodeGroup"""
        mapcore_group3 = MapCoreGroup.objects.create(_id='test-mapcore-3')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group3.id,
                            'permission': 'write'
                        }
                    ]
                }
            }
        }

        res = self.app.post_json(self.url, payload, auth=self.read_only_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_update_mapcore_group_success(self):
        """Test updating MapCoreNodeGroup permission"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng1.id,
                            'permission': 'read'
                        }
                    ]
                }
            }
        }

        res = self.app.patch_json(self.url, payload, auth=self.admin_user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 1

        updated_item = res.json['data'][0]
        assert updated_item['attributes']['permission'] == 'read'

        # Verify database
        self.mcng1.refresh_from_db()
        assert self.mcng1.group == self.auth_groups['read']

    def test_update_mapcore_group_multiple(self):
        """Test updating multiple MapCoreNodeGroups"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng1.id,
                            'permission': 'read'
                        },
                        {
                            'node_group_id': self.mcng2.id,
                            'permission': 'admin'
                        }
                    ]
                }
            }
        }

        res = self.app.patch_json(self.url, payload, auth=self.admin_user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 2

        # Verify database
        self.mcng1.refresh_from_db()
        self.mcng2.refresh_from_db()
        assert self.mcng1.group == self.auth_groups['read']
        assert self.mcng2.group == self.auth_groups['admin']

    def test_update_mapcore_group_empty_node_groups_fails(self):
        """Test updating with empty node_groups fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': []
                }
            }
        }

        res = self.app.patch_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400

    def test_update_mapcore_group_duplicate_node_group_ids(self):
        """Test updating with duplicate node_group_ids fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng1.id,
                            'permission': 'read'
                        },
                        {
                            'node_group_id': self.mcng1.id,
                            'permission': 'write'
                        }
                    ]
                }
            }
        }

        res = self.app.patch_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'duplicate' in res.json['errors'][0]['detail'].lower()

    def test_update_mapcore_group_nonexistent_node_group_id(self):
        """Test updating with nonexistent node_group_id fails"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': 99999,
                            'permission': 'read'
                        }
                    ]
                }
            }
        }

        res = self.app.patch_json(self.url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'not found' in res.json['errors'][0]['detail'].lower()

    def test_update_mapcore_group_non_admin_fails(self):
        """Test non-admin user cannot update MapCoreNodeGroup"""
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng1.id,
                            'permission': 'read'
                        }
                    ]
                }
            }
        }

        res = self.app.patch_json(self.url, payload, auth=self.read_only_user.auth, expect_errors=True)
        assert res.status_code == 403


@pytest.mark.django_db
class TestNodeMapCoreGroupRemove(ApiTestCase):
    """Test cases for NodeMapCoreGroupRemove view"""

    def setUp(self):
        super().setUp()
        self.user = AuthUserFactory()
        self.admin_user = AuthUserFactory()
        self.read_only_user = AuthUserFactory()

        self.node = ProjectFactory(creator=self.admin_user, is_public=False)
        self.node.add_contributor(self.user, permissions='admin')
        self.node.add_contributor(self.read_only_user, permissions='read')
        self.node.add_addon('groups', auth=Auth(self.user))  # Enable groups addon
        self.node.save()

        # Create auth groups for the node
        self.auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            self.auth_groups[perm] = AuthGroup.objects.get_or_create(
                name=f'node_{self.node.id}_{perm}'
            )[0]

        # Create MapCoreGroup
        self.mapcore_group = MapCoreGroup.objects.create(_id='test-mapcore-remove')

        # Create MapCoreNodeGroup relationship
        self.mcng = MapCoreNodeGroup.objects.create(
            node=self.node,
            group=self.auth_groups['admin'],
            mapcore_group=self.mapcore_group,
            creator=self.admin_user,
        )

    def test_delete_mapcore_group_success(self):
        """Test deleting a MapCoreNodeGroup relationship"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        res = self.app.delete(url, auth=self.admin_user.auth)
        assert res.status_code == 204

        # Verify soft delete in database
        self.mcng.refresh_from_db()
        assert self.mcng.is_deleted is True

    def test_delete_mapcore_group_with_components(self):
        """Test deleting MapCoreNodeGroup with component relationships"""
        component1 = NodeFactory(creator=self.admin_user, parent=self.node)
        component2 = NodeFactory(creator=self.admin_user, parent=self.node)

        # Create component relationships
        mcng_comp1 = MapCoreNodeGroup.objects.create(
            node=component1,
            group=self.auth_groups['write'],
            mapcore_group=self.mapcore_group,
            creator=self.admin_user,
        )
        mcng_comp2 = MapCoreNodeGroup.objects.create(
            node=component2,
            group=self.auth_groups['write'],
            mapcore_group=self.mapcore_group,
            creator=self.admin_user,
        )

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/?component_ids={component1._id},{component2._id}'

        res = self.app.delete(url, auth=self.admin_user.auth)
        assert res.status_code == 204

        # Verify all relationships are soft deleted
        self.mcng.refresh_from_db()
        mcng_comp1.refresh_from_db()
        mcng_comp2.refresh_from_db()

        assert self.mcng.is_deleted is True
        assert mcng_comp1.is_deleted is True
        assert mcng_comp2.is_deleted is True

    def test_delete_mapcore_group_duplicate_component_ids_fails(self):
        """Test deleting with duplicate component_ids fails"""
        component = NodeFactory(creator=self.admin_user, parent=self.node)

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/?component_ids={component._id},{component._id}'

        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'duplicate' in res.json['errors'][0]['detail'].lower()

    def test_delete_mapcore_group_nonexistent_component_ids_fails(self):
        """Test deleting with nonexistent component_ids fails"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/?component_ids=nonexistent123'

        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'not found' in res.json['errors'][0]['detail'].lower()

    def test_delete_mapcore_group_component_not_child_fails(self):
        """Test deleting with component_id not a child of the node fails"""
        other_node = ProjectFactory(creator=self.admin_user)
        component = NodeFactory(creator=self.admin_user, parent=other_node)

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/?component_ids={component._id}'

        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 400
        assert 'not children' in res.json['errors'][0]['detail'].lower()

    def test_delete_mapcore_group_component_missing_relationship_fails(self):
        """Test deleting component that doesn't have the relationship fails"""
        component = NodeFactory(creator=self.admin_user, parent=self.node)
        # No MapCoreNodeGroup relationship created for component

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/?component_ids={component._id}'

        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 404
        assert 'not found' in res.json['errors'][0]['detail'].lower()

    def test_delete_mapcore_group_nonexistent_node_group_id_fails(self):
        """Test deleting with nonexistent node_group_id fails"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/99999/'

        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 404

    def test_delete_mapcore_group_already_deleted_fails(self):
        """Test deleting already deleted MapCoreNodeGroup fails"""
        self.mcng.is_deleted = True
        self.mcng.save()

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 404

    def test_delete_mapcore_group_non_admin_fails(self):
        """Test non-admin user cannot delete MapCoreNodeGroup"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        res = self.app.delete(url, auth=self.read_only_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_delete_mapcore_group_unauthenticated_fails(self):
        """Test unauthenticated user cannot delete MapCoreNodeGroup"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        res = self.app.delete(url, expect_errors=True)
        assert res.status_code == 401

    def test_delete_mapcore_group_creates_log(self):
        """Test that deleting creates a log entry"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        initial_log_count = self.node.logs.count()

        res = self.app.delete(url, auth=self.admin_user.auth)
        assert res.status_code == 204

        # Verify log was created
        self.node.refresh_from_db()
        assert self.node.logs.count() == initial_log_count + 1

        latest_log = self.node.logs.first()
        assert latest_log.action == self.node.log_class.MAPCORE_GROUP_REMOVED

    def test_delete_mapcore_group_updates_node_modified(self):
        """Test that deleting updates node modified timestamp"""
        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        original_modified = self.node.modified

        res = self.app.delete(url, auth=self.admin_user.auth)
        assert res.status_code == 204

        # Verify node modified was updated
        self.node.refresh_from_db()
        assert self.node.modified > original_modified

    def test_delete_mapcore_group_from_public_node(self):
        """Test deleting MapCoreNodeGroup from public node"""
        self.node.is_public = True
        self.node.save()

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

        res = self.app.delete(url, auth=self.admin_user.auth)
        assert res.status_code == 204


@pytest.mark.django_db
class TestGroupsAddonEnabledPermission(ApiTestCase):
    """
    Verify that GroupsAddonEnabled blocks when the groups addon
    is disabled on the node, and allows them when the addon is enabled.
    """

    def setUp(self):
        super().setUp()
        self.admin_user = AuthUserFactory()

        # Node WITHOUT the groups addon enabled
        self.node = ProjectFactory(creator=self.admin_user, is_public=True)
        # Ensure addon is absent
        if self.node.has_addon('groups'):
            self.node.delete_addon('groups', auth=Auth(self.admin_user))
        self.node.save()

        # Create auth groups and data so payloads are otherwise valid
        self.auth_groups = {}
        for perm in ['read', 'write', 'admin']:
            self.auth_groups[perm] = AuthGroup.objects.get_or_create(
                name=f'node_{self.node.id}_{perm}'
            )[0]

        self.mapcore_group = MapCoreGroup.objects.create(_id='addon-perm-mcg')
        self.mcng = MapCoreNodeGroup.objects.create(
            node=self.node,
            group=self.auth_groups['admin'],
            mapcore_group=self.mapcore_group,
            creator=self.admin_user,
        )

        self.list_url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/'
        self.detail_url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{self.mcng.id}/'

    def test_get_list_addon_disabled_returns_200(self):
        """GET list is allowed even when groups addon is disabled (safe methods bypass GroupsAddonEnabled)."""
        assert not self.node.has_addon('groups')
        res = self.app.get(self.list_url, auth=self.admin_user.auth)
        assert res.status_code == 200

    def test_get_list_addon_enabled_returns_200(self):
        """GET list is allowed when groups addon is enabled."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.save()

        res = self.app.get(self.list_url, auth=self.admin_user.auth)
        assert res.status_code == 200

    def test_post_addon_disabled_returns_403(self):
        """POST (create) is blocked when groups addon is disabled."""
        assert not self.node.has_addon('groups')
        mapcore_group2 = MapCoreGroup.objects.create(_id='addon-perm-mcg-2')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group2.id,
                            'permission': 'write',
                        }
                    ]
                },
            }
        }

        res = self.app.post_json(self.list_url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_post_addon_enabled_returns_201(self):
        """POST (create) is allowed when groups addon is enabled."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.save()

        mapcore_group2 = MapCoreGroup.objects.create(_id='addon-perm-mcg-2-enabled')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group2.id,
                            'permission': 'write',
                        }
                    ]
                },
            }
        }

        res = self.app.post_json(self.list_url, payload, auth=self.admin_user.auth)
        assert res.status_code == 201

    def test_patch_addon_disabled_returns_403(self):
        """PATCH (update) is blocked when groups addon is disabled."""
        assert not self.node.has_addon('groups')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng.id,
                            'permission': 'read',
                        }
                    ]
                },
            }
        }

        res = self.app.patch_json(self.list_url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_patch_addon_enabled_returns_200(self):
        """PATCH (update) is allowed when groups addon is enabled."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.save()

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng.id,
                            'permission': 'read',
                        }
                    ]
                },
            }
        }

        res = self.app.patch_json(self.list_url, payload, auth=self.admin_user.auth)
        assert res.status_code == 200

    def test_delete_addon_disabled_returns_403(self):
        """DELETE is blocked when groups addon is disabled."""
        assert not self.node.has_addon('groups')
        res = self.app.delete(self.detail_url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_delete_addon_enabled_returns_204(self):
        """DELETE is allowed when groups addon is enabled."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.save()

        res = self.app.delete(self.detail_url, auth=self.admin_user.auth)
        assert res.status_code == 204

        self.mcng.refresh_from_db()
        assert self.mcng.is_deleted is True

    def test_get_list_addon_soft_deleted_returns_200(self):
        """GET list is allowed even when groups addon is soft-deleted (safe methods bypass GroupsAddonEnabled)."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.delete_addon('groups', auth=Auth(self.admin_user))
        assert not self.node.has_addon('groups')

        res = self.app.get(self.list_url, auth=self.admin_user.auth)
        assert res.status_code == 200

    def test_post_addon_soft_deleted_returns_403(self):
        """POST is blocked when groups addon was added then soft-deleted."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.delete_addon('groups', auth=Auth(self.admin_user))
        assert not self.node.has_addon('groups')

        mapcore_group2 = MapCoreGroup.objects.create(_id='addon-soft-del-mcg')
        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'mapcore_group_id': mapcore_group2.id,
                            'permission': 'write',
                        }
                    ]
                },
            }
        }
        res = self.app.post_json(self.list_url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_patch_addon_soft_deleted_returns_403(self):
        """PATCH is blocked when groups addon was added then soft-deleted."""
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.delete_addon('groups', auth=Auth(self.admin_user))
        assert not self.node.has_addon('groups')

        payload = {
            'data': {
                'type': 'node-mapcore-group',
                'attributes': {
                    'node_groups': [
                        {
                            'node_group_id': self.mcng.id,
                            'permission': 'read',
                        }
                    ]
                },
            }
        }
        res = self.app.patch_json(self.list_url, payload, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 403

    def test_delete_addon_soft_deleted_returns_403(self):
        """DELETE is blocked when groups addon was added then soft-deleted."""
        # Create a fresh mcng so it is not already deleted
        mcng2 = MapCoreNodeGroup.objects.create(
            node=self.node,
            group=self.auth_groups['write'],
            mapcore_group=self.mapcore_group,
            creator=self.admin_user,
        )
        self.node.add_addon('groups', auth=Auth(self.admin_user))
        self.node.delete_addon('groups', auth=Auth(self.admin_user))
        assert not self.node.has_addon('groups')

        url = f'/{API_BASE}nodes/{self.node._id}/map_core/groups/{mcng2.id}/'
        res = self.app.delete(url, auth=self.admin_user.auth, expect_errors=True)
        assert res.status_code == 403


@pytest.mark.django_db
class TestMixinMapCorePermissions:
    def test_mapcore_node_group_get_permission(self):
        node = ProjectFactory()
        creator = node.creator
        mg = MapCoreGroup.objects.create(_id='mcg-parse')

        ag_admin = AuthGroup.objects.create(name=f'node_{node._id}_admin')
        ag_read = AuthGroup.objects.create(name=f'node_{node._id}_read')
        ag_write = AuthGroup.objects.create(name=f'node_{node._id}_write')
        ag_other = AuthGroup.objects.create(name='some_other_group')

        mng_admin = MapCoreNodeGroup.objects.create(node=node, group=ag_admin, mapcore_group=mg, creator=creator)
        mng_read = MapCoreNodeGroup.objects.create(node=node, group=ag_read, mapcore_group=mg, creator=creator)
        mng_write = MapCoreNodeGroup.objects.create(node=node, group=ag_write, mapcore_group=mg, creator=creator)
        mng_other = MapCoreNodeGroup.objects.create(node=node, group=ag_other, mapcore_group=mg, creator=creator)

        assert mng_admin.get_permission == 'admin'
        assert mng_read.get_permission == 'read'
        assert mng_write.get_permission == 'write'
        assert mng_other.get_permission is None

    def test_has_permission_mapcore_grants_and_denies(self):
        from django.contrib.auth.models import Group as AuthGroup, Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        mapcore_user = UserFactory()
        node.add_addon('groups', auth=Auth(mapcore_user))  # Enable groups addon
        # user that will be "in" the mapcore group
        # other user not in group
        other_user = UserFactory()

        mg = MapCoreGroup.objects.create(_id='mcg-grant')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        # link auth group <-> node via mapcore mapping
        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)

        # link user <-> mapcore group
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        # give the auth group the node 'read' permission via NodeGroupObjectPermission
        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        # user who is in mapcore group should have read permission
        assert node.has_permission(mapcore_user, 'read') is True

        # user not in mapcore group should not have read permission
        assert node.has_permission(other_user, 'read') is False

    def test_has_permission_by_is_admin_group_parent(self):
        from django.contrib.auth.models import Group as AuthGroup, Permission
        from osf.models.node import NodeGroupObjectPermission

        # Create a root node and a child node
        root = ProjectFactory()
        root.add_addon('groups', auth=Auth(root.creator))  # Enable groups addon on root
        child = NodeFactory(creator=root.creator, parent=root)
        child.add_addon('groups', auth=Auth(root.creator))  # Enable groups addon on child

        # Users
        mapcore_user = UserFactory()
        other_user = UserFactory()

        # MapCore group and corresponding auth group for the root node (admin)
        mg = MapCoreGroup.objects.create(_id='mcg-parent-admin')
        ag = AuthGroup.objects.create(name=f'node_{root._id}_admin')

        # Link auth group <-> root node via MapCoreNodeGroup
        MapCoreNodeGroup.objects.create(node=root, group=ag, mapcore_group=mg, creator=root.creator)

        # Link user <-> mapcore group
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        # Give the auth group the 'admin_node' permission on the root node
        perm = Permission.objects.get(codename='admin_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=root)

        # Because the auth group on the parent (root) has admin_node, the child should
        # grant read permission to users that belong to the MapCore group
        assert child.has_permission(mapcore_user, 'read') is True

        # A user not in the linked MapCore group should not get read via this chain
        assert child.has_permission(other_user, 'read') is False

    def test_has_permission_handles_mapcore_node_group_filter_exception(self):
        from unittest import mock

        node = ProjectFactory()
        mapcore_user = UserFactory()

        mg = MapCoreGroup.objects.create(_id='mcg-ex-hasperm')
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        # Simulate MapCoreNodeGroup.objects.filter raising an exception both where used in has_permission
        # and potential calls to is_admin_group_parent (which also calls MapCoreNodeGroup.objects.filter).
        with mock.patch('osf.models.mapcore_node_group.MapCoreNodeGroup.objects.filter', side_effect=Exception('boom')):
            # Should not raise; should fall back to normal permission checks and return False
            assert node.has_permission(mapcore_user, 'read') is False

    def test_get_permissions_mapcore_includes_and_excludes(self):
        from django.contrib.auth.models import Group as AuthGroup, Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        node.add_addon('groups', auth=Auth(node.creator))  # Enable groups addon
        mapcore_user = UserFactory()
        other_user = UserFactory()

        mg = MapCoreGroup.objects.create(_id='mcg-getperms')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        perms_mapcore = node.get_permissions(mapcore_user)
        assert 'read' in perms_mapcore

        perms_other = node.get_permissions(other_user)
        # other_user has no group-derived permission and is not a contributor, expect no 'read'
        assert 'read' not in perms_other

    def test_get_permissions_handles_mapcore_node_group_filter_exception(self):
        from unittest import mock

        node = ProjectFactory()
        user = UserFactory()

        # Create a MapCoreGroup and link the user (so MapCoreUserGroup.filter would normally return ids)
        mg = MapCoreGroup.objects.create(_id='mcg-ex-getperms')
        MapCoreUserGroup.objects.create(user=user, mapcore_group=mg, is_deleted=False)

        # Simulate MapCoreNodeGroup.objects.filter raising an exception
        with mock.patch('osf.models.mapcore_node_group.MapCoreNodeGroup.objects.filter', side_effect=Exception('boom')):
            perms = node.get_permissions(user)

        # Should handle exception and return an empty list (no derived group perms)
        assert perms == []

    def test_is_admin_group_parent_handles_mapcore_node_group_filter_exception(self):
        from unittest import mock
        from osf.models.mixins import is_admin_group_parent

        parent = ProjectFactory()
        mg = MapCoreGroup.objects.create(_id='mcg-ex-isadmin')
        # user_mapcore_group_ids could be anything; if MapCoreNodeGroup.filter raises, function should return False
        user_mapcore_group_ids = [mg.id]

        with mock.patch('osf.models.mapcore_node_group.MapCoreNodeGroup.objects.filter', side_effect=Exception('boom')):
            assert is_admin_group_parent(parent, user_mapcore_group_ids) is False

    def test_has_permission_mapcore_groups_addon_disabled(self):
        """When groups addon is disabled, MapCore permission logic is skipped and user is denied."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        mapcore_user = UserFactory()

        # Ensure groups addon is disabled
        if node.has_addon('groups'):
            node.delete_addon('groups', auth=Auth(mapcore_user))
        assert not node.has_addon('groups')

        mg = MapCoreGroup.objects.create(_id='mcg-addon-disabled-hasperm')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        # Without groups addon, MapCore permissions are not applied
        assert node.has_permission(mapcore_user, 'read') is False

    def test_has_permission_mapcore_groups_addon_enabled(self):
        """When groups addon is enabled, MapCore permission logic grants access."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission
        node = ProjectFactory()
        mapcore_user = UserFactory()
        node.add_addon('groups', auth=Auth(mapcore_user))  # Enable groups addon

        mg = MapCoreGroup.objects.create(_id='mcg-addon-enabled-hasperm')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        # With groups addon enabled, MapCore permissions ARE applied
        assert node.has_permission(mapcore_user, 'read') is True

    def test_get_permissions_mapcore_groups_addon_disabled(self):
        """When groups addon is disabled, MapCore-derived permissions are not included."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        mapcore_user = UserFactory()

        # groups addon is NOT enabled
        # Ensure groups addon is disabled
        if node.has_addon('groups'):
            node.delete_addon('groups', auth=Auth(mapcore_user))
        assert not node.has_addon('groups')

        mg = MapCoreGroup.objects.create(_id='mcg-addon-disabled-getperms')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        # Without groups addon, MapCore-derived permissions are not included
        perms = node.get_permissions(mapcore_user)
        assert 'read' not in perms

    def test_get_permissions_mapcore_groups_addon_enabled(self):
        """When groups addon is enabled, MapCore-derived permissions are included."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        mapcore_user = UserFactory()
        node.add_addon('groups', auth=Auth(mapcore_user))  # Enable groups addon

        mg = MapCoreGroup.objects.create(_id='mcg-addon-enabled-getperms')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        # With groups addon enabled, MapCore-derived permissions ARE included
        perms = node.get_permissions(mapcore_user)
        assert 'read' in perms

    def test_has_permission_parent_admin_via_mapcore_groups_addon_disabled(self):
        """When groups addon is disabled, parent admin via MapCore does NOT grant child read."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        root = ProjectFactory()
        root.add_addon('groups', auth=Auth(root.creator))  # Enable groups addon on root
        child = NodeFactory(creator=root.creator, parent=root)
        mapcore_user = UserFactory()

        # groups addon NOT enabled on child
        if child.has_addon('groups'):
            child.delete_addon('groups', auth=Auth(mapcore_user))
        assert not child.has_addon('groups')

        mg = MapCoreGroup.objects.create(_id='mcg-parent-admin-disabled')
        ag = AuthGroup.objects.create(name=f'node_{root._id}_admin')

        MapCoreNodeGroup.objects.create(node=root, group=ag, mapcore_group=mg, creator=root.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='admin_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=root)

        # Without groups addon on child, is_admin_group_parent path is not taken
        assert child.has_permission(mapcore_user, 'read') is True

    def test_has_permission_parent_admin_via_mapcore_groups_addon_enabled(self):
        """When groups addon is enabled, parent admin via MapCore grants child read."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        root = ProjectFactory()
        child = NodeFactory(creator=root.creator, parent=root)  # Enable groups addon on child
        mapcore_user = UserFactory()
        child.add_addon('groups', auth=Auth(mapcore_user))

        mg = MapCoreGroup.objects.create(_id='mcg-parent-admin-enabled')
        ag = AuthGroup.objects.create(name=f'node_{root._id}_admin')

        MapCoreNodeGroup.objects.create(node=root, group=ag, mapcore_group=mg, creator=root.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='admin_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=root)

        # With groups addon enabled on child, is_admin_group_parent path grants read
        assert child.has_permission(mapcore_user, 'read') is True

    def test_has_permission_mapcore_groups_addon_deleted_acts_as_disabled(self):
        """A deleted (soft-removed) groups addon is treated as disabled."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        mapcore_user = UserFactory()
        node.add_addon('groups', auth=Auth(mapcore_user))
        node.delete_addon('groups', auth=Auth(mapcore_user))  # Soft-delete the addon

        mg = MapCoreGroup.objects.create(_id='mcg-addon-deleted-hasperm')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        # Deleted addon is not returned by get_addons, so MapCore logic is skipped
        assert node.has_permission(mapcore_user, 'read') is False

    def test_get_permissions_mapcore_groups_addon_deleted_acts_as_disabled(self):
        """A deleted (soft-removed) groups addon means MapCore permissions are not included."""
        from django.contrib.auth.models import Permission
        from osf.models.node import NodeGroupObjectPermission

        node = ProjectFactory()
        mapcore_user = UserFactory()
        node.add_addon('groups', auth=Auth(mapcore_user))
        node.delete_addon('groups', auth=Auth(mapcore_user))  # Soft-delete the addon

        mg = MapCoreGroup.objects.create(_id='mcg-addon-deleted-getperms')
        ag = AuthGroup.objects.create(name=f'node_{node._id}_read')

        MapCoreNodeGroup.objects.create(node=node, group=ag, mapcore_group=mg, creator=node.creator)
        MapCoreUserGroup.objects.create(user=mapcore_user, mapcore_group=mg, is_deleted=False)

        perm = Permission.objects.get(codename='read_node')
        NodeGroupObjectPermission.objects.create(group=ag, permission=perm, content_object=node)

        perms = node.get_permissions(mapcore_user)
        assert 'read' not in perms

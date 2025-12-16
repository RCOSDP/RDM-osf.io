import pytest
from unittest import mock

from api.institutions.authentication import update_mapcore_groups
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_user_group import MapCoreUserGroup
from osf_tests.factories import AuthUserFactory


@pytest.mark.django_db
class TestUpdateMapcoreGroups:
    """Test cases for update_mapcore_groups function"""

    @pytest.fixture
    def user(self):
        """Create a test user"""
        return AuthUserFactory()

    @pytest.fixture
    def mapcore_group(self):
        """Create a test mapcore group"""
        group, created = MapCoreGroup.objects.get_or_create(_id='test_group')
        return group

    def test_returns_early_when_prefix_not_set(self, user):
        """Test that function returns early when MAP_GATEWAY_ISMEMBEROF_PREFIX is not set"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', None):
            update_mapcore_groups(user, provider)

        # No groups should be created
        assert MapCoreUserGroup.objects.filter(user=user).count() == 0

    def test_returns_early_when_prefix_empty(self, user):
        """Test that function returns early when MAP_GATEWAY_ISMEMBEROF_PREFIX is empty"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', ''):
            update_mapcore_groups(user, provider)

        # No groups should be created
        assert MapCoreUserGroup.objects.filter(user=user).count() == 0

    def test_returns_early_when_no_groups_provided(self, user):
        """Test that function returns early when no groups are provided in provider"""
        provider = {
            'user': {}
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # No groups should be created
        assert MapCoreUserGroup.objects.filter(user=user).count() == 0

    def test_returns_early_when_groups_empty_string(self, user):
        """Test that function returns early when groups is empty string"""
        provider = {
            'user': {
                'groups': ''
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # No groups should be created
        assert MapCoreUserGroup.objects.filter(user=user).count() == 0

    def test_adds_single_new_group(self, user):
        """Test adding a single new group"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # One group should be created
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 1
        assert user_groups.first().mapcore_group._id == 'group1'

    def test_adds_multiple_new_groups(self, user):
        """Test adding multiple new groups separated by semicolon"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/group2;https://cg.gakunin.jp/gr/group3'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Three groups should be created
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 3
        group_ids = set(ug.mapcore_group._id for ug in user_groups)
        assert group_ids == {'group1', 'group2', 'group3'}

    def test_filters_groups_by_prefix(self, user):
        """Test that only groups with matching prefix are added"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1;https://other.prefix.jp/group2;https://cg.gakunin.jp/gr/group3'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Only two groups with matching prefix should be created
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 2
        group_ids = set(ug.mapcore_group._id for ug in user_groups)
        assert group_ids == {'group1', 'group3'}

    def test_ignores_empty_group_names(self, user):
        """Test that empty group names after prefix removal are ignored"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/;https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Only one valid group should be created
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 1
        assert user_groups.first().mapcore_group._id == 'group1'

    def test_marks_removed_groups_as_deleted(self, user, mapcore_group):
        """Test that existing groups not in new list are marked as deleted"""
        # Create an existing user group
        existing_group = MapCoreUserGroup.objects.create(
            user=user,
            mapcore_group=mapcore_group,
            is_deleted=False
        )

        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/new_group'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Existing group should be marked as deleted
        existing_group.refresh_from_db()
        assert existing_group.is_deleted is True
        assert existing_group.modified is not None

        # New group should be created
        new_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert new_groups.count() == 1
        assert new_groups.first().mapcore_group._id == 'new_group'

    def test_keeps_existing_groups_in_new_list(self, user, mapcore_group):
        """Test that existing groups in new list are kept and not deleted"""
        # Create an existing user group
        existing_group = MapCoreUserGroup.objects.create(
            user=user,
            mapcore_group=mapcore_group,
            is_deleted=False
        )

        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/test_group;https://cg.gakunin.jp/gr/new_group'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Existing group should still be active
        existing_group.refresh_from_db()
        assert existing_group.is_deleted is False

        # Two active groups should exist
        active_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert active_groups.count() == 2
        group_ids = set(ug.mapcore_group._id for ug in active_groups)
        assert group_ids == {'test_group', 'new_group'}

    def test_handles_mixed_update_scenario(self, user):
        """Test handling multiple groups: keep existing, delete removed, add new"""
        # Create existing groups
        group1, _ = MapCoreGroup.objects.get_or_create(_id='keep_group')
        group2, _ = MapCoreGroup.objects.get_or_create(_id='delete_group')

        MapCoreUserGroup.objects.create(user=user, mapcore_group=group1, is_deleted=False)
        MapCoreUserGroup.objects.create(user=user, mapcore_group=group2, is_deleted=False)

        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/keep_group;https://cg.gakunin.jp/gr/new_group'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Verify results
        active_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert active_groups.count() == 2
        group_ids = set(ug.mapcore_group._id for ug in active_groups)
        assert group_ids == {'keep_group', 'new_group'}

        # Verify deleted group
        deleted_group = MapCoreUserGroup.objects.get(user=user, mapcore_group=group2)
        assert deleted_group.is_deleted is True

    def test_handles_no_existing_groups(self, user):
        """Test adding groups when user has no existing groups"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/group2'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Two groups should be created
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 2
        group_ids = set(ug.mapcore_group._id for ug in user_groups)
        assert group_ids == {'group1', 'group2'}

    def test_handles_all_groups_removed(self, user):
        """Test when all existing groups are removed (no new groups match)"""
        # Create existing groups
        group1, _ = MapCoreGroup.objects.get_or_create(_id='group1')
        group2, _ = MapCoreGroup.objects.get_or_create(_id='group2')

        MapCoreUserGroup.objects.create(user=user, mapcore_group=group1, is_deleted=False)
        MapCoreUserGroup.objects.create(user=user, mapcore_group=group2, is_deleted=False)

        provider = {
            'user': {
                'groups': 'https://other.prefix.jp/group3'  # Different prefix, won't match
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # All existing groups should be marked as deleted
        active_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert active_groups.count() == 0

        deleted_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=True)
        assert deleted_groups.count() == 2

    def test_reuses_existing_mapcore_group(self, user, mapcore_group):
        """Test that existing MapCoreGroup is reused, not duplicated"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/test_group'
            }
        }

        initial_mapcore_group_count = MapCoreGroup.objects.count()

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # MapCoreGroup count should not increase (reused existing)
        assert MapCoreGroup.objects.count() == initial_mapcore_group_count

        # User group should be created with existing mapcore_group
        user_group = MapCoreUserGroup.objects.get(user=user, is_deleted=False)
        assert user_group.mapcore_group == mapcore_group

    def test_handles_duplicate_groups_in_input(self, user):
        """Test that duplicate group names in input are handled correctly"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/group1;https://cg.gakunin.jp/gr/group2'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Only unique groups should be created (set deduplication)
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 2
        group_ids = set(ug.mapcore_group._id for ug in user_groups)
        assert group_ids == {'group1', 'group2'}

    def test_ignores_already_deleted_groups(self, user):
        """Test that already deleted groups are not processed"""
        # Create existing groups, one already deleted
        group1, _ = MapCoreGroup.objects.get_or_create(_id='group1')
        group2, _ = MapCoreGroup.objects.get_or_create(_id='group2')

        MapCoreUserGroup.objects.create(user=user, mapcore_group=group1, is_deleted=False)
        MapCoreUserGroup.objects.create(user=user, mapcore_group=group2, is_deleted=True)

        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/new_group'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # Only the active group should be marked as deleted
        active_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert active_groups.count() == 1
        assert active_groups.first().mapcore_group._id == 'new_group'

        # Two groups should be deleted (group1 newly deleted, group2 already deleted)
        deleted_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=True)
        assert deleted_groups.count() == 2

    def test_handles_special_characters_in_group_names(self, user):
        """Test handling group names with special characters"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group-with-dashes;https://cg.gakunin.jp/gr/group_with_underscores;https://cg.gakunin.jp/gr/group.with.dots'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            update_mapcore_groups(user, provider)

        # All groups should be created with special characters preserved
        user_groups = MapCoreUserGroup.objects.filter(user=user, is_deleted=False)
        assert user_groups.count() == 3
        group_ids = set(ug.mapcore_group._id for ug in user_groups)
        assert group_ids == {'group-with-dashes', 'group_with_underscores', 'group.with.dots'}

    def test_bulk_update_called_when_groups_deleted(self, user):
        """Test that bulk_update is called when groups need to be deleted"""
        # Create existing groups
        group1, _ = MapCoreGroup.objects.get_or_create(_id='group1')
        group2, _ = MapCoreGroup.objects.get_or_create(_id='group2')

        MapCoreUserGroup.objects.create(user=user, mapcore_group=group1, is_deleted=False)
        MapCoreUserGroup.objects.create(user=user, mapcore_group=group2, is_deleted=False)

        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/new_group'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            with mock.patch('api.institutions.authentication.bulk_update') as mock_bulk_update:
                update_mapcore_groups(user, provider)

                # bulk_update should be called with the deleted groups
                assert mock_bulk_update.called
                call_args = mock_bulk_update.call_args
                deleted_list = call_args[0][0]
                assert len(deleted_list) == 2
                assert call_args[1]['update_fields'] == ['is_deleted', 'modified']

    def test_no_bulk_update_when_no_deletions(self, user):
        """Test that bulk_update is not called when no groups need to be deleted"""
        provider = {
            'user': {
                'groups': 'https://cg.gakunin.jp/gr/group1'
            }
        }

        with mock.patch('api.institutions.authentication.settings.MAP_GATEWAY_ISMEMBEROF_PREFIX', 'https://cg.gakunin.jp/gr/'):
            with mock.patch('api.institutions.authentication.bulk_update') as mock_bulk_update:
                update_mapcore_groups(user, provider)

                # bulk_update should not be called
                assert not mock_bulk_update.called

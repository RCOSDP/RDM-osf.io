import asyncio
import mock
import pytest
import unittest
from django.apps import apps

from rest_framework import status as http_status
from nose.tools import (assert_equal, assert_true, assert_false)
from django.utils import timezone

from addons.datasteward.tests.utils import DataStewardAddonTestCase
from addons.datasteward.views import (
    disable_datasteward_addon,
    enable_datasteward_addon,
    get_project_contributors,
    get_node_settings_model,
    bulk_create_contributors,
    clear_permissions,
    disconnect_addons_multiple_projects,
    task_after_add_contributor,
    task_after_update_contributor,
    task_after_remove_contributor,
    add_project_logs,
    add_contributor_permission,
    update_contributor_permission,
    after_remove_contributor_permission,
    BATCH_SIZE,
)
from framework.auth.core import Auth
from osf.exceptions import UserStateError, ValidationValueError
from osf.models import NodeLog, AbstractNode
from osf.models.contributor import Contributor
from osf.utils import permissions

from osf_tests.factories import AuthUserFactory, ContributorFactory, InstitutionFactory, ProjectFactory, \
    osfstorage_settings
from tests.base import OsfTestCase
from website.util import api_url_for

OSF_NODE = 'osf.node'


@pytest.mark.django_db
class TestDataStewardViews(DataStewardAddonTestCase, OsfTestCase, unittest.TestCase):
    def setUp(self):
        super(TestDataStewardViews, self).setUp()
        self.new_user = AuthUserFactory(fullname='datasteward@osf', username='datasteward@osf.com')
        self.new_user.save()
        self.project = ProjectFactory(creator=self.new_user)
        self.project.save()
        self.auth = Auth(self.new_user)

    def set_datasteward_addon(self):
        self.new_user.is_data_steward = True
        self.new_user.save()

        self.settings = self.new_user.get_or_add_addon(self.ADDON_SHORT_NAME)
        if not self.settings.enabled:
            self.settings.enabled = True
            self.settings.save()
            self.new_user.save()

    def test_datasteward_user_config_get_forbidden(self):
        url = api_url_for('datasteward_user_config_get')
        self.new_user.is_data_steward = False
        self.new_user.save()

        res = self.app.get(url, auth=self.new_user.auth, expect_errors=True)

        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)
        assert_equal(res.json, {})

    def test_datasteward_user_config_get_false_by_addon_settings_not_found(self):
        url = api_url_for('datasteward_user_config_get')
        self.new_user.is_data_steward = True
        self.new_user.save()

        res = self.app.get(url, auth=self.new_user.auth)

        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_false(res.json.get('enabled'))

    def test_datasteward_user_config_get_true(self):
        url = api_url_for('datasteward_user_config_get')
        self.set_datasteward_addon()

        res = self.app.get(url, auth=self.new_user.auth)

        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_true(res.json.get('enabled'))

    def test_datasteward_user_config_post_bad_request(self):
        url = api_url_for('datasteward_user_config_post')
        res = self.app.post_json(url, {}, auth=self.new_user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_datasteward_user_config_post_forbidden(self):
        url = api_url_for('datasteward_user_config_post')
        self.new_user.is_data_steward = False
        self.new_user.save()

        res = self.app.post_json(url, {'enabled': True}, auth=self.new_user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)

    @mock.patch('addons.datasteward.views.disable_datasteward_addon')
    def test_datasteward_user_config_post_enabled_is_false_and_skipped_projects_is_none(self, mock_disable_addon):
        self.set_datasteward_addon()
        url = api_url_for('datasteward_user_config_post')
        mock_disable_addon.return_value = None

        res = self.app.post_json(url, {'enabled': False}, auth=self.new_user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @mock.patch('addons.datasteward.views.disable_datasteward_addon')
    def test_datasteward_user_config_post_enabled_is_false_and_skipped_projects_is_not_none(self, mock_disable_addon):
        self.set_datasteward_addon()
        url = api_url_for('datasteward_user_config_post')
        project = ProjectFactory.build()
        mock_disable_addon.return_value = [project]

        res = self.app.post_json(url, {'enabled': False}, auth=self.new_user.auth, status=http_status.HTTP_200_OK)

        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_equal(res.json.get('skipped_projects')[0].get('name'), project.title)

    @mock.patch('addons.datasteward.views.enable_datasteward_addon')
    def test_datasteward_user_config_post_enabled_is_true_and_enable_addon_result_is_false(self, mock_enable_addon):
        self.set_datasteward_addon()
        url = api_url_for('datasteward_user_config_post')
        mock_enable_addon.return_value = False

        res = self.app.post_json(url, {'enabled': True}, auth=self.new_user.auth, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
        assert_equal(res.status_code, http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    @mock.patch('addons.datasteward.views.enable_datasteward_addon')
    def test_datasteward_user_config_post_enabled_is_true_and_enable_addon_result_is_true(self, mock_enable_addon):
        self.set_datasteward_addon()
        url = api_url_for('datasteward_user_config_post')
        mock_enable_addon.return_value = True

        res = self.app.post_json(url, {'enabled': True}, auth=self.new_user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)

    def test_enable_datasteward_addon_no_affiliated_institutions(self):
        result = enable_datasteward_addon(self.auth)

        assert_false(result)

    def test_enable_datasteward_addon_update_not_admin_permission_contributor_to_admin_permission_success(self):
        user = AuthUserFactory(fullname='enabledatasteward@osf', username='enabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        user.affiliated_institutions.add(institution)
        user.save()

        kwargs = node.contributor_kwargs
        kwargs['_order'] = 0
        new_contributor = ContributorFactory(**kwargs)
        new_contributor.user = user
        new_contributor.is_data_steward = False
        new_contributor.visible = True
        new_contributor.save()

        result = enable_datasteward_addon(Auth(user))

        updated_contributor = Contributor.objects.filter(node=node, user=user)
        assert_true(updated_contributor.exists() and updated_contributor.first().permission == permissions.ADMIN)
        assert_true(result)

    def test_enable_datasteward_addon_add_contributor_success(self):
        user = AuthUserFactory(fullname='enabledatasteward@osf', username='enabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        user.affiliated_institutions.add(institution)
        user.save()

        result = enable_datasteward_addon(Auth(user))

        updated_contributor = Contributor.objects.filter(node=node, user=user)
        assert_true(updated_contributor.exists() and updated_contributor.first().permission == permissions.ADMIN)
        assert_true(result)

    def test_enable_datasteward_addon_add_contributor_user_is_disabled(self):
        user = AuthUserFactory(fullname='enabledatasteward@osf', username='enabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        user.affiliated_institutions.add(institution)
        user.date_disabled = timezone.now()
        user.save()

        with self.assertRaises(ValidationValueError):
            enable_datasteward_addon(Auth(user))

    def test_enable_datasteward_addon_add_contributor_user_is_not_registered(self):
        user = AuthUserFactory(fullname='enabledatasteward@osf', username='enabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        user.affiliated_institutions.add(institution)
        user.is_registered = False
        user.save()

        with self.assertRaises(UserStateError):
            enable_datasteward_addon(Auth(user))

    def test_disable_datasteward_addon_affiliated_institutions_is_empty(self):
        result = disable_datasteward_addon(self.auth)

        assert_false(result)

    def test_disable_datasteward_addon_skip_project_has_only_one_admin(self):
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        self.new_user.affiliated_institutions.add(institution)
        self.new_user.save()

        contributor = Contributor.objects.filter(user=self.new_user, node=node).first()
        contributor.is_data_steward = True
        contributor.data_steward_old_permission = permissions.READ
        contributor.save()
        result = disable_datasteward_addon(self.auth)

        assert_true(len(result) == 1)

    def test_disable_datasteward_addon_update_permission_success(self):
        user = AuthUserFactory(fullname='disabledatasteward@osf', username='disabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        self.new_user.affiliated_institutions.add(institution)
        self.new_user.save()
        user.affiliated_institutions.add(institution)
        user.save()

        contributor = Contributor.objects.filter(user=self.new_user, node=node).first()
        contributor.is_data_steward = False
        contributor.save()

        kwargs = node.contributor_kwargs
        kwargs['_order'] = 0
        new_contributor = ContributorFactory(**kwargs)
        new_contributor.user = user
        new_contributor.is_data_steward = True
        new_contributor.visible = True
        new_contributor.data_steward_old_permission = permissions.READ
        new_contributor.save()

        node.add_permission(user, permissions.ADMIN, save=False)

        result = disable_datasteward_addon(Auth(user))

        assert_false(result)

    def test_disable_datasteward_addon_contributor_is_data_steward_is_False_skip_project(self):
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        self.new_user.affiliated_institutions.add(institution)
        self.new_user.save()

        contributor = Contributor.objects.filter(user=self.new_user, node=node).first()
        contributor.is_data_steward = False
        contributor.save()

        result = disable_datasteward_addon(self.auth)

        assert_false(result)

    def test_disable_datasteward_addon_remove_contributor_skip_project(self):
        user = AuthUserFactory(fullname='disabledatasteward@osf', username='disabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        self.new_user.affiliated_institutions.add(institution)
        self.new_user.save()
        user.affiliated_institutions.add(institution)
        user.save()

        contributor = Contributor.objects.filter(user=self.new_user, node=node).first()
        contributor.visible = False
        contributor.save()

        kwargs = node.contributor_kwargs
        kwargs['_order'] = 0
        new_contributor = ContributorFactory(**kwargs)
        new_contributor.user = user
        new_contributor.is_data_steward = True
        new_contributor.visible = True
        new_contributor.save()

        node.add_permission(user, permissions.ADMIN, save=False)

        result = disable_datasteward_addon(Auth(user))

        assert_true(len(result) == 1)

    def test_disable_datasteward_addon_remove_contributor_success(self):
        user = AuthUserFactory(fullname='disabledatasteward@osf', username='disabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        self.new_user.affiliated_institutions.add(institution)
        self.new_user.save()
        user.affiliated_institutions.add(institution)
        user.unclaimed_records = {}
        user.unclaimed_records[node._id] = {'name': node.title}
        user.save()

        contributor = Contributor.objects.filter(user=self.new_user, node=node).first()
        contributor.visible = True
        contributor.save()

        kwargs = node.contributor_kwargs
        kwargs['_order'] = 0
        new_contributor = ContributorFactory(**kwargs)
        new_contributor.user = user
        new_contributor.is_data_steward = True
        new_contributor.visible = True
        new_contributor.save()

        node.add_permission(user, permissions.ADMIN, save=False)

        result = disable_datasteward_addon(Auth(user))

        assert_false(result)

    def test_disable_datasteward_addon_skip_project_not_have_user_as_contributor(self):
        user = AuthUserFactory(fullname='disabledatasteward@osf', username='disabledatasteward@osf.com')
        institution = InstitutionFactory()
        node = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        institution.nodes.add(node)
        institution.save()
        self.new_user.affiliated_institutions.add(institution)
        self.new_user.save()
        user.affiliated_institutions.add(institution)
        user.save()

        result = disable_datasteward_addon(Auth(user))

        assert_false(result)

    def test_get_project_contributors(self):
        node1 = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        node2 = ProjectFactory(creator=self.new_user, type=OSF_NODE, is_deleted=False)
        contributor1 = ContributorFactory()
        contributor1.user = self.new_user
        contributor1.node = node1
        contributor2 = ContributorFactory()
        contributor2.user = self.new_user
        contributor2.node = node2
        contributors = [contributor1, contributor2]

        item1, item2, item3 = get_project_contributors(contributors, self.new_user, node1)
        assert item1 == [contributor2]
        assert item2 == [contributor1]
        assert item3 == contributor1

    def test_get_node_settings_model(self):
        setting = get_node_settings_model(apps.get_app_config('addons_datasteward'))
        assert setting is None
        setting = get_node_settings_model(osfstorage_settings)
        assert setting == osfstorage_settings.node_settings

    def test_bulk_create_contributors(self):
        with mock.patch.object(Contributor.objects, 'bulk_create') as mock_bulk_create:
            bulk_create_contributors(range(1, BATCH_SIZE + 1))
            assert mock_bulk_create.called

    def test_clear_permissions(self):
        project1 = ProjectFactory()
        project2 = ProjectFactory()
        project1.add_permission(self.new_user, permissions.ADMIN, save=False)
        project2.add_permission(self.new_user, permissions.READ, save=False)
        projects = [project1, project2]

        clear_permissions(projects, self.new_user)
        assert project1.get_permissions(self.new_user) == []
        assert project2.get_permissions(self.new_user) == []

    def test_disconnect_addons_multiple_projects(self):
        projects = [ProjectFactory(), ProjectFactory()]
        with mock.patch('addons.datasteward.views.bulk_update') as mock_bulk_update:
            disconnect_addons_multiple_projects(projects, self.new_user)
            assert mock_bulk_update.called

    def test_add_project_logs(self):
        project1 = ProjectFactory()
        project2 = ProjectFactory()
        project1.add_permission(self.new_user, permissions.ADMIN, save=False)
        project2.add_permission(self.new_user, permissions.ADMIN, save=False)
        projects = [project1, project2]

        add_project_logs(projects, self.new_user, NodeLog.CONTRIB_ADDED)
        assert NodeLog.objects.filter(node__in=projects, action=NodeLog.CONTRIB_ADDED).count() == 2

    def test_add_contributor_permission(self):
        new_user = AuthUserFactory()
        new_auth = Auth(new_user)
        with mock.patch('addons.datasteward.views.enqueue_postcommit_task') as mock_task:
            with mock.patch.object(AbstractNode, 'update_or_enqueue_on_resource_updated') as mock_resource_updated:
                self.project.set_identifier_value('doi', 'FK424601')
                loop = asyncio.new_event_loop()
                coro = loop.create_task(add_contributor_permission(self.project, new_auth))
                loop.run_until_complete(asyncio.wait([coro]))
                loop.close()

                assert mock_task.called
                assert mock_resource_updated.called
                assert permissions.ADMIN in self.project.get_permissions(new_user)

    def test_update_contributor_permission(self):
        new_user = AuthUserFactory()
        new_auth = Auth(new_user)
        with mock.patch('addons.datasteward.views.enqueue_postcommit_task') as mock_task:
            loop = asyncio.new_event_loop()
            coro = loop.create_task(update_contributor_permission(self.project, new_auth, permissions.READ))
            loop.run_until_complete(asyncio.wait([coro]))
            loop.close()
            assert mock_task.called
            assert self.project.get_permissions(new_user) == [permissions.READ]

    def test_after_remove_contributor_permission(self):
        new_user = AuthUserFactory()
        new_auth = Auth(new_user)
        with mock.patch('addons.datasteward.views.enqueue_postcommit_task') as mock_task:
            with mock.patch.object(AbstractNode, 'update_or_enqueue_on_resource_updated') as mock_resource_updated:
                self.project.set_identifier_value('doi', 'FK424601')
                loop = asyncio.new_event_loop()
                coro = loop.create_task(after_remove_contributor_permission(self.project, new_auth))
                loop.run_until_complete(asyncio.wait([coro]))
                loop.close()
                assert mock_task.called
                assert mock_resource_updated.called

    def test_task_after_add_contributor(self):
        with mock.patch('addons.datasteward.views.project_signals.contributors_updated') as mock_contributors_updated:
            with mock.patch('addons.datasteward.views.project_signals.contributor_added') as mock_contributor_added:
                task_after_add_contributor(self.project.id, self.new_user.id)
                assert mock_contributors_updated.send.called
                assert mock_contributor_added.send.called

    def test_task_after_update_contributor(self):
        with mock.patch('addons.datasteward.views.project_signals.write_permissions_revoked') as mock_write_permissions_revoked:
            with mock.patch('addons.datasteward.views.project_signals.contributors_updated') as mock_contributors_updated:
                task_after_update_contributor(self.project.id, permissions.READ)
                assert mock_write_permissions_revoked.send.called
                assert mock_contributors_updated.send.called

    def test_task_after_remove_contributor(self):
        with mock.patch('addons.datasteward.views.remove_contributor_from_subscriptions') as mock_remove_contributor_from_subscriptions:
            with mock.patch('addons.datasteward.views.project_signals.contributors_updated') as mock_contributors_updated:
                task_after_remove_contributor(self.project.id, self.new_user.id)
                assert mock_remove_contributor_from_subscriptions.called
                assert mock_contributors_updated.send.called

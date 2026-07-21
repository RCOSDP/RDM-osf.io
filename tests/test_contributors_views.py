# -*- coding: utf-8 -*-

import time
import datetime
import mock
from nose.tools import *  # noqa; PEP8 asserts

from osf_tests.factories import ProjectFactory, NodeFactory, AuthUserFactory, NodeRequestFactory, InstitutionFactory
from osf.utils import workflows
from osf.utils import permissions
from tests.base import OsfTestCase

from framework.auth.decorators import Auth

from website.profile import utils
from website.project.views.node import _get_contributor_invite_dates, node_contributors
from osf.models.nodelog import NodeLog


class TestContributorUtils(OsfTestCase):

    def setUp(self):
        super(TestContributorUtils, self).setUp()
        self.project = ProjectFactory()

    def test_serialize_user(self):
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert_true(serialized['visible'])
        assert_equal(serialized['permission'], permissions.ADMIN)

    def test_serialize_user_full_does_not_include_emails_by_default(self):
        serialized = utils.serialize_user(self.project.creator, self.project, full=True)
        assert_not_in('emails', serialized)

    def test_serialize_user_full_includes_email_if_is_profile(self):
        serialized = utils.serialize_user(
            self.project.creator,
            self.project,
            full=True,
            is_profile=True
        )
        assert_in('emails', serialized)

    def test_serialize_user_admin(self):
        serialized = utils.serialize_user(self.project.creator, self.project, admin=True)
        assert_false(serialized['visible'])
        assert_equal(serialized['permission'], permissions.READ)

    def test_serialize_user_includes_invite_date(self):
        invite_date = '2024-01-15'
        serialized = utils.serialize_user(self.project.creator, self.project, invite_date=invite_date)
        assert_equal(serialized['invite_date'], invite_date)

    def test_serialize_user_invite_date_defaults_to_none(self):
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert serialized['invite_date'] is None

    def test_serialize_user_email_field_present(self):
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert_in('email', serialized)

    def test_serialize_user_affiliation_no_institution(self):
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert_equal(serialized['affiliation'], '')

    def test_serialize_user_affiliation_with_institution(self):
        institution = InstitutionFactory()
        self.project.creator.affiliated_institutions.add(institution)
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert_equal(serialized['affiliation'], institution.name)

    def test_serialize_contributors_passes_invite_dates(self):
        contribs = list(self.project.contributor_set.all())
        invite_dates = {self.project.creator._id: '2023-05-01'}
        result = utils.serialize_contributors(contribs, self.project, invite_dates=invite_dates)
        assert_equal(len(result), 1)
        assert_equal(result[0]['invite_date'], '2023-05-01')

    def test_serialize_contributors_invite_date_none_when_not_in_dict(self):
        contribs = list(self.project.contributor_set.all())
        result = utils.serialize_contributors(contribs, self.project, invite_dates={})
        assert_equal(len(result), 1)
        assert result[0]['invite_date'] is None

    def test_serialize_contributors_no_invite_dates(self):
        contribs = list(self.project.contributor_set.all())
        result = utils.serialize_contributors(contribs, self.project)
        assert_equal(len(result), 1)
        assert result[0]['invite_date'] is None

    def test_serialize_access_requests(self):
        new_user = AuthUserFactory()
        node_request = NodeRequestFactory(
            creator=new_user,
            target=self.project,
            request_type=workflows.RequestTypes.ACCESS.value,
            machine_state=workflows.DefaultStates.INITIAL.value
        )
        node_request.run_submit(new_user)
        res = utils.serialize_access_requests(self.project)

        assert len(res) == 1
        assert res[0]['comment'] == node_request.comment
        assert res[0]['id'] == node_request._id
        assert res[0]['user'] == utils.serialize_user(new_user)


class TestContributorViews(OsfTestCase):

    def setUp(self):
        super(TestContributorViews, self).setUp()
        self.user = AuthUserFactory()
        self.auth = Auth(user=self.user)
        self.project = ProjectFactory(creator=self.user)

    def test_get_contributors_no_limit(self):
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=False,
        )
        self.project.save()
        url = self.project.api_url_for('get_contributors')
        res = self.app.get(url, auth=self.user.auth)
        # Should be two visible contributors on the project
        assert_equal(
            len(res.json['contributors']),
            2,
        )

    def test_get_contributors_with_limit(self):
        # Add five contributors
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=False,
        )
        self.project.save()
        # Set limit to three contributors
        url = self.project.api_url_for('get_contributors', limit=3)
        res = self.app.get(url, auth=self.user.auth)
        # Should be three visible contributors on the project
        assert_equal(
            len(res.json['contributors']),
            3,
        )
        # There should be two 'more' contributors not shown
        assert_equal(
            (res.json['more']),
            2,
        )

    def test_get_contributors_from_parent(self):
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            AuthUserFactory(),
            auth=self.auth,
            visible=False,
        )
        component = NodeFactory(parent=self.project, creator=self.user)

        user_already_on_component = AuthUserFactory()
        component.add_contributor(
            user_already_on_component,
            auth=self.auth,
            visible=True,
        )
        self.project.add_contributor(
            user_already_on_component,
            auth=self.auth,
            visible=True,
        )

        self.project.save()
        component.save()

        url = component.api_url_for('get_contributors_from_parent')
        res = self.app.get(url, auth=self.user.auth)
        # Should be all contributors, client-side handles marking
        # contributors that are already added to the child.

        ids = [contrib['id'] for contrib in res.json['contributors']]
        assert_not_in(user_already_on_component.id, ids)
        assert_equal(
            len(res.json['contributors']),
            2,
        )


class TestGetContributorInviteDates(OsfTestCase):

    def setUp(self):
        super(TestGetContributorInviteDates, self).setUp()
        self.user = AuthUserFactory()
        self.auth = Auth(user=self.user)
        self.project = ProjectFactory(creator=self.user)

    def _get_dates(self, project=None):
        node = project or self.project
        contribs = list(node.contributor_set.all())
        guids = [c.user._id for c in contribs]
        return _get_contributor_invite_dates(node, guids)

    def test_creator_gets_node_created_date(self):
        dates = self._get_dates()
        expected = self.project.created.strftime('%Y-%m-%d')
        assert_equal(dates[self.user._id], expected)

    def test_added_contributor_gets_log_date(self):
        new_user = AuthUserFactory()
        self.project.add_contributor(new_user, auth=self.auth, save=True)

        log = NodeLog.objects.filter(
            node=self.project,
            action=NodeLog.CONTRIB_ADDED,
        ).order_by('-date').first()

        dates = self._get_dates()
        expected = log.date.strftime('%Y-%m-%d')
        assert_equal(dates[new_user._id], expected)

    def test_admin_contrib_added_log_is_included(self):
        new_user = AuthUserFactory()
        # Simulate admin_contributor_added log (ユーザー登録代理機能)
        self.project.add_contributor(new_user, auth=self.auth, log=False, save=True)
        log_date = self.project.created + datetime.timedelta(days=1)
        NodeLog.objects.create(
            node=self.project,
            action=NodeLog.ADMIN_CONTRIB_ADDED,
            params={'contributors': [new_user._id]},
            user=self.user,
            date=log_date,
        )

        dates = self._get_dates()
        assert_in(new_user._id, dates)
        assert_not_equal(dates[new_user._id], self.project.created.strftime('%Y-%m-%d'))

    def test_contributor_with_no_log_gets_node_created_date(self):
        new_user = AuthUserFactory()
        # Add without log to simulate inherited contributor (component case)
        self.project.add_contributor(new_user, auth=self.auth, log=False, save=True)

        dates = self._get_dates()
        expected = self.project.created.strftime('%Y-%m-%d')
        assert_equal(dates[new_user._id], expected)

    def test_contributor_added_multiple_times_gets_most_recent_date(self):
        new_user = AuthUserFactory()
        self.project.add_contributor(new_user, auth=self.auth, save=True)

        # Simulate re-add by injecting a later log entry
        later_date = self.project.created + datetime.timedelta(days=30)
        NodeLog.objects.create(
            node=self.project,
            action=NodeLog.CONTRIB_ADDED,
            params={'contributors': [new_user._id]},
            user=self.user,
            date=later_date,
        )

        dates = self._get_dates()
        assert_equal(dates[new_user._id], later_date.strftime('%Y-%m-%d'))

    def test_creator_readded_gets_readd_date(self):
        # Creator removed then re-added — should show re-add date, not node_created
        self.project.remove_contributor(self.user, auth=self.auth)
        later_date = self.project.created + datetime.timedelta(days=10)
        NodeLog.objects.create(
            node=self.project,
            action=NodeLog.CONTRIB_ADDED,
            params={'contributors': [self.user._id]},
            user=self.user,
            date=later_date,
        )
        self.project.add_contributor(self.user, auth=self.auth, log=False, save=True)

        dates = self._get_dates()
        assert_equal(dates[self.user._id], later_date.strftime('%Y-%m-%d'))

    def test_all_current_contributors_have_dates(self):
        # _get_dates() passes only current-contributor guids; every one of them
        # must appear in the result regardless of whether a removed contributor's
        # log entry also leaks through.
        removed_user = AuthUserFactory()
        self.project.add_contributor(removed_user, auth=self.auth, save=True)
        self.project.remove_contributor(removed_user, auth=self.auth)

        dates = self._get_dates()

        contribs = list(self.project.contributor_set.all())
        current_guids = [c.user._id for c in contribs]
        assert_not_in(removed_user._id, current_guids)  # verify removal succeeded
        for guid in current_guids:
            assert guid in dates


class TestNodeContributorsView(OsfTestCase):
    """Tests for node_contributors view — verifies contributors/adminContributors
    serialization including invite_date, email, and affiliation fields."""

    def setUp(self):
        super(TestNodeContributorsView, self).setUp()
        self.user = AuthUserFactory()
        self.auth = Auth(user=self.user)
        self.project = ProjectFactory(creator=self.user)
        # ember_flag_is_active calls waffle.flag_is_active(request, ...) — patch
        # to False so decorator falls through to the real view.
        self._waffle_patcher = mock.patch('waffle.flag_is_active', return_value=False)
        self._waffle_patcher.start()
        # must_have_permission rebuilds auth via Auth.from_kwargs which calls
        # _get_current_user(). Patch it to return our test user.
        self._current_user_patcher = mock.patch(
            'framework.auth.core._get_current_user',
            return_value=self.user,
        )
        self._current_user_patcher.start()

    def tearDown(self):
        self._current_user_patcher.stop()
        self._waffle_patcher.stop()
        super(TestNodeContributorsView, self).tearDown()

    def _call_view(self, project=None):
        node = project or self.project
        return node_contributors(auth=self.auth, node=node)

    def test_contributors_key_present(self):
        ret = self._call_view()
        assert_in('contributors', ret)

    def test_admin_contributors_key_present(self):
        ret = self._call_view()
        assert_in('adminContributors', ret)

    def test_access_requests_key_present(self):
        ret = self._call_view()
        assert_in('access_requests', ret)

    def test_contributor_has_invite_date_field(self):
        ret = self._call_view()
        assert len(ret['contributors']) >= 1
        for contrib in ret['contributors']:
            assert_in('invite_date', contrib)

    def test_contributor_has_email_field(self):
        ret = self._call_view()
        for contrib in ret['contributors']:
            assert_in('email', contrib)

    def test_contributor_has_affiliation_field(self):
        ret = self._call_view()
        for contrib in ret['contributors']:
            assert_in('affiliation', contrib)

    def test_creator_invite_date_equals_node_created(self):
        # Creator has no CONTRIB_ADDED log, so fallback to node creation date.
        ret = self._call_view()
        creator_serialized = next(
            c for c in ret['contributors'] if c['id'] == self.user._id
        )
        expected = self.project.created.strftime('%Y-%m-%d')
        assert_equal(creator_serialized['invite_date'], expected)

    def test_added_contributor_invite_date_from_log(self):
        new_user = AuthUserFactory()
        self.project.add_contributor(new_user, auth=self.auth, save=True)

        log = NodeLog.objects.filter(
            node=self.project,
            action=NodeLog.CONTRIB_ADDED,
        ).order_by('-date').first()
        expected = log.date.strftime('%Y-%m-%d')

        ret = self._call_view()
        new_serialized = next(
            c for c in ret['contributors'] if c['id'] == new_user._id
        )
        assert_equal(new_serialized['invite_date'], expected)

    def test_contributor_affiliation_with_institution(self):
        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        ret = self._call_view()
        creator_serialized = next(
            c for c in ret['contributors'] if c['id'] == self.user._id
        )
        assert_equal(creator_serialized['affiliation'], institution.name)

    def test_admin_contributor_invite_date_equals_node_created(self):
        # Admin contributors (from parent) always get node_created as invite_date.
        parent = ProjectFactory(creator=self.user)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        node_created = component.created.strftime('%Y-%m-%d')
        for admin_contrib in ret['adminContributors']:
            assert_equal(admin_contrib['invite_date'], node_created)

    def test_admin_contributor_has_email_and_affiliation_fields(self):
        parent = ProjectFactory(creator=self.user)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        for admin_contrib in ret['adminContributors']:
            assert_in('email', admin_contrib)
            assert_in('affiliation', admin_contrib)

    def test_contributor_count_matches_project_contributors(self):
        new_user = AuthUserFactory()
        self.project.add_contributor(new_user, auth=self.auth, save=True)

        ret = self._call_view()
        expected_count = self.project.contributor_set.count()
        assert_equal(len(ret['contributors']), expected_count)

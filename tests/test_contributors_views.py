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

    def test_serialize_user_full_does_not_include_idp_email_without_is_profile(self):
        serialized = utils.serialize_user(self.project.creator, self.project, full=True, is_profile=False)
        assert_not_in('idp_email', serialized)

    def test_serialize_user_full_includes_idp_email_when_is_profile(self):
        serialized = utils.serialize_user(self.project.creator, self.project, full=True, is_profile=True)
        assert_in('idp_email', serialized)

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

    def test_serialize_user_email_not_included_by_default(self):
        user = self.project.creator
        serialized = utils.serialize_user(user, self.project)
        assert_not_in('email', serialized)

    def test_serialize_user_email_field_present_when_include_email_and_have_email(self):
        user = self.project.creator
        user.have_email = True
        user.save()
        serialized = utils.serialize_user(user, self.project, include_email=True)
        assert_in('email', serialized)
        assert_equal(serialized['email'], user.username)

    def test_serialize_user_email_field_empty_when_include_email_and_no_email(self):
        user = self.project.creator
        user.have_email = False
        user.save()
        serialized = utils.serialize_user(user, self.project, include_email=True)
        assert_in('email', serialized)
        assert_equal(serialized['email'], '')

    def test_serialize_user_affiliation_no_institution(self):
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert_equal(serialized['affiliation'], '')

    def test_serialize_user_affiliation_with_institution(self):
        institution = InstitutionFactory()
        self.project.creator.affiliated_institutions.add(institution)
        from django.db.models import prefetch_related_objects
        prefetch_related_objects([self.project.creator], 'affiliated_institutions')
        serialized = utils.serialize_user(self.project.creator, self.project)
        assert_equal(serialized['affiliation'], institution.name)

    def test_serialize_user_affiliation_selects_lowest_pk_institution(self):
        # With multiple institutions, the one with the lowest pk must be selected
        # (sorted ascending by pk, matching representative_affiliated_institution behaviour).
        inst1 = InstitutionFactory()
        inst2 = InstitutionFactory()
        low_pk_inst, high_pk_inst = (inst1, inst2) if inst1.pk < inst2.pk else (inst2, inst1)
        user = self.project.creator
        user.affiliated_institutions.add(low_pk_inst, high_pk_inst)
        from django.db.models import prefetch_related_objects
        prefetch_related_objects([user], 'affiliated_institutions')
        serialized = utils.serialize_user(user, self.project)
        assert_equal(serialized['affiliation'], low_pk_inst.name)

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
        assert_equal(dates[new_user._id], log_date.strftime('%Y-%m-%d'))

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

    def test_contributor_readded_gets_readd_date(self):
        # Contributor removed then re-added — should show re-add date, not original add date.
        # Use a non-creator user so remove_contributor succeeds (creator cannot be removed
        # when they are the only visible admin contributor).
        other_user = AuthUserFactory()
        self.project.add_contributor(other_user, auth=self.auth, save=True)
        self.project.remove_contributor(other_user, auth=self.auth)
        assert not self.project.is_contributor(other_user)

        later_date = self.project.created + datetime.timedelta(days=10)
        NodeLog.objects.create(
            node=self.project,
            action=NodeLog.CONTRIB_ADDED,
            params={'contributors': [other_user._id]},
            user=self.user,
            date=later_date,
        )
        self.project.add_contributor(other_user, auth=self.auth, log=False, save=True)

        dates = self._get_dates()
        assert_equal(dates[other_user._id], later_date.strftime('%Y-%m-%d'))

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
        # Use a separate parent_admin user who is NOT a contributor of the component,
        # so that parent_admin_contributors returns a non-empty list.
        parent = ProjectFactory(creator=self.user)
        parent_admin = AuthUserFactory()
        parent.add_contributor(parent_admin, permissions=permissions.ADMIN, auth=self.auth, save=True)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        assert len(ret['adminContributors']) >= 1, 'adminContributors must be non-empty for this test to be meaningful'
        node_created = component.created.strftime('%Y-%m-%d')
        for admin_contrib in ret['adminContributors']:
            assert_equal(admin_contrib['invite_date'], node_created)

    def test_admin_contributor_has_email_and_affiliation_fields(self):
        # Use a separate parent_admin user who is NOT a contributor of the component,
        # so that parent_admin_contributors returns a non-empty list.
        parent = ProjectFactory(creator=self.user)
        parent_admin = AuthUserFactory()
        parent.add_contributor(parent_admin, permissions=permissions.ADMIN, auth=self.auth, save=True)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        assert len(ret['adminContributors']) >= 1, 'adminContributors must be non-empty for this test to be meaningful'
        for admin_contrib in ret['adminContributors']:
            assert_in('email', admin_contrib)
            assert_in('affiliation', admin_contrib)

    def test_admin_contributor_email_value_when_have_email(self):
        # Verify email value (not just key presence) for admin contributors.
        parent = ProjectFactory(creator=self.user)
        parent_admin = AuthUserFactory()
        parent_admin.have_email = True
        parent_admin.save()
        parent.add_contributor(parent_admin, permissions=permissions.ADMIN, auth=self.auth, save=True)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        assert len(ret['adminContributors']) >= 1, 'adminContributors must be non-empty for this test to be meaningful'
        admin_serialized = next(c for c in ret['adminContributors'] if c['id'] == parent_admin._id)
        assert_equal(admin_serialized['email'], parent_admin.username)

    def test_admin_contributor_email_empty_when_no_email(self):
        parent = ProjectFactory(creator=self.user)
        parent_admin = AuthUserFactory()
        parent_admin.have_email = False
        parent_admin.save()
        parent.add_contributor(parent_admin, permissions=permissions.ADMIN, auth=self.auth, save=True)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        assert len(ret['adminContributors']) >= 1, 'adminContributors must be non-empty for this test to be meaningful'
        admin_serialized = next(c for c in ret['adminContributors'] if c['id'] == parent_admin._id)
        assert_equal(admin_serialized['email'], '')

    def test_admin_contributor_affiliation_with_institution(self):
        parent = ProjectFactory(creator=self.user)
        parent_admin = AuthUserFactory()
        institution = InstitutionFactory()
        parent_admin.affiliated_institutions.add(institution)
        parent.add_contributor(parent_admin, permissions=permissions.ADMIN, auth=self.auth, save=True)
        component = NodeFactory(parent=parent, creator=self.user)

        ret = node_contributors(auth=self.auth, node=component)

        assert len(ret['adminContributors']) >= 1, 'adminContributors must be non-empty for this test to be meaningful'
        admin_serialized = next(c for c in ret['adminContributors'] if c['id'] == parent_admin._id)
        assert_equal(admin_serialized['affiliation'], institution.name)

    def test_admin_contrib_added_log_invite_date_via_view(self):
        # Integration: ADMIN_CONTRIB_ADDED log (代理登録) must surface as invite_date
        # when the contributors list is fetched through the node_contributors view.
        new_user = AuthUserFactory()
        self.project.add_contributor(new_user, auth=self.auth, log=False, save=True)
        log_date = self.project.created + datetime.timedelta(days=2)
        NodeLog.objects.create(
            node=self.project,
            action=NodeLog.ADMIN_CONTRIB_ADDED,
            params={'contributors': [new_user._id]},
            user=self.user,
            date=log_date,
        )

        ret = self._call_view()
        new_serialized = next(c for c in ret['contributors'] if c['id'] == new_user._id)
        assert_equal(new_serialized['invite_date'], log_date.strftime('%Y-%m-%d'))

    def test_contributor_count_matches_project_contributors(self):
        new_user = AuthUserFactory()
        self.project.add_contributor(new_user, auth=self.auth, save=True)

        ret = self._call_view()
        expected_count = self.project.contributor_set.count()
        assert_equal(len(ret['contributors']), expected_count)

    def test_non_admin_contributor_has_no_email_field(self):
        # A read-only contributor calls node_contributors; their response must
        # NOT contain the 'email' key because include_email is False for
        # non-admin callers.
        read_user = AuthUserFactory()
        self.project.add_contributor(read_user, permissions=permissions.READ, auth=self.auth, save=True)
        read_auth = Auth(user=read_user)
        self._current_user_patcher.stop()
        patcher = mock.patch('framework.auth.core._get_current_user', return_value=read_user)
        patcher.start()
        try:
            ret = node_contributors(auth=read_auth, node=self.project)
        finally:
            patcher.stop()
            # Restart the original patcher so tearDown can stop it cleanly.
            self._current_user_patcher = mock.patch(
                'framework.auth.core._get_current_user',
                return_value=self.user,
            )
            self._current_user_patcher.start()
        for contrib in ret['contributors']:
            assert_not_in('email', contrib)

    def test_non_admin_contributor_invite_date_is_none(self):
        # Non-admin path passes invite_dates=None, so every contributor's
        # invite_date must be None (not a date string).
        read_user = AuthUserFactory()
        self.project.add_contributor(read_user, permissions=permissions.READ, auth=self.auth, save=True)
        read_auth = Auth(user=read_user)
        self._current_user_patcher.stop()
        patcher = mock.patch('framework.auth.core._get_current_user', return_value=read_user)
        patcher.start()
        try:
            ret = node_contributors(auth=read_auth, node=self.project)
        finally:
            patcher.stop()
            self._current_user_patcher = mock.patch(
                'framework.auth.core._get_current_user',
                return_value=self.user,
            )
            self._current_user_patcher.start()
        for contrib in ret['contributors']:
            assert_in('invite_date', contrib)
            assert_is_none(contrib['invite_date'])

    def test_non_admin_contributor_affiliation_is_empty(self):
        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        read_user = AuthUserFactory()
        self.project.add_contributor(read_user, permissions=permissions.READ, auth=self.auth, save=True)
        read_auth = Auth(user=read_user)
        self._current_user_patcher.stop()
        patcher = mock.patch('framework.auth.core._get_current_user', return_value=read_user)
        patcher.start()
        try:
            ret = node_contributors(auth=read_auth, node=self.project)
        finally:
            patcher.stop()
            self._current_user_patcher = mock.patch(
                'framework.auth.core._get_current_user',
                return_value=self.user,
            )
            self._current_user_patcher.start()
        for contrib in ret['contributors']:
            assert_equal(contrib['affiliation'], '')

    def test_non_admin_contributor_admin_contributors_have_no_email(self):
        parent = ProjectFactory(creator=self.user)
        parent_admin = AuthUserFactory()
        parent.add_contributor(parent_admin, permissions=permissions.ADMIN, auth=self.auth, save=True)
        read_user = AuthUserFactory()
        parent.add_contributor(read_user, permissions=permissions.READ, auth=self.auth, save=True)
        component = NodeFactory(parent=parent, creator=self.user)
        component.add_contributor(read_user, permissions=permissions.READ, auth=self.auth, save=True)
        read_auth = Auth(user=read_user)
        self._current_user_patcher.stop()
        patcher = mock.patch('framework.auth.core._get_current_user', return_value=read_user)
        patcher.start()
        try:
            ret = node_contributors(auth=read_auth, node=component)
        finally:
            patcher.stop()
            self._current_user_patcher = mock.patch(
                'framework.auth.core._get_current_user',
                return_value=self.user,
            )
            self._current_user_patcher.start()
        assert len(ret['adminContributors']) >= 1, 'adminContributors must be non-empty for this test to be meaningful'
        for admin_contrib in ret['adminContributors']:
            assert_not_in('email', admin_contrib)

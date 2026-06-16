import mock
from osf.models import Registration
import pytest
from rest_framework import status as http_status
from framework.exceptions import HTTPError
from framework.auth.core import Auth

from tests.base import OsfTestCase
from osf_tests.factories import RetractionFactory, Sanction, UserFactory, ProjectFactory, NodeFactory
from website.project.views.node import node_groups
from website import ember_osf_web
import waffle

pytestmark = pytest.mark.django_db


class TestNodeGroupsView(OsfTestCase):

    def test_node_groups_requires_read_permission(self):
        """
        If the calling user does not have READ permission, must_have_permission should raise 403.
        We call the decorated view using kwargs `nid` and `user` so the decorators can
        construct the Auth object from kwargs.
        """
        with self.context:
            node = ProjectFactory(is_public=False)
            user = UserFactory()

            with pytest.raises(HTTPError) as excinfo:
                # call decorated view; decorators expect nid/pid in kwargs
                node_groups(nid=node._id, user=user)
            err = excinfo.value
            assert err.code == http_status.HTTP_403_FORBIDDEN

    def test_node_groups_returns_expected_keys_when_permitted(self):
        """
        When user has permission, node_groups should return a dict containing 'groups' and 'adminGroups'.
        """
        with self.context:
            node = ProjectFactory(is_public=False)
            node.add_addon('groups', auth=Auth(node.creator))  # Enable groups addon
            creator = node.creator
            # Create a user and grant READ permission
            user = UserFactory()
            # grant read via add_contributor / permission helpers
            node.add_contributor(contributor=user, auth=Auth(creator), permissions='read')
            node.save()

            # Ensure ember flag does not divert to the ember app
            with mock.patch('waffle.flag_is_active', return_value=False):
                result = node_groups(nid=node._id, user=user)
            assert isinstance(result, dict)
            assert 'groups' in result
            assert 'adminGroups' in result

    def test_node_groups_redirects_if_retracted(self):
        """
        If node is retracted, must_not_be_retracted_registration makes the view return a redirect response.
        """
        with self.context:
            # Create a registration and an approved retraction using the factories
            retraction = RetractionFactory(state=Sanction.APPROVED, approve=True)
            registration = Registration.objects.get(retraction=retraction)
            # Ensure registration is public (decorator logic expects registration-like object)
            registration.is_public = True
            registration.save()

            # Use a user that has permission (creator)
            user = registration.creator

            # Call — decorator should return a Flask redirect Response
            # Use pid=... because this is a registration
            with mock.patch('waffle.flag_is_active', return_value=False):
                resp = node_groups(pid=registration._id, user=user)

            # Redirect responses from Flask typically have status_code 302
            # Accept either a Response-like object with status_code or a werkzeug Response
            assert hasattr(resp, 'status_code')
            assert resp.status_code in (301, 302, 303, 307)

    def test_node_groups_returns_ember_app_when_flag_active(self):
        """
        When the EMBER feature flag is active, the ember_flag_is_active decorator should return use_ember_app()
        instead of executing the view. Patch the decorator's use_ember_app to return a sentinel.
        """
        with self.context:
            node = ProjectFactory()
            user = node.creator

            # Patch waffle to report the feature flag active
            with mock.patch('waffle.flag_is_active', return_value=True):
                # Patch the imported use_ember_app name in the decorators module to return a sentinel
                # The decorator uses use_ember_app imported into website.ember_osf_web.decorators,
                # so patch that name to avoid loading actual assets.
                with mock.patch('website.ember_osf_web.decorators.use_ember_app', return_value='EMBER-SENTINEL'):
                    resp = node_groups(nid=node._id, user=user)
                    # Should be the sentinel we returned from patched use_ember_app
                    assert resp == 'EMBER-SENTINEL'

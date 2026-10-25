# -*- coding: utf-8 -*-
"""Property tests for the template access predicate.

The node-membership branch of template/engine access must admit exactly the
users who hold an explicit role on a related node: contributors and members
of mAP core groups bound to the node. Implicit parent-admin READ and public
visibility of the node itself grant nothing through this branch.
"""

import uuid

import pytest

from framework.auth.core import Auth
from framework.exceptions import HTTPError

from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_node_group import MapCoreNodeGroup
from osf.models.mapcore_user_group import MapCoreUserGroup
from osf.utils import permissions
from osf_tests.factories import (
    AuthUserFactory,
    InstitutionFactory,
    NodeFactory,
    ProjectFactory,
)
from tests.base import OsfTestCase

from addons.workflow.models import (
    WorkflowActivation,
    WorkflowDefinitionSnapshot,
    WorkflowEngine,
    WorkflowTemplate,
)
from addons.workflow.services import get_user_accessible_templates
from addons.workflow.views import _get_engine_or_404, _get_template_or_404

pytestmark = pytest.mark.django_db


class TemplateAccessPredicateTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.owner = AuthUserFactory()
        self.node = ProjectFactory(creator=self.owner)
        institution = InstitutionFactory()
        self.engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://workflow.example/api/',
            signing_kid='kid-test',
            institution=institution,
        )
        snapshot = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='definition-access',
            definition_key='definition-access',
            name='Access Process',
            version=1,
        )
        self.template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=snapshot,
            registered_by=self.owner,
        )

    def _bind_mapcore_group(self, node, user, permission=permissions.WRITE, enable_addon=True):
        if enable_addon:
            node.add_addon('groups', auth=Auth(node.creator))
        mapcore_group = MapCoreGroup.objects.create(_id='group-{}'.format(uuid.uuid4()))
        MapCoreNodeGroup.objects.create(
            node=node,
            group=node.get_group(permission),
            mapcore_group=mapcore_group,
            creator=node.creator,
        )
        MapCoreUserGroup.objects.create(user=user, mapcore_group=mapcore_group)

    def _assert_has_access(self, user, template=None, engine=None):
        template = template or self.template
        engine = engine or self.engine
        assert _get_template_or_404(template.pk, user) == template
        assert _get_engine_or_404(engine.engine_id, user) == engine
        assert template in get_user_accessible_templates(user)

    def _assert_denied(self, user, template=None, engine=None):
        template = template or self.template
        engine = engine or self.engine
        with pytest.raises(HTTPError) as excinfo:
            _get_template_or_404(template.pk, user)
        assert excinfo.value.code == 404
        with pytest.raises(HTTPError) as excinfo:
            _get_engine_or_404(engine.engine_id, user)
        assert excinfo.value.code == 404
        assert template not in get_user_accessible_templates(user)

    def test_contributor_has_access(self):
        contributor = AuthUserFactory()
        self.node.add_contributor(contributor, permissions=permissions.READ, auth=Auth(self.owner), save=True)
        self._assert_has_access(contributor)

    def test_mapcore_group_member_has_access(self):
        member = AuthUserFactory()
        self._bind_mapcore_group(self.node, member)
        self._assert_has_access(member)

    def _assert_activation_access(self, user):
        assert _get_template_or_404(self.template.pk, user) == self.template
        assert _get_engine_or_404(self.engine.engine_id, user) == self.engine
        # get_user_accessible_templates only lists templates hosted on the
        # user's own nodes; activation-node members are out of its scope
        assert self.template not in get_user_accessible_templates(user)

    def test_contributor_has_access_via_activation(self):
        contributor = AuthUserFactory()
        activation_node = ProjectFactory()
        activation_node.add_contributor(contributor, permissions=permissions.READ, auth=Auth(activation_node.creator), save=True)
        WorkflowActivation.objects.create(
            node=activation_node,
            template=self.template,
            activated_by=self.owner,
        )
        self._assert_activation_access(contributor)

    def test_mapcore_group_member_has_access_via_activation(self):
        member = AuthUserFactory()
        activation_node = ProjectFactory()
        self._bind_mapcore_group(activation_node, member)
        WorkflowActivation.objects.create(
            node=activation_node,
            template=self.template,
            activated_by=self.owner,
        )
        self._assert_activation_access(member)

    def test_parent_admin_denied(self):
        parent_admin = AuthUserFactory()
        parent = ProjectFactory(creator=parent_admin)
        component = NodeFactory(parent=parent, creator=self.owner)
        snapshot = WorkflowDefinitionSnapshot.objects.create(
            engine=self.engine,
            definition_id='definition-component',
            definition_key='definition-component',
            name='Component Process',
            version=1,
        )
        template = WorkflowTemplate.objects.create(
            node=component,
            definition=snapshot,
            registered_by=self.owner,
        )
        assert component.has_permission(parent_admin, permissions.READ)
        self._assert_denied(parent_admin, template=template)

    def test_stranger_denied_on_public_node(self):
        self.node.is_public = True
        self.node.save()
        self._assert_denied(AuthUserFactory())

    def test_unrelated_user_denied(self):
        self._assert_denied(AuthUserFactory())

    def test_group_member_denied_when_groups_addon_disabled(self):
        member = AuthUserFactory()
        self._bind_mapcore_group(self.node, member, enable_addon=False)
        self._assert_denied(member)

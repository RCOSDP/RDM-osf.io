# -*- coding: utf-8 -*-
"""Unit tests for workflow addon node settings."""

import uuid
from unittest import mock

import pytest

from framework.auth.core import Auth

from osf_tests.factories import AuthUserFactory, InstitutionFactory, ProjectFactory

from addons.workflow.models import (
    NodeSettings,
    WorkflowActivation,
    WorkflowDefinitionSnapshot,
    WorkflowEngine,
    WorkflowTemplate,
)
from tests.base import OsfTestCase

pytestmark = pytest.mark.django_db


class WorkflowNodeSettingsTests(OsfTestCase):
    def setUp(self):
        super().setUp()
        self.user = AuthUserFactory()
        self.auth = Auth(self.user)
        self.node = ProjectFactory(creator=self.user)
        self.node.add_addon('workflow', auth=self.auth)
        self.node_settings = self.node.get_addon('workflow')
        assert isinstance(self.node_settings, NodeSettings)

    def test_complete_always_true(self):
        assert self.node_settings.complete is True

    def test_active_templates_empty_without_entries(self):
        assert list(self.node_settings.active_templates) == []

    def test_active_templates_filters_inactive(self):
        institution = InstitutionFactory()
        engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://workflow.example/api/',
            signing_kid='kid-test',
            institution=institution,
        )
        snapshot_active = WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id='definition-active',
            definition_key='definition-active',
            name='Active Process',
            version=1,
        )
        snapshot_inactive = WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id='definition-inactive',
            definition_key='definition-inactive',
            name='Inactive Process',
            version=1,
        )

        active_template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=snapshot_active,
            registered_by=self.user,
        )
        inactive_template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=snapshot_inactive,
            registered_by=self.user,
            is_active=False,
        )

        WorkflowActivation.objects.create(
            node=self.node,
            template=active_template,
            activated_by=self.user,
            is_enabled=True,
        )
        WorkflowActivation.objects.create(
            node=self.node,
            template=inactive_template,
            activated_by=self.user,
            is_enabled=False,
        )

        templates = list(self.node_settings.active_templates)
        assert templates == [active_template]

    def test_active_templates_raises_without_owner(self):
        ownerless_settings = NodeSettings()
        with pytest.raises(RuntimeError):
            list(ownerless_settings.active_templates)

    def test_on_add_auto_activates_templates_for_contributors(self):
        other = AuthUserFactory()
        self.node.add_contributor(other, permissions='write', auth=self.auth, save=True)

        institution = InstitutionFactory()
        engine = WorkflowEngine.objects.create(
            engine_id=str(uuid.uuid4()),
            gateway_base_url='https://workflow.example/api/',
            signing_kid='kid-test',
            institution=institution,
        )
        snapshot = WorkflowDefinitionSnapshot.objects.create(
            engine=engine,
            definition_id='definition-auto',
            definition_key='definition-auto',
            name='Auto Process',
            version=1,
        )
        template = WorkflowTemplate.objects.create(
            node=self.node,
            definition=snapshot,
            registered_by=self.user,
            auto_activate=True,
        )

        with mock.patch('addons.workflow.services.get_user_accessible_templates', return_value=[template]):
            with mock.patch('addons.workflow.services.activate_workflow_activation') as mock_activate:
                self.node_settings.on_add()

        activation = WorkflowActivation.objects.get(node=self.node, template=template)
        assert activation.is_enabled is True
        mock_activate.assert_called_once_with(activation, self.user)

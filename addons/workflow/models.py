# -*- coding: utf-8 -*-
"""Database models for the workflow addon."""

from django.apps import apps
from django.db import models
from django.utils import timezone

from addons.base.models import BaseNodeSettings
from addons.workflow.token import validate_delegation_tokens, validate_token_settings
from osf.models.base import BaseModel
from osf.utils.datetime_aware_jsonfield import DateTimeAwareJSONField
from osf.utils.fields import EncryptedTextField, NonNaiveDateTimeField


class NodeSettings(BaseNodeSettings):
    """Node-level settings for the workflow addon."""

    @property
    def complete(self) -> bool:
        # Workflow add-on is considered configured once installed; templates are optional per use-case.
        return True

    @property
    def active_templates(self):
        template_model = apps.get_model('addons_workflow', 'WorkflowTemplate')
        if not self.owner_id:
            raise RuntimeError('Workflow addon settings must have an owner before querying templates.')
        return template_model.objects.filter(
            activations__node=self.owner,
            activations__is_enabled=True,
        )

    def on_add(self):
        """Auto-activate templates when workflow addon is enabled."""
        from addons.workflow.services import activate_workflow_activation, get_user_accessible_templates

        node = self.owner
        if not node:
            return

        contributors = list(node.contributors.all())
        if not contributors:
            return

        seen_template_ids = set()
        for user in contributors:
            auto_activate_templates = get_user_accessible_templates(
                user,
                is_active=True,
                auto_activate=True,
            )

            for template in auto_activate_templates:
                if template.id in seen_template_ids:
                    continue
                if not template.is_effectively_active:
                    continue
                seen_template_ids.add(template.id)

                activation, created = WorkflowActivation.objects.get_or_create(
                    node=node,
                    template=template,
                    defaults={
                        'activated_by': user,
                        'is_enabled': True,
                    },
                )
                if created or not activation.is_enabled:
                    activate_workflow_activation(activation, user)


class WorkflowEngine(BaseModel):
    """Configuration for a workflow gateway/engine pair."""

    engine_id = models.CharField(max_length=255, primary_key=True)
    label = models.CharField(max_length=255, default='')
    gateway_base_url = models.URLField()
    signing_kid = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        'osf.OSFUser',
        on_delete=models.PROTECT,
        related_name='workflow_engines',
        null=True,
        blank=True,
    )
    institution = models.ForeignKey(
        'osf.Institution',
        on_delete=models.PROTECT,
        related_name='workflow_engines',
    )
    verify_ssl = models.BooleanField(default=True)
    token_subject = models.CharField(max_length=255, default='rdm-workflow-service', blank=True)
    token_scope = models.CharField(max_length=255, default='workflow::delegate', blank=True)
    token_audience = models.CharField(max_length=255, blank=True, null=True)
    upload_whitelist_node_ids = DateTimeAwareJSONField(default=list, blank=True)
    token_issuer = models.CharField(max_length=255, blank=True, null=True)
    engine_claim = models.CharField(max_length=255, default='engine_id', blank=True)
    engine_claim_value = models.CharField(max_length=255, blank=True, null=True)
    token_lifetime_seconds = models.PositiveIntegerField(default=300)
    request_timeout = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    keyset_url = models.URLField(blank=True)

    class Meta:
        ordering = ('engine_id',)

    def __str__(self) -> str:  # pragma: no cover
        return f'WorkflowEngine(engine_id={self.engine_id})'

    @property
    def resolved_engine_claim_value(self) -> str:
        return self.engine_claim_value or self.engine_id

class WorkflowEngineKey(BaseModel):
    """Public key material registered for a workflow engine/gateway."""

    id = models.AutoField(primary_key=True)
    engine_id = models.CharField(max_length=255, db_index=True)
    kid = models.CharField(max_length=255)
    algorithm = models.CharField(max_length=32)
    public_key = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('engine_id', 'kid')
        ordering = ('engine_id', 'kid')

    def __str__(self) -> str:  # pragma: no cover
        return f'WorkflowEngineKey(engine_id={self.engine_id}, kid={self.kid})'


class WorkflowDefinitionSnapshot(BaseModel):
    """Materialized metadata for a workflow process definition fetched from an engine."""

    engine = models.ForeignKey(
        'addons_workflow.WorkflowEngine',
        on_delete=models.PROTECT,
        related_name='definition_snapshots',
    )
    definition_id = models.CharField(max_length=255)
    definition_key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    version = models.PositiveIntegerField()
    category = models.CharField(max_length=255, blank=True)
    deployment_id = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    form_schema = DateTimeAwareJSONField(default=dict, blank=True)
    definition_metadata = DateTimeAwareJSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('engine', 'definition_id')
        ordering = ('engine__engine_id', 'definition_key', 'version')

    def __str__(self) -> str:  # pragma: no cover
        engine_id = self.engine.engine_id if self.engine_id else 'unknown'
        return f'WorkflowDefinitionSnapshot(engine={engine_id}, definition_id={self.definition_id})'


class WorkflowTemplate(BaseModel):
    """Association between an RDM project and a workflow definition."""

    VISIBILITY_PROJECT = 'project'
    VISIBILITY_INSTITUTION = 'institution'
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_CHOICES = (
        (VISIBILITY_PROJECT, 'project'),
        (VISIBILITY_INSTITUTION, 'institution'),
        (VISIBILITY_PUBLIC, 'public'),
    )

    node = models.ForeignKey(
        'osf.AbstractNode',
        on_delete=models.CASCADE,
        related_name='workflow_templates',
    )
    definition = models.ForeignKey(
        'addons_workflow.WorkflowDefinitionSnapshot',
        on_delete=models.PROTECT,
        related_name='templates',
    )
    registered_by = models.ForeignKey(
        'osf.OSFUser',
        on_delete=models.PROTECT,
        related_name='workflow_templates',
    )
    label = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    token_settings = DateTimeAwareJSONField(default=dict, blank=True)
    delegation_tokens = DateTimeAwareJSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    auto_activate = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=32,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_PROJECT,
    )

    class Meta:
        unique_together = ('node', 'definition')
        ordering = ('node', 'definition__definition_key')

    def __str__(self) -> str:  # pragma: no cover
        definition_id = self.definition.definition_id if self.definition_id else 'unknown'
        return f'WorkflowTemplate(node={self.node_id}, definition={definition_id})'

    @property
    def _id(self) -> str:
        return str(self.id) if self.id is not None else ''

    @classmethod
    def load(cls, identifier):
        if isinstance(identifier, int):
            pk = identifier
        elif isinstance(identifier, str):
            if identifier.isdigit():
                pk = int(identifier)
            else:
                raise ValueError('WorkflowTemplate identifier must be a base-10 integer string')
        else:
            raise TypeError('WorkflowTemplate identifier must be an int or numeric string')
        try:
            return cls.objects.get(pk=pk)
        except cls.DoesNotExist:
            return None

    @property
    def engine_id(self) -> str:
        if not self.definition_id:
            return ''
        return self.definition.engine.engine_id

    @property
    def process_definition_id(self) -> str:
        if not self.definition_id:
            return ''
        return self.definition.definition_id

    @property
    def definition_key(self) -> str:
        if not self.definition_id:
            return ''
        return self.definition.definition_key

    @property
    def definition_name(self) -> str:
        if not self.definition_id:
            return ''
        return self.definition.name

    @property
    def definition_version(self) -> int:
        if not self.definition_id:
            return 0
        return self.definition.version

    @property
    def definition_category(self) -> str:
        if not self.definition_id:
            return ''
        return self.definition.category

    @property
    def definition_deployment_id(self) -> str:
        if not self.definition_id:
            return ''
        return self.definition.deployment_id

    @property
    def definition_description(self) -> str:
        return self.definition.description

    @property
    def definition_form_schema(self):
        return self.definition.form_schema

    @property
    def definition_metadata(self):
        return self.definition.definition_metadata

    @property
    def is_effectively_active(self) -> bool:
        return self.is_active and self.definition.engine.is_active

    def get_validated_token_settings(self):
        return validate_token_settings(self.token_settings)

    def get_validated_delegation_tokens(self):
        return validate_delegation_tokens(self.delegation_tokens)


class WorkflowActivation(BaseModel):
    """Enablement of a shared workflow template on a specific project."""

    node = models.ForeignKey(
        'osf.AbstractNode',
        on_delete=models.CASCADE,
        related_name='workflow_activations',
    )
    template = models.ForeignKey(
        'addons_workflow.WorkflowTemplate',
        on_delete=models.CASCADE,
        related_name='activations',
    )
    activated_by = models.ForeignKey(
        'osf.OSFUser',
        on_delete=models.PROTECT,
        related_name='workflow_activations',
    )
    delegation_tokens = DateTimeAwareJSONField(default=dict, blank=True)
    is_enabled = models.BooleanField(default=True)
    is_dismissed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('node', 'template')
        ordering = ('node', 'template')

    @property
    def _id(self) -> str:
        return str(self.id) if self.id is not None else ''

    @property
    def is_effectively_active(self) -> bool:
        return self.is_enabled and self.template.is_effectively_active

    def __str__(self) -> str:  # pragma: no cover
        return f'WorkflowActivation(node={self.node_id}, template={self.template_id})'

    def get_validated_delegation_tokens(self):
        return validate_delegation_tokens(self.delegation_tokens)


class WorkflowExecutorToken(BaseModel):
    """Per-user executor token for workflow activations.

    Each user who starts a workflow on an activation gets their own executor token.
    Tokens are reused across multiple runs by the same user on the same activation.
    """

    activation = models.ForeignKey(
        'addons_workflow.WorkflowActivation',
        on_delete=models.CASCADE,
        related_name='executor_tokens',
    )
    user = models.ForeignKey(
        'osf.OSFUser',
        on_delete=models.CASCADE,
        related_name='workflow_executor_tokens',
    )
    token_id = models.CharField(max_length=255)
    token_value = EncryptedTextField()
    created_at = NonNaiveDateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('activation', 'user')
        ordering = ('activation', 'user')

    def __str__(self) -> str:  # pragma: no cover
        return f'WorkflowExecutorToken(activation={self.activation_id}, user={self.user_id})'

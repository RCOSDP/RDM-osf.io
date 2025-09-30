# -*- coding: utf-8 -*-
import logging

from framework.celery_tasks import app as celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0)
def start_workflow_process_async(
    self, node_id, template_id, activation_id, started_by_id,
    business_key=None, label=None, variables=None,
):
    from osf.models import AbstractNode, OSFUser
    from addons.workflow.models import WorkflowTemplate, WorkflowActivation
    from addons.workflow.services import start_workflow_process

    node = AbstractNode.load(node_id)
    template = WorkflowTemplate.objects.get(id=template_id)
    activation = WorkflowActivation.objects.get(id=activation_id)
    started_by = OSFUser.load(started_by_id)

    return start_workflow_process(
        node,
        template=template,
        activation=activation,
        started_by=started_by,
        business_key=business_key,
        label=label,
        variables=variables,
    )


@celery_app.task(bind=True, max_retries=0)
def submit_task_action_async(
    self, node_id, task_id, user_id, engine_id, action,
    variables=None, assignee=None,
):
    from osf.models import AbstractNode, OSFUser
    from addons.workflow.services import submit_workflow_task_action

    node = AbstractNode.load(node_id)
    user = OSFUser.load(user_id)

    return submit_workflow_task_action(
        node, task_id, user,
        engine_id=engine_id,
        action=action,
        variables=variables,
        assignee=assignee,
    )

# -*- coding: utf-8 -*-
"""Utility helpers for the workflow add-on."""

from addons.workflow.apps import WorkflowAddonAppConfig


def serialize_workflow_widget(node):
    """Return widget metadata for rendering the workflow dashboard panel."""

    workflow = node.get_addon(WorkflowAddonAppConfig.short_name)
    if workflow is None:
        return {
            'complete': False,
            'include': False,
            'can_expand': True,
        }

    ret = {
        'complete': True,
        'include': False,
        'can_expand': True,
    }
    ret.update(workflow.config.to_json())
    return ret

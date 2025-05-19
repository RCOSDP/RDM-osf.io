# -*- coding: utf-8 -*-

# widget: ここから
def serialize_workflow_widget(node):
    workflow = node.get_addon('workflow')
    ret = {
        'complete': True
    }
    ret.update(workflow.config.to_json())
    return ret
# widget: ここまで

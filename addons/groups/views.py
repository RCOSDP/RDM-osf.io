from . import SHORT_NAME
from framework.auth.decorators import must_be_logged_in
from website.project.decorators import (
    must_be_valid_project,
    must_have_addon,
    must_have_permission
)
from osf.utils.permissions import READ


def _response_config(addon):
    return {
        'data': {
            'type': 'groups-config',
            'attributes': {}
        }
    }

@must_be_valid_project
@must_be_logged_in
@must_have_permission(READ)
@must_have_addon(SHORT_NAME, 'node')
def groups_get_config(auth, **kwargs):
    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    return _response_config(addon)

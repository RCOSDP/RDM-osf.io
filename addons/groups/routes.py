"""
Routes associated with the groups addon
"""

from framework.routing import Rule, json_renderer
from . import SHORT_NAME
from . import views


TEMPLATE_DIR = './addons/groups/templates/'

api_routes = {
    'rules': [
        Rule([
            '/project/<pid>/{}/settings/'.format(SHORT_NAME),
            '/project/<pid>/node/<nid>/{}/settings/'.format(SHORT_NAME),
        ], 'get', views.groups_get_config, json_renderer),
    ],
    'prefix': '/api/v1',
}

page_routes = {
    'rules': []
}

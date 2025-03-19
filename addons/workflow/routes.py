# -*- coding: utf-8 -*-
from framework.routing import Rule, json_renderer
from website.routes import notemplate
from . import SHORT_NAME
from . import views

# HTML endpoints
page_routes = {
    'rules': [
        # Home (Base) | GET
        Rule(
            [
                '/<pid>/{}'.format(SHORT_NAME),
                '/<pid>/node/<nid>/{}'.format(SHORT_NAME),
            ],
            'get',
            views.project_workflow,
            notemplate
        ),

    ]
}

# JSON endpoints
api_routes = {
    'rules': [
        Rule([
            '/project/<pid>/{}/settings'.format(SHORT_NAME),
            '/project/<pid>/node/<nid>/{}/settings'.format(SHORT_NAME),
        ], 'get', views.workflow_get_config, json_renderer),
        Rule([
            '/project/<pid>/{}/settings'.format(SHORT_NAME),
            '/project/<pid>/node/<nid>/{}/settings'.format(SHORT_NAME),
        ], 'put', views.workflow_set_config, json_renderer),

        Rule([
            '/project/<pid>/{}/config'.format(SHORT_NAME),
            '/project/<pid>/node/<nid>/{}/config'.format(SHORT_NAME),
        ], 'get', views.workflow_get_config_ember, json_renderer),
        Rule([
            '/project/<pid>/{}/config'.format(SHORT_NAME),
            '/project/<pid>/node/<nid>/{}/config'.format(SHORT_NAME),
        ], 'patch', views.workflow_set_config_ember, json_renderer),
        Rule([
            '/project/<pid>/{}/register_workflow'.format(SHORT_NAME),
        ], 'post', views.register_workflow_data, json_renderer),
        Rule([
            '/addons/workflow/registered_workflows/',
        ], 'get', views.get_registered_workflows, json_renderer),
        Rule([
            '/addons/workflow/all_registered_workflows/',
        ], 'get', views.get_all_registered_workflows, json_renderer),
        Rule([
            '/project/<pid>/{}/register_workflow/<workflow_id>'.format(SHORT_NAME),
        ], 'patch', views.update_workflow_data, json_renderer),
        Rule([
            '/project/<pid>/{}/remove_workflow/<workflow_id>'.format(SHORT_NAME),
        ], 'delete', views.remove_workflow_data, json_renderer),

        Rule([
            '/project/<pid>/{}/workflow_connection'.format(SHORT_NAME),
        ], 'get', views.workflow_connection, json_renderer),
        Rule([
            '/addons/workflow/start_workflow/',
        ], 'post', views.start_workflow_data, json_renderer),
    ],
    'prefix': '/api/v1',
}

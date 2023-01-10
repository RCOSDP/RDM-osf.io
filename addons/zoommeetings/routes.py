# -*- coding: utf-8 -*-
"""Routes for the zoommeetings addon.
"""

from framework.routing import Rule, json_renderer
from addons.zoommeetings import views

# JSON endpoints
api_routes = {
    'rules': [

        Rule(
            '/oauth/connect/zoommeetings',
            'post',
            views.zoommeetings_oauth_connect,
            json_renderer,
        ),

        Rule(
            [
                '/settings/zoommeetings/accounts/',
            ],
            'get',
            views.zoommeetings_account_list,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/zoommeetings/settings/',
                '/project/<pid>/node/<nid>/zoommeetings/settings/'
            ],
            'get',
            views.zoommeetings_get_config,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/zoommeetings/user_auth/',
                '/project/<pid>/node/<nid>/zoommeetings/user_auth/'
            ],
            'put',
            views.zoommeetings_import_auth,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/zoommeetings/user_auth/',
                '/project/<pid>/node/<nid>/zoommeetings/user_auth/'
            ],
            'delete',
            views.zoommeetings_deauthorize_node,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/zoommeetings/request_api',
                '/project/<pid>/node/<nid>/zoommeetings/request_api',
            ],
            'post',
            views.zoommeetings_request_api,
            json_renderer,
        ),

    ],
    'prefix': '/api/v1'
}

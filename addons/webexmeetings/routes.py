# -*- coding: utf-8 -*-
"""Routes for the webexmeetings addon.
"""

from framework.routing import Rule, json_renderer
from addons.webexmeetings import views

# JSON endpoints
api_routes = {
    'rules': [

        Rule(
            '/oauth/connect/webexmeetings',
            'post',
            views.webexmeetings_oauth_connect,
            json_renderer,
        ),

        Rule(
            [
                '/settings/webexmeetings/accounts/',
            ],
            'get',
            views.webexmeetings_account_list,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/webexmeetings/settings/',
                '/project/<pid>/node/<nid>/webexmeetings/settings/'
            ],
            'get',
            views.webexmeetings_get_config,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/webexmeetings/user_auth/',
                '/project/<pid>/node/<nid>/webexmeetings/user_auth/'
            ],
            'put',
            views.webexmeetings_import_auth,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/webexmeetings/user_auth/',
                '/project/<pid>/node/<nid>/webexmeetings/user_auth/'
            ],
            'delete',
            views.webexmeetings_deauthorize_node,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/webexmeetings/request_api',
                '/project/<pid>/node/<nid>/webexmeetings/request_api',
            ],
            'post',
            views.webexmeetings_request_api,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/webexmeetings/register_email',
                '/project/<pid>/node/<nid>/webexmeetings/register_email',
            ],
            'post',
            views.webexmeetings_register_email,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/webexmeetings/register_contributors_email',
                '/project/<pid>/node/<nid>/webexmeetings/register_contributors_email',
            ],
            'post',
            views.webexmeetings_register_contributors_email,
            json_renderer,
        ),

    ],
    'prefix': '/api/v1'
}

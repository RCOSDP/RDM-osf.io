# -*- coding: utf-8 -*-
"""Routes for the microsoftteams addon.
"""

from framework.routing import Rule, json_renderer
from addons.microsoftteams import views

# JSON endpoints
api_routes = {
    'rules': [

        Rule(
            '/oauth/connect/microsoftteams',
            'post',
            views.microsoftteams_oauth_connect,
            json_renderer,
        ),

        Rule(
            [
                '/settings/microsoftteams/accounts/',
            ],
            'get',
            views.microsoftteams_account_list,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/microsoftteams/settings/',
                '/project/<pid>/node/<nid>/microsoftteams/settings/'
            ],
            'get',
            views.microsoftteams_get_config,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/microsoftteams/user_auth/',
                '/project/<pid>/node/<nid>/microsoftteams/user_auth/'
            ],
            'put',
            views.microsoftteams_import_auth,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/microsoftteams/user_auth/',
                '/project/<pid>/node/<nid>/microsoftteams/user_auth/'
            ],
            'delete',
            views.microsoftteams_deauthorize_node,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/microsoftteams/request_api',
                '/project/<pid>/node/<nid>/microsoftteams/request_api',
            ],
            'post',
            views.microsoftteams_request_api,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/microsoftteams/register_email',
                '/project/<pid>/node/<nid>/microsoftteams/register_email',
            ],
            'post',
            views.microsoftteams_register_email,
            json_renderer,
        ),

        Rule(
            [
                '/project/<pid>/microsoftteams/register_contributors_email',
                '/project/<pid>/node/<nid>/microsoftteams/register_contributors_email',
            ],
            'post',
            views.microsoftteams_register_contributors_email,
            json_renderer,
        ),

    ],
    'prefix': '/api/v1'
}

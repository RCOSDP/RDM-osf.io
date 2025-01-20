from framework.routing import Rule, json_renderer

from . import views

api_routes = {
    'rules': [
        Rule(
            '/settings/datasteward/',
            'get',
            views.datasteward_user_config_get,
            json_renderer,
        ),
        Rule(
            '/settings/datasteward/',
            'post',
            views.datasteward_user_config_post,
            json_renderer,
        ),
    ],
    'prefix': '/api/v1'
}

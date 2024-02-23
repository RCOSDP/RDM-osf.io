from framework.routing import Rule, json_renderer
from website.routes import OsfWebRenderer

from .apps import SHORT_NAME
from . import views


oauth_routes = {
    'rules': [
        Rule(
            '/connect/weko/<repoid>/',
            'get',
            views.weko_oauth_connect,
            json_renderer,
        ),
        Rule(
            '/callback/weko/<repoid>/',
            'get',
            views.weko_oauth_callback,
            OsfWebRenderer('util/oauth_complete.mako', trust=False),
        ),
    ],
    'prefix': '/oauth'
}

api_routes = {
    'rules': [
        Rule(
            '/settings/{}/'.format(SHORT_NAME),
            'get',
            views.weko_user_config_get,
            json_renderer,
        ),
        Rule(
            '/settings/{}/accounts/'.format(SHORT_NAME),
            'get',
            views.weko_account_list,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/settings/'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/settings/'.format(SHORT_NAME),
            ],
            'get',
            views.weko_get_config,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/settings/'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/settings/'.format(SHORT_NAME),
            ],
            'put',
            views.weko_set_config,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/user-auth/'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/user-auth/'.format(SHORT_NAME),
            ],
            'put',
            views.weko_import_auth,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/user-auth/'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/user-auth/'.format(SHORT_NAME),
            ],
            'delete',
            views.weko_deauthorize_node,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/hgrid/root/'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/hgrid/root/'.format(SHORT_NAME),
            ],
            'get',
            views.weko_root_folder,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/metadata'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/metadata'.format(SHORT_NAME),
            ],
            'get',
            views.weko_get_file_metadata,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/schemas/'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/schemas/'.format(SHORT_NAME),
            ],
            'get',
            views.weko_get_available_schemas,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/index/<index_id>/files/<mnode>/<path:filepath>'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/index/<index_id>/files/<mnode>/<path:filepath>'.format(SHORT_NAME),
            ],
            'put',
            views.weko_publish_file,
            json_renderer,
        ),
        Rule(
            [
                '/project/<pid>/{}/index/<index_id>/files/<mnode>/<path:filepath>'.format(SHORT_NAME),
                '/project/<pid>/node/<nid>/{}/index/<index_id>/files/<mnode>/<path:filepath>'.format(SHORT_NAME),
            ],
            'get',
            views.weko_get_publishing_file,
            json_renderer,
        ),
    ],
    'prefix': '/api/v1'
}

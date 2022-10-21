# -*- coding: utf-8 -*-
"""Routes for the rushfiles addon.
"""

from framework.routing import Rule, json_renderer

from . import views

# JSON endpoints
api_routes = {
    'rules': [

        #### Profile settings ###

        Rule(
            [
                '/settings/rushfiles/accounts/',
            ],
            'get',
            views.rushfiles_account_list,
            json_renderer,

        ),

        ##### Node settings #####

        Rule(
            ['/project/<pid>/rushfiles/folders/',
             '/project/<pid>/node/<nid>/rushfiles/folders/'],
            'get',
            views.rushfiles_folder_list,
            json_renderer
        ),

        Rule(
            ['/project/<pid>/rushfiles/config/',
             '/project/<pid>/node/<nid>/rushfiles/config/'],
            'get',
            views.rushfiles_get_config,
            json_renderer
        ),

        Rule(
            ['/project/<pid>/rushfiles/config/',
             '/project/<pid>/node/<nid>/rushfiles/config/'],
            'put',
            views.rushfiles_set_config,
            json_renderer
        ),

        Rule(
            ['/project/<pid>/rushfiles/config/',
             '/project/<pid>/node/<nid>/rushfiles/config/'],
            'delete',
            views.rushfiles_deauthorize_node,
            json_renderer
        ),

        Rule(
            ['/project/<pid>/rushfiles/config/import-auth/',
             '/project/<pid>/node/<nid>/rushfiles/config/import-auth/'],
            'put',
            views.rushfiles_import_auth,
            json_renderer
        ),
    ],
    'prefix': '/api/v1'
}

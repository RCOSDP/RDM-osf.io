from framework.routing import Rule, json_renderer
from website.routes import OsfWebRenderer
from . import views

TEMPLATE_DIR = './addons/onlyoffice/templates'

edit_routes = {
    # Edit by ONLYOFFICE
    'rules': [
        Rule(['/<guid>/editonlyoffice/<file_id_ver>'], 'get',
        views.onlyoffice_edit_by_onlyoffice,
        OsfWebRenderer('edit_online.mako', trust=True, template_dir=TEMPLATE_DIR),)
    ]
}

wopi_routes = {
    # WOPI
    'rules': [
        Rule(['/files/<file_id_ver>'], 'get', views.onlyoffice_check_file_info, json_renderer,),
        Rule(['/files/<file_id_ver>'], 'post', views.onlyoffice_lock_file, json_renderer,),
        Rule(['/files/<file_id_ver>/contents'], ['get', 'post'], views.onlyoffice_file_content_view, json_renderer,),
    ],
    'prefix': '/wopi',
}
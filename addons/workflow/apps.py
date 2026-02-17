import os

from addons.base.apps import BaseAddonAppConfig


HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, 'templates')


class WorkflowAddonAppConfig(BaseAddonAppConfig):
    name = 'addons.workflow'
    label = 'addons_workflow'
    full_name = 'Workflow'
    short_name = 'workflow'
    configs = ['node']
    owners = ['node']
    categories = ['workflow']
    views = ['widget', 'page']
    user_settings_template = None
    node_settings_template = os.path.join(TEMPLATE_PATH, 'workflow_node_settings.mako')

    include_js = {}
    include_css = {
        'widget': [],
        'page': [],
    }

    has_page_icon = False

    @property
    def routes(self):
        from . import routes
        return [routes.page_routes, routes.api_routes]

    @property
    def node_settings(self):
        return self.get_model('NodeSettings')

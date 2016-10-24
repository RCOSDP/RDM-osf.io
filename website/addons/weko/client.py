import httplib as http
import logging
import requests
from StringIO import StringIO

from lxml import etree
from dataverse import Connection
from dataverse.exceptions import ConnectionError, UnauthorizedError, OperationFailedError

from framework.exceptions import HTTPError

from website.addons.weko import settings

logger = logging.getLogger('addons.weko.client')

APP_NAMESPACE = 'http://www.w3.org/2007/app'
ATOM_NAMESPACE = 'http://www.w3.org/2005/Atom'

class Connection(object):
    host = None
    token = None

    def __init__(self, host, token):
        self.host = host
        self.token = token

    def get(self, path):
        headers = {"Authorization":"Bearer " + self.token}
        resp = requests.get(self.host + path, headers=headers)
        if resp.status_code != 200:
            resp.raise_for_status()
        tree = etree.parse(StringIO(resp.content))
        logger.info('Connected: {}'.format(etree.tostring(tree)))
        return tree

def _connect(host, token):
    try:
        return Connection(host, token)
    except ConnectionError:
        return None


def connect_from_settings(node_settings):
    if not (node_settings and node_settings.external_account):
        return None

    host = 'http://104.198.102.120/weko-oauth/htdocs/weko/sword/'
    token = node_settings.external_account.oauth_key

    try:
        return Connection(host, token)
    except UnauthorizedError:
        return None


def connect_or_error(host, token):
    try:
        connection = _connect(host, token)
        if not connection:
            raise HTTPError(http.SERVICE_UNAVAILABLE)
        return connection
    except UnauthorizedError:
        raise HTTPError(http.UNAUTHORIZED)


def connect_from_settings_or_401(node_settings):
    if not (node_settings and node_settings.external_account):
        return None

    host = 'http://104.198.102.120/weko-oauth/htdocs/weko/sword/'
    token = node_settings.external_account.oauth_key

    return connect_or_error(host, token)


def get_files(dataset, published=False):
    version = 'latest-published' if published else 'latest'
    return dataset.get_files(version)


def get_datasets(weko):
    if weko is None:
        return []
    connection, title = weko
    root = connection.get('servicedocument.php')
    datasets = []
    for workspace in root.findall('.//{%s}workspace' % APP_NAMESPACE):
        if title == workspace.find('{%s}title' % ATOM_NAMESPACE).text:
            for collection in workspace.findall('{%s}collection' % APP_NAMESPACE):
                dtitle = collection.find('{%s}title' % ATOM_NAMESPACE).text
                dhref = collection.attrib['href']
                datasets.append({'title': dtitle, 'href': dhref})

    return datasets


def get_dataset(weko, href):
    if weko is None:
        return
    connection, title = weko
    root = connection.get('servicedocument.php')
    datasets = []
    for workspace in root.findall('.//{%s}workspace' % APP_NAMESPACE):
        if title == workspace.find('{%s}title' % ATOM_NAMESPACE).text:
            for collection in workspace.findall('{%s}collection' % APP_NAMESPACE):
                dtitle = collection.find('{%s}title' % ATOM_NAMESPACE).text
                dhref = collection.attrib['href']
                if dhref == href:
                    return {'title': dtitle, 'href': dhref}
    return None


def get_wekos(connection):
    if connection is None:
        return []
    root = connection.get('servicedocument.php')
    wekos = []
    for workspace in root.findall('.//{%s}workspace' % APP_NAMESPACE):
        title = workspace.find('{%s}title' % ATOM_NAMESPACE).text
        logger.info('title: {}'.format(title))
        wekos.append({'title': title, 'alias': title})
    return wekos


def get_weko(connection, alias):
    if connection is None:
        return
    return (connection, alias)

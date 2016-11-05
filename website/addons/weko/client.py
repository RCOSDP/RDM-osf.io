import logging
import requests
from io import BytesIO
from lxml import etree
import base64
from datetime import datetime

logger = logging.getLogger('addons.weko.client')

APP_NAMESPACE = 'http://www.w3.org/2007/app'
ATOM_NAMESPACE = 'http://www.w3.org/2005/Atom'
RDF_NAMESPACE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
DC_NAMESPACE = 'http://purl.org/metadata/dublin_core#'

class Index(object):
    raw = None
    parentIdentifier = None

    def __init__(self, desc):
        self.raw = {'title': desc.find('{%s}title' % DC_NAMESPACE).text,
                    'id': desc.find('{%s}identifier' % DC_NAMESPACE).text,
                    'about': desc.attrib['{%s}about' % RDF_NAMESPACE]}

    @property
    def nested(self):
        title = self.raw['title']
        nested = 0
        while title.startswith('--'):
            nested += 1
            title = title[2:]
        return nested

    @property
    def title(self):
        return self.raw['title'][self.nested * 2:]

    @property
    def identifier(self):
        return self.raw['id']

    @property
    def about(self):
        return self.raw['about']

class Item(object):
    raw = None
    parentIdentifier = None

    def __init__(self, entry):
        self.raw = {'id': entry.find('{%s}id' % ATOM_NAMESPACE).text.strip(),
                    'title': entry.find('{%s}title' % ATOM_NAMESPACE).text,
                    'updated': entry.find('{%s}updated' % ATOM_NAMESPACE).text}

    @property
    def about(self):
        return self.raw['id']

    @property
    def file_id(self):
        return 'item{}'.format(itemId(self.raw['id']))

    @property
    def title(self):
        return self.raw['title']

    @property
    def author(self):
        return self.raw['author']

    @property
    def updated(self):
        return self.raw['updated']


class Connection(object):
    host = None
    token = None

    def __init__(self, host, token):
        self.host = host
        self.token = token

    def get_login_user(self, default_user=None):
        headers = {"Authorization":"Bearer " + self.token}
        resp = requests.get(self.host + 'servicedocument.php', headers=headers)
        if resp.status_code != 200:
            resp.raise_for_status()
        return resp.headers.get('X-WEKO-Login-User', default_user)

    def get(self, path):
        headers = {"Authorization":"Bearer " + self.token}
        resp = requests.get(self.host + path, headers=headers)
        if resp.status_code != 200:
            resp.raise_for_status()
        tree = etree.parse(BytesIO(resp.content))
        return tree

    def get_url(self, url):
        headers = {"Authorization":"Bearer " + self.token}
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            resp.raise_for_status()
        tree = etree.parse(BytesIO(resp.content))
        return tree

    def delete_url(self, url):
        headers = {"Authorization":"Bearer " + self.token}
        resp = requests.delete(url, headers=headers)
        if resp.status_code != 200:
            resp.raise_for_status()

    def post_url(self, url, stream, headers={}):
        headers = headers.copy()
        headers["Authorization"] = "Bearer " + self.token
        resp = requests.post(url, headers=headers, data=stream)
        if resp.status_code != 200:
            resp.raise_for_status()
        tree = etree.parse(BytesIO(resp.content))
        return tree


def itemId(url, default_value=None):
    query = parse_qs(urlparse(url).query)
    if 'item_id' in query:
        return query['item_id'][0]
    elif 'itemId' in query:
        return query['itemId'][0]
    else:
        logger.warn('Unexpected Query: {}'.format(str(query)))
        return default_value

def _connect(host, token):
    try:
        return Connection(host, token)
    except ConnectionError:
        return None


def connect_from_settings(weko_settings, node_settings):
    if not (node_settings and node_settings.external_account):
        return None

    host = weko_settings.REPOSITORIES[node_settings.external_account.provider_id.split('@')[-1]]['host']
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


def connect_from_settings_or_401(weko_settings, node_settings):
    if not (node_settings and node_settings.external_account):
        return None

    host = weko_settings.REPOSITORIES[node_settings.external_account.provider_id.split('@')[-1]]['host']
    token = node_settings.external_account.oauth_key

    return connect_or_error(host, token)


def get_all_indices(connection, dataset=None):
    root = connection.get('servicedocument.php')
    indices = []
    for desc in root.findall('.//{%s}Description' % RDF_NAMESPACE):
        indices.append(Index(desc))

    ids = []
    for index in indices:
        if index.nested > 0:
            index.parentIdentifier = ids[index.nested - 1]

        if len(ids) == index.nested + 1:
            ids[index.nested] = index.identifier
        elif len(ids) > index.nested + 1:
            ids = ids[0:index.nested + 1]
            ids[index.nested] = index.identifier
        else:
            ids.append(index.identifier)
    return indices


def get_index_by_id(connection, index_id):
    return list(filter(lambda i: i.identifier == index_id, get_all_indices(connection)))[0]

def get_items(connection, index):
    root = connection.get_url(index.about)
    items = []
    for entry in root.findall('.//atom.entry'):
        logger.info('Name: {}'.format(entry.find('{%s}title' % ATOM_NAMESPACE).text))
        items.append(Item(entry))
    return items

def get_serviceitemtype(connection):
    root = connection.get('serviceitemtype.php')
    logger.info('Serviceitemtype: {}'.format(etree.tostring(root)))
    r = {'metadata': [], 'item_type': []}
    for metadata in root.findall('metadata'):
        for k in filter(lambda k: k.startswith('columnname_'),
                        metadata.attrib.keys()):
            r['metadata'].append({'column_id': k[11:],
                                  'column_name': metadata.attrib[k]})
    for item_types_elem in root.findall('itemTypes'):
        for item_type_elem in item_types_elem.findall('itemType'):
            item_type = {'mapping_info': item_type_elem.attrib['mapping_info'],
                         'name': item_type_elem.find('name').text,
                         'basic_attributes': [],
                         'additional_attributes': []}
            basic_attributes_elem = item_type_elem.find('basicAttributes')
            if basic_attributes_elem is not None:
                for attr_elem in basic_attributes_elem:
                    columns = []
                    for k in filter(lambda k: k.startswith('columnname_'),
                                    attr_elem.attrib.keys()):
                        columns.append({'column_id': k[11:],
                                        'column_name': attr_elem.attrib[k]})
                    item_type['basic_attributes'].append({'type': attr_elem.tag,
                                                          'columns': columns})
            for additional_attr_elem in item_type_elem.findall('.//additionalAttribute'):
                columns = []
                additional_attr = {'name': additional_attr_elem.find('name').text}
                for k in additional_attr_elem.attrib.keys():
                    if k.startswith('columnname_'):
                        columns.append({'column_id': k[11:],
                                        'column_name': additional_attr_elem.attrib[k]})
                    else:
                        additional_attr[k] = additional_attr_elem.attrib[k]
                item_type['additional_attributes'].append(additional_attr)
            r['item_type'].append(item_type)
    return r

def delete(connection, url):
    connection.delete_url(url)

def post(connection, insert_index_id, stream, stream_size):
    root = connection.get('servicedocument.php')
    target = None
    for collection in root.findall('.//{%s}collection' % APP_NAMESPACE):
        target = collection.attrib['href']
    logger.info('Post: {} on {}'.format(insert_index_id, target))
    weko_headers = {
        "Content-Disposition": "filename=temp.zip",
        "Content-Type": "application/zip",
        "Packaging": "http://purl.org/net/sword/package/SimpleZip",
        "Content-Length": str(stream_size),
        "insert_index": str(insert_index_id)
    }
    resp = connection.post_url(target, stream, headers=weko_headers)
    logger.info(etree.tostring(resp))
    for index, elem in enumerate(resp.findall('.//{%s}content' % ATOM_NAMESPACE)):
        src = elem.attrib['src']
        logger.info(src)
        if 'message' in elem.attrib:
            logger.warn('{}: {}'.format(index + 1, elem.attrib['message']))
    return src


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

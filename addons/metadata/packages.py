import io
import logging
import os
import re
import shutil
import tempfile

from stream_unzip import stream_unzip
from rocrate.rocrate import ROCrate
from rest_framework import status as http_status
import requests

from api.nodes.serializers import NodeSerializer
from api.base.utils import waterbutler_api_url_for
from framework.celery_tasks import app as celery_app
from framework.exceptions import HTTPError
from osf.models import OSFUser, AbstractNode
from website.util import waterbutler
from website import settings as website_settings


logger = logging.getLogger(__name__)


class RequestWrapper(object):
    def __init__(self, auth):
        self.auth = auth

    @property
    def user(self):
        logger.info(f'USER: {self.auth.user}')
        return self.auth.user

    @property
    def method(self):
        return 'PUT'

    @property
    def GET(self):
        return {}

class WaterButlerClient(object):
    def __init__(self, user, node):
        self.cookie = user.get_or_create_cookie().decode()
        self.node = node

    def get_provider(self, name):
        response = requests.get(
            waterbutler_api_url_for(
                self.node._id, name, path='/', _internal=True, meta=''
            ),
            headers={'content-type': 'application/json'},
            cookies={website_settings.COOKIE_NAME: self.cookie}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def resolve_file_path(self, dest_path):
        f = self.get_file(dest_path)
        logger.info(f'Resolved: {dest_path} = {f}')
        if 'attributes' not in f:
            return dest_path
        return dest_path.split('/')[0] + f['attributes']['path']

    def upload_file(self, file, file_name, dest_path):
        path = self.resolve_file_path(dest_path)
        return waterbutler.upload_file(self.cookie, self.node._id, file, file_name, path)

    def create_folder(self, folder_name, dest_path):
        path = self.resolve_file_path(dest_path)
        waterbutler.create_folder(self.cookie, self.node._id, folder_name, path)

    def get_file(self, path):
        path_segments = path.split('/')
        folder = path_segments[-1] == ''
        if folder:
            path_segments = path_segments[:-1]
        if len(path_segments) == 1:
            return self.get_provider(path_segments[0])
        parent_file = self.get_file('/'.join(path_segments[:-1]) + '/')
        kind = 'folder' if folder else 'file'
        target_path = '/'.join(path_segments[1:])
        if folder:
            target_path += '/'
        logger.info(f'Parent: {parent_file}')
        parent_entities = parent_file['data'] if 'data' in parent_file else parent_file
        for e in parent_entities:
            logger.info(f'Logger: {target_path}, {e}')
            if 'attributes' not in e:
                continue
            attr = e['attributes']
            if 'kind' in attr and attr['kind'] != kind:
                continue
            if 'materialized' in attr and attr['materialized'] == f'/{target_path}':
                return e
        return None


def start_importing(auth, title):
    serializer = NodeSerializer(context={
        'request': RequestWrapper(auth),
    })
    node = serializer.create({
        'title': title,
        'category': 'project',
        'creator': auth.user,
    })
    return node

def _load_ro_crate(url, work_dir):
    resp = requests.get(url, stream=True)
    for file_name, _, unzipped_chunks in stream_unzip(resp.iter_content()):
        file_name = file_name.decode('utf8')
        logger.info(f'ZIP-CONTENT: {file_name}')
        if file_name != 'ro-crate-metadata.json':
            # Skip data
            for chunk in unzipped_chunks:
                pass
            continue
        json_path = os.path.join(work_dir, file_name)
        with open(json_path, 'wb') as f:
            for chunk in unzipped_chunks:
                f.write(chunk)
        return ROCrate(work_dir)
    raise IOError('No ro-crate-metadata.json')

def _extract_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        assert '@value' in value, value
        return value['@value']
    assert isinstance(value, list), value
    return _extract_value(value[0])

def _extract_title(crate):
    value = crate.get('#root').properties()['dc:title']
    return _extract_value(value)

def _extract_description(crate):
    value = crate.get('#root').properties()['datacite:description']
    return _extract_value(value)

def _ensure_node(node, crate):
    node.description = _extract_description(crate)
    node.save()

def _ensure_folders(wb, crate, path):
    assert path.startswith('./'), path
    folders = [e for e in crate.data_entities if e.type == 'Folder' and e.id.startswith(path) and re.match(r'^[^/]+\/$', e.id[len(path):])]
    for e in folders:
        props = e.properties()
        name = _extract_value(props['name'])
        if wb.get_file(f'{path[2:]}{name}/') is None:
            logger.info(f'Creating folder... {name}')
            wb.create_folder(name, path[2:])
        _ensure_folders(wb, crate, f'{path}{name}/')

@celery_app.task(bind=True, max_retries=3)
def import_project(self, url, user_id, node_id):
    user = OSFUser.load(user_id)
    node = AbstractNode.load(node_id)
    wb = WaterButlerClient(user, node)
    work_dir = tempfile.mkdtemp()
    logger.info(f'Importing: {url} -> {node_id}, {work_dir}')
    self.update_state(state='provisioning node', meta={
        'progress': 0,
        'user': user_id,
        'node': node_id,
    })
    try:
        crate = _load_ro_crate(url, work_dir)
        logger.info(f'RO-Crate loaded: {crate}')
        _ensure_node(node, crate)
        self.update_state(state='provisioning folders', meta={
            'progress': 10,
            'user': user_id,
            'node': node_id,
        })
        _ensure_folders(wb, crate, './osfstorage/')
        self.update_state(state='provisioning files', meta={
            'progress': 50,
            'user': user_id,
            'node': node_id,
        })
        resp = requests.get(url, stream=True)
        for file_name, file_size, unzipped_chunks in stream_unzip(resp.iter_content()):
            file_name = file_name.decode('utf8')
            if not file_name.startswith('osfstorage/'):
                # Skip data
                for _ in unzipped_chunks:
                    pass
                continue
            logger.info(f'Restoring... {file_name}')
            folder_name, file_name_ = os.path.split(file_name)
            # TBD Wrap iterator to adapt BufferedIOBase
            buf = io.BytesIO()
            for chunk in unzipped_chunks:
                buf.write(chunk)
            wb.upload_file(io.BytesIO(buf.getvalue()), file_name_, folder_name + '/')
        self.update_state(state='finished', meta={
            'progress': 100,
            'user': user_id,
            'node': node_id,
        })
        return {
            'user': user_id,
            'node': node_id,
            'crate': {
                'title': _extract_title(crate),
                'description': _extract_description(crate),
            },
        }
    finally:
        shutil.rmtree(work_dir)

def get_task_result(auth, task_id):
    result = celery_app.AsyncResult(task_id)
    if result.info is not None and auth.user._id != result.info['user']:
        raise HTTPError(http_status.HTTP_403_FORBIDDEN)
    info = {}
    info.update(result.info)
    if 'node' in result.info:
        node = AbstractNode.load(result.info['node'])
        info['node_url'] = node.web_url_for('view_project')
    return {
        'state': result.state,
        'info': info,
    }

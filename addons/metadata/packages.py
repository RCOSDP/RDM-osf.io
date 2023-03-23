from datetime import datetime
import io
import json
import logging
import os
import re
import shutil
import tempfile
from zipfile import ZipFile

import furl
from django.contrib.contenttypes.models import ContentType
from stream_unzip import stream_unzip
from rocrate.rocrate import ROCrate
from rocrate.model.person import Person
from rocrate.model.contextentity import ContextEntity
from rocrate.model.data_entity import DataEntity
from rest_framework import status as http_status
import requests
import zipfly

from api.nodes.serializers import NodeSerializer
from api.base.utils import waterbutler_api_url_for
from framework.celery_tasks import app as celery_app
from framework.exceptions import HTTPError
from osf.models import OSFUser, AbstractNode, Comment, BaseFileNode
from website.util import waterbutler
from website import settings as website_settings
from osf.models.metaschema import RegistrationSchema
from . import SHORT_NAME
from addons.weko import settings as weko_settings


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
        logger.debug(f'Resolved: {dest_path} = {f}')
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
        logger.debug(f'Parent: {parent_file}')
        parent_entities = parent_file['data'] if 'data' in parent_file else parent_file
        for e in parent_entities:
            logger.debug(f'Logger: {target_path}, {e}')
            if 'attributes' not in e:
                continue
            attr = e['attributes']
            if 'kind' in attr and attr['kind'] != kind:
                continue
            if 'materialized' in attr and attr['materialized'] == f'/{target_path}':
                return e
        return None

class WaterButlerObject(object):
    def __init__(self, resp, wb, provider):
        self.raw = resp
        self.wb = wb
        self.provider = provider
        self._children = {}

    def get_files(self, _internal=True):
        logger.debug(f'list files: {self.links}')
        url = furl.furl(website_settings.WATERBUTLER_INTERNAL_URL if _internal else website_settings.WATERBUTLER_URL)
        file_url = furl.furl(self.links['new_folder'])
        url.path = str(file_url.path)
        response = requests.get(
            url.url,
            headers={'content-type': 'application/json'},
            cookies={website_settings.COOKIE_NAME: self.wb.cookie}
        )
        response.raise_for_status()
        return [WaterButlerObject(f, self.wb, self.provider) for f in response.json()['data']]
    
    def download_to(self, f, _internal=True):
        logger.debug(f'download content: {self.links}')
        url = furl.furl(website_settings.WATERBUTLER_INTERNAL_URL if _internal else website_settings.WATERBUTLER_URL)
        file_url = furl.furl(self.links['download'])
        url.path = str(file_url.path)
        response = requests.get(
            url.url,
            headers={'content-type': 'application/json'},
            cookies={website_settings.COOKIE_NAME: self.wb.cookie},
            stream=True,
        )
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192): 
            f.write(chunk)
        
    @property
    def guid(self):
        return self.raw['id']
        
    @property
    def attributes(self):
        return self.raw['attributes']

    @property
    def links(self):
        return self.raw['links']

    def __getattr__(self, name):
        attr = self.raw['attributes']
        if name in attr:
            return attr[name]
        raise AttributeError()

class WikiAsFile(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped
        
    def __getattr__(self, name):
        return getattr(self.wrapped, name)
        
    @property
    def contentType(self):
        return self.wrapped.content_type
    
    @property
    def modified_utc(self):
        return self.wrapped.date_modified
    
    @property
    def created_utc(self):
        return self.wrapped.versions[-1].date_created

class GeneratorIOStream(io.RawIOBase):

    def __init__(self, iter):
        self._iter = iter
        self._left = b''

    def _read1(self, size=None):
        while not self._left:
            try:
                self._left = next(self._iter)
            except StopIteration:
                break
        ret = self._left[:size]
        self._left = self._left[len(ret):]
        return ret
    
    def readall(self):
        l = []
        while True:
            m = self._read1()
            if not m:
                break
            l.append(m)
        return b''.join(l)

    def readinto(self, b):
        pos = 0
        while pos < len(b):
            n = len(b) - pos
            m = self._read1(n)
            if not m:
                break
            for i, v in enumerate(m):
                b[pos + i] = v
            pos += len(m)
        return pos


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

def _to_date(d):
    return d.date().isoformat()

def _to_datetime(d):
    return d.isoformat()

def _create_project_entities(crate, entity_id, node, extra_props=None):
    props = {
        '@type': 'CreativeWork',
        'name': node.title,
        'description': node.description,
        'dateCreated': _to_datetime(node.created),
        'dateModified': _to_datetime(node.modified),
        'isReplacedBy': {
            '@id': f'{entity_id}.jpcoar',
        }
    }
    if extra_props:
        props.update(extra_props)
    custom_props = {
        '@type': 'Project',
        'dc:title': [
            {
                '@value': node.title,
            },
        ],
        'description': {
            '@type': 'Description',
            'type': 'Other',
            'notation': [
                {
                    '@value': node.description,
                },
            ]
        },
        'createdAt': _to_date(node.created),
        'modifiedAt': _to_date(node.modified),
        'jpcoar:affiliation': [{
            '@type': 'Affiliation',
            'jpcoar:affiliationName': _to_localized(e, 'name', default_lang=None),
        } for e in node.affiliated_institutions.all()],
    }
    if node.license:
        custom_props.update({
            'dc:rights': ([{
                '@id': node.license.url,
            }] if node.license.url else []) + ([{
                '@value': _fill_license_params(node.license.text, node.node_license),
            }] if node.license.text else []),
        })
    
    return [
        ContextEntity(crate, entity_id, properties=props),
        ContextEntity(crate, f'{entity_id}.jpcoar', properties=custom_props)
    ]

def _fill_license_params(license_text, params):
    for k, v in params.items():
        pk = _snake_to_camel(k)
        if isinstance(v, list):
            if len(v) == 0:
                continue
            v = v[0]
        license_text = re.sub(r'{{\s*' + pk + r'\s*}}', v, license_text)
    return license_text

def _snake_to_camel(name):
    components = name.split('_')
    return components[0] + ''.join([c.capitalize() for c in components[1:]])
        
def _to_localized(o, prop, default_lang='en'):
    items = []
    items.append(dict([('@value', getattr(o, prop))] + ([('@language', default_lang)] if default_lang else [])))
    
    prop_ja = f'{prop}_ja'
    if not hasattr(o, prop_ja):
        return items
    value_ja = getattr(o, prop_ja)
    if not value_ja:
        return items
    items.append({
        '@value': value_ja,
        '@language': 'ja',
    })
    return items

def _to_localized_dict(o, prop):
    items = []
    items.append({
        '@value': o[prop],
        '@language': 'en',
    })
    prop_ja = f'{prop}_ja'
    if prop_ja not in o:
        return items
    value_ja = o[prop_ja]
    if not value_ja:
        return items
    items.append({
        '@value': value_ja,
        '@language': 'ja',
    })
    return items

def _create_creator_entities(crate, user, user_ids):
    if user._id not in user_ids:
        entity_id = f'#creator#{len(user_ids)}'
        user_ids[user._id] = entity_id
    else:
        entity_id = user_ids[user._id]
    return [
        Person(crate, entity_id, properties={
            'name': user.fullname,
            'affiliation': [e.name for e in user.affiliated_institutions.all()],
            'isReplacedBy': {
                '@id': f'{entity_id}.jpcoar',
            }
        }),
        ContextEntity(crate, f'{entity_id}.jpcoar', properties={
            '@type': 'Creator',
            'jpcoar:creatorName': _to_localized(user, 'fullname'),
            'jpcoar:givenName': _to_localized(user, 'given_name'),
            'jpcoar:familyName': _to_localized(user, 'family_name'),
            'jpcoar:affiliation': [{
                '@type': 'Affiliation',
                'jpcoar:affiliationName': _to_localized(e, 'name'),
            } for e in user.affiliated_institutions.all()],
        })
    ]

def _create_contributor_entities(crate, user, user_ids):
    if user._id in user_ids:
        return []
    entity_id = f'#contributor#{len(user_ids)}'
    user_ids[user._id] = entity_id
    return [
        Person(crate, entity_id, properties={
            'name': user.fullname,
            'affiliation': [e.name for e in user.affiliated_institutions.all()],
            'isReplacedBy': {
                '@id': f'{entity_id}.jpcoar',
            }
        }),
        ContextEntity(crate, f'{entity_id}.jpcoar', properties={
            '@type': 'Contributor',
            'jpcoar:contributorName': _to_localized(user, 'fullname'),
            'jpcoar:givenName': _to_localized(user, 'given_name'),
            'jpcoar:familyName': _to_localized(user, 'family_name'),
            'jpcoar:affiliation': [{
                '@type': 'Affiliation',
                'jpcoar:affiliationName': _to_localized(e, 'name'),
            } for e in user.affiliated_institutions.all()],
        })
    ]

def _create_comment_entities(crate, parent_id, comment, user_ids):
    comment_id = f'#comment#{comment._id}'
    r = [ContextEntity(crate, comment_id, properties={
        '@type': 'Comment',
        'dateCreated': _to_datetime(comment.created),
        'dateModified': _to_datetime(comment.modified),
        'parentItem': {
            '@id': parent_id,
        },
        'text': comment.content,
        'author': {
            '@id': user_ids[comment.user._id]
        } if comment.user._id in user_ids else None
    })]
    for reply in Comment.objects.filter(target___id=comment._id):
        r += _create_comment_entities(crate, comment_id, reply, user_ids)
    return r
    
def _create_file_entities(crate, base_path, node, wb_file, user_ids):
    r = []
    # TBD test
    web_file = BaseFileNode.objects.filter(
        _path=wb_file.path,
        provider=wb_file.provider,
        target_object_id=node.id,
        deleted=None,
        target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
    ).order_by('-id').first()

    path = os.path.join(base_path, wb_file.name)
    if wb_file.attributes['kind'] == 'folder':
        path += '/'
        wb_files = wb_file.get_files()
        for child in wb_files:
            r += _create_file_entities(crate, path, node, child, user_ids)
        crate.add(DataEntity(crate, path, properties={
            '@type': 'StorageProvider' if wb_file.path == '/' else 'Folder',
            'name': wb_file.name,
            'hasPart': [
                {'@id': f'{path}{child.name}' if child.attributes['kind'] == 'folder' else f'{path[2:]}{child.name}'}
                for child in wb_files
            ]
        }))
    else:
        comments = []
        if web_file is not None:
            comments = sum([_create_comment_entities(crate, path, c, user_ids) for c in Comment.objects.filter(root_target=web_file)], []) if web_file is not None and hasattr(web_file, 'comments') else []
        r.append((path, wb_file, comments))
        crate.add_file(path, dest_path=path, properties={
            'name': wb_file.name,
            'encodingFormat': wb_file.contentType,
            'contentSize': str(wb_file.size),
            'dateModified': wb_file.modified_utc,
            'dateCreated': wb_file.created_utc,
        })
    return r

def _create_log_entity(crate, log, user_ids):
    return ContextEntity(crate, log._id, properties={
        '@type': 'Action',
        'name': log.action,
        'startTime': _to_datetime(log.date),
        'agent': {
            '@id': user_ids[log.user._id]
        } if log.user is not None and log.user._id in user_ids else None,
        'object': {
            '@value': json.dumps(log.params),
        },
    })

def _ro_crate_path_list(node, work_dir, wb, config, task):
    crate, files = _build_ro_crate(node, wb, config)
    metadata_file = os.path.join(work_dir, 'ro-crate-metadata.json')
    zip_path = os.path.join(work_dir, 'work.zip')
    crate.write_zip(zip_path)
    with ZipFile(zip_path, 'r') as zf:
        with zf.open('ro-crate-metadata.json') as f:
            metadata = f.read()
            with open(metadata_file, 'wb') as df:
                df.write(metadata)
    yield {
        'fs': metadata_file,
        'n': 'ro-crate-metadata.json',
    }
    tmp_path = os.path.join(work_dir, 'temp.dat')
    for path, file, _ in files:
        logger.info(f'Downloading... {path}')
        assert path.startswith('./'), path
        with open(tmp_path, 'wb') as df:
            file.download_to(df)
        yield {
            'fs': tmp_path,
            'n': path[2:],
        }

def _build_ro_crate(node, wb, config):
    crate = ROCrate()
    crate.metadata.extra_terms.update({
        # TBD RO-Crateスキーマ定義
        "@vocab": "https://terms.rcos.nii.ac.jp/schema/1.0/",
        'isReplacedBy': 'http://purl.org/dc/terms/isReplacedBy',
        'dc': 'http://purl.org/dc/terms/',
        'datacite': 'https://schema.datacite.org/meta/kernel-4/',
        'jpcoar': 'https://github.com/JPCOAR/schema/blob/master/1.0/',
    })

    for project in _create_project_entities(crate, '#root', node, extra_props={
        'hasPart': {
            '@id': './',
        },
    }):
        crate.add(project)

    user_ids = {}
    crate.add(*_create_creator_entities(crate, node.creator, user_ids))
    crate.add(*sum([_create_contributor_entities(crate, user, user_ids) for user in node.contributors.all()], []))

    crate.add(*sum([
        _create_comment_entities(crate, '#root', comment, user_ids)
        for comment in Comment.objects.filter(node=node)
    ], []))

    files = []
    addons_config = config.get('addons', {})
    for addon_app in website_settings.ADDONS_AVAILABLE:
        addon_name = addon_app.short_name
        if addon_name in addons_config and not addons_config[addon_name].get('enable', True):
            logger.info(f'Skipped {addon_name}')
            continue
        addon = node.get_addon(addon_name)
        if addon is None:
            continue
        if not hasattr(addon, 'serialize_waterbutler_credentials'):
            continue
        logger.debug(f'ADDON(STORAGE): {addon_name}')
        provider = wb.get_provider(addon_name)
        for file in provider['data']:
            files += _create_file_entities(crate, f'./{addon_name}', node, WaterButlerObject(file, wb, addon_name), user_ids)

    # TBD
    # for wiki in node.wikis:
    #     wiki_ = WikiAsFile(wiki)
    #     files += _create_file_entities(crate, './wiki/', wiki_, wiki_, user_ids)
        
    for log in node.logs.all():
        crate.add(_create_log_entity(crate, log, user_ids))
        
    for _, _, comments in files:
        crate.add(*comments)
    return crate, files

def _to_metadata_value(value):
    return {
        'extra': [],
        'comments': [],
        'value': value,
    }

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
def export_project(self, user_id, node_id, config):
    user = OSFUser.load(user_id)
    node = AbstractNode.load(node_id)
    wb = WaterButlerClient(user, node)
    metadata_addon = node.get_addon(SHORT_NAME)
    schema_id = RegistrationSchema.objects.get(name=weko_settings.REGISTRATION_SCHEMA_NAME)._id
    logger.info(f'Exporting: {node_id}')
    self.update_state(state='exporting node', meta={
        'progress': 0,
        'user': user_id,
        'node': node_id,
    })
    work_dir = tempfile.mkdtemp()
    try:
        zfly = zipfly.ZipFly(paths=_ro_crate_path_list(node, work_dir, wb, config, self))
        zip_path = os.path.join(work_dir, 'package.zip')
        with open(zip_path, 'wb') as f:
            shutil.copyfileobj(GeneratorIOStream(zfly.generator()), f)
        # TBD
        file_name_ = 'example.zip'
        folder_name = 'weko'
        wb.upload_file(zip_path, file_name_, folder_name)
        metadata = {
            'path': 'weko/example.zip',
            'folder': False,
            'hash': '',
            'items': [
                {
                    'active': True,
                    'schema': schema_id,
                    'data': {
                        'grdm-file:pubdate': _to_metadata_value(datetime.now().date().isoformat()),
                        'grdm-file:Title.ja': _to_metadata_value(node.title),
                        'grdm-file:Description.subitem_description_type.ja': _to_metadata_value('Other'),
                        'grdm-file:Description.subitem_description.ja': _to_metadata_value(node.description),
                        'grdm-file:resourcetype': _to_metadata_value('dataset'),
                    },
                }
            ],
        }
        metadata_addon.set_file_metadata(metadata['path'], metadata)
        self.update_state(state='finished', meta={
            'progress': 100,
            'user': user_id,
            'node': node_id,
        })
        return {
            'TEST': True,
            'user': user_id,
            'node': node_id,
        }
    finally:
        shutil.rmtree(work_dir)

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
            wb.upload_file(GeneratorIOStream(unzipped_chunks), file_name_, folder_name + '/')
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
    if result.failed():
        raise result.info
    if result.info is not None and auth.user._id != result.info['user']:
        raise HTTPError(http_status.HTTP_403_FORBIDDEN)
    info = {}
    info.update(result.info or {})
    if result.info is not None and 'node' in result.info:
        node = AbstractNode.load(result.info['node'])
        info['node_url'] = node.web_url_for('view_project')
    return {
        'state': result.state,
        'info': info,
    }

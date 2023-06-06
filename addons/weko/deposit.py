# -*- coding: utf-8 -*-
import io
import logging
import os
import shutil
import tempfile
from zipfile import ZipFile

from framework.auth import Auth
from framework.celery_tasks import app as celery_app
from osf.models import AbstractNode, OSFUser
from osf.models.metaschema import RegistrationSchema

from addons.metadata.packages import WaterButlerClient, BaseROCrateFactory
from .apps import SHORT_NAME
from . import schema
from . import settings as weko_settings


logger = logging.getLogger('addons.weko.views')


class ROCrateFactory(BaseROCrateFactory):

    def __init__(self, node, work_dir, folder):
        super(ROCrateFactory, self).__init__(node, work_dir)
        self.folder = folder

    def _build_ro_crate(self, crate):
        user_ids = {}
        files = []
        for file in self.folder.get_files(_internal=True):
            files += self._create_file_entities(crate, f'./', file, user_ids)
        for _, _, comments in files:
            crate.add(*comments)
        return crate, files


def _download(node, file, tmp_dir):
    if file.kind == 'file':
        download_file_path = os.path.join(tmp_dir, file.name)
        with open(os.path.join(download_file_path), 'wb') as f:
            file.download_to(f, _internal=True)
        return download_file_path
    rocrate = ROCrateFactory(node, tmp_dir, file)
    download_file_path = os.path.join(tmp_dir, 'rocrate.zip')
    rocrate.download_to(download_file_path)
    return download_file_path


@celery_app.task(bind=True, max_retries=5, default_retry_delay=60)
def deposit_metadata(self, user_id, index_id, node_id, metadata_node_id, file_metadata, metadata_path, content_path, after_delete_path):
    user = OSFUser.load(user_id)
    logger.info(f'Deposit: {metadata_path}, {content_path} {self.request.id}')
    path = metadata_path
    if '/' not in path:
        raise ValueError(f'Malformed path: {path}')
    self.update_state(state='initializing', meta={
        'progress': 0,
        'path': metadata_path,
    })
    materialized_path = path[path.index('/'):]
    node = AbstractNode.load(node_id)
    weko_addon = node.get_addon(SHORT_NAME)
    weko_addon.set_publish_task_id(metadata_path, self.request.id)
    wb = WaterButlerClient(user, node)
    file = wb.get_file(path)
    logger.debug(f'File: {file}')
    if file is None:
        raise KeyError(f'File not found: {materialized_path}')
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        self.update_state(state='downloading', meta={
            'progress': 10,
            'path': metadata_path,
        })
        download_file_path = _download(node, file, tmp_dir)
        filesize = os.path.getsize(download_file_path)
        logger.info(f'Downloaded: {download_file_path} {filesize}')
        self.update_state(state='packaging', meta={
            'progress': 50,
            'path': metadata_path,
        })

        c = weko_addon.create_client()
        target_index = c.get_index_by_id(index_id)

        _, download_file_name = os.path.split(download_file_path)

        zip_path = os.path.join(tmp_dir, 'payload.zip')
        schema_id = RegistrationSchema.objects.get(name=weko_settings.REGISTRATION_SCHEMA_NAME)._id
        with ZipFile(zip_path, 'w') as zf:
            with zf.open(os.path.join('data/', download_file_name), 'w') as df:
                with open(download_file_path, 'rb') as sf:
                    shutil.copyfileobj(sf, df)
            with zf.open('data/index.csv', 'w') as f:
                with io.TextIOWrapper(f, encoding='utf8') as tf:
                    schema.write_csv(tf, target_index, [download_file_name], schema_id, file_metadata)
        headers = {
            'Packaging': 'http://purl.org/net/sword/3.0/package/SimpleZip',
            'Content-Disposition': 'attachment; filename=payload.zip',
        }
        files = {
            'file': ('payload.zip', open(zip_path, 'rb'), 'application/zip'),
        }
        self.update_state(state='uploading', meta={
            'progress': 60,
            'path': metadata_path,
        })
        logger.info(f'Uploading... {file_metadata}')
        respbody = c.deposit(files, headers=headers)
        logger.info(f'Uploaded: {respbody}')
        self.update_state(state='uploaded', meta={
            'progress': 100,
            'path': metadata_path,
        })
        links = [l for l in respbody['links'] if 'contentType' in l and '@id' in l and l['contentType'] == 'text/html']
        if after_delete_path:
            file.delete(_internal=True)
        weko_addon.create_waterbutler_deposit_log(
            Auth(user),
            'item_deposited',
            {
                'materialized': file.materialized,
                'path': file.path,
                'item_html_url': links[0]['@id'],
            },
        )
        return {
            'result': links[0]['@id'] if len(links) > 0 else None,
            'path': metadata_path,
        }
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

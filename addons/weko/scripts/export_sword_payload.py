"""Export WEKO SWORD payload artifacts from e-Rad style metadata."""

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

import django

django.setup()

from website.app import init_app
from osf.models.metaschema import RegistrationSchema

from addons.weko.deposit import _build_payload_zip


class _Index(object):
    def __init__(self, identifier, title):
        self.identifier = identifier
        self.title = title


class _StubInstitutionSet(object):
    def __init__(self, name=None):
        self._name = name

    def first(self):
        if self._name:
            return SimpleNamespace(name=self._name)
        return None


class _StubUser(object):
    def __init__(self, username, fullname, institution=None, extra=None):
        self.username = username
        self.fullname = fullname
        self.affiliated_institutions = _StubInstitutionSet(institution)
        self._extra = extra or {}

    def __getattr__(self, item):
        if item in self._extra:
            return self._extra[item]
        raise AttributeError(item)

    def __dir__(self):
        return ['username', 'fullname'] + list(self._extra.keys())


def _stage_files(definitions, work_dir):
    staged = []
    seen = set()
    for definition in definitions:
        name = definition['name']
        if name in seen:
            raise ValueError(f'Duplicated file name: {name}')
        seen.add(name)
        destination = os.path.join(work_dir, name)
        shutil.copyfile(definition['path'], destination)
        staged.append((name, definition['type']))
    return staged


def _load_schema_id(schema_name):
    schema = RegistrationSchema.objects.filter(name=schema_name).order_by('-schema_version').first()
    if schema is None:
        raise ValueError(f'Schema not found: {schema_name}')
    return schema._id


def _ensure_schema_id(file_metadatas, schema_id):
    items = []
    for metadata in file_metadatas:
        metadata_items = metadata['items']
        for item in metadata_items:
            items.append(item['schema'])
    if not items:
        raise ValueError('file_metadatas must contain items')
    if any(item != schema_id for item in items):
        raise ValueError('Schema mismatch between metadata and schema_id')


def _load_config(path):
    if path == '-':
        return json.load(sys.stdin)
    with open(path) as fp:
        return json.load(fp)


def _build_user(config):
    user_config = config.get('user')
    if not user_config:
        raise ValueError('user configuration is required')
    username = user_config.get('username')
    fullname = user_config.get('fullname', username or '')
    if not username:
        raise ValueError('user.username is required')
    institution = user_config.get('institution')
    extra = user_config.get('extra_attributes', {})
    return _StubUser(username=username, fullname=fullname, institution=institution, extra=extra)


def _generate_payload(config, output_path, fmt, flatten_ro_crate, log_level, skip_csv=False):
    init_app(routes=False)
    logging.getLogger().setLevel(log_level)
    logging.getLogger('bagit').setLevel(log_level)

    user = _build_user(config)

    schema_id = _load_schema_id(config['schema_name'])
    _ensure_schema_id(config['file_metadatas'], schema_id)

    index_def = config['index']
    target_index = _Index(index_def['id'], index_def['title'])

    project_metadatas = config.get('project_metadatas', [])
    additional_files = config.get('additional_files', [])

    with tempfile.TemporaryDirectory() as tmp_dir:
        download_file_names = _stage_files(config['files'], tmp_dir)
        additional_download_file_names = _stage_files(additional_files, tmp_dir)

        zip_path, bagit_dir = _build_payload_zip(
            user,
            target_index,
            schema_id,
            config['file_metadatas'],
            project_metadatas,
            download_file_names,
            additional_download_file_names,
            tmp_dir,
            config['node_id'],
            flatten_ro_crate=flatten_ro_crate,
            skip_csv_generation=skip_csv or (fmt == 'ro-crate'),
        )
        try:
            if fmt == 'zip':
                if output_path == '-':
                    with open(zip_path, 'rb') as src:
                        shutil.copyfileobj(src, sys.stdout.buffer)
                else:
                    shutil.copyfile(zip_path, output_path)
                return

            bag_data_dir = os.path.join(bagit_dir, 'data')
            if fmt == 'ro-crate':
                source = os.path.join(bag_data_dir, 'ro-crate-metadata.json')
            elif fmt == 'csv':
                source = os.path.join(bag_data_dir, 'index.csv')
            else:
                raise ValueError(f'Unsupported format: {fmt}')

            if not os.path.exists(source):
                raise ValueError(f'Expected artifact not found: {source}')
            if output_path == '-':
                with open(source, 'rb') as src:
                    shutil.copyfileobj(src, sys.stdout.buffer)
            else:
                shutil.copyfile(source, output_path)
        finally:
            shutil.rmtree(bagit_dir)


def main():
    parser = argparse.ArgumentParser(description='Export WEKO SWORD payload artifacts for testing.')
    parser.add_argument('config', help='Path to metadata configuration JSON')
    parser.add_argument('output', help='Destination path for the generated artifact')
    parser.add_argument(
        '--format',
        default='zip',
        choices=['zip', 'ro-crate', 'csv'],
        help='Artifact format to export. Default is zip (BagIt package).'
    )
    parser.add_argument(
        '--skip-csv',
        action='store_true',
        help='Skip index.csv generation when building a zip payload.'
    )
    parser.add_argument(
        '--skip-flatten',
        action='store_true',
        help='Skip JSON-LD flattening (only valid with --format=ro-crate).'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase verbosity (repeat for more detail).'
    )
    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose == 1:
        log_level = logging.INFO
    logging.basicConfig(level=log_level)

    config = _load_config(args.config)

    if args.skip_flatten and args.format != 'ro-crate':
        parser.error('--skip-flatten can only be used with --format=ro-crate')

    if args.skip_csv and args.format == 'csv':
        parser.error('--skip-csv cannot be used together with --format=csv')

    flatten_ro_crate = not args.skip_flatten
    _generate_payload(
        config,
        args.output,
        args.format,
        flatten_ro_crate,
        log_level,
        skip_csv=args.skip_csv,
    )


if __name__ == '__main__':
    main()

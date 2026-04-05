# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
import re
from jinja2 import Environment
from osf.models.metaschema import RegistrationSchema


logger = logging.getLogger(__name__)


class FileMetadataMigrator:
    """Migrate file metadata across FileMetadata, Registration, and DraftRegistration.

    transform_item: fn(item_data: dict) -> bool
        Mutates item_data in-place. Returns True if changed.
    transform_filemetadata_entry: fn(entry: dict) -> bool
        Mutates a filemetadata entry (with 'metadata' key) in-place. Returns True if changed.
        Used for Registration/DraftRegistration where filemetadata is nested.
    """

    def __init__(self, schema_name, transform_item, transform_filemetadata_entry=None):
        self.schema_name = schema_name
        self.transform_item = transform_item
        self.transform_filemetadata_entry = transform_filemetadata_entry or self._default_transform_entry

    @staticmethod
    def _default_transform_entry(entry):
        return False

    def _get_schema_ids(self):
        schemas = list(RegistrationSchema.objects.filter(name=self.schema_name))
        if not schemas:
            logger.warning(f'Skipped: No schema found for "{self.schema_name}"')
            return None
        return [s._id for s in schemas]

    def run(self):
        schema_ids = self._get_schema_ids()
        if schema_ids is None:
            return
        self._migrate_filemetadata(schema_ids)
        self._migrate_registration(schema_ids)
        self._migrate_draft_registration(schema_ids)

    def _migrate_filemetadata(self, schema_ids):
        from addons.metadata.models import FileMetadata
        for fm in FileMetadata.objects.filter(metadata__isnull=False, deleted__isnull=True):
            try:
                metadata = json.loads(fm.metadata)
            except json.JSONDecodeError:
                logger.warning(f'Skipped: bad JSON for FileMetadata {fm._id}', exc_info=True)
                continue
            dirty = False
            for item in metadata.get('items', []):
                if item.get('schema') not in schema_ids:
                    continue
                if self.transform_item(item.get('data', {})):
                    dirty = True
            if dirty:
                fm.metadata = json.dumps(metadata, ensure_ascii=False)
                fm.save()
                logger.info(f'Migrated FileMetadata {fm._id} path="{fm.path}"')

    def _migrate_registration(self, schema_ids):
        from osf.models import Registration
        registrations = Registration.objects.filter(
            registered_meta__isnull=False,
            registered_schema__name=self.schema_name,
        )
        for reg in registrations:
            dirty = False
            for meta_key, meta_value in reg.registered_meta.items():
                try:
                    filemetadatas = json.loads(meta_value.get('grdm-files', {}).get('value', '[]'))
                except json.JSONDecodeError:
                    logger.warning(f'Skipped: bad JSON for Registration {reg._id}', exc_info=True)
                    continue
                entry_dirty = False
                for entry in filemetadatas:
                    if self.transform_filemetadata_entry(entry):
                        entry_dirty = True
                if entry_dirty:
                    meta_value['grdm-files']['value'] = json.dumps(filemetadatas, ensure_ascii=False)
                    reg.registered_meta[meta_key] = meta_value
                    dirty = True
            if dirty:
                reg.save()
                logger.info(f'Migrated Registration {reg._id}')

    def _migrate_draft_registration(self, schema_ids):
        from osf.models import DraftRegistration
        drafts = DraftRegistration.objects.filter(
            registration_metadata__isnull=False,
            registration_schema__name=self.schema_name,
        )
        for draft in drafts:
            meta_value = draft.registration_metadata
            try:
                file_list = meta_value.get('grdm-files', {}).get('value', '[]')
                if not file_list:
                    continue
                filemetadatas = json.loads(file_list)
            except json.JSONDecodeError:
                logger.warning(f'Skipped: bad JSON for DraftRegistration {draft._id}', exc_info=True)
                continue
            entry_dirty = False
            for entry in filemetadatas:
                if self.transform_filemetadata_entry(entry):
                    entry_dirty = True
            if entry_dirty:
                meta_value['grdm-files']['value'] = json.dumps(filemetadatas, ensure_ascii=False)
                draft.save()
                logger.info(f'Migrated DraftRegistration {draft._id}')


def _name_string_to_object(value):
    """Convert a string name to {last, middle, first} object. Returns None if already object."""
    if isinstance(value, dict):
        return None
    if isinstance(value, str):
        return {'last': value, 'middle': '', 'first': ''}
    logger.warning(f'Unexpected name value type: {type(value).__name__}')
    return None


def _transform_creators_rows(rows):
    """Convert creator rows: rename name_ja -> name-ja, string -> object."""
    dirty = False
    for row in rows:
        for old_key, new_key in [('name_ja', 'name-ja'), ('name_en', 'name-en')]:
            if old_key in row:
                converted = _name_string_to_object(row.pop(old_key))
                row[new_key] = converted if converted is not None else row.get(new_key, '')
                dirty = True
            elif new_key in row:
                converted = _name_string_to_object(row[new_key])
                if converted is not None:
                    row[new_key] = converted
                    dirty = True
    return dirty


def transform_name_fields_item(data):
    """Transform name fields in FileMetadata item data (has {value: ...} wrappers)."""
    dirty = False
    # creators: data['grdm-file:creators'] = {'value': [...]}
    creators = data.get('grdm-file:creators')
    if creators is not None:
        rows = creators['value']
        if isinstance(rows, str):
            rows = json.loads(rows)
            creators['value'] = rows
        if isinstance(rows, list) and _transform_creators_rows(rows):
            dirty = True
    # data-man-name: data['grdm-file:data-man-name-ja'] = {'value': 'Full Name'}
    for key in ('grdm-file:data-man-name-ja', 'grdm-file:data-man-name-en'):
        field = data.get(key)
        if field is not None:
            converted = _name_string_to_object(field['value'])
            if converted is not None:
                field['value'] = converted
                dirty = True
    return dirty


def transform_name_fields_entry(entry):
    """Transform name fields in Registration/DraftRegistration filemetadata entry (no {value:} wrappers)."""
    metadata = entry.get('metadata', {})
    dirty = False
    # creators: metadata['grdm-file:creators'] = [...]
    creators = metadata.get('grdm-file:creators')
    if isinstance(creators, list) and _transform_creators_rows(creators):
        dirty = True
    # data-man-name: metadata['grdm-file:data-man-name-ja'] = 'Full Name'
    for key in ('grdm-file:data-man-name-ja', 'grdm-file:data-man-name-en'):
        value = metadata.get(key)
        if value is not None:
            converted = _name_string_to_object(value)
            if converted is not None:
                metadata[key] = converted
                dirty = True
    return dirty


def _convert_metadata_key(key):
    if '-' not in key:
        return [key]
    return [key, key.replace('-', '_')]

def _convert_metadata_grdm_files(value, questions):
    if len(value) == 0:
        return {}
    values = json.loads(value)
    r = []
    for v in values:
        obj = {'path': v['path']}
        metadata = v['metadata']
        for key in metadata.keys():
            if key.startswith('grdm-file:'):
                dispkey = key[10:]
            else:
                dispkey = key
            for suffix_, v_ in _convert_metadata_value(key, metadata[key], questions):
                for k in _convert_metadata_key(dispkey):
                    obj[f'{k}{suffix_}'] = v_
        r.append(obj)
    return r

def _to_jinja_dict(value):
    if value is None:
        return value
    if not isinstance(value, dict):
        return value
    r = {}
    r.update(value)
    for key in value.keys():
        r[key.replace('-', '_')] = value[key]
    return r

def _to_jinja_list(value):
    if value is None:
        return value
    if not isinstance(value, list):
        return value
    r = []
    for v in value:
        if isinstance(v, dict):
            r.append(_to_jinja_dict(v))
            continue
        r.append(v)
    return r

def _convert_metadata_value(key, value, questions):
    if 'value' not in value:
        return [('', value)]
    v = value['value']
    if key == 'grdm-files':
        return [('', _convert_metadata_grdm_files(v, questions))]
    if key in questions and 'type' in questions[key] and \
            questions[key]['type'] == 'string' and 'format' in questions[key] and \
            questions[key]['format'] == 'file-creators':
        return [('', json.loads(v) if v != '' else [])]
    if key in questions and 'type' in questions[key] and \
            questions[key]['type'] == 'object':
        return [('', _to_jinja_dict(v))]
    if key in questions and 'type' in questions[key] and \
            questions[key]['type'] == 'array':
        return [('', _to_jinja_list(v))]
    if key in questions and 'type' in questions[key] and \
            questions[key]['type'] == 'choose' and 'options' in questions[key]:
        values = [('', v)]
        for opt in questions[key]['options']:
            if not isinstance(opt, dict) or 'text' not in opt or 'tooltip' not in opt:
                continue
            if opt['text'] != v:
                continue
            for sep in '-_':
                tooltip = opt['tooltip']
                values += [(f'{sep}tooltip', tooltip)]
                if tooltip is None:
                    continue
                for j, t in enumerate(tooltip.split('|')):
                    values += [(f'{sep}tooltip{sep}{j}', t)]
        return values
    return [('', v)]

def _convert_metadata(metadata, questions):
    r = {}
    for key in metadata.keys():
        for suffix, v in _convert_metadata_value(key, metadata[key], questions):
            for k in _convert_metadata_key(key):
                r[f'{k}{suffix}'] = v
    return r

def _quote_csv(value):
    f = io.StringIO()
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    if isinstance(value, list):
        w.writerow(value)
    else:
        w.writerow([value])
    return f.getvalue().rstrip()

def _name_to_str_ja(value):
    """Convert name dict to Japanese format: 姓ミドルネーム名 (no spaces)."""
    if isinstance(value, str):
        logger.warning(f'namestr_ja: expected dict but got str: {value!r}')
        return value
    parts = [value['last'], value['middle'], value['first']]
    return ''.join(p for p in parts if p)

def _name_to_str_en(value):
    """Convert name dict to English format: First Middle Last (space-separated)."""
    if isinstance(value, str):
        logger.warning(f'namestr_en: expected dict but got str: {value!r}')
        return value
    parts = [value['first'], value['middle'], value['last']]
    return ' '.join(p for p in parts if p)

def make_report_as_csv(format, draft_metadata, schema):
    questions = dict([(q['qid'], q) for q in sum([page['questions'] for page in schema['pages']], [])])
    env = Environment(autoescape=False)
    env.filters['quotecsv'] = _quote_csv
    env.filters['namestr_ja'] = _name_to_str_ja
    env.filters['namestr_en'] = _name_to_str_en
    template = env.from_string(format.csv_template)
    template_metadata = _convert_metadata(draft_metadata, questions)
    return 'report.csv', template.render(**template_metadata)

def ensure_registration_report(schema_name, report_name_and_order, csv_template):
    from .models import RegistrationReportFormat
    registration_schema = RegistrationSchema.objects.filter(
        name=schema_name
    ).order_by('-schema_version').first()
    report_name = report_name_and_order
    order = None
    m = re.match(r'^(\d+):\s*(.*)$', report_name_and_order)
    if m:
        order = int(m.group(1))
        report_name = m.group(2)
    template_query = RegistrationReportFormat.objects.filter(
        registration_schema_id=registration_schema._id, name=report_name
    )
    if csv_template is None:
        if template_query.exists():
            template_query.delete()
            logger.info(f'Format deleted: {registration_schema._id}, {report_name}')
        return
    if template_query.exists():
        template = template_query.first()
    else:
        template = RegistrationReportFormat.objects.create(
            registration_schema_id=registration_schema._id,
            name=report_name
        )
    template.csv_template = csv_template
    if order is not None:
        template.order = order
    logger.info(f'Format registered: {registration_schema._id}, "{report_name}" as index {order}')
    template.save()

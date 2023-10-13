import csv
from datetime import datetime
import json
import logging
import re

from jinja2 import Environment

from osf.models.metaschema import RegistrationSchema


logger = logging.getLogger(__name__)


columns_default = [
    ('#.id', '#ID', '#', '#', ''),
    ('.uri', 'URI', '', '', ''),
    ('.feedback_mail[0]', '.FEEDBACK_MAIL[0]', '', 'Allow Multiple', ''),
    ('.cnri', '.CNRI', '', '', ''),
    ('.doi_ra', '.DOI_RA', '', '', ''),
    ('.doi', '.DOI', '', '', ''),
    ('.edit_mode', 'Keep/Upgrade Version', '', 'Required', 'Keep'),
]


def _generate_file_columns(index, download_file_name, download_file_type):
    columns = []
    columns.append((f'.file_path[{index}]', f'.ファイルパス[{index}]', '', 'Allow Multiple', download_file_name))
    base_item = f'.metadata.item_1617605131499[{index}]'
    base_file = f'File[{index}]'
    columns.append((f'{base_item}.filename', f'{base_file}.表示名', '', 'Allow Multiple', download_file_name))
    if download_file_type is not None:
        columns.append((f'{base_item}.format', f'{base_file}.フォーマット', '', 'Allow Multiple', download_file_type))
    return columns

def _get_metadata_value(file_metadata_data, item, lang, index):
    assert 'type' in item, item
    if item['type'] == 'const':
        if 'depends' in item:
            value = _get_metadata_value(file_metadata_data, item['depends'], lang, index)
            if not value:
                return ''
        return item['value']
    key = f'grdm-file:{item["key"]}'
    if lang is not None:
        key += f'.{lang}'
    if key not in file_metadata_data:
        return ''
    value = file_metadata_data[key]['value']
    if item['type'] == 'property':
        return value
    if item['type'] == 'jsonproperty':
        logger.debug(f'jsonproperty: {value}')
        return json.loads(value)[index][item['value']]
    raise KeyError(item['type'])

def _get_item_variables(file_metadata, schema=None):
    values = {
        'value': '',
    }
    if file_metadata is None:
        return values
    if 'value' in file_metadata:
        v = file_metadata['value']
        if schema is not None and 'options' in schema:
            options = [
                o
                for o in schema['options']
                if o.get('text', None) == v or (not v and o.get('default', False))
            ]
            if len(options) == 0:
                logger.debug(f'No suitable options: value={v}, schema={schema}')
            else:
                option = options[0]
                v = option['text']
                if 'tooltip' in option:
                    values['tooltip'] = option['tooltip']
                    langs = option['tooltip'].split('|')
                    if len(langs) > 1:
                        for i, s in enumerate(langs):
                            values[f'tooltip_{i}'] = s
                    else:
                        for i in range(2):
                            values[f'tooltip_{i}'] = option['tooltip']
        values['value'] = v
    if 'object' in file_metadata:
        o = file_metadata['object']
        for k, v in o.items():
            values[f'object_{k}'] = v
    return values

def _get_value(file_metadata, text, commonvars=None, schema=None):
    values = _get_item_variables(file_metadata, schema=schema)
    if commonvars is not None:
        values.update(commonvars)
    env = Environment(autoescape=False)
    template = env.from_string(text)
    return template.render(**values)

def _to_columns(full_key, value, weko_key_counts=None):
    if f'{full_key}.__value__' in weko_key_counts:
        if weko_key_counts[f'{full_key}.__value__'] != value:
            raise ValueError(f'Different values to the same key are detected: {value}, {weko_key_counts[f"{full_key}.__value__"]}')
        logger.debug(f'Skipped duplicated item: {full_key}')
        return []
    weko_key_counts[f'{full_key}.__value__'] = value
    return [
        (
            full_key,
            '',
            '',
            '',
            value,
        )
    ]

def _is_column_present(file_metadata, item, commonvars=None, schema=None):
    if not isinstance(item, dict):
        return True
    present_expression = item.get('@createIf', None)
    if present_expression is None:
        return True
    return _get_value(file_metadata, present_expression, commonvars=commonvars, schema=schema)

def _get_columns(file_metadata, weko_key_prefix, weko_props, weko_key_counts=None, commonvars=None, schema=None):
    if isinstance(weko_props, str):
        value = _get_value(file_metadata, weko_props, commonvars=commonvars, schema=schema)
        return _to_columns(weko_key_prefix, value, weko_key_counts=weko_key_counts)
    columns = []
    for key in sorted(weko_props.keys()):
        items = weko_props[key]
        if key.startswith('@'):
            continue
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if not _is_column_present(file_metadata, item, commonvars=commonvars, schema=schema):
                continue
            full_key = _resolve_array_index(weko_key_counts, f'{weko_key_prefix}.{key}')
            if isinstance(item, dict):
                # Subitem
                columns += _get_columns(
                    file_metadata,
                    full_key,
                    item,
                    weko_key_counts=weko_key_counts,
                    commonvars=commonvars,
                    schema=schema,
                )
                continue
            value = _get_value(file_metadata, item, commonvars=commonvars, schema=schema)
            columns += _to_columns(full_key, value, weko_key_counts=weko_key_counts)
    return columns

def _get_item_metadata_key(key):
    m = re.match(r'^(.+)\[[0-9]*\]$', key)
    if m:
        return _get_item_metadata_key(m.group(1))
    return key

def _find_schema_question(schema, qid):
    if 'pages' not in schema:
        return 
    for page in schema['pages']:
        if 'questions' not in page:
            continue
        for question in page['questions']:
            if question['qid'] == qid:
                return question
    logger.warning(f'Question {qid} not found: schema={schema}')
    raise KeyError(f'Question {qid} not found')

def get_available_schema_id(file_metadata):
    from .models import RegistrationMetadataMapping
    available_schema_ids = [
        mapping.registration_schema_id
        for mapping in RegistrationMetadataMapping.objects.all()
    ]
    items = [
        item
        for item in file_metadata['items']
        if item.get('active', False) and item.get('schema', None) in available_schema_ids
    ]
    if len(items):
        return items[0]['schema']
    items = [
        item
        for item in file_metadata['items']
        if item.get('schema', None) in available_schema_ids
    ]
    if len(items):
        return items[0]['schema']
    raise ValueError(f'Available schemas not found: {file_metadata}')

def _get_common_variables(file_metadata_data, schema, skip_empty=False):
    r = {
        'nowdate': datetime.now().strftime('%Y-%m-%d'),
    }
    for key in file_metadata_data.keys():
        if skip_empty and not file_metadata_data[key].get('value', ''):
            continue
        values = _get_item_variables(
            file_metadata_data[key],
            schema=_find_schema_question(schema.schema, key),
        )
        key_ = key.replace('-', '_').replace(':', '_').replace('.', '_')
        r.update(dict([(f'{key_}_{k}', v) for k, v in values.items()]))
    return r

def _resolve_array_index(weko_key_counts, key):
    m = re.match(r'^(.+)\[(.*)\]$', key)
    if not m:
        return key
    key_body = m.group(1)
    index_id = m.group(2)
    weko_key_ids = weko_key_counts.get(key_body, None)
    if weko_key_ids is None:
        weko_key_ids = []
    if not index_id:
        weko_key_count = len(weko_key_ids)
        weko_key_counts[key_body] = weko_key_ids + [None]
        return f'{key_body}[{weko_key_count}]'
    matched = [i for i, weko_key_id in enumerate(weko_key_ids) if weko_key_id == index_id]
    if len(matched) == 0:
        # New key
        weko_key_count = len(weko_key_ids)
        weko_key_counts[key_body] = weko_key_ids + [index_id]
        return f'{key_body}[{weko_key_count}]'
    # Existing key
    weko_key_count = matched[0]
    return f'{key_body}[{weko_key_count}]'

def _expand_listed_key(mappings):
    r = {}
    for k, v in mappings.items():
        for e in k.split():
            r[e] = v
    return r

def write_csv(f, target_index, download_file_names, schema_id, file_metadata, project_metadata):
    from .models import RegistrationMetadataMapping
    header = ['#ItemType', 'デフォルトアイテムタイプ（フル）(15)', 'https://localhost:8443/items/jsonschema/15']

    columns = [('.publish_status', '.PUBLISH_STATUS', '', 'Required', 'private')]
    columns.append(('.metadata.path[0]', '.IndexID[0]', '', 'Allow Multiple', target_index.identifier))
    columns.append(('.pos_index[0]', '.POS_INDEX[0]', '', 'Allow Multiple', target_index.title))
    for i, (download_file_name, download_file_type) in enumerate(download_file_names):
        columns += _generate_file_columns(i, download_file_name, download_file_type)

    file_metadata_items = [item for item in file_metadata['items'] if item['schema'] == schema_id]
    if len(file_metadata_items) == 0:
        raise ValueError(f'Schema not found: {schema_id}')
    file_metadata_item = file_metadata_items[0]
    file_metadata_data = file_metadata_item['data']

    schema = RegistrationSchema.objects.get(_id=schema_id)
    mapping_def = RegistrationMetadataMapping.objects.get(
        registration_schema_id=schema._id,
    )
    logger.debug(f'Mappings: {mapping_def.rules}')
    mappings = _expand_listed_key(mapping_def.rules)

    weko_key_counts = {}
    commonvars = _get_common_variables(file_metadata_data, schema)
    sources = [('file', file_metadata_data)]
    if project_metadata is not None:
        commonvars.update(_get_common_variables(project_metadata, schema, skip_empty=True))
        sources.append(('project', project_metadata))
    for key in sorted(mappings.keys()):
        for source_type, source in sources:
            commonvars['context'] = source_type
            if key not in mappings:
                logger.warning(f'No mappings: {key}')
                continue
            weko_mapping = mappings[key]
            if weko_mapping is None:
                logger.debug(f'No mappings: {key}')
                continue
            source_data = source.get(key, {
                'value': '',
            }) if key != '_' else None
            question_schema = _find_schema_question(schema.schema, key) if key != '_' else None
            if key == '_' or weko_mapping.get('@type', None) == 'string':
                if not _is_column_present(
                    source_data,
                    weko_mapping,
                    commonvars=commonvars,
                    schema=question_schema,
                ):
                    logger.debug(f'Skipped: {key}')
                    continue
                columns += _get_columns(
                    source_data,
                    f'.metadata',
                    weko_mapping,
                    weko_key_counts=weko_key_counts,
                    commonvars=commonvars,
                    schema=question_schema,
                )
                continue
            if weko_mapping['@type'] != 'jsonarray':
                raise ValueError(f'Unexpected type: {weko_mapping["@type"]}')
            value = source_data.get('value', '')
            jsonarray = json.loads(value) if len(value) > 0 else []
            for jsonelement in jsonarray:
                columns += _get_columns(
                    {
                        'object': jsonelement,
                    },
                    f'.metadata',
                    weko_mapping,
                    weko_key_counts=weko_key_counts,
                    commonvars=commonvars,
                    schema=question_schema,
                )

    columns += columns_default
    logger.debug(f'Columns: {columns}')

    cf = csv.writer(f)
    cf.writerow(header)
    cf.writerow([c for c, _, _, _, _ in columns])
    cf.writerow([c for _, c, _, _, _ in columns])
    cf.writerow([c for _, _, c, _, _ in columns])
    cf.writerow([c for _, _, _, c, _ in columns])
    cf.writerow([c for _, _, _, _, c in columns])

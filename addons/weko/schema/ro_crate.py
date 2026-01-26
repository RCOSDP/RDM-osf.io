import json
import logging
import re
from copy import deepcopy
from urllib.parse import urlparse

from osf.models.metaschema import RegistrationSchema

from .base import (
    expand_listed_key, get_sources_for_key, find_schema_question, is_special_key, is_key_present, get_value, resolve_array_index
)
from .constants_mebyo import MEBYO_SCHEMA_NAME
from .ro_crate_mebyo import generate_dataset_metadata, get_weko_item_id


logger = logging.getLogger(__name__)


def _set_object_value(dest_object, key, value):
    logger.debug(f'SET {key} = {value}, target={dest_object}')
    key = key.lstrip('.')
    m = re.match(r'([^\.]+)\[([^]]+)\](\..+)?', key)
    if m:
        # Array
        key = m.group(1)
        index = m.group(2)
        subkey = m.group(3)
        if key not in dest_object:
            dest_object[key] = []
        else:
            if not isinstance(dest_object[key], list):
                raise ValueError(f'{key} is not an array')
        if not re.match(r'^[0-9]+$', index):
            raise ValueError(f'Invalid array index: {index}')
        index = int(index)
        current = len(dest_object[key])
        for i in range(current, index + 1):
            dest_object[key].append(None)
        if not subkey:
            dest_object[key][index] = value
            return
        if dest_object[key][index] is None:
            dest_object[key][index] = {}
        _set_object_value(dest_object[key][index], subkey.lstrip('.'), value)
        return
    m = re.match(r'([^\.]+)(\..+)?', key)
    if not m:
        raise ValueError(f'Invalid key: {key}')
    key = m.group(1)
    subkey = m.group(2)
    if not subkey:
        dest_object[key] = value
        return
    if key not in dest_object:
        dest_object[key] = {}
    else:
        if not isinstance(dest_object[key], dict):
            raise ValueError(f'{key} is not an object')
    _set_object_value(dest_object[key], subkey.lstrip('.'), value)


def _build_value(dest_object, full_key, value, weko_key_counts=None):
    if f'{full_key}.__value__' in weko_key_counts:
        if weko_key_counts[f'{full_key}.__value__'] != value:
            key_value = weko_key_counts[f'{full_key}.__value__']
            raise ValueError(f'Different values to the same key are detected: {value}, {key_value}')
        logger.debug(f'Skipped duplicated item: {full_key}')
        return []
    weko_key_counts[f'{full_key}.__value__'] = value
    _set_object_value(dest_object, full_key, value)


def _build_values(dest_object, file_metadata, weko_key_prefix, weko_props, weko_key_counts=None, commonvars=None, schema=None):
    if isinstance(weko_props, str):
        value = get_value(file_metadata, weko_props, commonvars=commonvars, schema=schema)
        _build_value(dest_object, weko_key_prefix, value, weko_key_counts=weko_key_counts)
        return
    for key in sorted(weko_props.keys()):
        items = weko_props[key]
        if key.startswith('@'):
            continue
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if not is_key_present(file_metadata, item, commonvars=commonvars, schema=schema):
                continue
            full_key = resolve_array_index(weko_key_counts, f'{weko_key_prefix}.{key}')
            if isinstance(item, dict):
                # Subitem
                _build_values(
                    dest_object,
                    file_metadata,
                    full_key,
                    item,
                    weko_key_counts=weko_key_counts,
                    commonvars=commonvars,
                    schema=schema,
                )
                continue
            value = get_value(file_metadata, item, commonvars=commonvars, schema=schema)
            _build_value(dest_object, full_key, value, weko_key_counts=weko_key_counts)


def is_json_array_of_dicts(val):
    if isinstance(val, str) and val.startswith('[') and val.endswith(']'):
        try:
            parsed = json.loads(val)
            return isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed)
        except json.JSONDecodeError:
            return False
    return False


def normalize_base_id(base_id):
    return re.sub(r'\d+$', '', base_id)


def simplify_subitem(data, field_name, key_name, base_id, lang, cnt):
    if field_name in data:
        try:
            subitems = json.loads(data[field_name])
            if isinstance(subitems, list) and subitems:
                new_entries = []
                for i, sub in enumerate(subitems, start=1):
                    cnt += 1

                    if str(lang) == '':
                        new_entry = {
                            '@id': f'{base_id}{cnt}',
                            '@type': sub.get('@type', 'PropertyValue'),
                            'value': sub.get(key_name, '')
                        }
                    else:
                        new_entry = {
                            '@id': f'{base_id}{cnt}',
                            '@type': sub.get('@type', 'PropertyValue'),
                            'language': sub.get('language', lang),
                            'value': sub.get(key_name, '')
                        }

                    new_entries.append(new_entry)
                return new_entries, cnt
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning('Could not parse %s: %s', field_name, exc)
    return [], cnt


def _flatten_json_ld_root(object, counts=None):
    entities = []
    if counts is None:
        counts = {}

    root_data = object.get('root', {})
    affiliationInx = 0
    emailCnt = 0
    nameCnt = 0
    keywordCnt = 0
    for key, values in root_data.items():
        if isinstance(values, list):
            clone = values.copy()
            for item in values:

                if '@id' in item:
                    root_raw_id = item.get('@id')
                    root_base_id = normalize_base_id(root_raw_id)
                    if 'affiliation' in item:
                        affiliationCnt = 0
                        parent_raw_id = item['@id']
                        parent_base_id = normalize_base_id(parent_raw_id)
                        simplified_affiliations = []
                        affiliations_final_values = []
                        iCnt = 0

                        for affiliation_entry in item['affiliation']:
                            raw_id = affiliation_entry['@id']
                            base_id = normalize_base_id(raw_id)
                            lang = affiliation_entry['language']

                            entries, affiliationCnt = simplify_subitem(
                                affiliation_entry, 'subitem_belonging', 'belonging', base_id, lang, affiliationCnt
                            )
                            simplified_affiliations.extend(entries)

                            entries, affiliationCnt = simplify_subitem(
                                affiliation_entry, 'subitem_belonging_en', 'belonging-en', base_id, lang, affiliationCnt
                            )
                            simplified_affiliations.extend(entries)

                        for iCnt in range(1, (len(simplified_affiliations) // 2) + 1):
                            sorted_values = []
                            ja_index = iCnt - 1
                            en_index = ja_index + len(simplified_affiliations) // 2
                            affiliationInx += 1

                            if en_index < len(simplified_affiliations):
                                sorted_values.append(simplified_affiliations[ja_index])
                                sorted_values.append(simplified_affiliations[en_index])

                                new_entry = {
                                    '@id': 'Organization' + str(affiliationInx),
                                    '@type': 'Organization',
                                    'name': sorted_values
                                }
                                affiliations_final_values.append(new_entry)

                        item['affiliation'] = affiliations_final_values

                        i = 0
                        while (i < len(affiliations_final_values)):
                            array_format = [affiliations_final_values[i]]
                            if i == 0:
                                clone[i]['@id'] = root_base_id + str(i + 1)
                                clone[i]['affiliation'] = array_format
                            else:
                                new_entry = clone[0].copy()
                                new_entry['@id'] = root_base_id + str(i + 1)
                                new_entry['affiliation'] = array_format
                                clone.append(new_entry)
                            i += 1

                    if 'email' in item:
                        simplified_emails = []
                        for email_entry in item['email']:
                            raw_id = email_entry['@id']
                            base_id = normalize_base_id(raw_id)
                            entries, emailCnt = simplify_subitem(
                                email_entry, 'subitem_contact', 'contact', base_id, '', emailCnt
                            )
                            simplified_emails.extend(entries)
                        item['email'] = simplified_emails

                        i = 0
                        while (i < len(simplified_emails)):
                            array_format = array_format = [simplified_emails[i]]
                            clone[i]['email'] = array_format
                            i += 1

                    if 'name' in item:
                        simplified_names = []
                        final_values = []
                        for name_entry in item['name']:
                            raw_id = name_entry['@id']
                            base_id = normalize_base_id(raw_id)

                            lang = name_entry['language']

                            entries, nameCnt = simplify_subitem(
                                name_entry, 'subitem_name', 'name', base_id, lang, nameCnt
                            )
                            simplified_names.extend(entries)

                            entries, nameCnt = simplify_subitem(
                                name_entry, 'subitem_name_en', 'name-en', base_id, lang, nameCnt
                            )
                            simplified_names.extend(entries)

                        for iCnt in range(1, (len(simplified_names) // 2) + 1):
                            sorted_values = []
                            ja_index = iCnt - 1
                            en_index = ja_index + len(simplified_names) // 2

                            if en_index < len(simplified_names):
                                sorted_values.append(simplified_names[ja_index])
                                sorted_values.append(simplified_names[en_index])

                                final_values.append(sorted_values)

                        item['name'] = final_values

                        i = 0
                        while (i < len(final_values)):
                            clone[i]['name'] = final_values[i]
                            i += 1

                    if 'keywords' in item:
                        parent_raw_id = item['@id']
                        parent_base_id = normalize_base_id(parent_raw_id)
                        simplified_values = []
                        final_values = []
                        iCnt = 0

                        for value_entry in item['keywords']:
                            raw_id = value_entry['@id']
                            base_id = normalize_base_id(raw_id)
                            lang = value_entry['language']
                            entries, keywordCnt = simplify_subitem(
                                value_entry, 'subitem_filename', 'filename', base_id, lang, keywordCnt
                            )
                            simplified_values.extend(entries)

                            entries, keywordCnt = simplify_subitem(
                                value_entry, 'subitem_filename_en', 'filename-en', base_id, lang, keywordCnt
                            )
                            simplified_values.extend(entries)

                        for iCnt in range(1, (len(simplified_values) // 2) + 1):
                            sorted_values = []
                            ja_index = iCnt - 1
                            en_index = ja_index + len(simplified_values) // 2

                            if en_index < len(simplified_values):
                                sorted_values.append(simplified_values[ja_index])
                                sorted_values.append(simplified_values[en_index])

                                new_entry = {
                                    '@id': f'{parent_base_id}{iCnt}',
                                    '@type': item.get('@type', 'PropertyValue'),
                                    'value': sorted_values
                                }

                                final_values.append(new_entry)
                        root_data['rdm:keywords'] = final_values

                    if 'subitem_filename' in item:
                        try:
                            subitems = json.loads(item['subitem_filename'])
                        except (TypeError, ValueError) as exc:
                            logger.warning('Could not parse subitem_filename: %s', exc)
                        else:
                            if isinstance(subitems, list) and subitems:
                                new_entries = []
                                for i, sub in enumerate(subitems, start=1):
                                    new_entry = {
                                        '@id': f'{root_base_id}{i}',
                                        '@type': item.get('@type', 'PropertyValue'),
                                        'value': sub.get('filename', '')
                                    }
                                    new_entries.append(new_entry)
                                root_data[key] = new_entries

                # analysisType 特殊対応
                if key == 'ams:analysisType' and len(values) == 1:
                    parent_raw_id = values[0]['@id']
                    parent_base_id = normalize_base_id(parent_raw_id)
                    final_values = []
                    iCnt = 0

                    for iCnt, value_str in enumerate(values[0]['value'], start=1):
                        new_entry = {
                            '@id': f'{parent_base_id}{iCnt}',
                            '@type': values[0].get('@type', 'PropertyValue'),
                            'value': value_str
                        }

                        final_values.append(new_entry)
                    root_data[key] = final_values

            if key == 'creator' or key == 'contributor':
                root_data[key] = clone

    for key, entity in object.items():
        if isinstance(entity, list):
            for e in entity:
                if '@id' not in e and '@type' not in e:
                    continue
                if '@id' not in e:
                    e['@id'] = _generate_json_ld_id(e, counts)
                entities += _flatten_json_ld(e, counts)
            continue
        if '@id' not in entity:
            continue
        entities += _flatten_json_ld(entity, counts)
    return sorted(entities, key=lambda x: x['@id'])


def _generate_json_ld_id(entity, counts):
    type_name = entity['@type']
    if isinstance(type_name, list):
        type_name = type_name[0]
    type_name = type_name.replace(':', '_')
    if type_name not in counts:
        counts[type_name] = 0
    counts[type_name] += 1
    return f'_:{type_name}{counts[type_name]}'


def _is_reference(value):
    if not isinstance(value, dict):
        return False
    keys = list(value.keys())
    return len(keys) == 1 and keys[0] == '@id'


def _is_literal(value):
    if isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, list):
        return all([isinstance(v, str) for v in value])


def _flatten_json_ld(object, counts):
    flattened_object = {}
    entities = [flattened_object]
    for key, value in object.items():
        if _is_literal(value) or _is_reference(value):
            flattened_object[key] = value
            continue
        if key in ['@id', '@type']:
            flattened_object[key] = value
            continue
        if isinstance(value, dict):
            if '@type' not in value:
                continue

            entity_id = value.get('@id', _generate_json_ld_id(value, counts))
            new_value = dict(value)
            new_value['@id'] = entity_id

            entities += _flatten_json_ld(new_value, counts)
            flattened_object[key] = {'@id': entity_id}
            continue
        if isinstance(value, list):
            new_value = []
            for v in value:
                if not isinstance(v, dict):
                    continue

                if _is_reference(v) or _is_literal(v):
                    new_value.append(v)
                    continue

                if '@type' not in v:
                    continue

                entity_id = v.get('@id', _generate_json_ld_id(v, counts))

                new_v = dict(v)
                new_v['@id'] = entity_id

                entities += _flatten_json_ld(new_v, counts)
                new_value.append({'@id': entity_id})

            flattened_object[key] = new_value
            continue
    return entities


def _collect_graph_entities(object):
    graph = []
    root = object.get('root')
    if root:
        graph.append(root)
    for key, value in object.items():
        if key == 'root':
            continue
        if isinstance(value, list):
            graph.extend(value)
        else:
            graph.append(value)
    return graph


def _build_hierarchical_object(user, target_index, file_metadata, download_file_names, project_metadatas, schema, mappings, node_id):
    weko_key_counts = {}
    hierarchical_object = {}
    for key in sorted(mappings.keys()):
        for source, commonvars in get_sources_for_key(
            user, target_index, file_metadata, download_file_names, project_metadatas, schema, key
        ):

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

            question_schema = find_schema_question(schema.schema, key) if not is_special_key(key) else None
            if key == '_' or weko_mapping.get('@type', None) == 'string':
                if not is_key_present(
                    source_data,
                    weko_mapping,
                    commonvars=commonvars,
                    schema=question_schema,
                ):
                    logger.debug(f'Skipped: {key}')
                    continue
                _build_values(
                    hierarchical_object,
                    source_data,
                    '',
                    weko_mapping,
                    weko_key_counts=weko_key_counts,
                    commonvars=commonvars,
                    schema=question_schema,
                )
                continue
            if weko_mapping['@type'] in ['array', 'jsonarray']:
                value = source_data.get('value', '')
                if weko_mapping['@type'] == 'jsonarray':
                    if value is None or not isinstance(value, str):
                        logger.warn(f'Unexpected value: {value}, {key}')
                        continue
                    jsonarray = json.loads(value) if value is not None and len(value) > 0 else []
                else:
                    if value is None or not isinstance(value, list):
                        logger.warn(f'Unexpected value: {value}, {key}')
                        continue
                    jsonarray = value if value is not None else []
                for i, jsonelement in enumerate(jsonarray):
                    target_data = {
                        'object': jsonelement,
                    }
                    if not is_key_present(
                        target_data,
                        weko_mapping,
                        commonvars=commonvars,
                        schema=question_schema,
                    ):
                        logger.debug(f'Skipped: {key}[{i}]')
                        continue
                    _build_values(
                        hierarchical_object,
                        target_data,
                        '',
                        weko_mapping,
                        weko_key_counts=weko_key_counts,
                        commonvars=commonvars,
                        schema=question_schema,
                    )
                continue
            if weko_mapping['@type'] in ['object', 'jsonobject']:
                value = source_data.get('value', '')
                if 'choose-additional-metadata' in value:
                    url = value['choose-additional-metadata']
                    value_data = json.loads(url['value'])
                    file_path = value_data[0]['path']
                    file_name = file_path.split('/')[-1]
                    for item in value_data:
                        item['path'] = item['path'].replace('osfstorage/', '')
                    url['value'] = file_name
                    value['choose-additional-metadata'] = url
                if 'absolute_url' in value:
                    url = value['absolute_url']
                    parsed_url = urlparse(url)
                    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}'
                    value['absolute_url'] = str(base_url) + '/' + str(node_id) + '/'
                if weko_mapping['@type'] == 'jsonobject':
                    if value is None or not isinstance(value, str):
                        logger.warn(f'Unexpected value: {value}, {key}')
                        continue
                    jsonobject = json.loads(value) if value is not None and len(value) > 0 else {}
                else:
                    if value is None or not isinstance(value, dict):
                        logger.warn(f'Unexpected value: {value}, {key}')
                        continue
                    jsonobject = value if value is not None else {}
                target_data = {
                    'object': jsonobject,
                }
                if not is_key_present(
                    target_data,
                    weko_mapping,
                    commonvars=commonvars,
                    schema=question_schema,
                ):
                    logger.debug(f'Skipped: {key}')
                    continue
                _build_values(
                    hierarchical_object,
                    target_data,
                    '',
                    weko_mapping,
                    weko_key_counts=weko_key_counts,
                    commonvars=commonvars,
                    schema=question_schema,
                )
                continue
            raise ValueError(f'Unexpected type: {weko_mapping["@type"]}')
    return hierarchical_object


def _prepare_file_metadata_entries(file_metadatas, download_file_names, schema_id):
    entries = []
    for metadata, downloads in zip(file_metadatas, download_file_names):
        items = [item for item in metadata['items'] if item['schema'] == schema_id]
        if len(items) == 0:
            raise ValueError(f'Schema not found: {metadata}, {schema_id}')
        key_data = items[0]['data']
        file_type = key_data.get('grdm-file:file-type', {}).get('value', '')
        entries.append({
            'file_metadata': metadata,
            'download_file_names': downloads,
            'file_type': file_type,
        })
    return entries

def write_ro_crate_json(user, f, target_index, download_file_names, schema_id, file_metadatas, project_metadatas, node_id, flatten=True, base_host=None):
    from ..models import RegistrationMetadataMapping

    schema = RegistrationSchema.objects.get(_id=schema_id)
    mapping_def = RegistrationMetadataMapping.objects.filter(
        registration_schema_id=schema._id,
        filename='ro-crate-metadata.json',
    ).first()
    if mapping_def is None:
        raise ValueError(f'No mapping definition: {schema_id}')
    logger.debug(f'Mappings: {mapping_def.rules}')
    for i, file_metadata in enumerate(file_metadatas):
        logger.debug(f'File metadata #{i}: {file_metadata}')
    for i, project_metadata in enumerate(project_metadatas):
        logger.debug(f'Project metadata #{i}: {project_metadata}')

    mappings = expand_listed_key(mapping_def.rules)
    entries = _prepare_file_metadata_entries(file_metadatas, download_file_names, schema._id)
    allow_empty_files = mapping_def.rules['@metadata']['allow_empty_files']
    if not entries:
        if not allow_empty_files:
            raise ValueError('No file metadata available to build RO-Crate dataset')
        # Create a dummy entry to allow processing with project metadata only
        entries = [{
            'file_metadata': {'items': [{'schema': schema._id, 'data': {}}]},
            'download_file_names': [],
            'file_type': '',
        }]

    should_split = len(entries) > 1

    graph_entities = []
    counts = {}
    dataset_records = []
    ro_crate_metadata_entity = None
    for index, entry in enumerate(entries):
        entry_object = _build_hierarchical_object(
            user,
            target_index,
            entry['file_metadata'],
            entry['download_file_names'],
            project_metadatas,
            schema,
            mappings,
            node_id,
        )

        root_id = f'#dataset-{index + 1}' if should_split else './'
        root = entry_object.get('root')
        if root is not None:
            root['@id'] = root_id

        ro_crate_metadata = entry_object.pop('ro_crate_metadata', None)
        if ro_crate_metadata is not None:
            if 'about' in ro_crate_metadata:
                ro_crate_metadata['about']['@id'] = root_id
            if should_split:
                if ro_crate_metadata_entity is None:
                    ro_crate_metadata_entity = deepcopy(ro_crate_metadata)
            else:
                graph_entities.append(ro_crate_metadata)

        files = entry_object.get('file', [])
        for (filename, _), entity in zip(entry['download_file_names'], files):
            # Path relative to ro-crate-metadata.json (located in data/)
            entity['@id'] = f'files/{filename}'

        if flatten:
            entry_entities = _flatten_json_ld_root(entry_object, counts=counts)
        else:
            entry_entities = _collect_graph_entities(entry_object)

        file_ids = [
            entity.get('@id')
            for entity in entry_entities
            if entity.get('@type') == 'File'
        ]
        dataset_entity = next(
            (entity for entity in entry_entities if entity.get('@id') == root_id),
            None,
        )
        assert dataset_entity is not None, f'Dataset entity not generated: {root_id}'
        dataset_records.append({
            'entity': dataset_entity,
            'files': file_ids,
            'root_id': root_id,
            'file_type': entry['file_type'],
        })

        if should_split:
            if file_ids:
                dataset_entity['hasPart'] = [{'@id': file_id} for file_id in file_ids]
        else:
            dataset_entity['wk:isSplited'] = False
            if file_ids:
                existing_parts = dataset_entity.get('hasPart', [])
                dataset_entity['hasPart'] = existing_parts + [{'@id': file_id} for file_id in file_ids]

        graph_entities.extend(entry_entities)

    if should_split:
        for record in dataset_records:
            dataset_entity = record['entity']
            dataset_entity.pop('@type', None)
            dataset_entity.pop('wk:isSplited', None)

        aggregator = {'@id': './', '@type': 'Dataset', 'wk:isSplited': True}

        shared_candidate_keys = {'name', 'description', 'datePublished'}
        shared_candidate_keys.update(
            key
            for record in dataset_records
            for key in record['entity'].keys()
            if key.startswith('wk:') and key != 'wk:isSplited'
        )

        def _is_empty_value(value):
            return value in (None, '', [], {})

        for key in sorted(shared_candidate_keys):
            values = [record['entity'].get(key) for record in dataset_records]
            non_empty_values = [value for value in values if not _is_empty_value(value)]
            if not non_empty_values:
                continue
            reference = non_empty_values[0]
            if all(value == reference or _is_empty_value(value) for value in values):
                aggregator[key] = deepcopy(reference)

        aggregator['hasPart'] = [
            {'@id': record['entity']['@id']}
            for record in dataset_records
        ]

        manuscripts = [r for r in dataset_records if r['file_type'] == 'manuscript']
        datasets = [r for r in dataset_records if r['file_type'] != 'manuscript']

        item_link_counter = 0
        for manuscript in manuscripts:
            links = []
            for dataset in datasets:
                item_link_counter += 1
                link_id = f'_:itemLink{item_link_counter}'
                link_entity = {
                    '@id': link_id,
                    '@type': 'PropertyValue',
                    'value': 'isSupplementedBy',
                    'identifier': dataset['root_id']
                }
                graph_entities.append(link_entity)
                links.append({'@id': link_id})
            if links:
                manuscript['entity']['wk:itemLinks'] = links

        for dataset in datasets:
            links = []
            for manuscript in manuscripts:
                item_link_counter += 1
                link_id = f'_:itemLink{item_link_counter}'
                link_entity = {
                    '@id': link_id,
                    '@type': 'PropertyValue',
                    'value': 'isSupplementTo',
                    'identifier': manuscript['root_id']
                }
                graph_entities.append(link_entity)
                links.append({'@id': link_id})
            if links:
                dataset['entity']['wk:itemLinks'] = links

        assert ro_crate_metadata_entity is not None, 'ro-crate-metadata.json entity not found'
        ro_crate_metadata_entity['about']['@id'] = './'
        graph_entities.append(aggregator)
        graph_entities.append(ro_crate_metadata_entity)

    json_ld = {
        '@context': [
            'https://w3id.org/ro/crate/1.1/context',
            'http://purl.org/wk/v1/wk-context.jsonld',
            {
                'ams:analysisType': 'https://purl.org/rdm/ontology/analysisType',
                'ams:descriptionOfExperimentalCondition': 'https://purl.org/rdm/ontology/descriptionOfExperimentalCondition',
                'ams:purposeOfExperiment': 'https://purl.org/rdm/ontology/purposeOfExperiment',
                'ams:analysisOtherType': 'https://purl.org/rdm/ontology/analysisOtherType',
                'ams:anonymousProcessing': 'https://purl.org/rdm/ontology/anonymousProcessing',
                'ams:availabilityOfCommercialUse': 'https://purl.org/rdm/ontology/availabilityOfCommercialUse',
                'ams:conflictOfInterest': 'https://purl.org/rdm/ontology/conflictOfInterest',
                'ams:conflictOfInterestName': 'https://purl.org/rdm/ontology/conflictOfInterestName',
                'ams:consentForProvisionToAThirdParty': 'https://purl.org/rdm/ontology/consentForProvisionToAThirdParty',
                'ams:dataPolicyFree': 'https://purl.org/rdm/ontology/dataPolicyFree',
                'ams:descriptionOfExperimentalCondition': 'https://purl.org/rdm/ontology/descriptionOfExperimentalCondition',
                'ams:ethicsReviewCommitteeApproval': 'https://purl.org/rdm/ontology/ethicsReviewCommitteeApproval',
                'ams:icIsNo': 'https://purl.org/rdm/ontology/icIsNo',
                'ams:identifier': 'https://purl.org/rdm/ontology/identifier',
                'ams:industrialUse': 'https://purl.org/rdm/ontology/industrialUse',
                'ams:informedConsent': 'https://purl.org/rdm/ontology/informedConsent',
                'ams:license': 'https://purl.org/rdm/ontology/license',
                'ams:namesToBeIncludedInTheAcknowledgments': 'https://purl.org/rdm/ontology/namesToBeIncludedInTheAcknowledgments',
                'ams:necessityOfContactAndPermission': 'https://purl.org/rdm/ontology/necessityOfContactAndPermission',
                'ams:necessityOfIncludingInAcknowledgments': 'https://purl.org/rdm/ontology/necessityOfIncludingInAcknowledgments',
                'ams:otherConditionsOrSpecialNotes': 'https://purl.org/rdm/ontology/otherConditionsOrSpecialNotes',
                'ams:overseasOfferings': 'https://purl.org/rdm/ontology/overseasOfferings',
                'ams:projectId': 'https://purl.org/rdm/ontology/projectId',
                'ams:purposeOfExperiment': 'https://purl.org/rdm/ontology/purposeOfExperiment',
                'ams:repository': 'https://purl.org/rdm/ontology/repository',
                'ams:repositoryId': 'https://purl.org/rdm/ontology/repositoryId',
                'ams:repositoryInfo': 'https://purl.org/rdm/ontology/repositoryInfo',
                'ams:targetTypeOfAcquiredData': 'https://purl.org/rdm/ontology/targetTypeOfAcquiredData',
                'ams:existExternalMetadata': 'https://purl.org/rdm/ontology/existExternalMetadata',
                'ams:externalMetadataFiles': 'https://purl.org/rdm/ontology/externalMetadataFiles',
                'rdm:Dataset': 'https://purl.org/rdm/ontology/Dataset',
                'rdm:AccessRights': 'https://purl.org/rdm/ontology/AccessRights',
                'rdm:MetadataDocument': 'https://purl.org/rdm/ontology/MetadataDocument',
                'rdm:field': 'https://purl.org/rdm/ontology/field',
                'rdm:keywords': 'https://purl.org/rdm/ontology/keywords',
                'rdm:metadataFiles': 'https://purl.org/rdm/ontology/metadataFiles',
                'rdm:project': 'https://purl.org/rdm/ontology/project',
                'rdm:name': 'https://purl.org/rdm/ontology/name',
                'dc:type': 'http://purl.org/dc/elements/1.1/type',
                'jpcoar:addtionalType': 'https://github.com/JPCOAR/schema/blob/master/2.0/#addtionalType'
            },
            {
                'ams': 'https://purl.org/rdm/ontology/'
            },
            {
                'wk': 'https://purl.org/rdm/ontology/'
            },
            {
                'rdm': 'https://purl.org/rdm/ontology/'
            },
            {
                'odrl': 'http://www.w3.org/ns/odrl.jsonld'
            },
            {
                'dc': 'http://purl.org/dc/elements/1.1/'
            },
            {
                'jpcoar': 'https://github.com/JPCOAR/schema/blob/master/2.0/'
            },
            {
                'datacite': 'http://datacite.org/schema/kernel-4'
            }
        ],
        '@graph': graph_entities,
    }

    # 未病スキーマ　データセットメタデータ・ファイルメタデータ対応
    if mapping_def.rules['@metadata'].get('schemaname') == MEBYO_SCHEMA_NAME:
        entity_list, properties = generate_dataset_metadata(project_metadatas)
        json_ld['@graph'].extend(entity_list)
        match = next((d for d in json_ld['@graph'] if d.get('@id') == './'), None)
        match.update(properties)

        # 未病スキーマ アイテムの更新用プロパティ追加
        weko_item_id = get_weko_item_id(project_metadatas)
        if weko_item_id and base_host:
            match.update(
                {
                    'wk:editMode': 'Upgrade',
                    'uri': f'{base_host}records/{weko_item_id}',
                    'identifier': f'{weko_item_id}'
                }
            )

    logger.debug(f'Generated RO-Crate: {json.dumps(json_ld, ensure_ascii=False)}')
    json.dump(json_ld, f, indent=2, ensure_ascii=False)

import csv
import json
import logging
import re


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

def _generate_file_columns(index, download_file_name):
    columns = []
    columns.append((f'.file_path[{index}]', f'.ファイルパス[{index}]', '', 'Allow Multiple', download_file_name))
    base_item = f'.metadata.item_1617605131499[{index}]'
    base_file = f'File[{index}]'
    columns.append((f'{base_item}.filename', f'{base_file}.表示名', '', 'Allow Multiple', download_file_name))
    columns.append((f'{base_item}.accessrole', f'{base_file}.アクセス', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.date[0].dateType', f'{base_file}.オープンアクセスの日付[0].日付タイプ', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.date[0].dateValue', f'{base_file}.オープンアクセスの日付[0].日付', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.displaytype', f'{base_file}.表示形式', '', 'Allow Multiple', 'simple'))
    columns.append((f'{base_item}.fileDate[0].fileDateType', f'{base_file}.日付[0].日付タイプ', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.fileDate[0].fileDateValue', f'{base_file}.日付[0].日付', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.filesize[0].value', f'{base_file}.サイズ[0].サイズ', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.format', f'{base_file}.フォーマット', '', 'Allow Multiple', 'text/plain'))
    columns.append((f'{base_item}.groups', f'{base_file}.グループ', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.licensefree', f'{base_file}.自由ライセンス', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.licensetype', f'{base_file}.ライセンス', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.url.label', f'{base_file}.本文URL.ラベル', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.url.objectType', f'{base_file}.本文URL.オブジェクトタイプ', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.url.url', f'{base_file}.本文URL.本文URL', '', 'Allow Multiple', ''))
    columns.append((f'{base_item}.version', f'{base_file}.バージョン情報', '', 'Allow Multiple', ''))
    return columns

mapping_table = {'pubdate': 'pubdate',
    'item_1617186331708[].subitem_1551255647225': 'Title',
    'item_1617186331708[].subitem_1551255648112': {'type': 'language',
    'keys': ['Title']},
    'item_1617186385884[].subitem_1551255720400': 'Alternative Title',
    'item_1617186385884[].subitem_1551255721061': {'type': 'language',
    'keys': ['Alternative Title']},
    'item_1617186419668[]': {
    'type': 'file-creators',
    'key': 'Creator',
    'items': {
        'nameIdentifiers[0].nameIdentifierScheme': {'type': 'const', 'value': ''},
        'nameIdentifiers[0].nameIdentifierURI': {'type': 'const', 'value': ''},
        'nameIdentifiers[0].nameIdentifier': {'type': 'const', 'value': ''},
        'creatorNames[0].creatorName': {'type': 'jsonproperty', 'key': 'Creator', 'value': 'name_ja'},
        'creatorNames[0].creatorNameLang': {'type': 'const', 'value': 'ja'},
        'creatorNames[1].creatorName': {'type': 'jsonproperty', 'key': 'Creator', 'value': 'name_en'},
        'creatorNames[1].creatorNameLang': {'type': 'const', 'value': 'en'},
        'familyNames[0].familyName': {'type': 'const', 'value': ''},
        'familyNames[0].familyNameLang': {'type': 'const', 'value': ''},
        'givenNames[0].givenName': {'type': 'const', 'value': ''},
        'givenNames[0].givenNameLang': {'type': 'const', 'value': ''},
        'creatorAlternatives[0].creatorAlternative': {'type': 'const', 'value': ''},
        'creatorAlternatives[0].creatorAlternativeLang': {'type': 'const',
        'value': ''},
        'creatorMails[0].creatorMail': {'type': 'const', 'value': ''},
        'creatorAffiliations[0].affiliationNameIdentifiers[0].affiliationNameIdentifier': {'type': 'const',
        'value': ''},
        'creatorAffiliations[0].affiliationNameIdentifiers[0].affiliationNameIdentifierScheme': {'type': 'const',
        'value': ''},
        'creatorAffiliations[0].affiliationNameIdentifiers[0].affiliationNameIdentifierURI': {'type': 'const',
        'value': ''},
        'creatorAffiliations[0].affiliationNames[0].affiliationName': {'type': 'const',
        'value': ''},
        'creatorAffiliations[0].affiliationNames[0].affiliationNameLang': {'type': 'const',
        'value': ''}
    }
    },
    'item_1617349709064[]': {
    'type': 'file-creators',
    'key': 'Contributor',
    'items': {
        'contributorType': {'type': 'const', 'value': ''},
        'nameIdentifiers[0].nameIdentifierScheme': {'type': 'const', 'value': ''},
        'nameIdentifiers[0].nameIdentifierURI': {'type': 'const', 'value': ''},
        'nameIdentifiers[0].nameIdentifier': {'type': 'const', 'value': ''},
        'contributorNames[0].contributorName': {'type': 'jsonproperty', 'key': 'Contributor', 'value': 'name_ja'},
        'contributorNames[0].lang': {'type': 'const', 'value': 'ja'},
        'contributorNames[1].contributorName': {'type': 'jsonproperty', 'key': 'Contributor', 'value': 'name_en'},
        'contributorNames[1].lang': {'type': 'const', 'value': 'en'},
        'familyNames[0].familyName': {'type': 'const', 'value': ''},
        'familyNames[0].familyNameLang': {'type': 'const', 'value': ''},
        'givenNames[0].givenName': {'type': 'const', 'value': ''},
        'givenNames[0].givenNameLang': {'type': 'const', 'value': ''},
        'creatorAlternatives[0].creatorAlternative': {'type': 'const', 'value': ''},
        'creatorAlternatives[0].creatorAlternativeLang': {'type': 'const',
        'value': ''},
        'contributorAlternatives[0].contributorAlternative': {'type': 'const',
        'value': ''},
        'contributorAlternatives[0].contributorAlternativeLang': {'type': 'const',
        'value': ''},
        'contributorAffiliations[0].contributorAffiliationNameIdentifiers[0].contributorAffiliationNameIdentifier': {'type': 'const',
        'value': ''},
        'contributorAffiliations[0].contributorAffiliationNameIdentifiers[0].contributorAffiliationScheme': {'type': 'const',
        'value': ''},
        'contributorAffiliations[0].contributorAffiliationNameIdentifiers[0].contributorAffiliationURI': {'type': 'const',
        'value': ''},
        'contributorAffiliations[0].contributorAffiliationNames[0].contributorAffiliationName': {'type': 'const',
        'value': ''},
        'contributorAffiliations[0].contributorAffiliationNames[0].contributorAffiliationNameLang': {'type': 'const',
        'value': ''},
        'contributorMails[0].contributorMail': {'type': 'const', 'value': ''}
    }
    },
    'item_1617186476635.subitem_1522299639480': 'アクセス権',
    'item_1617351524846.subitem_1523260933860': 'APC',
    'item_1617186499011[].subitem_1522650727486': 'Rights.権利情報Resource',
    'item_1617186499011[].subitem_1522651041219': 'Rights.権利情報',
    'item_1617186499011[].subitem_1522650717957': {'type': 'language',
    'keys': ['Rights.権利情報Resource', 'Rights.権利情報']},
    'item_1617610673286[].nameIdentifiers[0].nameIdentifierScheme': 'Rights Holder.nameIdentifiers.nameIdentifierScheme',
    'item_1617610673286[].nameIdentifiers[0].nameIdentifierURI': 'Rights Holder.nameIdentifiers.nameIdentifierURI',
    'item_1617610673286[].nameIdentifiers[0].nameIdentifier': 'Rights Holder.nameIdentifiers.nameIdentifier',
    'item_1617610673286[].rightHolderNames[0].rightHolderLanguage': 'Rights Holder.rightHolderNames.rightHolderLanguage',
    'item_1617610673286[].rightHolderNames[0].rightHolderName': 'Rights Holder.rightHolderNames.rightHolderName',
    'item_1617186609386[].subitem_1522300014469': 'Subject.主題Scheme',
    'item_1617186609386[].subitem_1522300048512': 'Subject.主題URI',
    'item_1617186609386[].subitem_1523261968819': 'Subject.主題',
    'item_1617186609386[].subitem_1522299896455': {'type': 'language',
    'keys': ['Subject.主題Scheme', 'Subject.主題URI', 'Subject.主題']},
    'item_1617186626617[].subitem_description_type': 'Description.subitem_description_type',
    'item_1617186626617[].subitem_description': 'Description.subitem_description',
    'item_1617186626617[].subitem_description_language': {'type': 'language',
    'keys': ['Description.subitem_description_type',
    'Description.subitem_description']},
    'item_1617186643794[].subitem_1522300316516': '出版者',
    'item_1617186643794[].subitem_1522300295150': {'type': 'language',
    'keys': ['出版者']},
    'item_1617186660861[].subitem_1522300695726': 'Date.日付タイプ',
    'item_1617186660861[].subitem_1522300722591': 'Date.日付',
    'item_1617186702042[].subitem_1551255818386': 'Language',
    'item_1617258105262.resourcetype': 'resourcetype',
    'item_1617349808926.subitem_1523263171732': 'バージョン情報',
    'item_1617265215918.subitem_1522305645492': '出版タイプ',
    'item_1617186783814[].subitem_identifier_uri': 'Identifier.subitem_identifier_uri',
    'item_1617186783814[].subitem_identifier_type': 'Identifier.subitem_identifier_type',
    'item_1617353299429[0].subitem_1522306207484': 'Relation.関連タイプ',
    'item_1617353299429[0].subitem_1522306287251.subitem_1522306382014': 'Relation.関連識別子.識別子タイプ',
    'item_1617353299429[0].subitem_1522306287251.subitem_1522306436033': 'Relation.関連識別子.関連識別子',
    'item_1617353299429[0].subitem_1523320863692[0].subitem_1523320867455': 'Relation.関連名称.言語',
    'item_1617353299429[0].subitem_1523320863692[0].subitem_1523320909613': 'Relation.関連名称.関連名称',
    'item_1617186859717[].subitem_1522658031721': '時間的範囲',
    'item_1617186859717[].subitem_1522658018441': {'type': 'language',
    'keys': ['時間的範囲']},
    'item_1617186882738[0].subitem_geolocation_point.subitem_point_longitude': 'Geo Location.subitem_geolocation_point.subitem_point_longitude',
    'item_1617186882738[0].subitem_geolocation_point.subitem_point_latitude': 'Geo Location.subitem_geolocation_point.subitem_point_latitude',
    'item_1617186882738[0].subitem_geolocation_box.subitem_west_longitude': 'Geo Location.subitem_geolocation_box.subitem_west_longitude',
    'item_1617186882738[0].subitem_geolocation_box.subitem_east_longitude': 'Geo Location.subitem_geolocation_box.subitem_east_longitude',
    'item_1617186882738[0].subitem_geolocation_box.subitem_south_latitude': 'Geo Location.subitem_geolocation_box.subitem_south_latitude',
    'item_1617186882738[0].subitem_geolocation_box.subitem_north_latitude': 'Geo Location.subitem_geolocation_box.subitem_north_latitude',
    'item_1617186882738[0].subitem_geolocation_place[0].subitem_geolocation_place_text': 'Geo Location.subitem_geolocation_place.subitem_geolocation_place_text',
    'item_1617186901218[0].subitem_1522399143519.subitem_1522399281603': 'Funding Reference.助成機関識別子.助成機関識別子タイプ',
    'item_1617186901218[0].subitem_1522399143519.subitem_1522399333375': 'Funding Reference.助成機関識別子.助成機関識別子',
    'item_1617186901218[0].subitem_1522399412622[0].subitem_1522399416691': 'Funding Reference.助成機関名.言語',
    'item_1617186901218[0].subitem_1522399412622[0].subitem_1522737543681': 'Funding Reference.助成機関名.助成機関名',
    'item_1617186901218[0].subitem_1522399571623.subitem_1522399585738': 'Funding Reference.研究課題番号.研究課題URI',
    'item_1617186901218[0].subitem_1522399571623.subitem_1522399628911': 'Funding Reference.研究課題番号.研究課題番号',
    'item_1617186901218[0].subitem_1522399651758[0].subitem_1522721910626': 'Funding Reference.研究課題名.言語',
    'item_1617186901218[0].subitem_1522399651758[0].subitem_1522721929892': 'Funding Reference.研究課題名.研究課題名',
    'item_1617186920753[].subitem_1522646500366': 'Source Identifier.収録物識別子タイプ',
    'item_1617186920753[].subitem_1522646572813': 'Source Identifier.収録物識別子',
    'item_1617186941041[].subitem_1522650091861': '収録物名',
    'item_1617186941041[].subitem_1522650068558': {'type': 'language',
    'keys': ['収録物名']},
    'item_1617186959569.subitem_1551256328147': 'Volume Number',
    'item_1617186981471.subitem_1551256294723': 'Issue Number',
    'item_1617186994930.subitem_1551256248092': 'Number of Pages',
    'item_1617187024783.subitem_1551256198917': 'Page Start',
    'item_1617187045071.subitem_1551256185532': 'Page End',
    'item_1617187056579.bibliographic_titles[0].bibliographic_title': 'Bibliographic Information.bibliographic_titles.bibliographic_title',
    'item_1617187056579.bibliographic_titles[0].bibliographic_titleLang': 'Bibliographic Information.bibliographic_titles.bibliographic_titleLang',
    'item_1617187056579.bibliographicVolumeNumber': 'Bibliographic Information.bibliographicVolumeNumber',
    'item_1617187056579.bibliographicIssueNumber': 'Bibliographic Information.bibliographicIssueNumber',
    'item_1617187056579.bibliographicPageStart': 'Bibliographic Information.bibliographicPageStart',
    'item_1617187056579.bibliographicPageEnd': 'Bibliographic Information.bibliographicPageEnd',
    'item_1617187056579.bibliographicNumberOfPages': 'Bibliographic Information.bibliographicNumberOfPages',
    'item_1617187056579.bibliographicIssueDates.bibliographicIssueDate': 'Bibliographic Information.bibliographicIssueDates.bibliographicIssueDate',
    'item_1617187056579.bibliographicIssueDates.bibliographicIssueDateType': 'Bibliographic Information.bibliographicIssueDates.bibliographicIssueDateType',
    'item_1617187087799.subitem_1551256171004': 'Dissertation Number',
    'item_1617187112279[].subitem_1551256126428': 'Degree Name',
    'item_1617187112279[].subitem_1551256129013': {'type': 'language',
    'keys': ['Degree Name']},
    'item_1617187136212.subitem_1551256096004': 'Date Granted',
    'item_1617944105607[0].subitem_1551256015892[0].subitem_1551256027296': 'Degree Grantor.Degree Grantor Name Identifier.Degree Grantor Name Identifier',
    'item_1617944105607[0].subitem_1551256015892[0].subitem_1551256029891': 'Degree Grantor.Degree Grantor Name Identifier.Degree Grantor Name Identifier Scheme',
    'item_1617944105607[0].subitem_1551256037922[0].subitem_1551256042287': 'Degree Grantor.Degree Grantor Name.Degree Grantor Name',
    'item_1617944105607[0].subitem_1551256037922[0].subitem_1551256047619': 'Degree Grantor.Degree Grantor Name.Language',
    'item_1617187187528[0].subitem_1599711633003[0].subitem_1599711636923': 'Conference.Conference Name.Conference Name',
    'item_1617187187528[0].subitem_1599711633003[0].subitem_1599711645590': 'Conference.Conference Name.Language',
    'item_1617187187528[0].subitem_1599711655652': 'Conference.Conference Sequence',
    'item_1617187187528[0].subitem_1599711660052[0].subitem_1599711680082': 'Conference.Conference Sponsor.Conference Sponsor',
    'item_1617187187528[0].subitem_1599711660052[0].subitem_1599711686511': 'Conference.Conference Sponsor.Language',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711731891': 'Conference.Conference Date.Start Year',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711727603': 'Conference.Conference Date.Start Month',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711712451': 'Conference.Conference Date.Start Day',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711743722': 'Conference.Conference Date.End Year',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711739022': 'Conference.Conference Date.End Month',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711704251': 'Conference.Conference Date.Conference Date',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711735410': 'Conference.Conference Date.End Day',
    'item_1617187187528[0].subitem_1599711699392.subitem_1599711745532': 'Conference.Conference Date.Language',
    'item_1617187187528[0].subitem_1599711758470[0].subitem_1599711769260': 'Conference.Conference Venue.Conference Venue',
    'item_1617187187528[0].subitem_1599711758470[0].subitem_1599711775943': 'Conference.Conference Venue.Language',
    'item_1617187187528[0].subitem_1599711788485[0].subitem_1599711798761': 'Conference.Conference Place.Conference Place',
    'item_1617187187528[0].subitem_1599711788485[0].subitem_1599711803382': 'Conference.Conference Place.Language',
    'item_1617187187528[0].subitem_1599711813532': 'Conference.Conference Country',
    'item_1617620223087[].subitem_1565671169640': 'Heading.Banner Headline',
    'item_1617620223087[].subitem_1565671178623': 'Heading.Subheading',
    'item_1617620223087[].subitem_1565671149650': {'type': 'language',
    'keys': ['Heading.Banner Headline', 'Heading.Subheading']},
    'parentkey.subitem_systemidt_identifier': 'system_identifier_uri.subitem_systemidt_identifier',
    'parentkey.subitem_systemidt_identifier_type': 'system_identifier_uri.subitem_systemidt_identifier_type',
    'parentkey.subitem_systemfile_filename[].subitem_systemfile_filename_label': 'system_file.subitem_systemfile_filename.subitem_systemfile_filename_label',
    'parentkey.subitem_systemfile_filename[].subitem_systemfile_filename_type': 'system_file.subitem_systemfile_filename.subitem_systemfile_filename_type',
    'parentkey.subitem_systemfile_filename[].subitem_systemfile_filename_uri': 'system_file.subitem_systemfile_filename.subitem_systemfile_filename_uri',
    'parentkey.subitem_systemfile_mimetype': 'system_file.subitem_systemfile_mimetype',
    'parentkey.subitem_systemfile_size': 'system_file.subitem_systemfile_size',
    'parentkey.subitem_systemfile_datetime[].subitem_systemfile_datetime_date': 'system_file.subitem_systemfile_datetime.subitem_systemfile_datetime_date',
    'parentkey.subitem_systemfile_datetime[].subitem_systemfile_datetime_type': 'system_file.subitem_systemfile_datetime.subitem_systemfile_datetime_type',
    'parentkey.subitem_systemfile_version': 'system_file.subitem_systemfile_version'
}

def _get_metadata_value(file_metadata_data, item, lang, index):
    assert 'type' in item, item
    if item['type'] == 'const':
        return item['value']
    key = f'grdm-file:{item["key"]}'
    if lang is not None:
        key += f'.{lang}'
    value = file_metadata_data[key]['value']
    if item['type'] == 'property':
        return value
    if item['type'] == 'jsonproperty':
        logger.info(f'jsonproperty: {value}')
        return json.loads(value)[index][item['value']]
    raise KeyError(item['type'])

def _get_item_indices(file_metadata_data, item):
    if 'jsonarray_key' in item:
        value = _get_metadata_value(file_metadata_data, {
            'type': 'property',
            'key': item['jsonarray_key'],
        }, None, None)
        if value == '':
            return 0
        return len(json.loads(value))
    return 1

def _get_item_metadata_key(key):
    if key.endswith('[]'):
        return _get_item_metadata_key(key[:-2])
    return key

def _to_item_metadata_keys(key, keys, item, prefix):
    if len(keys) != 2 or any(['.' in k for k in keys]):
        return None
    value_keys = [k for k in keys if isinstance(mapping_table[f'{key}.{k}'], str)]
    lang_keys = [k for k in keys if not isinstance(mapping_table[f'{key}.{k}'], str)]
    if len(value_keys) == 0 or len(lang_keys) == 0:
        return None
    values = item['attribute_value_mlt']
    value_key = value_keys[0]
    lang_key = lang_keys[0]
    item_name = mapping_table[f'{key}.{value_key}']
    return dict([
        (f'{prefix}{item_name}.{v[lang_key]}', _to_metadata_entity(v[value_key]))
        for v in values
        if value_key in v
    ])

def _to_item_metadata_json(metadata_def, values):
    logger.info(f'Metadata: {metadata_def} = {values}')
    return {}

def _to_metadata_entity(value):
    return {
        'extra': [],
        'comments': [],
        'value': value,
    }

def _to_item_metadata(key, item, prefix='grdm-file:'):
    if key in mapping_table and isinstance(mapping_table[key], str):
        return {
            f'{prefix}{mapping_table[key]}': _to_metadata_entity(item['attribute_value']),
        }
    if key in mapping_table and isinstance(mapping_table[key], dict):
        return _to_item_metadata_json(mapping_table[key], item['attribute_value_mlt'])
    keys = [k[len(key) + 1:] for k in mapping_table.keys() if k.startswith(f'{key}.')]
    r = _to_item_metadata_keys(key, keys, item, prefix)
    if r is not None:
        return r
    logger.warning(f'Conversion not supported: {key} = {item}')
    return {}

def to_metadata(schema_id, item):
    weko_metadata = item.raw['metadata']['_item_metadata']
    logger.info(f'to_metadata: {weko_metadata} as {schema_id}')
    toplevel_keys = set()
    r = {}
    for key in mapping_table.keys():
        toplevel_key = key.split('.')[0]
        if toplevel_key in toplevel_keys:
            continue
        toplevel_keys.add(toplevel_key)
        toplevel_item = weko_metadata.get(_get_item_metadata_key(toplevel_key), None)
        if toplevel_item is None:
            continue
        r.update(_to_item_metadata(toplevel_key, toplevel_item))
    return r


def write_csv(f, target_index, download_file_names, schema_id, file_metadata):
    header = ['#ItemType', 'デフォルトアイテムタイプ（フル）(15)', 'https://localhost:8443/items/jsonschema/15']

    columns = [('.publish_status', '.PUBLISH_STATUS', '', 'Required', 'public')]
    columns.append(('.metadata.path[0]', '.IndexID[0]', '', 'Allow Multiple', target_index.identifier))
    columns.append(('.pos_index[0]', '.POS_INDEX[0]', '', 'Allow Multiple', target_index.title))
    for i, download_file_name in enumerate(download_file_names):
        columns += _generate_file_columns(i, download_file_name)

    file_metadata_item = [item for item in file_metadata['items'] if item['schema'] == schema_id][0]
    file_metadata_data = file_metadata_item['data']

    items = _get_toplevel_items(mapping_table)
    for tkey, titem in items.items():
        if titem['languages'] is None:
            for j in range(_get_item_indices(file_metadata_data, titem)):
                for key, item in titem['items']:
                    if any([c[0].startswith('.metadata.' + tkey) for c in columns_default]):
                        logger.info(f'Duplicated Key: {key} = {item}')
                    m = re.match(r'^([a-zA-Z_0-9]+)\[\]\.(.+)$', key)
                    value = _get_metadata_value(file_metadata_data, item, None, j)
                    if len(value) == 0:
                        continue
                    if m:
                        columns.append((f'.metadata.{m.group(1)}[{j}].{m.group(2)}', '', '', '', value))
                    else:
                        columns.append((f'.metadata.{key}', '', '', '', value))
            continue
        for i, lang in enumerate(titem['languages']):
            empty = False
            for key, item in titem['items']:
                if any([c[0].startswith('.metadata.' + tkey) for c in columns_default]):
                    logger.info(f'Key: {key} = {item}')
                m = re.match(r'^([a-zA-Z_0-9]+)\[\]\.(.+)$', key)
                assert m, key
                value = _get_metadata_value(file_metadata_data, item, lang, None)
                if len(value) == 0:
                    empty = True
                    break
                columns.append((f'.metadata.{m.group(1)}[{i}].{m.group(2)}', '', '', '', value))
            if empty:
                continue
            language_key = titem['language_key']
            m = re.match(r'^([a-zA-Z_0-9]+)\[\]\.(.+)$', language_key)
            assert m, language_key
            columns.append((f'.metadata.{m.group(1)}[{i}].{m.group(2)}', '', '', '', lang))

    columns += columns_default

    cf = csv.writer(f)
    cf.writerow(header)
    cf.writerow([c for c, _, _, _, _ in columns])
    cf.writerow([c for _, c, _, _, _ in columns])
    cf.writerow([c for _, _, c, _, _ in columns])
    cf.writerow([c for _, _, _, c, _ in columns])
    cf.writerow([c for _, _, _, _, c in columns])

def _get_toplevel_items(mapping_table):
    items = {}
    for key, mapping_item in mapping_table.items():
        toplevel_key = key[:key.index('.')] if '.' in key else key
        if toplevel_key not in items:
            items[toplevel_key] = {
                'languages': None,
                'items': [],
            }
        if not isinstance(mapping_item, str) and 'type' in mapping_item:
            if mapping_item['type'] == 'language':
                items[toplevel_key]['languages'] = ['ja', 'en']
                items[toplevel_key]['language_key'] = key
            elif mapping_item['type'] == 'file-creators':
                items[toplevel_key]['jsonarray_key'] = mapping_item['key']
                items[toplevel_key]['items'] += [(f'{key}.{k}', v) for k, v in mapping_item['items'].items()]
            else:
                logger.warn(f'Unexpected type: {mapping_item["type"]}')
                del items[toplevel_key]
        elif isinstance(mapping_item, str):
            items[toplevel_key]['items'].append((key, {
                'type': 'property',
                'key': mapping_item,
            }))
        else:
            raise ValueError(f'Unexpected mapping_item: {mapping_item}')
    for key_, i in list(items.items()):
        if any([(('[]' in key[key.index('.'):]) if '.' in key else False) for key, _ in i['items']]):
            logger.warn(f'Unsupported key: {key_}')
            del items[key_]
    return items
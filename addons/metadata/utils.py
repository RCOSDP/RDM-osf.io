# -*- coding: utf-8 -*-
import csv
import io
import json
import logging
from jinja2 import Environment
from osf.models.metaschema import RegistrationSchema

from . import SHORT_NAME


logger = logging.getLogger(__name__)


def _convert_metadata_key(key):
    if '-' not in key:
        return [key]
    return [key, key.replace('-', '_')]

def _convert_metadata_grdm_files(value):
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
            v_ = _convert_metadata_value(key, metadata[key])
            for k in _convert_metadata_key(dispkey):
                obj[k] = v_
        r.append(obj)
    return r

def _convert_metadata_value(key, value):
    if 'value' not in value:
        return value
    v = value['value']
    if key == 'grdm-files':
        return _convert_metadata_grdm_files(v)
    return v

def _convert_metadata(metadata):
    r = {}
    for key in metadata.keys():
        v = _convert_metadata_value(key, metadata[key])
        for k in _convert_metadata_key(key):
            r[k] = v
    return r

def _quote_csv(value):
    f = io.StringIO()
    w = csv.writer(f)
    if isinstance(value, list):
        w.writerow(value)
    else:
        w.writerow([value])
    return f.getvalue().rstrip()

def append_user_social(ret, user):
    addon = user.get_addon(SHORT_NAME)
    if addon is None:
        return
    ret['eRadResearcherNumber'] = addon.get_erad_researcher_number()

def unserialize_user_social(json_data, user):
    erad_researcher_number = json_data.get('eRadResearcherNumber', None)
    addon = user.get_addon(SHORT_NAME)
    if not addon:
        user.add_addon(SHORT_NAME)
        addon = user.get_addon(SHORT_NAME)
    addon.set_erad_researcher_number(erad_researcher_number)

def make_report_as_csv(format, draft_metadata):
    env = Environment(autoescape=False)
    env.filters['quotecsv'] = _quote_csv
    template = env.from_string(format.csv_template)
    template_metadata = _convert_metadata(draft_metadata)
    return 'report.csv', template.render(**template_metadata)

def ensure_registration_report(schema_name, report_name, csv_template):
    from .models import RegistrationReportFormat
    registration_schema = RegistrationSchema.objects.get(name=schema_name)
    template_query = RegistrationReportFormat.objects.filter(
        registration_schema_id=registration_schema._id, name=report_name
    )
    if template_query.exists():
        template = template_query.first()
    else:
        template = RegistrationReportFormat.objects.create(
            registration_schema_id=registration_schema._id,
            name=report_name
        )
    template.csv_template = csv_template
    logger.info(f'Format registered: {registration_schema._id}')
    template.save()
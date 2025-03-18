# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks


def ensure_registration_reports(*args):
    from api.base import settings
    from addons.metadata import FULL_NAME
    from addons.metadata.utils import ensure_registration_report
    from addons.metadata.report_format import REPORT_FORMATS

    if FULL_NAME not in settings.INSTALLED_APPS:
        return
    for schema_name, report_name, csv_template in REPORT_FORMATS:
        ensure_registration_report(schema_name, report_name, csv_template)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0245_ensure_schema_and_reports'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationschemablock',
            name='auto_date',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registrationschemablock',
            name='auto_title',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registrationschemablock',
            name='auto_value',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registrationschemablock',
            name='hide_projectmetadata',
            field=models.BooleanField(default=False),
        ),
        UpdateRegistrationSchemasAndSchemaBlocks(),
        migrations.RunPython(ensure_registration_reports, ensure_registration_reports),
    ]

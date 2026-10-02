# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
import osf.utils.datetime_aware_jsonfield
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0265_add_additional_funding'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationschemablock',
            name='ui',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(
                null=True, blank=True,
            ),
        ),
        UpdateRegistrationSchemasAndSchemaBlocks(),
    ]

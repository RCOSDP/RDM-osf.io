# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0232_merge_20230905_0321'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationschemablock',
            name='conditional_required',
            field=models.TextField(null=True),
        ),
        UpdateRegistrationSchemasAndSchemaBlocks()
    ]

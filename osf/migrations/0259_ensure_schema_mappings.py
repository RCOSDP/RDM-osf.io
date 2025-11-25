# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0258_update_registration_schema'),
    ]

    operations = [
        UpdateRegistrationSchemasAndSchemaBlocks(),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0257_merge_20251023_1304'),
        ('osf', '0235_merge_20240611_0335'),
        ('osf', '0258_merge_20251110_0428'),
    ]

    operations = [
        UpdateRegistrationSchemasAndSchemaBlocks(),
    ]

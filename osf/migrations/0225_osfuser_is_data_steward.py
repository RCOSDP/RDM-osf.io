# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2023-02-20 10:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0224_ensure_schema_and_reports'),
    ]

    operations = [
        migrations.AddField(
            model_name='osfuser',
            name='is_data_steward',
            field=models.BooleanField(default=False),
        ),
    ]

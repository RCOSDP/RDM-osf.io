# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2023-02-13 11:17
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('addons_osfstorage', '0006_rename_deleted_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='region',
            name='is_allowed',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='region',
            name='is_readonly',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='nodesettings',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_osfstorage_node_settings', to='osf.AbstractNode'),
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2022-08-23 09:01
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('addons_osfstorage', '0007_auto_20220823_0900'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nodesettings',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_osfstorage_node_settings', to='osf.AbstractNode'),
        ),
    ]

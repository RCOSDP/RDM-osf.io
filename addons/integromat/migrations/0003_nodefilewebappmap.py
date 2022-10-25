# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2022-03-03 01:43
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import osf.models.base


class Migration(migrations.Migration):

    dependencies = [
        ('addons_integromat', '0002_auto_20220210_1403'),
    ]

    operations = [
        migrations.CreateModel(
            name='NodeFileWebappMap',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('_id', models.CharField(db_index=True, default=osf.models.base.generate_object_id, max_length=24, unique=True)),
                ('node_file_guid', models.CharField(default=None, max_length=255, unique=True)),
                ('slack_channel_id', models.CharField(default=None, max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, osf.models.base.QuerySetExplainMixin),
        ),
    ]
# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2021-06-11 06:20
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0179_rdmwebmeetingapps_rdmworkflows'),
        ('addons_integromat', '0018_auto_20210610_0311'),
    ]

    operations = [
        migrations.CreateModel(
            name='nodeWorkflows',
            fields=[
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('alternative_webhook_url', osf.utils.fields.EncryptedTextField(blank=True, null=True)),
                ('node_settings', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='addons_integromat.NodeSettings')),
                ('workflow', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='osf.RdmWorkflows')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2023-07-24 03:51
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def add_region_and_root_id_value(apps, schema_editor):
    OneDriveNodeSettings = apps.get_model('addons_onedrivebusiness', 'nodesettings')
    OsfNodeSettings = apps.get_model('addons_osfstorage', 'nodesettings')
    for osfnodesettings in OsfNodeSettings.objects.all():
        onedrivenodesettings = OneDriveNodeSettings.objects.filter(owner_id=osfnodesettings.owner_id)
        if onedrivenodesettings.exists():
            for onedrive in onedrivenodesettings:
                onedrive.region_id = osfnodesettings.region_id
                onedrive.root_node_id = osfnodesettings.root_node_id
                onedrive.save()


def noop(*args):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('addons_osfstorage', '0008_auto_20230323_0918'),
        ('addons_onedrivebusiness', '0002_nodesettings_drive_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='nodesettings',
            name='region',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='one_drive_business_region_id', to='addons_osfstorage.Region'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='root_node',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='one_drive_business_root_node_id', to='osf.BaseFileNode'),
        ),
        migrations.RunPython(add_region_and_root_id_value, noop)
    ]

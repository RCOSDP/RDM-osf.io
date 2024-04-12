# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2023-07-24 03:51
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def add_region_and_root_id_value(apps, schema_editor):
    OciNodeSettings = apps.get_model('addons_ociinstitutions', 'nodesettings')
    OsfNodeSettings = apps.get_model('addons_osfstorage', 'nodesettings')
    for osfnodesettings in OsfNodeSettings.objects.all():
        ociNodeSettings = OciNodeSettings.objects.filter(owner_id=osfnodesettings.owner_id)
        if ociNodeSettings.exists():
            for oci in ociNodeSettings:
                oci.region_id = osfnodesettings.region_id
                oci.root_node_id = osfnodesettings.root_node_id
                oci.save()


def noop(*args):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('addons_osfstorage', '0008_auto_20230323_0918'),
        ('addons_ociinstitutions', '0002_auto_20210312_2336'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nodesettings',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='oci_node_settings', to='osf.AbstractNode'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='region',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='oci_region_id', to='addons_osfstorage.Region'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='root_node',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='oci_root_node_id', to='osf.BaseFileNode'),
        ),
        migrations.RunPython(add_region_and_root_id_value, noop)
    ]

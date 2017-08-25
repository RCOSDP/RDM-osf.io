# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-08-24 09:58
from __future__ import unicode_literals

from django.db import migrations, models
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0042_preprintprovider_share_title'),
    ]

    operations = [
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='osfuser',
            name='date_last_access',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='eppn',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='eptid',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='groups_initialized',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='have_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='osfuser',
            name='groups',
            field=models.ManyToManyField(related_name='users_group', to='osf.Group'),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='groups_admin',
            field=models.ManyToManyField(related_name='users_group_admin', to='osf.Group'),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='groups_sync',
            field=models.ManyToManyField(related_name='users_group_sync', to='osf.Group'),
        ),
    ]

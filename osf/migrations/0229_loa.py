# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2023-03-16 12:32
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import osf.models.base


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0228_auto_20230314_0205'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoA',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('aal', models.IntegerField(blank=True, choices=[(1, 'AAL1'), (2, 'AAL2')], null=True)),
                ('ial', models.IntegerField(blank=True, choices=[(1, 'IAL1'), (2, 'IAL2')], null=True)),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='osf.Institution')),
                ('modifier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': (('view_loa', 'Can view loa'), ('admin_loa', 'Can manage loa')),
            },
            bases=(models.Model, osf.models.base.QuerySetExplainMixin),
        ),
    ]
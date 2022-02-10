# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2022-02-10 07:29
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import osf.models.base


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0216_merge_20211009_0007'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstitutionEntitlement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('entitlement', models.CharField(max_length=255)),
                ('login_availability', models.BooleanField(default=True)),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='osf.Institution')),
                ('modifier_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            bases=(models.Model, osf.models.base.QuerySetExplainMixin),
        ),
        migrations.AlterUniqueTogether(
            name='institutionentitlement',
            unique_together=set([('institution', 'entitlement')]),
        ),
    ]
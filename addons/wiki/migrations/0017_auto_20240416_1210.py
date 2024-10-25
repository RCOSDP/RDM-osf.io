# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2024-04-16 12:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('addons_wiki', '0016_auto_20240307_0010'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wikipage',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='addons_wiki.WikiPage'),
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2024-09-15 21:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('addons_metadata', '0011_importedaddonsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationreportformat',
            name='order',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]

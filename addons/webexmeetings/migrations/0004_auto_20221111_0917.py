# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2022-11-11 09:17
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('addons_webexmeetings', '0003_auto_20221102_0523'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendees',
            name='is_guest',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterUniqueTogether(
            name='attendees',
            unique_together=set([('email_address', 'node_settings', 'external_account', 'is_active')]),
        ),
    ]
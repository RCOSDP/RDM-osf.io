# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2022-10-20 05:55
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('addons_microsoftteams', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='attendees',
            unique_together=set([('email_address', 'node_settings', 'external_account', 'is_guest')]),
        ),
    ]
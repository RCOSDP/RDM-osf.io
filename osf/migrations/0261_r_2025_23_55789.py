# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('osf', '0260_merge_20251126_1230'),
    ]

    operations = [
        migrations.AddField(
            model_name='osfuser',
            name='aal',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='osfuser',
            name='ial',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

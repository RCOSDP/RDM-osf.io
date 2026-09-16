# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('addons_workflow', '0004_workflowengine_label'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowactivation',
            name='is_dismissed',
            field=models.BooleanField(default=False),
        ),
    ]

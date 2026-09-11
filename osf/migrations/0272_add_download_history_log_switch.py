# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from osf import features
from osf.utils.migrations import AddWaffleSwitches


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0271_merge_20260622_1735'),
    ]

    operations = [
        AddWaffleSwitches([features.ENABLE_DOWNLOAD_HISTORY_LOG], active=False),
    ]

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import osf.models.base


class Migration(migrations.Migration):
    dependencies = [
        ('osf', '0261_r_2025_23_55789'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoA',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name='created'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    'aal',
                    models.IntegerField(
                        blank=True,
                        choices=[(0, 'NULL'), (1, 'AAL1'), (2, 'AAL2')],
                        null=True,
                    ),
                ),
                (
                    'ial',
                    models.IntegerField(
                        blank=True,
                        choices=[(0, 'NULL'), (1, 'IAL1'), (2, 'IAL2')],
                        null=True,
                    ),
                ),
                (
                    'is_mfa',
                    models.BooleanField(
                        choices=[(False, 'Disabled'), (True, 'Enabled')],
                        default=False,
                        verbose_name='Display MFA link button',
                    ),
                ),
                (
                    'institution',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='osf.Institution',
                    ),
                ),
                (
                    'modifier',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'permissions': (
                    ('view_loa', 'Can view loa'),
                    ('admin_loa', 'Can manage loa'),
                ),
            },
            bases=(models.Model, osf.models.base.QuerySetExplainMixin),
        ),
    ]

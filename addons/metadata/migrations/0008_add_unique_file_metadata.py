# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, transaction


def ensure_unique_project_id_path(*args):
    from addons.metadata.models import FileMetadata

    def compare(before, current):
        if before.deleted is None and current.deleted is not None:
            return False
        if before.deleted is not None and current.deleted is None:
            return True
        return before.modified < current.modified

    with transaction.atomic():
        last_metadatas = {}
        for metadata in FileMetadata.objects.order_by('modified').all():
            key = (metadata.project_id, metadata.path)
            if key not in last_metadatas or compare(last_metadatas[key], metadata):
                last_metadatas[key] = metadata
        for metadata in FileMetadata.objects.order_by('modified').all():
            key = (metadata.project_id, metadata.path)
            if last_metadatas[key].id != metadata.id:
                metadata.delete()


def noop(*args):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('addons_metadata', '0007_user_to_file_metadata'),
    ]

    operations = [
        migrations.RunPython(ensure_unique_project_id_path, noop),
        migrations.AlterUniqueTogether(
            name='filemetadata',
            unique_together=set([('project_id', 'path')]),
        ),
    ]

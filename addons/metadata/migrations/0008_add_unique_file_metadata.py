# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import logging

from django.db import connection, migrations

logger = logging.getLogger(__name__)


def ensure_unique_project_id_path(*args):
    from addons.metadata.models import FileMetadata
    # Deletes the newest from each set of FileMetadata
    sql = """
    SELECT f.id
    FROM addons_metadata_filemetadata f
    INNER JOIN (
      SELECT path, MAX(modified) as max_modified
      FROM addons_metadata_filemetadata
      GROUP BY path
    ) AS max_dates ON f.path = max_dates.path
    WHERE f.modified < max_dates.max_modified;
    """
    # It is possible that new duplicate data will be created during migration in the old service instance,
    # in which case migration should fail, so have the migration run again.
    with connection.cursor() as cursor:
        cursor.execute(sql)
        ids = list(sum(cursor.fetchall(), ()))
        logger.info('Deleting duplicate FileMetadata with `id`s {}'.format(ids))
        FileMetadata.objects.filter(id__in=ids).delete()
        logger.info('Deleted.')


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

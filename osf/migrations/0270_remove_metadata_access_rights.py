from django.db import migrations

noop = migrations.RunPython.noop

TARGET_SCHEMA_NAME = '公的資金による研究データのメタデータ登録'

OBSOLETE_KEY = 'grdm-file:metadata-access-rights'


def _transform_item(data):
    if OBSOLETE_KEY in data:
        data.pop(OBSOLETE_KEY, None)
        return True
    return False


def _transform_entry(entry):
    metadata = entry.get('metadata', {})
    if OBSOLETE_KEY in metadata:
        metadata.pop(OBSOLETE_KEY, None)
        return True
    return False


def remove_metadata_access_rights(*args):
    from addons.metadata.utils import FileMetadataMigrator
    migrator = FileMetadataMigrator(
        TARGET_SCHEMA_NAME,
        _transform_item,
        _transform_entry,
    )
    migrator.run()


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0269_merge_20260525_0425'),
    ]

    operations = [
        migrations.RunPython(remove_metadata_access_rights, noop),
    ]

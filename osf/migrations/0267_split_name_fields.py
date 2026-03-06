import logging

from django.db import migrations

from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks

logger = logging.getLogger(__name__)

noop = migrations.RunPython.noop

TARGET_SCHEMA_NAME = '公的資金による研究データのメタデータ登録'


def migrate_name_fields(*args):
    from addons.metadata.utils import (
        FileMetadataMigrator,
        transform_name_fields_item,
        transform_name_fields_entry,
    )
    migrator = FileMetadataMigrator(
        TARGET_SCHEMA_NAME,
        transform_name_fields_item,
        transform_name_fields_entry,
    )
    migrator.run()


def ensure_registration_mappings(*args):
    from addons.weko.utils import ensure_registration_metadata_mapping
    from addons.weko.mappings import REGISTRATION_METADATA_MAPPINGS

    for schema_name, mappings in REGISTRATION_METADATA_MAPPINGS:
        ensure_registration_metadata_mapping(schema_name, mappings)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0266_add_ui_to_registration_schema_block'),
    ]

    operations = [
        UpdateRegistrationSchemasAndSchemaBlocks(),
        migrations.RunPython(migrate_name_fields, noop),
        migrations.RunPython(ensure_registration_mappings, ensure_registration_mappings),
    ]

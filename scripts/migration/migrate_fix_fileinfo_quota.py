#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_fix_fileinfo_quota.py

Fix missing or zero-size FileInfo records and recalculate UserQuota.

Background
----------
During Move/Copy operations, if a system error occurs after the file has been
written but before the FileInfo hook completes, the resulting OsfStorageFile may
have no FileInfo row (or a row with file_size=0).  This causes UserQuota.used to
be under-counted for the affected project creator.

This script:
1. Finds all non-deleted OsfStorageFile nodes that are missing a FileInfo record
   OR have a FileInfo record with file_size=0.
2. Populates file_size from the latest FileVersion.size (which is authoritative).
3. Collects all unique project creators affected by the above.
4. Calls update_user_used_quota(user) for each affected user to re-sync
   UserQuota.used from the actual FileInfo totals.
   Storage type is determined per-project (NII_STORAGE or CUSTOM_STORAGE).
5. Exports a CSV report of all processed records.

Error Handling (fail-fast):
    The script fails fast. As soon as it hits a record that cannot be fully fixed —
    its size cannot be determined, or its project creator / storage_type cannot be
    resolved — or any unexpected error, it logs THAT single record and raises
    immediately, so an administrator can fix that record and re-run. It does NOT
    scan the whole dataset to collect and print a list of every problem. This
    behaviour is identical in dry-run and in a real run.

    All DB updates run inside a single transaction (transaction.atomic). If an error
    is raised part-way through a real run, every change is rolled back and the
    database is left untouched (no partially-applied fixes).

    Note on file size: size is read from the latest FileVersion. A genuine
    file_size == 0 is a valid size and a FileInfo record with file_size=0 is
    created/updated; only an indeterminable size (None) is treated as an error.

Usage:
    # Fix and export results to CSV
    python -m scripts.migration.migrate_fix_fileinfo_quota
    python -m scripts.migration.migrate_fix_fileinfo_quota --output result.csv

    # Preview changes and export to CSV without writing to DB (dry run)
    python -m scripts.migration.migrate_fix_fileinfo_quota --dry
    python -m scripts.migration.migrate_fix_fileinfo_quota --dry --output preview.csv
"""

import os
import csv
import logging
import argparse
from datetime import datetime

import django

# Setup Django before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.base.settings')
django.setup()

from django.db import transaction
from django.db.models import Q

from addons.osfstorage.models import OsfStorageFile
from osf.models import FileInfo, OSFUser
from website.util.quota import update_user_used_quota, get_project_storage_type
from scripts import utils as script_utils
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

RESULT_FIELDNAMES = [
    # osf_file_id     : _id (hex string) of the OsfStorageFile / BaseFileNode record
    # fileinfo_id     : integer PK of the FileInfo record inserted/updated (empty in dry_run)
    # fileinfo__id    : _id (hex string) of the FileInfo record inserted/updated (empty in dry_run)
    # fileinfo_file_id: integer PK of BaseFileNode — the value stored as file_id (FK) in the FileInfo table
    # fileinfo_created: True = new FileInfo row INSERT-ed, False = existing row UPDATE-d (empty in dry_run)
    # action          : would_update (dry-run) | created | updated
    # quota_recalculated: True if quota was recalculated for this file's creator
    'osf_file_id', 'file_name',
    'fileinfo_id', 'fileinfo__id', 'fileinfo_file_id',
    'file_size_bytes', 'project_guid', 'creator_id', 'storage_type',
    'fileinfo_created', 'action', 'quota_recalculated', 'dry_run',
]


# --- Scanning Operations ---

def get_broken_file_nodes():
    """Return queryset of OsfStorageFile nodes that:
    - are not deleted (deleted_on is None)
    - either have no FileInfo, or have FileInfo with file_size == 0

    Optimized using a LEFT OUTER JOIN query to avoid subquery bottlenecks with large datasets.
    """
    return (
        OsfStorageFile.objects
        .filter(deleted_on=None, deleted_by_id=None)
        .filter(Q(fileinfo__isnull=True) | Q(fileinfo__file_size=0))
        # NOTE: Do NOT use prefetch_related('target') here.
        # BaseFileNode uses TypedModel + GenericForeignKey; Django's GFK prefetch cache
        # is incompatible with TypedModel proxy resolution and returns None even when
        # target_content_type_id is valid. Use direct lookup instead (see resolve_target).
    )


def _bulk_get_latest_version_sizes(osf_file_ids):
    """Fetch the latest FileVersion size for each OsfStorageFile in bulk.
    Returns a dict mapping osf_file.id -> size (int or None).
    """
    if not osf_file_ids:
        return {}

    # Access the M2M through-model (BaseFileVersionsThrough) without importing it directly.
    # Fields: basefilenode_id (FK → BaseFileNode), fileversion_id (FK → FileVersion)
    ThroughModel = OsfStorageFile.versions.through

    # Single JOIN query: fetches all through-entries + related FileVersion data at once.
    entries = (
        ThroughModel.objects
        .filter(basefilenode_id__in=osf_file_ids)
        .select_related('fileversion')
    )

    # Group by file and pick the version with the highest numeric identifier.
    # result maps: file_node_id → (version_number_int, size)
    best = {}  # file_node_id -> (ver_num, size)
    for entry in entries:
        fv = entry.fileversion
        file_node_id = entry.basefilenode_id

        # identifier is a text field ('1', '2', ...) — parse to int for correct ordering
        try:
            ver_num = int(fv.identifier)
        except (TypeError, ValueError):
            ver_num = -1  # non-numeric identifiers rank last

        if file_node_id not in best or ver_num > best[file_node_id][0]:
            # Resolve size: prefer fv.size, fall back to metadata dict
            size = fv.size
            if size is None and isinstance(fv.metadata, dict):
                try:
                    size = int(fv.metadata.get('size'))
                except (TypeError, ValueError):
                    size = None
            best[file_node_id] = (ver_num, size)

    return {file_id: info[1] for file_id, info in best.items()}


def scan_broken_files():
    """Scan for OsfStorageFile nodes with missing or zero-size FileInfo.

    Fails fast: the moment a record is found that cannot be fully fixed (size cannot
    be determined, or its project creator / storage_type cannot be resolved), this
    raises so the administrator can fix that one record and re-run. No DB writes.
    Returns a list of fully-fixable row dicts when every record is OK.
    """
    broken_files = list(get_broken_file_nodes())
    total = len(broken_files)
    logger.info('Scanning OsfStorageFile records...')
    logger.info('Found {} file node(s) with missing or zero-size FileInfo.'.format(total))

    # Bulk-fetch latest version sizes to avoid N+1 queries
    file_ids = [f.id for f in broken_files]
    size_map = _bulk_get_latest_version_sizes(file_ids)

    rows = []
    for osf_file in broken_files:
        size = size_map.get(osf_file.id)

        # Fail fast: the size must be determinable. (A genuine file_size == 0 is a
        # valid size and is NOT an error — only an indeterminable size is.)
        if size is None:
            raise RuntimeError(
                'File {} (_id={}) — could not determine size from any FileVersion. '
                'Fix this record and re-run.'.format(osf_file.name, osf_file._id)
            )

        # Resolve the project target, then its creator / guid / storage_type.
        project_guid = ''
        creator_id = ''
        storage_type_value = None
        try:
            # Direct lookup via ContentType to avoid GFK+TypedModel prefetch incompatibility.
            # osf_file.target (GFK accessor) returns None when used after prefetch_related
            # because TypedModel proxy resolution breaks the GFK prefetch cache.
            target = None
            if osf_file.target_content_type_id and osf_file.target_object_id:
                ct = ContentType.objects.get_for_id(osf_file.target_content_type_id)
                model_class = ct.model_class()
                if model_class:
                    target = model_class.objects.filter(id=osf_file.target_object_id).first()

            if target is not None:
                first_guid = target.guids.values_list('_id', flat=True).first()
                project_guid = first_guid or ''
                creator = getattr(target, 'creator', None)
                if creator:
                    creator_id = creator._id
                storage_type_value = get_project_storage_type(target)
        except Exception as e:
            # Fail fast: do not swallow unexpected errors.
            logger.error('Could not resolve target/creator for file {}: {} — aborting (fail fast).'.format(
                osf_file._id, e
            ))
            raise

        # Fail fast: creator and storage_type must be resolvable to recalculate quota.
        if not creator_id:
            raise RuntimeError(
                'File {} (_id={}, project_guid={}) — creator could not be resolved '
                '(target missing or has no creator). Fix this record and re-run.'.format(
                    osf_file.name, osf_file._id, project_guid
                )
            )
        if storage_type_value is None:
            raise RuntimeError(
                'File {} (_id={}, project_guid={}) — project storage_type could not be '
                'determined. Fix this record and re-run.'.format(
                    osf_file.name, osf_file._id, project_guid
                )
            )

        rows.append({
            'osf_file_id': osf_file._id,       # hex _id string of OsfStorageFile
            'fileinfo_file_id': osf_file.id,   # integer PK stored as file_id FK in FileInfo table
            'file_name': osf_file.name,
            'file_size_bytes': size,
            'project_guid': project_guid,
            'creator_id': creator_id,
            'storage_type': storage_type_value,
            'osf_file': osf_file,
        })

    logger.info('Scan complete. {} record(s) ready to fix.'.format(len(rows)))
    return rows


def print_results(rows):
    """Display scanned records in a formatted summary table."""
    if not rows:
        print('   No broken FileInfo records found.')
        return

    def _disp(value):
        # Display helper: never let None (or any value) break str formatting.
        return '' if value is None else str(value)

    print('\n' + '-' * 160)
    print(' {:<26} {:<16} {:<22} {:<18} {:<16} {:<14} {:<18}'.format(
        'OSF_FILE_ID (_id)', 'FILEINFO_FILE_ID', 'FILE_NAME', 'PROJECT_GUID', 'CREATOR_ID', 'STORAGE_TYPE', 'SIZE (bytes)'
    ))
    print('-' * 160)
    for r in rows:
        print(' {:<26} {:<16} {:<22} {:<18} {:<16} {:<14} {:<18}'.format(
            _disp(r.get('osf_file_id')),
            _disp(r.get('fileinfo_file_id')),
            _disp(r.get('file_name'))[:20],
            _disp(r.get('project_guid')),
            _disp(r.get('creator_id')),
            _disp(r.get('storage_type')),
            _disp(r.get('file_size_bytes')),
        ))
    print('-' * 160)
    print(' Total: {} record(s) would be updated.\n'.format(len(rows)))


# --- Updating Operations ---

def apply_fixes(rows, dry_run=False):
    """Apply FileInfo fixes and recalculate UserQuota for affected users.

    This function wraps all database modifications in a single database transaction
    when dry_run is False. If any unhandled exception occurs, the transaction is
    rolled back, ensuring database consistency.

    If dry_run is True, no database writes are performed.
    Returns the list of result rows with 'action', 'quota_recalculated', and 'dry_run' fields added.
    """
    if dry_run:
        logger.info('[DRY RUN] Simulating FileInfo updates (no DB writes)...')
        return _apply_fixes_internal(rows, dry_run=True)
    else:
        logger.info('Applying FileInfo updates (wrapped in database transaction)...')
        with transaction.atomic():
            return _apply_fixes_internal(rows, dry_run=False)


def _apply_fixes_internal(rows, dry_run=False):
    """Internal helper to apply fixes, called inside/outside transaction.

    Every row here is already fully fixable (scan_broken_files fails fast otherwise),
    so each row gets a FileInfo update and contributes to a UserQuota recalculation.
    """
    result_rows = []
    affected_user_storage = set()  # set of (creator_id, storage_type)
    fixed = 0

    for row in rows:
        # scan stores the osf_file object on the row; fall back to a lookup just in case.
        osf_file = row.get('osf_file')
        if osf_file is None:
            osf_file = OsfStorageFile.objects.filter(_id=row['osf_file_id']).first()
        if osf_file is None:
            # Fail fast: a scanned row must resolve to a file.
            raise RuntimeError('File {} not found when applying fix.'.format(row['osf_file_id']))

        fileinfo_id = ''
        fileinfo__id = ''
        fileinfo_created = ''
        if not dry_run:
            fileinfo_obj, created = FileInfo.objects.update_or_create(
                file=osf_file,
                defaults={'file_size': row['file_size_bytes']},
            )
            fileinfo_id = fileinfo_obj.id        # integer PK of FileInfo
            fileinfo__id = fileinfo_obj._id      # hex _id string of FileInfo
            fileinfo_created = created           # True = INSERT, False = UPDATE

        creator_id = row['creator_id']
        storage_type = row['storage_type']
        affected_user_storage.add((creator_id, storage_type))

        action = 'would_update' if dry_run else ('created' if fileinfo_created else 'updated')

        logger.info('{} {} (osf_file_id={}, fileinfo_id={}, fileinfo__id={}, fileinfo_file_id={}, created={}) file_size={} bytes storage_type={}'.format(
            '[DRY RUN]' if dry_run else 'Fixed:',
            row['file_name'], row['osf_file_id'],
            fileinfo_id, fileinfo__id, row['fileinfo_file_id'],
            fileinfo_created, row['file_size_bytes'], storage_type,
        ))

        result_rows.append({
            'osf_file_id': row['osf_file_id'],
            'fileinfo_file_id': row['fileinfo_file_id'],
            'file_name': row['file_name'],
            'file_size_bytes': row['file_size_bytes'],
            'project_guid': row['project_guid'],
            'creator_id': row['creator_id'],
            'storage_type': row['storage_type'],
            'fileinfo_id': fileinfo_id,
            'fileinfo__id': fileinfo__id,
            'fileinfo_created': fileinfo_created,
            'action': action,
            'quota_recalculated': False,  # will be updated below after quota recalc
            'dry_run': dry_run,
        })
        fixed += 1

    logger.info('FileInfo backfill complete. fixed={} (dry={})'.format(fixed, dry_run))

    # --- Recalculate UserQuota.used for all affected (user, storage_type) pairs ---
    logger.info('Recalculating UserQuota.used for {} unique (user, storage_type) pair(s).'.format(
        len(affected_user_storage)
    ))

    quota_updated = 0
    recalculated_user_storage = set()

    for user_id, storage_type in sorted(affected_user_storage):
        try:
            user = OSFUser.load(user_id)
            if user is None:
                # Fail fast: a creator_id resolved during scan must load here.
                raise RuntimeError(
                    'User {} (storage_type={}) could not be loaded for quota recalc.'.format(
                        user_id, storage_type
                    )
                )

            if not dry_run:
                update_user_used_quota(user, storage_type=storage_type, is_recalculating_quota=True)

            logger.info('{} Recalculated quota for user {} (storage_type={})'.format(
                '[DRY RUN]' if dry_run else '', user_id, storage_type
            ))
            quota_updated += 1
            recalculated_user_storage.add((user_id, storage_type))
        except Exception as e:
            # Fail fast: re-raise so transaction.atomic() rolls back ALL FileInfo updates.
            logger.error('Failed to recalculate quota for user {} (storage_type={}): {} — '
                         'rolling back transaction (fail fast).'.format(user_id, storage_type, e))
            raise

    logger.info('Quota recalculation complete. updated={} (dry={})'.format(quota_updated, dry_run))

    # Update quota_recalculated flag in result rows
    for row in result_rows:
        if dry_run:
            row['quota_recalculated'] = 'would_recalculate'
        elif (row['creator_id'], row['storage_type']) in recalculated_user_storage:
            row['quota_recalculated'] = True

    return result_rows


# --- CSV Export ---

def save_result_csv(result_rows, output_path):
    """Save full results to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(result_rows)
    total = len(result_rows)
    print('\n Exported {} result(s) to: {}'.format(total, output_path))


# --- Main ---

def main():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_output = f'migrate_fix_fileinfo_quota_{ts}.csv'

    parser = argparse.ArgumentParser(
        description='Fix missing/zero-size FileInfo records and recalculate UserQuota.',
    )
    parser.add_argument(
        '--output', '-o',
        default=default_output,
        help=f'Output CSV file path (default: {default_output})',
    )
    parser.add_argument(
        '--dry', action='store_true', default=False,
        help='Run in dry-run mode (do not commit updates to the database).',
    )

    args = parser.parse_args()

    if not args.dry:
        script_utils.add_file_logger(logger, __file__)

    # Configure console logging format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )

    # 1. Scan for broken records
    rows = scan_broken_files()

    if not rows:
        print('No broken FileInfo records found.')
        return

    # 2. Print summary table
    print_results(rows)

    # 3. Apply fixes (or simulate in dry-run mode). scan_broken_files() has already
    #    failed fast on any unfixable record, so every row here is fully fixable.
    result_rows = apply_fixes(rows, dry_run=args.dry)

    # 4. Export results to CSV
    save_result_csv(result_rows, args.output)


if __name__ == '__main__':
    main()

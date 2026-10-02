#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_encoding_errors.py

Scan and fix Japanese encoding issues and HTML entities using Django ORM,
then export the results directly to a CSV file.
This script targets:
  - UserExtendedData (field: data JSONB)
  - OSFUser (fields: fullname, given_name, middle_names, family_name,
                      suffix, given_name_ja, middle_names_ja, family_name_ja,
                      department, jobs, schools, social)

Usage:
    # Preview updates and export results to CSV without making changes to DB (dry run)
    python -m scripts.fix_encoding_errors --dry
    python -m scripts.fix_encoding_errors --dry --output preview.csv

    # Apply fixes using a previously reviewed CSV file
    python -m scripts.fix_encoding_errors --input-csv preview.csv
    python -m scripts.fix_encoding_errors --input-csv preview.csv --output result.csv
"""

import sys
import os
import re
import csv
import json
import logging
import copy
import argparse
from datetime import datetime

import django
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError

# Setup Django before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.base.settings')
django.setup()

from osf.models import UserExtendedData, OSFUser
from scripts import utils as script_utils

logger = logging.getLogger(__name__)

# --- Patterns ---
HTML_ENTITY_RE = re.compile(r'&#\d+;|&#x[0-9a-fA-F]+;')
JAPANESE_ERROR_ENCODING_HINT_RE = re.compile(r'[\u00c0-\u00cf\u00e0-\u00ef\u00aa\u00ba]')
_NUM_ENT_RE = re.compile(r'&#(\d+);|&#x([0-9a-fA-F]+);')

UNRECOVERABLE_NOTICE = '[UNRECOVERABLE: missing bytes - partial result] '
UNRECOVERABLE_CANNOT_FIX = '[UNRECOVERABLE: cannot fix]'

# Unicode replacement character (U+FFFD). It is produced when a partial decode
# (errors='replace') drops missing bytes. It is a VALID character for the target
# columns, so Django model constraints will NOT reject it on save(). We must
# detect it explicitly: a value that still contains it has not been fully
# recovered and must never be written to the DB.
REPLACEMENT_CHAR = '�'

OSFUSER_STRING_COLUMNS = [
    'fullname',
    'given_name',
    'middle_names',
    'family_name',
    'suffix',
    'given_name_ja',
    'middle_names_ja',
    'family_name_ja',
    'department',
]

OSFUSER_JSON_COLUMNS = [
    'jobs',
    'schools',
    'social',
]

RESULT_FIELDNAMES = [
    'source_table', 'id', 'user_guid', 'user_id', 'field_path',
    'issues', 'original_value', 'suggested_fix', 'fix_applied', 'value_after', 'fix_status',
]

# --- Helper Functions ---

def _entities_as_latin1(s):
    """Replace &#NNN; numeric entities with chr(N), keeping within Latin-1 range."""
    def repl(m):
        n = int(m.group(1)) if m.group(1) is not None else int(m.group(2), 16)
        return chr(n) if n <= 255 else m.group(0)
    return _NUM_ENT_RE.sub(repl, s)


def try_fix_japanese_error_encoding(s):
    """
    Attempt to fix Japanese error encoding by re-encoding as latin-1 and decoding as utf-8.
    Returns (fixed_string, is_partial):
      - is_partial=True  : decode succeeded with errors='replace' (some bytes were lost)
      - is_partial=False : decode succeeded cleanly
      - (None, False)    : fix not possible or no improvement
    """
    partial = False
    try:
        fixed = s.encode('latin1').decode('utf-8')
    except UnicodeDecodeError:
        try:
            fixed = s.encode('latin1').decode('utf-8', errors='replace')
            partial = True
        except UnicodeError:
            # Expected encoding failure -> this string cannot be fixed by the
            # latin1->utf-8 round-trip. Return None so the caller marks it as
            # unrecoverable and continues. Any other (unexpected) exception is
            # left to propagate, per fail-fast.
            return None, False
    except UnicodeError:
        # s contains characters outside Latin-1 (e.g. real Japanese mixed with
        # mojibake): this fix method does not apply. Treat as "cannot fix".
        return None, False

    orig_bad = len(JAPANESE_ERROR_ENCODING_HINT_RE.findall(s))
    fixed_bad = len(JAPANESE_ERROR_ENCODING_HINT_RE.findall(fixed))
    if fixed_bad < orig_bad:
        return fixed, partial
    return None, False


def detect_issues(s):
    """Return list of issue labels found in string s."""
    issues = []
    if HTML_ENTITY_RE.search(s):
        issues.append('html_entities')
    if JAPANESE_ERROR_ENCODING_HINT_RE.search(s):
        issues.append('japanese_error_encoding')
    return issues


def suggest_fix(s, issues):
    """
    Return (suggested_fix, is_partial) for the given string and detected issues.
    Returns (None, False) if no fix is possible.
    """
    if 'html_entities' in issues:
        fixed, partial = try_fix_japanese_error_encoding(_entities_as_latin1(s))
        if fixed:
            return fixed, partial
    if 'japanese_error_encoding' in issues:
        fixed, partial = try_fix_japanese_error_encoding(s)
        if fixed:
            return fixed, partial
    return None, False


def walk(obj, path=''):
    """Recursively yield (path, str_value) for all string leaves in a JSON object."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, '{}.{}'.format(path, k) if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, '{}[{}]'.format(path, i))
    elif isinstance(obj, str):
        yield (path, obj)


def compute_fix_status(suggested_fix):
    """Return 'clean', 'partial', or 'unrecoverable' based on suggested_fix."""
    if suggested_fix == UNRECOVERABLE_CANNOT_FIX:
        return 'unrecoverable'
    if suggested_fix.startswith(UNRECOVERABLE_NOTICE):
        return 'partial'
    return 'clean'


def make_error_row(source_table, record_id, user_guid, user_id, path, val):
    """Build a single error row dict from a string value that has issues."""
    issues = detect_issues(val)
    if not issues:
        return None
    fixed, is_partial = suggest_fix(val, issues)
    if fixed is None:
        suggested = UNRECOVERABLE_CANNOT_FIX
    elif is_partial:
        suggested = UNRECOVERABLE_NOTICE + fixed
    else:
        suggested = fixed
    return {
        'source_table':   source_table,
        'id':             record_id,
        'user_guid':      user_guid,
        'user_id':        user_id,
        'field_path':     path,
        'issues':         ','.join(issues),
        'original_value': val,
        'suggested_fix':  suggested,
        'fix_status':     compute_fix_status(suggested),
    }


def get_clean_fix(suggested_fix):
    """Return the actual fix value (strip UNRECOVERABLE_NOTICE prefix if present)."""
    if suggested_fix.startswith(UNRECOVERABLE_NOTICE):
        return suggested_fix[len(UNRECOVERABLE_NOTICE):]
    return suggested_fix


def set_nested_value(obj, path, new_value):
    """
    Set a value inside a nested dict/list structure using a dot/bracket path string.
    E.g. path='jobs[0].institution' -> obj['jobs'][0]['institution'] = new_value
    Returns the modified obj (mutated in-place).
    """
    tokens = re.split(r'\.|\[(\d+)\]', path)
    parts = []
    for t in tokens:
        if t is None or t == '':
            continue
        if t.isdigit():
            parts.append(int(t))
        else:
            parts.append(t)

    node = obj
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = new_value
    return obj


def _get_nested_value(obj, path):
    """
    Read a value from a nested dict/list structure using a dot/bracket path string.
    Mirror of set_nested_value — raises KeyError/IndexError if path does not exist.
    """
    tokens = re.split(r'\.|\[(\d+)\]', path)
    parts = []
    for t in tokens:
        if t is None or t == '':
            continue
        parts.append(int(t) if t.isdigit() else t)
    node = obj
    for part in parts:
        node = node[part]
    return node


def _get_osfuser_field_value(user, field_path):
    """
    Read the current value from an OSFUser instance at the given field_path.
    Supports both simple string columns and nested JSON columns.
    Raises ValueError for unknown top-level columns.
    """
    top_col = field_path.split('.')[0].split('[')[0]
    if top_col in OSFUSER_STRING_COLUMNS:
        return getattr(user, top_col)
    if top_col in OSFUSER_JSON_COLUMNS:
        # A NULL/empty JSON column is a VALID data state (the user simply has no
        # social/jobs/schools entries), NOT a data defect to fail-fast on. Default
        # to an empty container so the nested read below behaves consistently.
        col_data = getattr(user, top_col) or (dict() if top_col == 'social' else list())
        sub_path = field_path[len(top_col):]
        if sub_path.startswith('.'):
            sub_path = sub_path[1:]
        if not sub_path:
            return col_data
        return _get_nested_value(col_data, sub_path)
    raise ValueError('Unknown field_path top column: {}'.format(top_col))


# --- Scanning Operations ---

def scan_userextendeddata():
    """Scan UserExtendedData.data JSONB field for encoding issues."""
    records = UserExtendedData.objects.select_related('user').all()

    logger.info('Scanning UserExtendedData records...')
    rows = []
    for record in records.iterator():
        if record.user is None:
            raise ValueError('UserExtendedData id={} has no associated user'.format(record.id))
        if not record.user._id:
            raise ValueError('OSFUser id={} has no _id (guid)'.format(record.user.id))
        # NULL/empty `data` is a VALID state (record with no extended data), not a
        # defect: fall back to an empty dict so walk() simply yields nothing.
        data = record.data or {}
        user_guid = record.user._id
        user_id = record.user.id

        for path, val in walk(data):
            row = make_error_row('osf_userextendeddata', record.id, user_guid, user_id, path, val)
            if row:
                rows.append(row)
    logger.info('UserExtendedData scan completed. Found {} error(s).'.format(len(rows)))
    return rows


def scan_osfuser():
    """Scan OSFUser string and JSON columns for encoding issues."""
    records = OSFUser.objects.all()

    logger.info('Scanning OSFUser records...')
    rows = []
    for user in records.iterator():
        if not user._id:
            raise ValueError('OSFUser id={} has no _id (guid)'.format(user.id))
        user_id = user.id
        user_guid = user._id

        # Simple string columns
        for col in OSFUSER_STRING_COLUMNS:
            if not hasattr(user, col):
                raise ValueError('OSFUser model has no attribute "{}"'.format(col))
            val = getattr(user, col)
            if not val:
                continue
            row = make_error_row('osf_osfuser', user_id, user_guid, user_id, col, val)
            if row:
                rows.append(row)

        # JSON columns
        for col in OSFUSER_JSON_COLUMNS:
            if not hasattr(user, col):
                raise ValueError('OSFUser model has no attribute "{}"'.format(col))
            data = getattr(user, col)
            # NULL/empty JSON column is a VALID state (user has no entries for this
            # column), not a defect: nothing to scan, so skip without failing.
            if not data:
                continue
            for path, val in walk(data):
                row = make_error_row('osf_osfuser', user_id, user_guid, user_id,
                                     '{}.{}'.format(col, path), val)
                if row:
                    rows.append(row)
    logger.info('OSFUser scan completed. Found {} error(s).'.format(len(rows)))
    return rows


def print_errors(rows):
    """Display scanned encoding errors in a formatted table."""
    if not rows:
        print('   No encoding errors found.')
        return

    print('\n' + '-' * 180)
    print(' {:<22} | {:>8} | {:>10} | {:<12} | {:<30} | {:<25} | {:<35} | {}'.format(
        'SOURCE', 'ID', 'USER_ID', 'USER_GUID', 'FIELD_PATH', 'ISSUES', 'ORIGINAL_VALUE', 'SUGGESTED_FIX'
    ))
    print('-' * 180)
    for r in rows:
        orig_val = r['original_value'] or ''
        suggested = r['suggested_fix'] or ''
        val_display = orig_val[:33] + '...' if len(orig_val) > 33 else orig_val
        fix_display = suggested[:50] + '...' if len(suggested) > 50 else suggested
        print(
            ' {:<22} | {:>8} | {:>10} | {:<12} | '
            '{:<30} | {:<25} | {:<35} | {}'.format(
                r['source_table'] or '',
                str(r['id']) if r['id'] is not None else '',
                str(r['user_id']) if r['user_id'] is not None else '',
                str(r['user_guid']) if r['user_guid'] is not None else '',
                (r['field_path'] or '')[:30],
                r['issues'] or '',
                val_display,
                fix_display
            )
        )
    print('-' * 180)

    # Summary
    by_table = {}
    for r in rows:
        by_table[r['source_table']] = by_table.get(r['source_table'], 0) + 1
    for table, count in sorted(by_table.items()):
        print('   {}: {} error(s)'.format(table, count))
    print(' Total: {} error(s)'.format(len(rows)))


def save_result_csv(result_rows, output_path):
    """Save full results with before/after status to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(result_rows)
    print('\n Exported {} result(s) to: {}'.format(len(result_rows), output_path))


# --- Updating Operations ---

def apply_fixes(rows, dry_run=False, is_from_csv=False):
    """
    Apply fixes to database using Django ORM inside a transaction.
    If dry_run is True, the transaction will be rolled back at the end.
    Returns list of result rows with fix status.
    """
    # Group changes by model instance to minimize database writes
    ued_updates = {}
    user_updates = {}

    for row in rows:
        if row['source_table'] == 'osf_userextendeddata':
            ued_updates.setdefault(row['id'], []).append(row)
        elif row['source_table'] == 'osf_osfuser':
            user_updates.setdefault(row['id'], []).append(row)

    result_rows = []
    fixable_count = 0
    skipped_count = 0

    if dry_run:
        logger.info('[DRY RUN] Simulating database updates inside a transaction...')
    else:
        logger.info('Starting database transaction to apply fixes...')

    try:
        with transaction.atomic():
            # 1. Update UserExtendedData instances
            for record_id, ued_rows in ued_updates.items():
                try:
                    record = UserExtendedData.objects.get(id=record_id)
                except UserExtendedData.DoesNotExist:
                    raise ValueError('UserExtendedData id={} not found in DB'.format(record_id))

                # NULL/empty `data` is a VALID state, not a defect; default to an
                # empty dict so set_nested_value can build the path to update.
                data = record.data or {}
                has_changes = False

                for row in ued_rows:
                    result = dict(row)
                    result['fix_applied'] = ''
                    result['value_after'] = ''

                    if is_from_csv:
                        should_fix = row.get('fix_applied', '').strip().upper() == 'YES'
                    else:
                        # Only auto-apply clean fixes. 'partial' results lost bytes
                        # and must be reviewed by a human before applying.
                        should_fix = row.get('fix_status') == 'clean'

                    if should_fix:
                        if is_from_csv:
                            current_val = _get_nested_value(data, row['field_path'])
                            if current_val != row.get('original_value', ''):
                                raise ValueError(
                                    'UserExtendedData id={} field={}: original_value in CSV {!r} does not match '
                                    'current DB value {!r}. DB may have been updated after export. '
                                    'Please re-run the dry-run scan and review the CSV again.'.format(
                                        record_id, row['field_path'],
                                        row.get('original_value'), current_val,
                                    )
                                )
                        clean_fix = get_clean_fix(row['suggested_fix'])
                        data = set_nested_value(data, row['field_path'], clean_fix)
                        has_changes = True
                        result['fix_applied'] = 'YES'
                        result['value_after'] = clean_fix
                        fixable_count += 1
                        logger.info('   Fixed: [UserExtendedData] id={} path={}'.format(record_id, row['field_path']))
                    else:
                        if is_from_csv:
                            result['fix_applied'] = row.get('fix_applied', '')
                        elif row.get('fix_status') == 'partial':
                            result['fix_applied'] = 'NO (PARTIAL - REVIEW NEEDED)'
                        else:
                            result['fix_applied'] = 'NO (UNRECOVERABLE)'
                        result['value_after'] = row['original_value']
                        skipped_count += 1

                    result_rows.append(result)

                if has_changes:
                    # Deepcopy to guarantee DirtyFieldsMixin registers the change
                    record.data = copy.deepcopy(data)
                    record.save()

            # 2. Update OSFUser instances
            for user_id, u_rows in user_updates.items():
                try:
                    user = OSFUser.objects.get(id=user_id)
                except OSFUser.DoesNotExist:
                    raise ValueError('OSFUser id={} not found in DB'.format(user_id))

                has_changes = False
                changed_json_cols = set()

                for row in u_rows:
                    result = dict(row)
                    result['fix_applied'] = ''
                    result['value_after'] = ''

                    if is_from_csv:
                        should_fix = row.get('fix_applied', '').strip().upper() == 'YES'
                    else:
                        # Only auto-apply clean fixes. 'partial' results lost bytes
                        # and must be reviewed by a human before applying.
                        should_fix = row.get('fix_status') == 'clean'

                    if should_fix:
                        if is_from_csv:
                            current_val = _get_osfuser_field_value(user, row['field_path'])
                            if current_val != row.get('original_value', ''):
                                raise ValueError(
                                    'OSFUser id={} field={}: original_value in CSV {!r} does not match '
                                    'current DB value {!r}. DB may have been updated after export. '
                                    'Please re-run the dry-run scan and review the CSV again.'.format(
                                        user_id, row['field_path'],
                                        row.get('original_value'), current_val,
                                    )
                                )
                        clean_fix = get_clean_fix(row['suggested_fix'])
                        path = row['field_path']
                        top_col = path.split('.')[0].split('[')[0]

                        if top_col in OSFUSER_STRING_COLUMNS:
                            setattr(user, top_col, clean_fix)
                            has_changes = True
                            result['fix_applied'] = 'YES'
                            result['value_after'] = clean_fix
                            fixable_count += 1
                            logger.info('   Fixed: [OSFUser] id={} field={}'.format(user_id, path))
                        elif top_col in OSFUSER_JSON_COLUMNS:
                            # NULL/empty JSON column is a VALID state, not a defect;
                            # default to an empty container so set_nested_value can
                            # build the path to update.
                            col_data = getattr(user, top_col, None) or (dict() if top_col == 'social' else list())
                            sub_path = path[len(top_col):]
                            if sub_path.startswith('.'):
                                sub_path = sub_path[1:]

                            col_data = set_nested_value(col_data, sub_path, clean_fix)
                            setattr(user, top_col, copy.deepcopy(col_data))
                            has_changes = True
                            changed_json_cols.add(top_col)
                            result['fix_applied'] = 'YES'
                            result['value_after'] = clean_fix
                            fixable_count += 1
                            logger.info('   Fixed: [OSFUser] id={} field={}'.format(user_id, path))
                    else:
                        if is_from_csv:
                            result['fix_applied'] = row.get('fix_applied', '')
                        elif row.get('fix_status') == 'partial':
                            result['fix_applied'] = 'NO (PARTIAL - REVIEW NEEDED)'
                        else:
                            result['fix_applied'] = 'NO (UNRECOVERABLE)'
                        result['value_after'] = row['original_value']
                        skipped_count += 1

                    result_rows.append(result)

                if has_changes:
                    # Validate only the JSON column(s) we modified, using the field's own
                    # validators (validate_social / validate_history_item). We deliberately
                    # avoid full_clean() so unrelated/legacy fields cannot block a legitimate
                    # fix and to skip uniqueness DB queries. Note: these validators check the
                    # whole column value, so pre-existing invalid data in the same column will
                    # also trigger a fail-fast here.
                    for col in changed_json_cols:
                        try:
                            OSFUser._meta.get_field(col).run_validators(getattr(user, col))
                        except DjangoValidationError as e:
                            raise ValueError(
                                'OSFUser id={} column "{}" failed model validation after applying the fix: {}. '
                                'The column may contain other invalid/legacy data; please review the record.'.format(
                                    user_id, col, '; '.join(e.messages),
                                )
                            )
                    user.save()

            if dry_run:
                # Rollback transaction so no database changes are saved
                transaction.set_rollback(True)
                logger.info('[DRY RUN] Transaction rolled back successfully. No changes saved.')
            else:
                logger.info('Transaction committed successfully.')

        if not dry_run:
            logger.info('Applied: {} fix(es), Skipped: {} record(s)'.format(fixable_count, skipped_count))
        else:
            logger.info('[DRY RUN] Would apply {} fix(es) and skip {} record(s)'.format(fixable_count, skipped_count))

    except Exception as e:
        logger.exception('Error during transaction execution - rolled back.')
        raise

    return result_rows


# --- Main ---

def main():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_output = f'fix_result_{ts}.csv'

    parser = argparse.ArgumentParser(
        description='Scan and fix encoding errors in UserExtendedData and OSFUser using Django ORM.',
    )
    parser.add_argument(
        '--output', '-o',
        default=default_output,
        help=f'Output CSV file path (default: {default_output})',
    )
    parser.add_argument(
        '--dry', action='store_true', default=False,
        help='Run script in dry-run mode (do not commit updates to the database).',
    )
    parser.add_argument(
        '--input-csv', '-i',
        default=None,
        help='Input CSV file generated in a dry run to apply specific fixes from.',
    )

    args = parser.parse_args()

    if not args.dry and not args.input_csv:
        parser.error('the following arguments are required: --input-csv/-i (unless running in dry run mode with --dry)')

    if not args.dry:
        # For actual runs modifying data, set up file logging
        script_utils.add_file_logger(logger, __file__)

    # Configure root/console logging format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )

    # 1. Scan errors or load from CSV
    rows = []
    is_from_csv = False
    if args.input_csv:
        logger.info('Loading records to fix from CSV file: {}'.format(args.input_csv))
        if not os.path.exists(args.input_csv):
            print('Error: Input CSV file "{}" does not exist.'.format(args.input_csv))
            sys.exit(1)

        try:
            with open(args.input_csv, mode='r', encoding='utf-8-sig') as f:
                # restkey/restval let us detect rows whose column count differs
                # from the header: extra fields land in '__overflow__', missing
                # trailing fields are filled with None.
                reader = csv.DictReader(f, restkey='__overflow__', restval=None)

                # Check headers: must match the exported schema exactly
                # (correct column names, no missing column, no extra column).
                if not reader.fieldnames:
                    print('Error: Input CSV has no header row.')
                    sys.exit(1)
                expected_headers = set(RESULT_FIELDNAMES)
                actual_headers = set(reader.fieldnames)
                missing_cols = expected_headers - actual_headers
                extra_cols = actual_headers - expected_headers
                if missing_cols or extra_cols:
                    msg = 'Error: Input CSV header does not match the expected schema ({} columns).'.format(len(RESULT_FIELDNAMES))
                    if missing_cols:
                        msg += ' Missing column(s): {}.'.format(', '.join(sorted(missing_cols)))
                    if extra_cols:
                        msg += ' Unexpected column(s): {}.'.format(', '.join(sorted(extra_cols)))
                    print(msg)
                    sys.exit(1)

                try:
                    for line_no, row in enumerate(reader, start=2):
                        if not row:
                            continue

                        # Validate column count on this data row (no missing/extra fields)
                        if row.get('__overflow__') is not None:
                            print('Error: Row {} is invalid: it has more columns than the header.'.format(line_no))
                            sys.exit(1)
                        if any(value is None for key, value in row.items() if key != '__overflow__'):
                            print('Error: Row {} is invalid: it has fewer columns than the header.'.format(line_no))
                            sys.exit(1)

                        # Validate source_table
                        source_table = row.get('source_table')
                        if not source_table:
                            print('Error: Row {} is invalid: missing "source_table".'.format(line_no))
                            sys.exit(1)
                        source_table = source_table.strip()
                        if source_table not in ('osf_userextendeddata', 'osf_osfuser'):
                            print('Error: Row {} is invalid: "source_table" "{}" is not a recognised value.'.format(line_no, source_table))
                            sys.exit(1)

                        # Validate id
                        id_val = row.get('id')
                        if not id_val:
                            print('Error: Row {} is invalid: missing "id".'.format(line_no))
                            sys.exit(1)
                        try:
                            record_id = int(id_val.strip())
                        except ValueError:
                            print('Error: Row {} is invalid: "id" "{}" is not a valid integer.'.format(line_no, id_val))
                            sys.exit(1)

                        # Validate field_path
                        field_path = row.get('field_path')
                        if not field_path:
                            print('Error: Row {} is invalid: missing "field_path".'.format(line_no))
                            sys.exit(1)
                        field_path = field_path.strip()

                        # Validate required identity columns. These echo the exported
                        # record and must not be blank (the customer asked for an
                        # explicit empty-check on required fields such as user._id).
                        user_guid = (row.get('user_guid') or '').strip()
                        if not user_guid:
                            print('Error: Row {} is invalid: missing "user_guid".'.format(line_no))
                            sys.exit(1)
                        user_id = (row.get('user_id') or '').strip()
                        if not user_id:
                            print('Error: Row {} is invalid: missing "user_id".'.format(line_no))
                            sys.exit(1)

                        # Validate suggested_fix if fix_applied is YES
                        fix_applied = (row.get('fix_applied') or '').strip()
                        suggested_fix = row.get('suggested_fix') or ''
                        if fix_applied.upper() == 'YES' and not suggested_fix:
                            print('Error: Row {} is invalid: "fix_applied" is "YES" but "suggested_fix" is empty.'.format(line_no))
                            sys.exit(1)
                        # Refuse to apply a value that still carries an UNRECOVERABLE marker,
                        # otherwise the literal marker text would be written into the DB.
                        if fix_applied.upper() == 'YES' and '[UNRECOVERABLE:' in suggested_fix:
                            print(
                                'Error: Row {} is invalid: "fix_applied" is "YES" but "suggested_fix" still '
                                'contains an UNRECOVERABLE marker ({!r}). Set "fix_applied" to NO, or replace '
                                '"suggested_fix" with the corrected value (remove the marker text).'.format(
                                    line_no, suggested_fix,
                                )
                            )
                            sys.exit(1)

                        # Refuse to apply a value that still contains the Unicode
                        # replacement character (U+FFFD). It signals a partial decode
                        # that lost bytes; Django model constraints accept it on save(),
                        # so we must fail fast here instead of writing corrupted data.
                        if fix_applied.upper() == 'YES' and REPLACEMENT_CHAR in get_clean_fix(suggested_fix):
                            print(
                                'Error: Row {} is invalid: "fix_applied" is "YES" but "suggested_fix" still '
                                'contains the Unicode replacement character (U+FFFD "{}"), which means the value '
                                'was not fully recovered. Set "fix_applied" to NO, or replace "suggested_fix" '
                                'with a fully corrected value.'.format(line_no, REPLACEMENT_CHAR)
                            )
                            sys.exit(1)

                        # When this row will be applied, validate the target column and the
                        # corrected value itself (column existence / length / residual issues).
                        if fix_applied.upper() == 'YES':
                            clean_fix = get_clean_fix(suggested_fix)
                            top_col = field_path.split('.')[0].split('[')[0]

                            if source_table == 'osf_osfuser':
                                if top_col not in OSFUSER_STRING_COLUMNS and top_col not in OSFUSER_JSON_COLUMNS:
                                    print('Error: Row {} is invalid: "field_path" top column "{}" is not a known OSFUser column.'.format(line_no, top_col))
                                    sys.exit(1)
                                # CharField columns are constrained by the DB (varchar(max_length)).
                                # Check it early here so we fail fast with a clear message instead
                                # of a low-level DataError mid-transaction.
                                if top_col in OSFUSER_STRING_COLUMNS:
                                    max_len = OSFUser._meta.get_field(top_col).max_length
                                    if max_len is not None and len(clean_fix) > max_len:
                                        print('Error: Row {} is invalid: "suggested_fix" length {} exceeds the max_length {} of column "{}".'.format(
                                            line_no, len(clean_fix), max_len, top_col))
                                        sys.exit(1)

                            # Warn (do not stop) if the corrected value still appears to contain
                            # encoding / HTML-entity issues. This is heuristic: accented Latin
                            # letters can trigger a false positive, so a human should confirm.
                            residual_issues = detect_issues(clean_fix)
                            if residual_issues:
                                logger.warning(
                                    'Row %s: "suggested_fix" still appears to contain issue(s) [%s] after the fix: %r. '
                                    'Please double-check this is a legitimate value before applying.',
                                    line_no, ','.join(residual_issues), clean_fix,
                                )

                        rows.append({
                            'source_table': source_table,
                            'id': record_id,
                            'user_guid': user_guid,
                            'user_id': user_id,
                            'field_path': field_path,
                            'issues': (row.get('issues') or '').strip(),
                            'original_value': row.get('original_value') or '',
                            'suggested_fix': suggested_fix,
                            'fix_applied': fix_applied,
                            'fix_status': compute_fix_status(suggested_fix),
                        })
                except csv.Error as e:
                    print('Error: Failed to parse CSV file "{}" due to formatting error: {}'.format(args.input_csv, e))
                    sys.exit(1)
        except Exception:
            # Fail fast: log the full traceback and re-raise so the unexpected
            # error is not swallowed. (sys.exit(1) above raises SystemExit, which
            # is not an Exception subclass, so the explicit validation exits are
            # unaffected by this handler.)
            logger.exception('Unexpected error while opening/reading CSV file "%s".', args.input_csv)
            raise

        is_from_csv = True
        logger.info('Loaded {} records from CSV.'.format(len(rows)))
    else:
        # Default: scan database
        rows.extend(scan_userextendeddata())
        rows.extend(scan_osfuser())

    if not rows:
        print('No encoding errors found.')
        return

    # Print the table of found/loaded errors
    if rows:
        print_errors(rows)

    # 2. Apply fixes (conditionally committing or rolling back)
    result_rows = apply_fixes(rows, dry_run=args.dry, is_from_csv=is_from_csv)

    # 3. Export results to CSV
    save_result_csv(result_rows, args.output)


if __name__ == '__main__':
    main()

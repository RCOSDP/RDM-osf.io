#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_encoding_errors_django.py

Scan and fix Japanese encoding issues and HTML entities using Django ORM,
then export the results directly to a CSV file.
This script targets:
  - UserExtendedData (field: data JSONB)
  - OSFUser (fields: fullname, given_name, middle_names, family_name,
                      suffix, given_name_ja, middle_names_ja, family_name_ja,
                      department, jobs, schools, social)

Usage:
    # Scan, update encoding errors in DB using Django ORM, and export results to CSV
    python -m scripts.fix_encoding_errors_django
    python -m scripts.fix_encoding_errors_django --output result.csv

    # Preview updates and export results to CSV without making changes to DB (dry run)
    python -m scripts.fix_encoding_errors_django --dry
    python -m scripts.fix_encoding_errors_django --dry --include-unrecoverable --output preview.csv
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

# Setup Django before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.base.settings')
django.setup()

from osf.models import UserExtendedData, OSFUser
from scripts import utils as script_utils

logger = logging.getLogger(__name__)

# --- Patterns ---
HTML_ENTITY_RE = re.compile(r'&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);')
JAPANESE_ERROR_ENCODING_HINT_RE = re.compile(r'[ÃÂâãåÄäªº\u00c3\u00c2\u00e3\u00e2]')
_NUM_ENT_RE = re.compile(r'&#(\d+);|&#x([0-9a-fA-F]+);')

UNRECOVERABLE_NOTICE = '[UNRECOVERABLE: missing bytes - partial result] '
UNRECOVERABLE_CANNOT_FIX = '[UNRECOVERABLE: cannot fix]'

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
    'issues', 'original_value', 'suggested_fix', 'fix_applied', 'value_after',
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
        except Exception:
            return None, False
    except Exception:
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
    }


def is_fixable(row, include_unrecoverable):
    """Determine whether a row can/should be applied as a fix."""
    sf = row['suggested_fix']
    if sf == UNRECOVERABLE_CANNOT_FIX:
        return False
    if sf.startswith(UNRECOVERABLE_NOTICE):
        return include_unrecoverable
    return True


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


# --- Scanning Operations ---

def scan_userextendeddata():
    """Scan UserExtendedData.data JSONB field for encoding issues."""
    records = UserExtendedData.objects.select_related('user').all()

    logger.info('Scanning UserExtendedData records...')
    rows = []
    for record in records.iterator():
        data = record.data or {}
        user_guid = record.user._id if record.user else 'N/A'
        user_id = record.user.id if record.user else 'N/A'

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
        user_id = user.id
        user_guid = user._id or 'N/A'

        # Simple string columns
        for col in OSFUSER_STRING_COLUMNS:
            val = getattr(user, col, None)
            if not val:
                continue
            row = make_error_row('osf_osfuser', user_id, user_guid, user_id, col, val)
            if row:
                rows.append(row)

        # JSON columns
        for col in OSFUSER_JSON_COLUMNS:
            data = getattr(user, col, None)
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

def apply_fixes(rows, include_unrecoverable, dry_run=False):
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
                record = UserExtendedData.objects.get(id=record_id)
                data = record.data or {}
                has_changes = False

                for row in ued_rows:
                    result = dict(row)
                    result['fix_applied'] = ''
                    result['value_after'] = ''

                    if is_fixable(row, include_unrecoverable):
                        clean_fix = get_clean_fix(row['suggested_fix'])
                        data = set_nested_value(data, row['field_path'], clean_fix)
                        has_changes = True
                        result['fix_applied'] = 'YES'
                        result['value_after'] = clean_fix
                        fixable_count += 1
                        logger.info('   Fixed: [UserExtendedData] id={} path={}'.format(record_id, row['field_path']))
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
                user = OSFUser.objects.get(id=user_id)
                has_changes = False

                for row in u_rows:
                    result = dict(row)
                    result['fix_applied'] = ''
                    result['value_after'] = ''

                    if is_fixable(row, include_unrecoverable):
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
                            col_data = getattr(user, top_col, None) or (dict() if top_col == 'social' else list())
                            sub_path = path[len(top_col):]
                            if sub_path.startswith('.'):
                                sub_path = sub_path[1:]

                            col_data = set_nested_value(col_data, sub_path, clean_fix)
                            setattr(user, top_col, copy.deepcopy(col_data))
                            has_changes = True
                            result['fix_applied'] = 'YES'
                            result['value_after'] = clean_fix
                            fixable_count += 1
                            logger.info('   Fixed: [OSFUser] id={} field={}'.format(user_id, path))
                    else:
                        result['fix_applied'] = 'NO (UNRECOVERABLE)'
                        result['value_after'] = row['original_value']
                        skipped_count += 1

                    result_rows.append(result)

                if has_changes:
                    user.save()

            if dry_run:
                # Rollback transaction so no database changes are saved
                transaction.set_rollback(True)
                logger.info('[DRY RUN] Transaction rolled back successfully. No changes saved.')
            else:
                logger.info('Transaction committed successfully.')

        if not dry_run:
            logger.info('Applied: {} fix(es), Skipped: {} UNRECOVERABLE record(s)'.format(fixable_count, skipped_count))
        else:
            logger.info('[DRY RUN] Would apply {} fix(es) and skip {} UNRECOVERABLE record(s)'.format(fixable_count, skipped_count))

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
        '--include-unrecoverable', action='store_true', default=False,
        help='Also apply fixes for records marked as unrecoverable/partial result.',
    )
    parser.add_argument(
        '--dry', action='store_true', default=False,
        help='Run script in dry-run mode (do not commit updates to the database).',
    )

    args = parser.parse_args()

    if not args.dry:
        # For actual runs modifying data, set up file logging
        script_utils.add_file_logger(logger, __file__)

    # Configure root/console logging format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
    )

    # 1. Scan errors
    rows = []
    rows.extend(scan_userextendeddata())
    rows.extend(scan_osfuser())

    if not rows:
        print('   No encoding errors found.')
        return

    # Print the table of found errors
    print_errors(rows)

    # 2. Apply fixes (conditionally committing or rolling back)
    result_rows = apply_fixes(rows, args.include_unrecoverable, dry_run=args.dry)

    # 3. Export results to CSV
    save_result_csv(result_rows, args.output)


if __name__ == '__main__':
    main()

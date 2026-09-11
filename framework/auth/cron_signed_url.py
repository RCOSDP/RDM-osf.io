# -*- coding: utf-8 -*-
"""HMAC-signed, time-limited URL auth for cron-triggered admin endpoints.

Used by No.1 (admin/rdm_custom_storage_location/views.py:external_acc_update)
and No.82 (admin/rdm_statistics/views.py:GatherView), which are called by
cron.sh scripts with no interactive user/session. A signed URL looks like
`.../<ts>/<signature>/`, where `ts` is a microsecond-resolution Unix
timestamp and `signature` is HMAC(secret, ts).

Security comes from two independent checks, both required:
  1. authenticity - signature must match HMAC(CRON_SIGNED_URL_SECRET, ts)
  2. freshness - ts must be within CRON_SIGNED_URL_TTL_SECONDS of "now"

Timestamp precision (microseconds) does not itself add security - it is a
customer requirement, not a defense mechanism. Both checks above are what
actually make an intercepted URL become useless after CRON_SIGNED_URL_TTL_SECONDS.
"""
import hmac
import time

from website import settings


def _sign(ts):
    return hmac.new(
        key=settings.CRON_SIGNED_URL_SECRET.encode('utf-8'),
        msg=str(ts).encode('utf-8'),
        digestmod=settings.CRON_SIGNED_URL_HMAC_ALGORITHM,
    ).hexdigest()


def generate_signed_params():
    """Returns (ts, signature) as strings, ready to drop into a URL path.

    ts is a microsecond-resolution Unix timestamp (str), per customer
    requirement (see module docstring).
    """
    ts = str(int(time.time() * 1000000))
    return ts, _sign(ts)


def verify_signed_params(ts, signature, ttl_seconds=None):
    """Verifies a (ts, signature) pair produced by generate_signed_params().

    Returns True only if signature matches ts AND ts is within ttl_seconds
    of now (in either direction). Returns False for any malformed input
    instead of raising.
    """
    if ttl_seconds is None:
        ttl_seconds = settings.CRON_SIGNED_URL_TTL_SECONDS
    if not ts or not signature:
        return False
    try:
        ts_us = int(ts)
    except (TypeError, ValueError):
        return False
    expected_signature = _sign(ts)
    if not hmac.compare_digest(expected_signature, signature.lower()):
        return False
    now_us = int(time.time() * 1000000)
    ttl_us = int(ttl_seconds * 1000000)
    return abs(now_us - ts_us) <= ttl_us

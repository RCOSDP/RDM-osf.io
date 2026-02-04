# -*- coding: utf-8 -*-
"""Keyset utilities for workflow gateway integration."""

from pathlib import Path
from typing import Dict, List

from rest_framework import status as http_status

from framework.exceptions import HTTPError

from addons.workflow import settings as workflow_settings


def _read_text(path: str) -> str:
    resolved = Path(path)
    if not resolved.exists():
        raise HTTPError(http_status.HTTP_404_NOT_FOUND, data={'message': f'Workflow gateway key file not found: {path}'})

    try:
        content = resolved.read_text()
    except OSError as error:
        raise HTTPError(http_status.HTTP_500_INTERNAL_SERVER_ERROR, data={'message': f'Failed to read key file: {path}'}) from error

    return content.strip()


def build_public_keyset() -> Dict[str, List[Dict[str, str]]]:
    """Construct a JWKS-like payload from configured key specifications."""
    specs = workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS
    if not specs:
        raise HTTPError(http_status.HTTP_503_SERVICE_UNAVAILABLE, data={'message': 'Workflow gateway keys are not configured.'})

    keys: List[Dict[str, str]] = []
    for spec in specs:
        kid = spec['kid']
        algorithm = spec['alg']

        if algorithm.startswith('HS'):
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': f'HMAC algorithm not supported for gateway key {kid}.'})

        public_key = _read_text(spec['public_key_path'])

        # Ensure private key exists as well (used when signing tokens).
        _read_text(spec['private_key_path'])

        keys.append({
            'kid': kid,
            'alg': algorithm,
            'public_key': public_key,
        })

    return {'keys': keys}

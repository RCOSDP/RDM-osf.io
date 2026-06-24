# -*- coding: utf-8 -*-
"""Utilities for managing workflow engine public keys."""

from typing import Dict, NamedTuple, Tuple

from rest_framework import status as http_status

from framework.exceptions import HTTPError

from addons.workflow.models import WorkflowEngineKey


class EnginePublicKey(NamedTuple):
    engine_id: str
    kid: str
    algorithm: str
    public_key: str


def _normalize_entry(entry: WorkflowEngineKey) -> EnginePublicKey:
    return EnginePublicKey(
        engine_id=entry.engine_id,
        kid=entry.kid,
        algorithm=entry.algorithm,
        public_key=entry.public_key,
    )


def list_engine_public_keys() -> Dict[Tuple[str, str], EnginePublicKey]:
    """Return active workflow engine keys indexed by (engine_id, kid)."""
    records: Dict[Tuple[str, str], EnginePublicKey] = {}
    for entry in WorkflowEngineKey.objects.filter(is_active=True):
        records[(entry.engine_id, entry.kid)] = _normalize_entry(entry)
    return records


def get_engine_public_key(engine_id: str, kid: str) -> EnginePublicKey:
    try:
        entry = WorkflowEngineKey.objects.get(engine_id=engine_id, kid=kid, is_active=True)
    except WorkflowEngineKey.DoesNotExist as error:
        raise HTTPError(http_status.HTTP_404_NOT_FOUND, data={'message': f'Unknown workflow engine key (engine_id={engine_id}, kid={kid})'}) from error
    return _normalize_entry(entry)

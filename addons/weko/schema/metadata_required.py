# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Set


def _has_value(entry: Any) -> bool:
    v = entry.get('value') if isinstance(entry, dict) else entry

    if v is None:
        return False

    if isinstance(v, str):
        s = v.strip()
        return not (s == '' or s == '[]')

    if isinstance(v, list):
        return len(v) > 0

    return True


def _collect_required_qids(schema: Dict[str, Any]) -> Set[str]:
    req: Set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get('required') is True and isinstance(node.get('qid'), str):
                req.add(node['qid'])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema or {})
    return req


def _normalize_project_meta(pm: Any) -> Dict[str, Any]:
    if isinstance(pm, list):
        pm = pm[0] if pm else {}
    if not isinstance(pm, dict):
        return {}
    out: Dict[str, Any] = {}
    for k, v in pm.items():
        if isinstance(v, dict):
            out[k] = v
        elif isinstance(v, list):
            out[k] = [x if isinstance(x, dict) else {'value': x} for x in v]
        else:
            out[k] = {'value': v}
    return out


def find_missing_required_fields(schema: Dict[str, Any], project_meta: Any) -> List[str]:
    pm = _normalize_project_meta(project_meta)
    missing: List[str] = []
    for qid in sorted(_collect_required_qids(schema)):
        if not _has_value(pm.get(qid)):
            missing.append(qid)
    return missing


def is_mebyo_schema(schema_id: str) -> bool:
    from ..models import RegistrationMetadataMapping
    from .constants_mebyo import MEBYO_SCHEMA_NAME
    mapping_def = RegistrationMetadataMapping.objects.filter(
        registration_schema_id=schema_id,
        filename='ro-crate-metadata.json',
    ).first()

    if mapping_def is None:
        return False
    try:
        return mapping_def.rules.get('@metadata', {}).get('schemaname') == MEBYO_SCHEMA_NAME
    except AttributeError:
        return False

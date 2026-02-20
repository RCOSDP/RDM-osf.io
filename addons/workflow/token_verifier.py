# -*- coding: utf-8 -*-
"""Verification helpers for tokens issued by workflow engines/gateways."""

from typing import Any, Dict, Optional

import jwt
from rest_framework import status as http_status

from framework.exceptions import HTTPError

from addons.workflow.engine_keys import get_engine_public_key


def verify_engine_token(token: str, engine_id: str, *, audience: Optional[str] = None, issuer: Optional[str] = None) -> Dict[str, Any]:
    """Verify a JWT presented by a workflow engine/gateway."""

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as error:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Malformed gateway token header.'}) from error

    kid = header.get('kid')
    if not kid:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST, data={'message': 'Gateway token missing kid.'})

    key = get_engine_public_key(engine_id, kid)

    decode_kwargs: Dict[str, Any] = {
        'algorithms': [key.algorithm],
        'options': {'verify_aud': False},
    }
    if audience:
        decode_kwargs['audience'] = audience
        decode_kwargs['options']['verify_aud'] = True
    if issuer:
        decode_kwargs['issuer'] = issuer

    try:
        payload = jwt.decode(token, key.public_key, **decode_kwargs)
    except jwt.ExpiredSignatureError as error:
        raise HTTPError(http_status.HTTP_401_UNAUTHORIZED, data={'message': 'Gateway token expired.'}) from error
    except jwt.InvalidTokenError as error:
        raise HTTPError(http_status.HTTP_401_UNAUTHORIZED, data={'message': 'Gateway token invalid.'}) from error

    presented_engine_id = payload.get('engine_id')
    if presented_engine_id and presented_engine_id != engine_id:
        raise HTTPError(http_status.HTTP_401_UNAUTHORIZED, data={'message': 'Gateway token engine_id mismatch.'})

    return payload

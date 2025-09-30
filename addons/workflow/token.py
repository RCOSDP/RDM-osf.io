# -*- coding: utf-8 -*-
"""Token management for workflow delegation."""

import logging
from typing import Any, Dict

from rest_framework import status as http_status

from framework.exceptions import HTTPError
from osf.models import ApiOAuth2PersonalToken, ApiOAuth2Scope

logger = logging.getLogger(__name__)


ALLOWED_TOKEN_MODES = frozenset({'none', 'read', 'readwrite'})
ALLOWED_TOKEN_ROLES = frozenset({'creator', 'manager', 'executor'})
REQUIRED_DELEGATION_FIELDS = frozenset({'token_id', 'token_value', 'scope', 'token_owner'})

TOKEN_MODE_TO_SCOPE = {
    'read': ['osf.full_read'],
    'readwrite': ['osf.full_read', 'osf.full_write'],
}


def validate_token_settings(data: Any) -> Dict[str, str]:
    """Validate token_settings structure for user mode requests.

    Expected structure:
        {
            "creator_mode": "readwrite",
            "manager_mode": "read",
            "executor_mode": "none"
        }

    Args:
        data: User-provided token_settings data

    Returns:
        Validated token_settings dictionary

    Raises:
        HTTPError: On validation failure
    """
    if not isinstance(data, dict):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'token_settings must be a dict'},
        )

    validated: Dict[str, str] = {}
    for role in ALLOWED_TOKEN_ROLES:
        key = f'{role}_mode'
        if key in data:
            mode = data[key]
            if mode not in ALLOWED_TOKEN_MODES:
                raise HTTPError(
                    http_status.HTTP_400_BAD_REQUEST,
                    data={'message': f'Invalid {key}: must be one of {ALLOWED_TOKEN_MODES}'},
                )
            validated[key] = mode

    extra_keys = set(data.keys()) - {f'{r}_mode' for r in ALLOWED_TOKEN_ROLES}
    if extra_keys:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': f'Unexpected keys in token_settings: {sorted(extra_keys)}'},
        )

    return validated


def validate_delegation_tokens(data: Any) -> Dict[str, Dict[str, str]]:
    """Validate delegation_tokens structure for issued tokens.

    Expected structure:
        {
            "creator": {
                "token_id": "abc123",
                "token_value": "tok_...",
                "scope": "osf.full_write",
                "token_owner": "user123"
            }
        }

    Args:
        data: System-managed delegation_tokens data

    Returns:
        Validated delegation_tokens dictionary

    Raises:
        HTTPError: On validation failure
    """
    if not isinstance(data, dict):
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': 'delegation_tokens must be a dict'},
        )

    validated: Dict[str, Dict[str, str]] = {}
    for role, token_data in data.items():
        if role not in ALLOWED_TOKEN_ROLES:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': f'Invalid delegation token role: {role}'},
            )

        if not isinstance(token_data, dict):
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': f'delegation_tokens[{role}] must be a dict'},
            )

        missing = REQUIRED_DELEGATION_FIELDS - set(token_data.keys())
        if missing:
            raise HTTPError(
                http_status.HTTP_400_BAD_REQUEST,
                data={'message': f'delegation_tokens[{role}] missing required fields: {sorted(missing)}'},
            )

        for field in REQUIRED_DELEGATION_FIELDS:
            if not isinstance(token_data[field], str):
                raise HTTPError(
                    http_status.HTTP_400_BAD_REQUEST,
                    data={'message': f'delegation_tokens[{role}][{field}] must be a string'},
                )

        validated[role] = {
            'token_id': token_data['token_id'],
            'token_value': token_data['token_value'],
            'scope': token_data['scope'],
            'token_owner': token_data['token_owner'],
        }

    return validated


def create_delegation_token(user, role: str, mode: str, label: str = '') -> Dict[str, str]:
    """Create a Personal Access Token for workflow delegation.

    Args:
        user: OSFUser who will own this token
        role: Token role ('creator', 'manager', 'executor')
        mode: Token mode ('read', 'readwrite')
        label: Optional descriptive label for the token name

    Returns:
        Dictionary with token_id (PAT _id for revocation), token_value (actual token), scope, and token_owner (user._id)

    Raises:
        HTTPError: On validation failure
    """
    if role not in ALLOWED_TOKEN_ROLES:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': f'Invalid role: {role}'},
        )

    if mode not in TOKEN_MODE_TO_SCOPE:
        raise HTTPError(
            http_status.HTTP_400_BAD_REQUEST,
            data={'message': f'Invalid mode: {mode}. Must be "read" or "readwrite".'},
        )

    scope_names = TOKEN_MODE_TO_SCOPE[mode]

    scopes = []
    for scope_name in scope_names:
        scope = ApiOAuth2Scope.objects.filter(name=scope_name, is_active=True, is_public=True).first()
        if not scope:
            logger.error(f'[Workflow Token] Scope not found: {scope_name}')
            raise HTTPError(
                http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                data={'message': f'Scope {scope_name} not found or inactive'},
            )
        scopes.append(scope)

    token_name = f'Workflow delegation: {role}'
    if label:
        token_name += f' ({label})'

    token = ApiOAuth2PersonalToken(
        owner=user,
        name=token_name,
    )
    token.save()
    for scope in scopes:
        token.scopes.add(scope)

    return {
        'token_id': token._id,
        'token_value': token.token_id,
        'scope': scope_name,
        'token_owner': user._id,
    }


def revoke_delegation_token(token_id: str) -> None:
    """Revoke a delegation PAT by its database ID.

    Args:
        token_id: The _id of the ApiOAuth2PersonalToken

    Raises:
        HTTPError: If token not found
    """
    token = ApiOAuth2PersonalToken.objects.filter(_id=token_id).first()
    if not token:
        raise HTTPError(
            http_status.HTTP_404_NOT_FOUND,
            data={'message': f'Token {token_id} not found'},
        )

    token.deactivate(save=True)

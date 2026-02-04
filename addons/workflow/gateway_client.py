# -*- coding: utf-8 -*-
"""HTTP client for interacting with external workflow gateways."""

import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import jwt
import requests
from rest_framework import status as http_status

from framework.exceptions import HTTPError

from addons.workflow import settings as workflow_settings
from addons.workflow.models import WorkflowEngine


DEFAULT_TOKEN_SUBJECT = 'rdm-workflow-service'
DEFAULT_TOKEN_SCOPE = 'workflow::delegate'
DEFAULT_TOKEN_LIFETIME_SECONDS = 300
DEFAULT_REQUEST_TIMEOUT = 10


class WorkflowGatewayConfigurationError(HTTPError):
    """Raised when the gateway client configuration is incomplete."""

    def __init__(self, message: str):
        super().__init__(http_status.HTTP_503_SERVICE_UNAVAILABLE, data={'message': message})


class WorkflowGatewayClientError(HTTPError):
    """Raised when an upstream gateway request fails."""

    def __init__(self, status_code: int, message: str, detail: Optional[Any] = None):
        payload: Dict[str, Any] = {'message': message}
        if detail is not None:
            payload['detail'] = detail
        super().__init__(status_code, data=payload)


@lru_cache(maxsize=None)
def _load_private_key(path: str) -> str:
    resolved = Path(path)
    if not resolved.exists():
        raise WorkflowGatewayConfigurationError(f'Workflow gateway signing key not found: {path}')
    try:
        return resolved.read_text()
    except OSError as error:
        raise WorkflowGatewayConfigurationError(f'Failed to read workflow gateway signing key: {path}') from error


@lru_cache(maxsize=None)
def _get_key_spec_by_kid(kid: str) -> Dict[str, Any]:
    for spec in workflow_settings.RDM_TO_WORKFLOW_GATEWAY_KEYS:
        if spec.get('kid') == kid:
            return spec
    raise WorkflowGatewayConfigurationError(f'Unknown signing kid for workflow gateway: {kid}')


class WorkflowGatewayClient:
    """Small wrapper around the workflow gateway REST interface."""

    def __init__(self, engine_id: str, *, allow_inactive: bool = False):
        self.engine_id = engine_id
        try:
            if allow_inactive:
                engine = WorkflowEngine.objects.get(engine_id=engine_id)
            else:
                engine = WorkflowEngine.objects.get(engine_id=engine_id, is_active=True)
        except WorkflowEngine.DoesNotExist as error:
            raise WorkflowGatewayConfigurationError(
                f'Workflow engine not configured or inactive: {engine_id}'
            ) from error

        self._engine = engine
        self._base_url = engine.gateway_base_url
        self._signing_kid = engine.signing_kid
        self._key_spec = _get_key_spec_by_kid(self._signing_kid)
        self._timeout = engine.request_timeout or DEFAULT_REQUEST_TIMEOUT
        self._verify_ssl = engine.verify_ssl

    def _issue_token(self) -> str:
        now = int(time.time())
        ttl = int(self._engine.token_lifetime_seconds or DEFAULT_TOKEN_LIFETIME_SECONDS)
        subject = self._engine.token_subject or DEFAULT_TOKEN_SUBJECT
        scope = self._engine.token_scope or DEFAULT_TOKEN_SCOPE
        audience = self._engine.token_audience
        issuer = self._engine.token_issuer
        engine_claim_name = self._engine.engine_claim or 'engine_id'
        engine_claim_value = self._engine.resolved_engine_claim_value

        payload: Dict[str, Any] = {
            'sub': subject,
            'iat': now,
            'exp': now + ttl,
        }
        if scope:
            payload['scope'] = scope
        if audience:
            payload['aud'] = audience
        if issuer:
            payload['iss'] = issuer
        if engine_claim_name:
            payload[engine_claim_name] = engine_claim_value

        headers = {'kid': self._signing_kid}
        private_key_path = self._key_spec.get('private_key_path')
        if not private_key_path:
            raise WorkflowGatewayConfigurationError(
                f'private_key_path missing for signing kid={self._signing_kid}'
            )
        private_key = _load_private_key(private_key_path)
        algorithm = self._key_spec.get('alg') or 'RS256'

        token = jwt.encode(payload, private_key, algorithm=algorithm, headers=headers)
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        return token

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        base = self._base_url.rstrip('/') + '/'
        url = urljoin(base, path.lstrip('/'))
        token = self._issue_token()
        headers = {'Authorization': f'Bearer {token}'}
        try:
            response = requests.request(
                method,
                url,
                params=params,
                json=json,
                files=files,
                data=data,
                headers=headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
            )
        except requests.RequestException as error:
            raise WorkflowGatewayClientError(
                http_status.HTTP_502_BAD_GATEWAY,
                'Failed to contact workflow gateway',
                detail=str(error),
            ) from error

        if response.status_code >= 400:
            detail: Any
            try:
                detail = response.json()
            except ValueError:
                detail = response.text or None
            raise WorkflowGatewayClientError(
                response.status_code,
                'Workflow gateway request failed',
                detail=detail,
            )

        if not response.content:
            return None
        content_type = response.headers.get('Content-Type', '')
        if 'json' in content_type:
            return response.json()
        return response.text

    def list_process_definitions(self, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', '/flowable/process-definitions', params=params)

    def get_process_definition(self, definition_id: str) -> Any:
        return self._request('GET', f'/flowable/process-definitions/{definition_id}')

    def get_process_definition_start_form(self, definition_id: str) -> Any:
        return self._request('GET', f'/flowable/process-definitions/{definition_id}/start-form')

    def list_process_instances(self, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', '/flowable/process-instances', params=params)

    def get_process_instance(self, instance_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', f'/flowable/process-instances/{instance_id}', params=params)

    def start_process_instance(self, payload: Dict[str, Any]) -> Any:
        return self._request('POST', '/flowable/process-instances', json=payload)

    def list_tasks(self, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', '/flowable/tasks', params=params)

    def get_task(self, task_id: str) -> Any:
        return self._request('GET', f'/flowable/tasks/{task_id}')

    def get_historic_process_instance(self, instance_id: str) -> Any:
        return self._request('GET', f'/flowable/history/historic-process-instances/{instance_id}')

    def list_historic_process_instances(self, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', '/flowable/history/historic-process-instances', params=params)

    def list_historic_tasks(self, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request('GET', '/flowable/history/historic-task-instances', params=params)

    def update_task(self, task_id: str, payload: Dict[str, Any]) -> Any:
        return self._request('POST', f'/flowable/tasks/{task_id}', json=payload)

    def get_task_form(self, task_id: str) -> Any:
        return self._request('GET', f'/flowable/tasks/{task_id}/form')

    def terminate_process_instance(
        self,
        instance_id: str,
        *,
        reason: Optional[str] = None,
        cascade: bool = False,
    ) -> Any:
        params: Dict[str, Any] = {}
        if reason:
            params['deleteReason'] = reason
        if cascade:
            params['cascade'] = 'true'
        return self._request('DELETE', f'/flowable/process-instances/{instance_id}', params=params or None)

    def deploy_process_definition(self, zip_file: Any, deployment_name: str, filename: Optional[str] = None) -> Any:
        """Deploy BPMN + forms from ZIP to Flowable via Gateway.

        Args:
            zip_file: Binary file object (ZIP archive)
            deployment_name: Name for the deployment
            filename: Original filename (defaults to 'workflow.zip')

        Returns:
            Deployment response from Gateway/Flowable
        """
        files = {'file': (filename or 'workflow.zip', zip_file, 'application/zip')}
        data = {
            'deploymentName': deployment_name,
            'category': 'rdm',
            'enableDuplicateFiltering': 'true',
        }
        return self._request('POST', '/flowable/deployments', files=files, data=data)

    def get_public_keyset(self) -> Dict[str, Any]:
        payload = self._request('GET', '/keyset')
        if not isinstance(payload, dict):
            raise WorkflowGatewayClientError(
                http_status.HTTP_502_BAD_GATEWAY,
                'Workflow gateway returned an unexpected payload for keyset request.',
                detail=payload,
            )
        if 'keys' not in payload:
            raise WorkflowGatewayClientError(
                http_status.HTTP_502_BAD_GATEWAY,
                'Workflow gateway keyset missing required "keys" attribute.',
                detail=payload,
            )
        return payload


@lru_cache(maxsize=None)
def get_gateway_client(engine_id: str) -> 'WorkflowGatewayClient':
    return WorkflowGatewayClient(engine_id)


def list_gateways() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for engine in WorkflowEngine.objects.all():
        payload[engine.engine_id] = {
            'gateway_base_url': engine.gateway_base_url,
            'signing_kid': engine.signing_kid,
            'is_active': engine.is_active,
        }
    return payload

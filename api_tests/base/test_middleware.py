# -*- coding: utf-8 -*-
from django.http import HttpResponse, JsonResponse

from future.moves.urllib.parse import urlparse
import json
import mock
from nose.tools import *  # noqa:
from rest_framework import status as http_status
from rest_framework.test import APIRequestFactory
from django.test.utils import override_settings

from website.util import api_v2_url
from api.base import settings
from api.base.middleware import CorsMiddleware, ServiceAccessControlMiddleware
from tests.base import ApiTestCase
from osf_tests import factories


class MiddlewareTestCase(ApiTestCase):
    MIDDLEWARE = None

    def setUp(self):
        super(MiddlewareTestCase, self).setUp()
        self.middleware = self.MIDDLEWARE()
        self.mock_response = mock.Mock()
        self.request_factory = APIRequestFactory()


class TestCorsMiddleware(MiddlewareTestCase):
    MIDDLEWARE = CorsMiddleware

    @override_settings(CORS_ORIGIN_ALLOW_ALL=False)
    def test_institutions_added_to_cors_whitelist(self):
        url = api_v2_url('users/me/')
        domain = urlparse('https://dinosaurs.sexy')
        factories.InstitutionFactory(
            domains=[domain.netloc.lower()],
            name='Institute for Sexy Lizards'
        )
        settings.load_origins_whitelist()
        request = self.request_factory.get(url, HTTP_ORIGIN=domain.geturl())
        response = HttpResponse()
        self.middleware.process_request(request)
        self.middleware.process_response(request, response)
        assert_equal(response['Access-Control-Allow-Origin'], domain.geturl())

    @override_settings(CORS_ORIGIN_ALLOW_ALL=False)
    def test_preprintproviders_added_to_cors_whitelist(self):
        url = api_v2_url('users/me/')
        domain = urlparse('https://dinoprints.sexy')
        factories.PreprintProviderFactory(
            domain=domain.geturl().lower(),
            _id='DinoXiv'
        )
        settings.load_origins_whitelist()
        request = self.request_factory.get(url, HTTP_ORIGIN=domain.geturl())
        response = HttpResponse()
        self.middleware.process_request(request)
        self.middleware.process_response(request, response)
        assert_equal(response['Access-Control-Allow-Origin'], domain.geturl())

    @override_settings(CORS_ORIGIN_ALLOW_ALL=False)
    def test_cross_origin_request_with_cookies_does_not_get_cors_headers(self):
        url = api_v2_url('users/me/')
        domain = urlparse('https://dinosaurs.sexy')
        request = self.request_factory.get(url, HTTP_ORIGIN=domain.geturl())
        response = {}
        with mock.patch.object(request, 'COOKIES', True):
            self.middleware.process_request(request)
            self.middleware.process_response(request, response)
        assert_not_in('Access-Control-Allow-Origin', response)

    @override_settings(CORS_ORIGIN_ALLOW_ALL=False)
    def test_cross_origin_request_with_Authorization_gets_cors_headers(self):
        url = api_v2_url('users/me/')
        domain = urlparse('https://dinosaurs.sexy')
        request = self.request_factory.get(
            url,
            HTTP_ORIGIN=domain.geturl(),
            HTTP_AUTHORIZATION='Bearer aqweqweohuweglbiuwefq'
        )
        response = HttpResponse()
        self.middleware.process_request(request)
        self.middleware.process_response(request, response)
        assert_equal(response['Access-Control-Allow-Origin'], domain.geturl())

    @override_settings(CORS_ORIGIN_ALLOW_ALL=False)
    def test_cross_origin_request_with_Authorization_and_cookie_does_not_get_cors_headers(
            self):
        url = api_v2_url('users/me/')
        domain = urlparse('https://dinosaurs.sexy')
        request = self.request_factory.get(
            url,
            HTTP_ORIGIN=domain.geturl(),
            HTTP_AUTHORIZATION='Bearer aqweqweohuweglbiuwefq'
        )
        response = {}
        with mock.patch.object(request, 'COOKIES', True):
            self.middleware.process_request(request)
            self.middleware.process_response(request, response)
        assert_not_in('Access-Control-Allow-Origin', response)

    @override_settings(CORS_ORIGIN_ALLOW_ALL=False)
    def test_non_institution_preflight_request_requesting_authorization_header_gets_cors_headers(
            self):
        url = api_v2_url('users/me/')
        domain = urlparse('https://dinosaurs.sexy')
        request = self.request_factory.options(
            url,
            HTTP_ORIGIN=domain.geturl(),
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization'
        )
        response = HttpResponse()
        self.middleware.process_request(request)
        self.middleware.process_response(request, response)
        assert_equal(response['Access-Control-Allow-Origin'], domain.geturl())


class TestServiceAccessControlMiddleware(MiddlewareTestCase):
    MIDDLEWARE = ServiceAccessControlMiddleware

    def test_process_request(self):
        with mock.patch('api.base.middleware.check_api_service_access') as mock_check_access:
            mock_check_access.return_value = None
            url = api_v2_url('users/me/')
            domain = urlparse('https://dinosaurs.sexy')
            request = self.request_factory.options(
                url,
                HTTP_ORIGIN=domain.geturl(),
                HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
                HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization'
            )
            result = self.middleware.process_request(request)
            assert mock_check_access.called
            assert result is None

    def test_process_request_error(self):
        with mock.patch('api.base.middleware.check_api_service_access') as mock_check_access:
            mock_check_access.return_value = JsonResponse(
                {'errors': [{'message': 'User is not allowed to access this API.', 'status': http_status.HTTP_403_FORBIDDEN}]},
                status=http_status.HTTP_403_FORBIDDEN)
            url = api_v2_url('users/me/')
            domain = urlparse('https://dinosaurs.sexy')
            request = self.request_factory.options(
                url,
                HTTP_ORIGIN=domain.geturl(),
                HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET',
                HTTP_ACCESS_CONTROL_REQUEST_HEADERS='authorization'
            )
            result = self.middleware.process_request(request)
            assert mock_check_access.called
            assert result is not None
            assert result.status_code == http_status.HTTP_403_FORBIDDEN
            json_response = json.loads(result.content.decode('utf-8'))
            assert len(json_response.get('errors', [])) == 1

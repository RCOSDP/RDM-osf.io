import pytest

from api.base.settings.defaults import API_BASE
from osf_tests.factories import (
    AuthUserFactory,
    RegionFactory,
    ProjectFactory,
    NodeFactory
)
from unittest import mock
from addons.osfstorage.models import Region
from api.regions.views import RegionMixin
from django.test import RequestFactory
from api.base.requests import EmbeddedRequest
from django.http import HttpRequest
from osf.models import Node


@pytest.mark.django_db
class TestRegionDetail:

    @pytest.fixture()
    def region(self):
        return RegionFactory(name='Frankfort', _id='eu-central-1')

    @pytest.fixture()
    def bad_url(self):
        return '/{}regions/blah/'.format(API_BASE)

    @pytest.fixture()
    def region_url(self, region):
        return '/{}regions/{}/'.format(
            API_BASE, region._id)

    @pytest.fixture()
    def user(self):
        return AuthUserFactory()

    def test_region_detail(self, app, region_url, user):
        # test not auth
        reg = RegionFactory()
        with mock.patch('addons.osfstorage.models.Region.objects.get', return_value=reg):
            detail_res = app.get(region_url)
            assert detail_res.status_code == 200
            assert detail_res.json['data']['attributes']['name'] == reg.name
            assert detail_res.json['data']['id'] == reg._id

            # test auth
            detail_res = app.get(region_url, auth=user.auth)
            assert detail_res.status_code == 200

    def test_region_not_found(self, app, bad_url):
        with mock.patch('addons.osfstorage.models.Region.objects.get', side_effect=Region.DoesNotExist('mock error')):
            detail_res = app.get(bad_url, expect_errors=True)
            assert detail_res.status_code == 404

    def test_get_region_mixin(self):
        reg = RegionFactory()
        request = RequestFactory().get('/fake_path')
        user = AuthUserFactory()
        request.user = user
        request.version = '2.0'
        request._request = HttpRequest()
        node = ProjectFactory()
        new_component = NodeFactory(parent=node)
        component_node_settings = new_component.get_addon('osfstorage')
        component_node_settings.region = reg
        component_node_settings.save()
        kwargs = {
            'is_embedded': True,
            'region_id': reg.id
        }
        fake_request = EmbeddedRequest(request, parents={Node: {node.id: component_node_settings}})
        reg_factory = RegionMixinFactory(kwargs, fake_request)
        res = RegionMixin.get_region(reg_factory)
        assert res.id == reg.id
        assert res.name == reg.name

    def test_get_region_mixin_exception(self):
        reg = RegionFactory()
        request = RequestFactory().get('/fake_path')
        user = AuthUserFactory()
        request.user = user
        request.version = '2.0'
        request._request = HttpRequest()
        node = ProjectFactory()
        kwargs = {
            'is_embedded': True,
            'region_id': reg.id
        }
        fake_request = EmbeddedRequest(request, parents={Node: {node.id: node}})
        reg_factory = RegionMixinFactory(kwargs, fake_request)
        res = RegionMixin.get_region(reg_factory)
        assert res is not None


class RegionMixinFactory:
    def __init__(self, kwargs, request, region_lookup_url_kwarg='region_id'):
        self.kwargs = kwargs
        self.request = request
        self.region_lookup_url_kwarg = region_lookup_url_kwarg

    def check_object_permissions(self, request, reg):
        return None

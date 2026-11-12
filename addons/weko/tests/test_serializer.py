# -*- coding: utf-8 -*-
"""Serializer tests for the WEKO addon."""
import mock
from nose.tools import *  # noqa (PEP8 asserts)

from website.util import web_url_for
from addons.base.tests.serializers import StorageAddonSerializerTestSuiteMixin
from addons.weko.tests.factories import WEKOAccountFactory
from addons.weko.serializer import WEKOSerializer

from tests.base import OsfTestCase
from addons.weko.tests import utils


fake_host = 'https://weko3.test.nii.ac.jp/weko/sword/'


def mock_requests_get(url, **kwargs):
    if url == 'https://weko3.test.nii.ac.jp/weko/api/tree?action=browsing':
        return utils.MockResponse(utils.fake_weko_indices, 200)
    if url == 'https://weko3.test.nii.ac.jp/weko/api/index/?q=100':
        return utils.MockResponse(utils.fake_weko_items, 200)
    if url == 'https://weko3.test.nii.ac.jp/weko/api/records/1000':
        return utils.MockResponse(utils.fake_weko_item, 200)
    return utils.mock_response_404


class TestWEKOSerializer(StorageAddonSerializerTestSuiteMixin, OsfTestCase):
    addon_short_name = 'weko'
    Serializer = WEKOSerializer
    ExternalAccountFactory = WEKOAccountFactory
    client = None

    def set_provider_id(self, pid):
        self.node_settings.index_id = pid

    def setUp(self):
        self.mock_requests_get = mock.patch('requests.get')
        self.mock_requests_get.side_effect = mock_requests_get
        self.mock_requests_get.start()
        self.mock_find_repository = mock.patch('addons.weko.provider.find_repository')
        self.mock_find_repository.return_value = {
            'host': fake_host,
            'client_id': None,
            'client_secret': None,
            'authorize_url': None,
            'access_token_url': None,
        }
        self.mock_find_repository.start()
        super(TestWEKOSerializer, self).setUp()

    def tearDown(self):
        self.mock_requests_get.stop()
        self.mock_find_repository.stop()
        super(TestWEKOSerializer, self).tearDown()

    def test_serialize_acccount(self):
        ea = self.ExternalAccountFactory()
        expected = {
            'id': ea._id,
            'provider_id': ea.provider_id,
            'provider_name': ea.provider_name,
            'provider_short_name': ea.provider,
            'display_name': ea.display_name,
            'profile_url': ea.profile_url,
            'nodes': [],
            'host': ea.oauth_key,
        }
        assert_equal(self.ser.serialize_account(ea), expected)

    def test_serialize_settings_authorized(self):
        with mock.patch.object(type(self.node_settings), 'has_auth', return_value=True):
            serialized = self.ser.serialize_settings(self.node_settings, self.user, self.client)
        for key in self.required_settings:
            assert_in(key, serialized)
        assert_in('owner', serialized['urls'])
        assert_equal(serialized['urls']['owner'], web_url_for(
            'profile_view_id',
            uid=self.user_settings.owner._id
        ))
        assert_in('ownerName', serialized)
        assert_equal(serialized['ownerName'], self.user_settings.owner.fullname)
        assert_in('savedIndex', serialized)

    def test_serialize_settings_names_indices_in_the_page_language(self):
        def requests_get(url, **kwargs):
            if kwargs.get('headers', {}).get('Accept-Language') == 'ja':
                return utils.MockResponse([{'id': 100, 'name': 'サンプルインデックス'}], 200)
            return utils.MockResponse([{'id': 100, 'name': 'Sample Index'}], 200)

        with mock.patch.object(type(self.node_settings), 'has_auth', return_value=True), \
                mock.patch.object(WEKOSerializer, 'credentials_are_valid', return_value=True), \
                mock.patch('requests.get', side_effect=requests_get), \
                self.app.app.test_request_context(headers={'Accept-Language': 'ja-JP'}):
            serialized = self.ser.serialize_settings(self.node_settings, self.user, self.client)

        assert_equal(serialized['indices'], [{
            'title': 'Sample Index',
            'localizedTitle': 'サンプルインデックス',
            'id': 100,
            'children': [],
        }])

    def test_serialize_settings_falls_back_to_the_default_name_and_warns(self):
        def requests_get(url, **kwargs):
            if kwargs.get('headers', {}).get('Accept-Language') == 'ja':
                return utils.MockResponse([{'id': 100, 'name': 'サンプルインデックス'}], 200)
            return utils.MockResponse([{'id': 100, 'name': 'Sample Index'}, {'id': 101, 'name': 'New Index'}], 200)

        with mock.patch.object(type(self.node_settings), 'has_auth', return_value=True), \
                mock.patch.object(WEKOSerializer, 'credentials_are_valid', return_value=True), \
                mock.patch('requests.get', side_effect=requests_get), \
                self.app.app.test_request_context(headers={'Accept-Language': 'ja'}), \
                self.assertLogs('addons.weko.serializer', level='WARNING') as logs:
            serialized = self.ser.serialize_settings(self.node_settings, self.user, self.client)

        assert_equal([i['localizedTitle'] for i in serialized['indices']], ['サンプルインデックス', 'New Index'])
        assert_equal(len(logs.records), 1)
        assert_in('101', logs.records[0].getMessage())

    def test_serialize_settings_authorized_folder_is_set(self):
        pass

    def test_serialize_settings_authorized_no_folder(self):
        pass

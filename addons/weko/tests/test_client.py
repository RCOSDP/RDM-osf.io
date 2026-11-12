# -*- coding: utf-8 -*-
import mock
from mock import call
from nose.tools import *  # noqa

from tests.base import OsfTestCase

from addons.weko import client
from addons.weko.tests import utils


def mock_requests_get(url, **kwargs):
    if url == 'https://test.sample.nii.ac.jp/api/tree?action=browsing':
        return utils.MockResponse(utils.fake_weko_indices, 200)
    if url == 'https://test.sample.nii.ac.jp/api/index/?q=100':
        return utils.MockResponse(utils.fake_weko_items, 200)
    if url == 'https://test.sample.nii.ac.jp/api/records/1000':
        return utils.MockResponse(utils.fake_weko_item, 200)
    return utils.mock_response_404


def _fake_truncated_indices(expanded_ids):
    grandchildren = [{'id': '300', 'name': 'Grandchild 1', 'children': []}]
    if '201' in expanded_ids:
        grandchildren.append({'id': '301', 'name': 'Grandchild 2', 'children': []})
    else:
        grandchildren.append({'id': 'more'})
    children = [{'id': '200', 'name': 'Child 1', 'children': []}]
    if '100' in expanded_ids:
        children.append({'id': '201', 'name': 'Child 2', 'children': grandchildren})
    else:
        children.append({'id': 'more'})
    return [{'id': '100', 'name': 'Sample Index', 'children': children}]


def mock_requests_get_truncated(url, **kwargs):
    prefix = 'https://test.sample.nii.ac.jp/api/tree?action=browsing'
    if url == prefix:
        return utils.MockResponse(_fake_truncated_indices([]), 200)
    if url.startswith(prefix + '&more_ids='):
        expanded_ids = url[len(prefix + '&more_ids='):].split('/')
        return utils.MockResponse(_fake_truncated_indices(expanded_ids), 200)
    return utils.mock_response_404


def mock_requests_get_never_expanded(url, **kwargs):
    if url.startswith('https://test.sample.nii.ac.jp/api/tree?action=browsing'):
        return utils.MockResponse(_fake_truncated_indices([]), 200)
    return utils.mock_response_404


class TestWEKOClient(OsfTestCase):
    def setUp(self):
        self.host = utils.fake_weko_host
        self.conn = client.Client(self.host)
        super(TestWEKOClient, self).setUp()

    def tearDown(self):
        super(TestWEKOClient, self).tearDown()

    @mock.patch('requests.get', side_effect=mock_requests_get)
    def test_weko_get_indices(self, get_req_mock):
        indices = self.conn.get_indices()
        assert_equal(len(indices), 1)
        assert_equal(indices[0].title, 'Sample Index')
        assert_equal(indices[0].identifier, 100)

    @mock.patch('requests.get', side_effect=mock_requests_get_truncated)
    def test_weko_get_indices_expands_truncated_children(self, get_req_mock):
        indices = self.conn.get_indices()

        titles = [i.title for i in client._flatten_indices(indices)]
        assert_equal(titles, ['Sample Index', 'Child 1', 'Child 2', 'Grandchild 1', 'Grandchild 2'])
        assert_equal(
            [c[0][0] for c in get_req_mock.call_args_list],
            [
                'https://test.sample.nii.ac.jp/api/tree?action=browsing',
                'https://test.sample.nii.ac.jp/api/tree?action=browsing&more_ids=100',
                'https://test.sample.nii.ac.jp/api/tree?action=browsing&more_ids=100/201',
            ]
        )

    @mock.patch('requests.get', side_effect=mock_requests_get_never_expanded)
    def test_weko_get_indices_fails_when_weko_keeps_children_truncated(self, get_req_mock):
        with assert_raises(ValueError):
            self.conn.get_indices()

    @mock.patch('requests.get', side_effect=mock_requests_get)
    def test_weko_get_indices_asks_for_the_given_language(self, get_req_mock):
        self.conn.get_indices(accept_language='ja')

        get_req_mock.assert_called_once_with(
            'https://test.sample.nii.ac.jp/api/tree?action=browsing',
            auth=(None, None),
            headers={'Accept-Language': 'ja'},
            timeout=client.DEFAULT_TIMEOUT,
        )

    @mock.patch('requests.get', side_effect=mock_requests_get)
    def test_weko_get_index_by_id(self, get_req_mock):
        index = self.conn.get_index_by_id(100)
        assert_equal(index.title, 'Sample Index')
        assert_equal(index.identifier, 100)

        with assert_raises(ValueError):
            self.conn.get_index_by_id(101)

    @mock.patch('requests.get', side_effect=mock_requests_get)
    def test_weko_get_items(self, get_req_mock):
        index = self.conn.get_index_by_id(100)
        items = index.get_items()

        assert_equal(len(items), 1)
        assert_equal(items[0].title, 'Sample Item')
        assert_equal(items[0].identifier, 1000)

    @mock.patch('requests.get', side_effect=mock_requests_get)
    def test_weko_get_item_by_id(self, get_req_mock):
        index = self.conn.get_index_by_id(100)
        item = index.get_item_by_id(1000)

        assert_equal(item.title, 'Sample Item')
        assert_equal(item.identifier, 1000)

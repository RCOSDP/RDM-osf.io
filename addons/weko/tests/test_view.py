# -*- coding: utf-8 -*-
from celery import states
from framework.celery_tasks import app as celery_app
from rest_framework import status as http_status

import logging
import mock
from nose.tools import *  # noqa

from framework.auth import Auth
from tests.base import OsfTestCase, get_default_metaschema
from osf_tests.factories import AuthUserFactory, InstitutionFactory, ExternalAccountFactory
from framework.exceptions import HTTPError

from addons.base.tests.views import (
    OAuthAddonConfigViewsTestCaseMixin
)
from addons.weko import views
from addons.weko.tests.utils import WEKOAddonTestCase
from website.util import api_url_for
from addons.weko.tests import utils
from admin.rdm_addons.utils import get_rdm_addon_option


logger = logging.getLogger(__name__)
fake_host = 'https://weko3.test.nii.ac.jp/weko/sword/'


def mock_requests_get(url, **kwargs):
    if url == 'https://weko3.test.nii.ac.jp/weko/api/tree?action=browsing':
        return utils.MockResponse(utils.fake_weko_indices, 200)
    if url == 'https://weko3.test.nii.ac.jp/weko/api/index/?q=100':
        return utils.MockResponse(utils.fake_weko_items, 200)
    if url == 'https://weko3.test.nii.ac.jp/weko/api/records/1000':
        return utils.MockResponse(utils.fake_weko_item, 200)
    return utils.mock_response_404


class TestWEKOViews(WEKOAddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
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
        super(TestWEKOViews, self).setUp()

        self.institution = InstitutionFactory()
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

        rdm_addon_option = get_rdm_addon_option(self.institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = True
        rdm_addon_option.save()

        self.repository_external_account = ExternalAccountFactory()
        self.repository_external_account.display_name = 'https://test.nii.ac.jp#WEKO test account'
        self.repository_external_account.save()
        rdm_addon_option.external_accounts.add(self.repository_external_account)

        self.user_has_repo = AuthUserFactory()
        self.user_has_repo.affiliated_institutions.add(self.institution)

        self.no_repo_institution = InstitutionFactory()
        self.user_has_no_repo = AuthUserFactory()
        self.user_has_no_repo.affiliated_institutions.add(self.no_repo_institution)
        self.project.add_contributor(self.user_has_no_repo)

    def tearDown(self):
        self.mock_requests_get.stop()
        self.mock_find_repository.stop()
        super(TestWEKOViews, self).tearDown()

    def test_weko_user_config_get(self):
        url = self.project.api_url_for('weko_user_config_get')
        res = self.app.get(url, auth=self.user_has_repo.auth)
        logger.info(res.json)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        assert_in('userHasAuth', res.json['result'])
        assert_false(res.json['result']['userHasAuth'])
        assert_in('urls', res.json['result'])
        assert_in('repositories', res.json['result'])
        assert_equal(res.json['result']['repositories'], [
            {
                'id': self.repository_external_account.provider_id,
                'name': 'WEKO test account'
            }
        ])

        res = self.app.get(url, auth=self.user_has_no_repo.auth)
        logger.info(res.json)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        assert_in('userHasAuth', res.json['result'])
        assert_false(res.json['result']['userHasAuth'])
        assert_in('urls', res.json['result'])
        assert_in('repositories', res.json['result'])
        assert_equal(res.json['result']['repositories'], [])

    def test_weko_settings_rdm_addons_denied(self):
        rdm_addon_option = get_rdm_addon_option(self.institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = False
        rdm_addon_option.save()
        try:
            url = self.project.api_url_for('weko_oauth_connect', repoid='test')
            rv = self.app.get(
                url,
                auth=self.user.auth,
                expect_errors=True
            )
            assert_equal(rv.status_int, http_status.HTTP_403_FORBIDDEN)
        finally:
            rdm_addon_option.is_allowed = True
            rdm_addon_option.save()

    def test_weko_set_index_no_settings(self):
        user = AuthUserFactory()
        self.project.add_contributor(user, save=True)
        url = self.project.api_url_for('weko_set_config')
        res = self.app.put_json(
            url, {'index': 'hammertofall'}, auth=user.auth,
            expect_errors=True
        )
        assert_equal(res.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_weko_set_index_no_auth(self):
        user = AuthUserFactory()
        user.add_addon('weko')
        self.project.add_contributor(user, save=True)
        url = self.project.api_url_for('weko_set_config')
        res = self.app.put_json(
            url, {'index': 'hammertofall'}, auth=user.auth,
            expect_errors=True
        )
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_weko_remove_node_settings_owner(self):
        url = self.node_settings.owner.api_url_for('weko_deauthorize_node')
        ret = self.app.delete(url, auth=self.user.auth)
        result = self.Serializer().serialize_settings(node_settings=self.node_settings, current_user=self.user)
        assert_equal(result['nodeHasAuth'], False)

    def test_weko_remove_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('weko_deauthorize_node')
        ret = self.app.delete(url, auth=None, expect_errors=True)

        assert_equal(ret.status_code, 401)

    def test_weko_get_node_settings_owner(self):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.index_id = 'bucket'
        self.node_settings.save()
        url = self.node_settings.owner.api_url_for('weko_get_config')
        res = self.app.get(url, auth=self.user.auth)

        result = res.json['result']
        assert_equal(result['nodeHasAuth'], True)
        assert_equal(result['userIsOwner'], True)
        assert_equal(result['savedIndex']['id'], self.node_settings.index_id)

    def test_weko_get_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('weko_get_config')
        unauthorized = AuthUserFactory()
        ret = self.app.get(url, auth=unauthorized.auth, expect_errors=True)

        assert_equal(ret.status_code, 403)

    def test_get_config(self):
        url = self.project.api_url_for('{0}_get_config'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        serialized = self.Serializer().serialize_settings(
            self.node_settings,
            self.user,
            self.client
        )
        serialized_except_repos = dict(
            [(key, value) for key, value in serialized.items() if key != 'repositories']
        )
        result_except_repos = dict(
            [(key, value) for key, value in res.json['result'].items() if key != 'repositories']
        )
        assert_equal(serialized_except_repos, result_except_repos)
        assert_equal(len(res.json['result']['repositories']), 1)
        assert_equal(res.json['result']['repositories'][0]['name'], 'WEKO test account')

    def test_get_config_for_user_has_no_repo(self):
        url = self.project.api_url_for('{0}_get_config'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=self.user_has_no_repo.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        serialized = self.Serializer().serialize_settings(
            self.node_settings,
            self.user_has_no_repo,
            self.client
        )
        assert_equal(serialized, res.json['result'])

    def test_set_config(self):
        pass

    def test_folder_list(self):
        pass


class TestResolveDepositTask(OsfTestCase):

    def _mock_async_result(self, state, infos):
        # 参照ごとに次の値を返す (尽きたら最後の値を返す)。例外も値として返したいため
        # side_effectにはリストではなく関数を渡す
        values = list(infos)
        def next_info():
            return values.pop(0) if len(values) > 1 else values[0]
        aresult = mock.Mock()
        type(aresult).state = mock.PropertyMock(return_value=state)
        type(aresult).info = mock.PropertyMock(side_effect=next_info)
        return aresult

    def _resolve(self, state, infos):
        aresult = self._mock_async_result(state, infos)
        with mock.patch.object(celery_app, 'AsyncResult', return_value=aresult):
            return views._resolve_deposit_task('fake-task-id')

    def test_progress_while_uploading(self):
        progress, error, result, response = self._resolve(
            'uploading', [{'progress': 60, 'paths': ['/f.txt']}],
        )
        assert_equal(progress, {'state': 'uploading', 'rate': 60})
        assert_equal(error, None)
        assert_equal(result, None)

    def test_result_when_deposited(self):
        progress, error, result, response = self._resolve(
            states.SUCCESS,
            [{'result': 'https://weko.test/records/1', 'response': {'links': []}}],
        )
        assert_equal(result, 'https://weko.test/records/1')
        assert_equal(response, {'links': []})
        assert_equal(progress, None)

    def test_error_when_failed(self):
        progress, error, result, response = self._resolve(
            states.FAILURE, [IOError('deposit failed')],
        )
        assert_equal(error, 'deposit failed')
        assert_equal(progress, None)

    def test_task_completing_while_reading_state(self):
        # 進行中はinfoの参照ごとにバックエンドへ問い合わせるため、'progress'の有無を
        # 判定した後、値を取り出す前に完了へ遷移すると 'progress' が消える
        progress, error, result, response = self._resolve(
            'uploaded',
            [
                {'progress': 100, 'paths': ['/f.txt']},
                {'progress': 100, 'paths': ['/f.txt']},
                {'result': 'https://weko.test/records/1', 'paths': ['/f.txt']},
            ],
        )
        assert_equal(progress, {'state': 'uploaded', 'rate': 100})
        assert_equal(error, None)

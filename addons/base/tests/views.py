# -*- coding: utf-8 -*-

import time
from unittest import mock

import itsdangerous
import mock
import pytest
import responses
from future.moves.urllib.parse import urlparse, parse_qs
from nose.tools import (assert_equal, assert_false, assert_in, assert_is_none,
                        assert_not_equal, assert_raises, assert_true)
from rest_framework import status as http_status

from addons.base.tests.base import OAuthAddonTestCaseMixin
from addons.osfstorage.models import OsfStorageFileNode
from addons.osfstorage.tests.utils import StorageTestCase
from admin.rdm_addons.utils import get_rdm_addon_option
from api_tests.utils import create_test_file
from framework.auth import Auth
from framework.exceptions import HTTPError
from osf.utils import permissions
from osf_tests.factories import AuthUserFactory, ProjectFactory, InstitutionFactory
from website.util import api_url_for, web_url_for
from future.moves.urllib.parse import urlparse, parse_qs
from nose.tools import *  # noqa
from nose.tools import (assert_equal, assert_false, assert_in, assert_is_none,
                        assert_not_equal, assert_raises, assert_true)
from rest_framework import status as http_status

from addons.base.tests.base import OAuthAddonTestCaseMixin
from addons.github.tests.factories import GitHubAccountFactory, GoogleDriveAccountFactory
from addons.osfstorage.models import OsfStorageFileNode
from admin.rdm_addons.utils import get_rdm_addon_option
from api_tests.utils import create_test_file
from framework.auth import signing
from framework.auth.core import Auth
from framework.exceptions import HTTPError
from osf.models import Session
from osf.utils import permissions
from osf_tests.factories import (AuthUserFactory, ProjectFactory,
                                 )
from osf_tests.factories import InstitutionFactory, RegionFactory
from tests.base import OsfTestCase
from tests.test_timestamp import create_test_file
from website import settings
from website.util import api_url_for
from website.util import web_url_for
from addons.osfstorage.tests.factories import OsfStorageAccountFactory


class OAuthAddonAuthViewsTestCaseMixin(OAuthAddonTestCaseMixin):

    @property
    def Provider(self):
        raise NotImplementedError()

    def test_oauth_start(self):
        url = api_url_for(
            'oauth_connect',
            service_name=self.ADDON_SHORT_NAME
        )
        res = self.app.get(url, auth=self.user.auth)
        assert res.status_code == http_status.HTTP_302_FOUND
        redirect_url = urlparse(res.location)
        redirect_params = parse_qs(redirect_url.query)
        provider_url = urlparse(self.Provider().auth_url)
        provider_params = parse_qs(provider_url.query)
        for param, value in redirect_params.items():
            if param == 'state':  # state may change between calls
                continue
            assert value == provider_params[param]

    def test_oauth_start_rdm_addons_denied(self):
        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        rdm_addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = False
        rdm_addon_option.save()
        url = api_url_for(
            'oauth_connect',
            service_name=self.ADDON_SHORT_NAME
        )
        res = self.app.get(url, auth=self.user.auth, expect_errors=True)
        assert res.status_code == http_status.HTTP_403_FORBIDDEN
        assert_in(b'You are prohibited from using this add-on.', res.body)

    @mock.patch('website.oauth.views.session')
    def test_oauth_finish(self, mock_session):
        url = web_url_for(
            'oauth_callback',
            service_name=self.ADDON_SHORT_NAME
        )
        if self.Provider._oauth_version == 1:
            url += '?oauth_token=abc123&oauth_token_secret=def456'
        elif self.Provider._oauth_version == 2:
            url += '?state=abc123'
        with mock.patch.object(self.Provider, 'auth_callback') as mock_callback:
            mock_callback.return_value = True
            if self.Provider._oauth_version == 1:
                mock_session.data = {'oauth_states': {self.ADDON_SHORT_NAME: {'token': 'abc123', 'secret': 'def456'}}}
            elif self.Provider._oauth_version == 2:
                mock_session.data = {'oauth_states': {self.ADDON_SHORT_NAME: {'state': 'abc123'}}}
            res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        name, args, kwargs = mock_callback.mock_calls[0]
        assert_equal(kwargs['user']._id, self.user._id)

    @mock.patch('website.oauth.views.session')
    def test_oauth_finish_rdm_addons_denied(self, mock_session):
        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        rdm_addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = False
        rdm_addon_option.save()
        url = web_url_for(
            'oauth_callback',
            service_name=self.ADDON_SHORT_NAME
        ) + '?state=abc123'
        mock_session.data = {'oauth_states': {self.ADDON_SHORT_NAME: {'state': 'abc123'}}}
        res = self.app.get(url, auth=self.user.auth, expect_errors=True)
        assert res.status_code == http_status.HTTP_403_FORBIDDEN
        assert_in(b'You are prohibited from using this add-on.', res.body)

    def test_delete_external_account(self):
        url = api_url_for(
            'oauth_disconnect',
            external_account_id=self.external_account._id
        )
        res = self.app.delete(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        self.user.reload()
        for account in self.user.external_accounts.all():
            assert_not_equal(account._id, self.external_account._id)
        assert_false(self.user.external_accounts.exists())

    def test_delete_external_account_not_owner(self):
        other_user = AuthUserFactory()
        url = api_url_for(
            'oauth_disconnect',
            external_account_id=self.external_account._id
        )
        res = self.app.delete(url, auth=other_user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)

class OAuthAddonConfigViewsTestCaseMixin(OAuthAddonTestCaseMixin):

    @property
    def folder(self):
        raise NotImplementedError("This test suite must expose a 'folder' property.")

    @property
    def Serializer(self):
        raise NotImplementedError()

    @property
    def client(self):
        raise NotImplementedError()

    def test_import_auth(self):
        ea = self.ExternalAccountFactory()
        self.user.external_accounts.add(ea)
        self.user.save()

        node = ProjectFactory(creator=self.user)
        node_settings = node.get_or_add_addon(self.ADDON_SHORT_NAME, auth=Auth(self.user))
        node.save()
        url = node.api_url_for('{0}_import_auth'.format(self.ADDON_SHORT_NAME))
        res = self.app.put_json(url, {
            'external_account_id': ea._id
        }, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        node_settings.reload()
        assert_equal(node_settings.external_account._id, ea._id)

        node.reload()
        last_log = node.logs.latest()
        assert_equal(last_log.action, '{0}_node_authorized'.format(self.ADDON_SHORT_NAME))

    def test_import_auth_invalid_account(self):
        ea = self.ExternalAccountFactory()

        node = ProjectFactory(creator=self.user)
        node.add_addon(self.ADDON_SHORT_NAME, auth=self.auth)
        node.save()
        url = node.api_url_for('{0}_import_auth'.format(self.ADDON_SHORT_NAME))
        res = self.app.put_json(url, {
            'external_account_id': ea._id
        }, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_import_auth_cant_write_node(self):
        ea = self.ExternalAccountFactory()
        user = AuthUserFactory()
        user.add_addon(self.ADDON_SHORT_NAME, auth=Auth(user))
        user.external_accounts.add(ea)
        user.save()

        node = ProjectFactory(creator=self.user)
        node.add_contributor(user, permissions=permissions.READ, auth=self.auth, save=True)
        node.add_addon(self.ADDON_SHORT_NAME, auth=self.auth)
        node.save()
        url = node.api_url_for('{0}_import_auth'.format(self.ADDON_SHORT_NAME))
        res = self.app.put_json(url, {
            'external_account_id': ea._id
        }, auth=user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_set_config(self):
        self.node_settings.set_auth(self.external_account, self.user)
        url = self.project.api_url_for('{0}_set_config'.format(self.ADDON_SHORT_NAME))
        res = self.app.put_json(url, {
            'selected': self.folder
        }, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        self.project.reload()
        assert_equal(
            self.project.logs.latest().action,
            '{0}_folder_selected'.format(self.ADDON_SHORT_NAME)
        )
        assert_equal(res.json['result']['folder']['path'], self.folder['path'])

    def test_get_config(self):
        url = self.project.api_url_for('{0}_get_config'.format(self.ADDON_SHORT_NAME))
        with mock.patch.object(type(self.Serializer()), 'credentials_are_valid', return_value=True):
            res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('result', res.json)
        serialized = self.Serializer().serialize_settings(
            self.node_settings,
            self.user,
            self.client
        )
        assert_equal(serialized, res.json['result'])

    def test_get_config_unauthorized(self):
        url = self.project.api_url_for('{0}_get_config'.format(self.ADDON_SHORT_NAME))
        user = AuthUserFactory()
        self.project.add_contributor(user, permissions=permissions.READ, auth=self.auth, save=True)
        res = self.app.get(url, auth=user.auth, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_get_config_not_logged_in(self):
        url = self.project.api_url_for('{0}_get_config'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=None, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_302_FOUND)

    def test_account_list_single(self):
        url = api_url_for('{0}_account_list'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('accounts', res.json)
        assert_equal(len(res.json['accounts']), 1)

    def test_account_list_multiple(self):
        ea = self.ExternalAccountFactory()
        self.user.external_accounts.add(ea)
        self.user.save()

        url = api_url_for('{0}_account_list'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        assert_in('accounts', res.json)
        assert_equal(len(res.json['accounts']), 2)

    def test_account_list_not_authorized(self):
        url = api_url_for('{0}_account_list'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=None, expect_errors=True)
        assert_equal(res.status_code, http_status.HTTP_302_FOUND)

    def test_folder_list(self):
        # Note: if your addon's folder_list view makes API calls
        # then you will need to implement test_folder_list in your
        # subclass, mock any API calls, and call super.
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.save()
        url = self.project.api_url_for('{0}_folder_list'.format(self.ADDON_SHORT_NAME))
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        # TODO test result serialization?

    def test_deauthorize_node(self):
        url = self.project.api_url_for('{0}_deauthorize_node'.format(self.ADDON_SHORT_NAME))
        res = self.app.delete(url, auth=self.user.auth)
        assert_equal(res.status_code, http_status.HTTP_200_OK)
        self.node_settings.reload()
        assert_is_none(self.node_settings.external_account)
        assert_false(self.node_settings.has_auth)

        # A log event was saved
        self.project.reload()
        last_log = self.project.logs.latest()
        assert_equal(last_log.action, '{0}_node_deauthorized'.format(self.ADDON_SHORT_NAME))

class OAuthCitationAddonConfigViewsTestCaseMixin(OAuthAddonConfigViewsTestCaseMixin):

    @property
    def citationsProvider(self):
        raise NotImplementedError()

    @property
    def foldersApiUrl(self):
        raise NotImplementedError()

    @property
    def documentsApiUrl(self):
        raise NotImplementedError()

    @property
    def mockResponses(self):
        raise NotImplementedError()

    def setUp(self):
        super(OAuthCitationAddonConfigViewsTestCaseMixin, self).setUp()
        self.mock_verify = mock.patch.object(
            self.client,
            '_verify_client_validity'
        )
        self.mock_verify.start()

    def tearDown(self):
        self.mock_verify.stop()
        super(OAuthCitationAddonConfigViewsTestCaseMixin, self).tearDown()

    def test_set_config(self):
        with mock.patch.object(self.client, '_folder_metadata') as mock_metadata:
            mock_metadata.return_value = self.folder
            url = self.project.api_url_for('{0}_set_config'.format(self.ADDON_SHORT_NAME))
            res = self.app.put_json(url, {
                'external_list_id': self.folder.json['id'],
                'external_list_name': self.folder.name,
            }, auth=self.user.auth)
            assert_equal(res.status_code, http_status.HTTP_200_OK)
            self.project.reload()
            assert_equal(
                self.project.logs.latest().action,
                '{0}_folder_selected'.format(self.ADDON_SHORT_NAME)
            )
            assert_equal(res.json['result']['folder']['name'], self.folder.name)

    def test_get_config(self):
        with mock.patch.object(self.client, '_folder_metadata') as mock_metadata:
            mock_metadata.return_value = self.folder
            self.node_settings.api._client = 'client'
            self.node_settings.save()
            url = self.project.api_url_for('{0}_get_config'.format(self.ADDON_SHORT_NAME))
            res = self.app.get(url, auth=self.user.auth)
            assert_equal(res.status_code, http_status.HTTP_200_OK)
            assert_in('result', res.json)
            result = res.json['result']
            serialized = self.Serializer(
                node_settings=self.node_settings,
                user_settings=self.node_settings.user_settings
            ).serialized_node_settings
            serialized['validCredentials'] = self.citationsProvider().check_credentials(self.node_settings)
            assert_equal(serialized, result)

    def test_folder_list(self):
        with mock.patch.object(self.client, '_get_folders'):
            self.node_settings.set_auth(self.external_account, self.user)
            self.node_settings.save()
            url = self.project.api_url_for('{0}_citation_list'.format(self.ADDON_SHORT_NAME))
            res = self.app.get(url, auth=self.user.auth)
            assert_equal(res.status_code, http_status.HTTP_200_OK)

    def test_check_credentials(self):
        with mock.patch.object(self.client, 'client', new_callable=mock.PropertyMock) as mock_client:
            self.provider = self.citationsProvider()
            mock_client.side_effect = HTTPError(403)
            assert_false(self.provider.check_credentials(self.node_settings))

            mock_client.side_effect = HTTPError(402)
            with assert_raises(HTTPError):
                self.provider.check_credentials(self.node_settings)

    def test_widget_view_complete(self):
        # JSON: everything a widget needs
        self.citationsProvider().set_config(
            self.node_settings,
            self.user,
            self.folder.json['id'],
            self.folder.name,
            Auth(self.user)
        )
        assert_true(self.node_settings.complete)
        assert_equal(self.node_settings.list_id, 'Fake Key')

        res = self.citationsProvider().widget(self.project.get_addon(self.ADDON_SHORT_NAME))

        assert_true(res['complete'])
        assert_equal(res['list_id'], 'Fake Key')

    def test_widget_view_incomplete(self):
        # JSON: tell the widget when it hasn't been configured
        self.node_settings.clear_settings()
        self.node_settings.save()
        assert_false(self.node_settings.complete)
        assert_equal(self.node_settings.list_id, None)

        res = self.citationsProvider().widget(self.project.get_addon(self.ADDON_SHORT_NAME))

        assert_false(res['complete'])
        assert_is_none(res['list_id'])

    @responses.activate
    def test_citation_list_root(self):

        responses.add(
            responses.Response(
                responses.GET,
                self.foldersApiUrl,
                body=self.mockResponses['folders'],
                content_type='application/json'
            )
        )

        res = self.app.get(
            self.project.api_url_for('{0}_citation_list'.format(self.ADDON_SHORT_NAME)),
            auth=self.user.auth
        )
        root = res.json['contents'][0]
        assert_equal(root['kind'], 'folder')
        assert_equal(root['id'], 'ROOT')
        assert_equal(root['parent_list_id'], '__')

    @responses.activate
    def test_citation_list_non_root(self):

        responses.add(
            responses.Response(
                responses.GET,
                self.foldersApiUrl,
                body=self.mockResponses['folders'],
                content_type='application/json'
            )
        )

        responses.add(
            responses.Response(
                responses.GET,
                self.documentsApiUrl,
                body=self.mockResponses['documents'],
                content_type='application/json'
            )
        )

        res = self.app.get(
            self.project.api_url_for('{0}_citation_list'.format(self.ADDON_SHORT_NAME), list_id='ROOT'),
            auth=self.user.auth
        )

        children = res.json['contents']
        assert_equal(len(children), 7)
        assert_equal(children[0]['kind'], 'folder')
        assert_equal(children[1]['kind'], 'file')
        assert_true(children[1].get('csl') is not None)

    @responses.activate
    def test_citation_list_non_linked_or_child_non_authorizer(self):
        non_authorizing_user = AuthUserFactory()
        self.project.add_contributor(non_authorizing_user, save=True)

        self.node_settings.list_id = 'e843da05-8818-47c2-8c37-41eebfc4fe3f'
        self.node_settings.save()

        responses.add(
            responses.Response(
                responses.GET,
                self.foldersApiUrl,
                body=self.mockResponses['folders'],
                content_type='application/json'
            )
        )

        responses.add(
            responses.Response(
                responses.GET,
                self.documentsApiUrl,
                body=self.mockResponses['documents'],
                content_type='application/json'
            )
        )

        res = self.app.get(
            self.project.api_url_for('{0}_citation_list'.format(self.ADDON_SHORT_NAME), list_id='ROOT'),
            auth=non_authorizing_user.auth,
            expect_errors=True
        )
        assert_equal(res.status_code, http_status.HTTP_403_FORBIDDEN)


class TestAddonLogsDifferentProvider(OsfTestCase):

    def setUp(self):
        super(TestAddonLogsDifferentProvider, self).setUp()
        self.user = AuthUserFactory()
        self.user_non_contrib = AuthUserFactory()
        self.auth_obj = Auth(user=self.user)
        self.node = ProjectFactory(creator=self.user)
        self.file = OsfStorageFileNode.create(
            target=self.node,
            path='/testfile',
            _id='testfile',
            name='testfile',
            materialized_path='/testfile'
        )
        self.file.save()
        self.session = Session(data={'auth_user_id': self.user._id})
        self.session.save()
        self.cookie = itsdangerous.Signer(settings.SECRET_KEY).sign(self.session._id)
        self.configure_addon()

    def configure_addon(self):
        self.user.add_addon('github')
        self.user_addon = self.user.get_addon('github')
        self.oauth_settings = GitHubAccountFactory(display_name='john')
        self.oauth_settings.save()
        self.user.external_accounts.add(self.oauth_settings)
        self.user.save()
        self.node.add_addon('github', self.auth_obj)
        self.node_addon = self.node.get_addon('github')
        self.node_addon.user = 'john'
        self.node_addon.repo = 'youre-my-best-friend'
        self.node_addon.user_settings = self.user_addon
        self.node_addon.external_account = self.oauth_settings
        self.node_addon.save()
        self.user_addon.oauth_grants[self.node._id] = {self.oauth_settings._id: []}
        self.user_addon.save()

        self.user.add_addon('osfstorage')
        self.user_addon2 = self.user.get_addon('osfstorage')
        self.oauth_settings2 = OsfStorageAccountFactory(display_name='john')
        self.oauth_settings2.save()
        self.user.external_accounts.add(self.oauth_settings2)
        self.user.save()
        self.node.add_addon('osfstorage', self.auth_obj)
        self.node_addon2 = self.node.get_addon('osfstorage')
        self.node_addon2.user = 'john'
        self.node_addon2.repo = 'youre-my-best-friend'
        self.node_addon2.user_settings = self.user_addon2
        self.node_addon2.external_account = self.oauth_settings2
        self.node_addon2.save()
        self.user_addon2.save()

    def build_payload(self, metadata, **kwargs):
        options = dict(
            auth={'id': self.user._id},
            action='create',
            provider=self.node_addon.config.short_name,
            metadata=metadata,
            time=time.time() + 1000,
        )
        options.update(kwargs)
        options = {
            key: value
            for key, value in options.items()
            if value is not None
        }
        message, signature = signing.default_signer.sign_payload(options)
        return {
            'payload': message,
            'signature': signature,
        }

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_file_move_different_provider_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')
        src_provider = 'github'
        dest_provider = 'osfstorage'
        # Create file
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': src_provider,
            'name': filename,
            'materialized': '/' + filename,
            'path': '/' + filename,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }), headers={'Content-Type': 'application/json'}, expect_errors=True)

        # Move the file
        movedfilepath = 'cool_folder/' + filename
        res = self.app.put_json(wb_log_url, self.build_payload(
            action='move',
            metadata={
                'path': '/' + movedfilepath,
            },
            source={
                'provider': src_provider,
                'name': filename,
                'materialized': '/' + filename,
                'path': '/' + filename,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'nid': self.node._id,
            },
            destination={
                'provider': dest_provider,
                'name': filename,
                'materialized': '/' + movedfilepath,
                'path': '/' + movedfilepath,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'nid': self.node._id,
            },
        ), headers={'Content-Type': 'application/json'}, expect_errors=True)
        assert res.status_code == 404


@pytest.mark.django_db
class TestAddonsBaseView(StorageTestCase):
    def setUp(self):
        super(TestAddonsBaseView, self).setUp()

    def test_addon_view_or_download_file_legacy_not_found(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123', 'action': 'view'}
        self.user_addon = self.user.get_or_add_addon('twofactor')
        self.user_addon.is_confirmed = True
        self.user_addon.save()
        file = create_test_file(target=self.node, user=self.user)
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon', side_effect=[self.user_addon, self.node.get_addon('osfstorage')]):
                    with mock.patch('addons.osfstorage.models.NodeSettings.get_root', side_effect=OsfStorageFileNode.DoesNotExist('mock error')):
                        url = self.node.web_url_for(
                            'addon_view_or_download_file_legacy',
                            path=file._id,
                            provider=file.provider
                        )
                        resp = self.app.get(
                            url,
                            auth=self.user.auth,
                            headers={'X-OSF-OTP': 'fake_otp'},
                            expect_errors=True
                        )
                        assert resp.status_code == 404

    def test_disable_addon_exception(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123'}
        with mock.patch('addons.base.views.request', mock_request):
            verify_url = self.node.api_url_for('disable_addon', addon='osfstorage')
            resp = self.app.post(
                verify_url,
                {
                    'addon': 'fake_addon',
                    'node': self.node,
                },
                auth=self.user.auth,
                expect_errors=True)
            assert resp.status_code == 400

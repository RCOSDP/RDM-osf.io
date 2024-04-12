# -*- coding: utf-8 -*-

import os
import datetime
import time
import functools

import furl
import itsdangerous
import jwe
import jwt
import mock
import pytest
from django.utils import timezone
from framework.auth import cas, signing
from framework.auth.core import Auth
from framework.exceptions import HTTPError
from nose.tools import *  # noqa
from tests.base import OsfTestCase, get_default_metaschema
from api_tests.utils import create_test_file
from osf_tests.factories import (
    AuthUserFactory, ProjectFactory,
    RegistrationFactory, DraftRegistrationFactory,
    RegionFactory,
    InstitutionFactory,
    PreprintFactory,
)
from website import settings
from api.base import settings as api_settings
from addons.base import views
from addons.github.exceptions import ApiError
from addons.github.models import GithubFolder, GithubFile, GithubFileNode
from addons.github.tests.factories import GitHubAccountFactory, GoogleDriveAccountFactory
from addons.osfstorage.models import OsfStorageFileNode, OsfStorageFolder, NodeSettings
from addons.osfstorage.tests.factories import FileVersionFactory
from osf.models import NodeLog, Session, QuickFilesNode, RdmFileTimestamptokenVerifyResult, RdmUserKey
from osf.models import files as file_models
from osf.models.files import BaseFileNode, TrashedFileNode
from osf.models.mixins import AddonModelMixin
from osf.utils.permissions import WRITE, READ
from website.project import new_private_link
from website.project.views.node import _view_project as serialize_node
from website.project.views.node import serialize_addons, collect_node_config_js
from website.util import api_url_for, rubeus
from website.util.timestamp import userkey_generation
from dateutil.parser import parse as parse_date
from framework import sentry
from tests.test_timestamp import create_test_file


class SetEnvironMiddleware(object):

    def __init__(self, app, **kwargs):
        self.app = app
        self.kwargs = kwargs

    def __call__(self, environ, start_response):
        environ.update(self.kwargs)
        return self.app(environ, start_response)


class TestAddonAuth(OsfTestCase):

    def setUp(self):
        super(TestAddonAuth, self).setUp()
        self.user = AuthUserFactory()
        self.auth_obj = Auth(user=self.user)
        self.node = ProjectFactory(creator=self.user)
        self.session = Session(data={'auth_user_id': self.user._id})
        self.session.save()
        self.cookie = itsdangerous.Signer(settings.SECRET_KEY).sign(self.session._id).decode()
        self.configure_addon()
        self.JWE_KEY = jwe.kdf(settings.WATERBUTLER_JWE_SECRET.encode('utf-8'), settings.WATERBUTLER_JWE_SALT.encode('utf-8'))

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

    def build_url(self, **kwargs):
        options = {'payload': jwe.encrypt(jwt.encode({'data': dict(dict(
            path='test_path/',
            action='download',
            nid=self.node._id,
            metrics={'uri': settings.MFR_SERVER_URL},
            provider=self.node_addon.config.short_name), **kwargs),
            'exp': timezone.now() + datetime.timedelta(seconds=settings.WATERBUTLER_JWT_EXPIRATION),
        }, settings.WATERBUTLER_JWT_SECRET, algorithm=settings.WATERBUTLER_JWT_ALGORITHM), self.JWE_KEY)}
        return api_url_for('get_auth', **options)

    def test_auth_download(self):
        url = self.build_url()
        res = self.app.get(url, auth=self.user.auth)
        data = jwt.decode(jwe.decrypt(res.json['payload'].encode('utf-8'), self.JWE_KEY), settings.WATERBUTLER_JWT_SECRET, algorithm=settings.WATERBUTLER_JWT_ALGORITHM)['data']
        assert_equal(data['auth'], views.make_auth(self.user))
        assert_equal(data['credentials'], self.node_addon.serialize_waterbutler_credentials())
        assert_equal(data['settings'], self.node_addon.serialize_waterbutler_settings())
        expected_url = furl.furl(self.node.api_url_for('create_waterbutler_log', _absolute=True, _internal=True))
        observed_url = furl.furl(data['callback_url'])
        observed_url.port = expected_url.port
        assert_equal(expected_url, observed_url)

    def test_auth_render_action_returns_200(self):
        url = self.build_url(action='render')
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, 200)

    def test_auth_render_action_requires_read_permission(self):
        node = ProjectFactory(is_public=False)
        url = self.build_url(action='render', nid=node._id)
        res = self.app.get(url, auth=self.user.auth, expect_errors=True)
        # Fix assert result
        assert_equal(res.status_code, 400)

    def test_auth_export_action_returns_200(self):
        url = self.build_url(action='export')
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, 200)

    def test_auth_export_action_requires_read_permission(self):
        node = ProjectFactory(is_public=False)
        url = self.build_url(action='export', nid=node._id)
        res = self.app.get(url, auth=self.user.auth, expect_errors=True)
        # Fix assert result
        assert_equal(res.status_code, 400)

    def test_auth_missing_args(self):
        url = self.build_url(cookie=None)
        res = self.app.get(url, expect_errors=True)
        # Fix assert result
        assert_equal(res.status_code, 200)

    def test_auth_bad_cookie(self):
        url = self.build_url(cookie=self.cookie)
        res = self.app.get(url, expect_errors=True)
        assert_equal(res.status_code, 200)
        data = jwt.decode(jwe.decrypt(res.json['payload'].encode('utf-8'), self.JWE_KEY), settings.WATERBUTLER_JWT_SECRET, algorithm=settings.WATERBUTLER_JWT_ALGORITHM)['data']
        assert_equal(data['auth'], views.make_auth(self.user))
        assert_equal(data['credentials'], self.node_addon.serialize_waterbutler_credentials())
        assert_equal(data['settings'], self.node_addon.serialize_waterbutler_settings())
        expected_url = furl.furl(self.node.api_url_for('create_waterbutler_log', _absolute=True, _internal=True))
        observed_url = furl.furl(data['callback_url'])
        observed_url.port = expected_url.port
        assert_equal(expected_url, observed_url)

    def test_auth_cookie(self):
        url = self.build_url(cookie=self.cookie[::-1])
        res = self.app.get(url, expect_errors=True)
        # Fix assert result
        assert_equal(res.status_code, 200)

    def test_auth_missing_addon(self):
        url = self.build_url(provider='queenhub')
        res = self.app.get(url, expect_errors=True, auth=self.user.auth)
        assert_equal(res.status_code, 400)

    @mock.patch('addons.base.views.cas.get_client')
    def test_auth_bad_bearer_token(self, mock_cas_client):
        mock_cas_client.return_value = mock.Mock(profile=mock.Mock(return_value=cas.CasResponse(authenticated=False)))
        url = self.build_url()
        res = self.app.get(url, headers={'Authorization': 'Bearer invalid_access_token'}, expect_errors=True)
        # Fix assert result
        assert_equal(res.status_code, 200)

    def test_action_downloads_marks_version_as_seen(self):
        noncontrib = AuthUserFactory()
        node = ProjectFactory(is_public=True, creator=self.user)
        test_file = create_test_file(node, self.user)
        url = self.build_url(nid=node._id, action='render', provider='osfstorage', path=test_file.path)
        res = self.app.get(url, auth=noncontrib.auth)
        assert_equal(res.status_code, 200)

        # Add a new version, make sure that does not have a record
        version = FileVersionFactory()
        test_file.add_version(version)
        test_file.save()

        versions = test_file.versions.order_by('created')
        assert versions.first().seen_by.filter(guids___id=noncontrib._id).exists()
        assert not versions.last().seen_by.filter(guids___id=noncontrib._id).exists()

    def test_action_download_contrib(self):
        test_file = create_test_file(self.node, self.user)
        url = self.build_url(action='download', provider='osfstorage', path=test_file.path, version=1)
        nlogs = self.node.logs.count()
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, 200)

        test_file.reload()
        assert_equal(test_file.get_download_count(), 0) # contribs don't count as downloads
        assert_equal(self.node.logs.count(), nlogs) # don't log downloads

    def test_action_download_non_contrib(self):
        noncontrib = AuthUserFactory()
        node = ProjectFactory(is_public=True)
        test_file = create_test_file(node, self.user)
        url = self.build_url(nid=node._id, action='download', provider='osfstorage', path=test_file.path, version=1)
        nlogs = node.logs.count()
        res = self.app.get(url, auth=noncontrib.auth)
        assert_equal(res.status_code, 200)

        test_file.reload()
        assert_equal(test_file.get_download_count(), 1)
        assert_equal(node.logs.count(), nlogs) # don't log views

    def test_action_download_mfr_views_contrib(self):
        test_file = create_test_file(self.node, self.user)
        url = self.build_url(action='render', provider='osfstorage', path=test_file.path, version=1)
        nlogs = self.node.logs.count()
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, 200)

        test_file.reload()
        assert_equal(test_file.get_view_count(), 0) # contribs don't count as views
        assert_equal(self.node.logs.count(), nlogs) # don't log views

    def test_action_download_mfr_views_non_contrib(self):
        noncontrib = AuthUserFactory()
        node = ProjectFactory(is_public=True)
        test_file = create_test_file(node, self.user)
        url = self.build_url(nid=node._id, action='render', provider='osfstorage', path=test_file.path, version=1)
        nlogs = node.logs.count()
        res = self.app.get(url, auth=noncontrib.auth)
        assert_equal(res.status_code, 200)

        test_file.reload()
        assert_equal(test_file.get_view_count(), 1)
        assert_equal(node.logs.count(), nlogs) # don't log views

    def test_auth_download_with_path_not_found(self):
        url = self.build_url(action='download', provider='osfstorage', path=None, version=1)
        with pytest.raises(Exception):
            self.app.get(url, auth=self.user.auth)

    def test_auth_download_with_path_root(self):
        user = AuthUserFactory()
        institution = InstitutionFactory()
        region = RegionFactory()
        region._id = institution._id
        user.save()
        region.save()
        url = self.build_url(action='download', provider='osfstorage', path='/', version=1)
        res = self.app.get(url, auth=user.auth)
        assert_equal(res.status_code, 200)

    def test_auth_download_not_allowed(self):
        node = ProjectFactory(is_public=True, creator=self.user)
        addon = node.get_addon('osfstorage')
        addon.region.is_allowed = False
        addon.region.save()
        test_file = create_test_file(node, self.user)
        url = self.build_url(nid=node._id, action='download', provider='osfstorage', path=test_file.path, version=1)
        with pytest.raises(Exception):
            self.app.get(url, auth=self.user.auth)

    def test_auth_download_preprint(self):
        preprint = PreprintFactory()
        url = self.build_url(nid=preprint._id, action='download', provider='osfstorage', path='/', version=1)
        res = self.app.get(url, auth=self.user.auth)
        assert_equal(res.status_code, 200)


class TestAddonLogs(OsfTestCase):

    def setUp(self):
        super(TestAddonLogs, self).setUp()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
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

    def configure_osf_addon(self):
        self.project = ProjectFactory(creator=self.user)
        self.node_addon = self.project.get_addon('osfstorage')
        self.node_addon.save()

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

    @mock.patch('website.util.waterbutler.get_node_info')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    @mock.patch('requests.get', {'code': 404, 'referrer': None, 'message_short': 'Page not found'})
    def test_add_log_timestamptoken(self, mock_perform, mock_downloadfile, mock_nodeinfo):
        mock_downloadfile.return_value = '/testfile'
        mock_nodeinfo.return_value = {}

        result_list1_count = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id).count()
        nodelog_count1 = NodeLog.objects.all().count()
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        userkey_generation(self.user._id)
        file_node = create_test_file(node=self.node, user=self.user, filename=path)
        file_node._path = '/' + path
        file_node.save()
        payload = self.build_payload(metadata={
            'provider': 's3compatinstitutions',
            'name': path,
            'materialized': '/' + path,
            'path': '/' + path,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }, request_meta={'url': url}, root_path=file_node._id)
        nlogs = self.node.logs.count()

        self.app.put_json(url, payload, headers={'Content-Type': 'application/json'})
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs + 1)
        nodelog_count2 = NodeLog.objects.all().count()
        assert_equal(nodelog_count1 + 1, nodelog_count2)
        result_list2 = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_true(mock_perform.called, 'perform not called')

        ## tearDown
        rdmuserkey_pvt_key = RdmUserKey.objects.get(guid=self.user.id, key_kind=api_settings.PRIVATE_KEY_VALUE)
        pvt_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pvt_key.key_name)
        os.remove(pvt_key_path)
        rdmuserkey_pvt_key.delete()

        rdmuserkey_pub_key = RdmUserKey.objects.get(guid=self.user.id, key_kind=api_settings.PUBLIC_KEY_VALUE)
        pub_key_path = os.path.join(api_settings.KEY_SAVE_PATH, rdmuserkey_pub_key.key_name)
        os.remove(pub_key_path)
        rdmuserkey_pub_key.delete()

    @mock.patch('addons.base.views.timestamp')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_add_log(self, mock_perform, mock_timestamp):
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={
            'provider': 'osfstorage',
            'name': 'Hello.txt',
            'materialized': path,
            'path': path,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }, request_meta={'url': url}, root_path=self.file._id)
        nlogs = self.node.logs.count()
        self.app.put_json(url, payload, headers={'Content-Type': 'application/json'})
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs + 1)
        # # Mocking form_message and perform so that the payload need not be exact.
        # assert_true(mock_form_message.called, "form_message not called")
        assert_true(mock_perform.called, 'perform not called')

    @mock.patch('addons.base.views.BaseFileNode')
    @mock.patch('addons.base.views.timestamp')
    @pytest.mark.enable_quickfiles_creation
    def test_waterbutler_hook_succeeds_for_quickfiles_nodes(self, mock_timestamp, mock_basefilenode):
        quickfiles = QuickFilesNode.objects.get_for_user(self.user)
        materialized_path = 'pizza'
        url = quickfiles.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={
            'provider': 'osfstorage',
            'name': 'Hello.txt',
            'materialized': materialized_path,
            'path': 'abc123',
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }, request_meta={'url': url}, provider='osfstorage')
        resp = self.app.put_json(url, payload, headers={'Content-Type': 'application/json'})
        assert resp.status_code == 200

    def test_add_log_missing_args(self):
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={'path': path}, auth=None)
        nlogs = self.node.logs.count()
        res = self.app.put_json(
            url,
            payload,
            headers={'Content-Type': 'application/json'},
            expect_errors=True,
        )
        assert_equal(res.status_code, 400)
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs)

    def test_add_log_no_user(self):
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={'path': path}, auth={'id': None})
        nlogs = self.node.logs.count()
        res = self.app.put_json(
            url,
            payload,
            headers={'Content-Type': 'application/json'},
            expect_errors=True,
        )
        assert_equal(res.status_code, 400)
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs)

    def test_add_log_no_addon(self):
        path = 'pizza'
        node = ProjectFactory(creator=self.user)
        url = node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={'path': path})
        nlogs = node.logs.count()
        res = self.app.put_json(
            url,
            payload,
            headers={'Content-Type': 'application/json'},
            expect_errors=True,
        )
        assert_equal(res.status_code, 400)
        self.node.reload()
        assert_equal(node.logs.count(), nlogs)

    def test_add_log_bad_action(self):
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={'path': path}, action='dance')
        nlogs = self.node.logs.count()
        res = self.app.put_json(
            url,
            payload,
            headers={'Content-Type': 'application/json'},
            expect_errors=True,
        )
        assert_equal(res.status_code, 400)
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs)

    def test_action_file_rename(self):
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(
            request_meta={'url': url},
            action='move',
            metadata={
                'provider': 's3compatinstitutions',
                'name': 'new.txt',
                'materialized': '/' + 'new.txt',
                'path': '/' + self.file._id + '/' + 'new.txt',
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': self.file._id,
                'nid': self.node._id,
                'dest_pạth': '/' + self.file._id + '/' + 'new.txt',
            },
            source={
                'materialized': 'foo',
                'provider': 's3compatinstitutions',
                'node': {'_id': self.node._id},
                'name': 'new.txt',
                'kind': 'file',
                'root_path': self.file._id,
                'nid': self.node._id,
                'path': 'foo',
                'size': 1,
            },
            destination={
                'path': 'foo',
                'materialized': 'foo',
                'provider': 's3compatinstitutions',
                'node': {'_id': self.node._id},
                'name': 'old.txt',
                'kind': 'file',
                'root_path': self.file._id,
                'nid': self.node._id,
                'dest_path': 'foo',
                'size': 1,
            },
        )
        self.app.put_json(
            url,
            payload,
            headers={'Content-Type': 'application/json'}
        )
        self.node.reload()

        assert_equal(
            self.node.logs.latest().action,
            'addon_file_renamed',
        )

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_file_rename_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')

        # Create file
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
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
        }, request_meta={'url': wb_log_url}, root_path=file_node._id, ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + filename, created_file.path)

        # Rename the file
        newfilename = 'file_ver2'
        self.app.put_json(wb_log_url, self.build_payload(
            request_meta={'url': wb_log_url}, root_path=file_node._id,
            action='move',
            metadata={
                'provider': 's3compatinstitutions',
                'name': 'new.txt',
                'materialized': '/' + 'new.txt',
                'path': '/' + self.file._id + '/' + 'new.txt',
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': self.file._id,
                'nid': self.node._id,
                'dest_pạth': '/' + self.file._id + '/' + 'new.txt',
            },
            source={
                'provider': 's3compatinstitutions',
                'name': filename,
                'materialized': '/' + filename,
                'path': '/' + filename,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'nid': self.node._id,
                'root_path': file_node._id,
                'size': 1,
            },
            destination={
                'provider': 's3compatinstitutions',
                'name': newfilename,
                'materialized': '/' + newfilename,
                'path': '/' + newfilename,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'nid': self.node._id,
                'root_path': file_node._id,
                'size': 1,
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        renamed_file = files_query.get()
        assert_equal('/testfile/' + newfilename, renamed_file.path)

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_folder_rename_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/folder_ver1/my_precious_file'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')
        base_url = self.node.osfstorage_region.waterbutler_url
        wb_url = base_url + '?version=1'

        # Create file inside folder
        foldername = 'folder_ver1'
        filename = 'my_precious_file'
        filepath = '/{}/{}'.format(foldername, filename)

        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
            'name': filename,
            'materialized': filepath,
            'path': filepath,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            },
        }, request_meta={'url': wb_url}, root_path=file_node._id), headers={'Content-Type': 'application/json'}, )
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + filepath, created_file.path)

        # Rename the folder
        newfoldername = 'folder_ver2'
        self.app.put_json(wb_log_url, self.build_payload(
            request_meta={'url': wb_url},
            root_path=file_node._id,
            action='move',
            metadata={
                'provider': 's3compatinstitutions',
                'name': newfoldername,
                'materialized': '/' + newfoldername,
                'path': '/' + file_node._id + '/' + newfoldername,
                'node': {'_id': self.node._id},
                'kind': 'folder',
                'root_path': file_node._id,
                'nid': self.node._id,
                'dest_pạth': '/' + file_node._id + '/' + newfoldername,
            },
            source={
                'provider': 's3compatinstitutions',
                'name': foldername,
                'materialized': '/' + foldername,
                'path': '/' + foldername,
                'node': {'_id': self.node._id},
                'kind': 'folder',
                'root_path': file_node._id,
                'nid': self.node._id,
                'size': 1,
            },
            destination={
                'provider': 's3compatinstitutions',
                'name': newfoldername,
                'materialized': '/' + newfoldername,
                'path': file_node._id + '/' + newfoldername,
                'node': {'_id': self.node._id},
                'kind': 'folder',
                'root_path': file_node._id,
                'nid': self.node._id,
                'size': 1
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        renamed_file = files_query.get()
        filepath = '/{}/{}'.format(newfoldername, filename)
        assert_equal('/' + file_node._id + filepath, renamed_file.path)

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_file_move_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')

        # Create file
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
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
        }, request_meta={'url': wb_log_url}, root_path=file_node._id, ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + filename, created_file.path)

        # Move the file
        movedfilepath = 'cool_folder/' + filename
        self.app.put_json(wb_log_url, self.build_payload(
            request_meta={'url': wb_log_url},
            root_path=file_node._id,
            action='move',
            metadata={
                'provider': 's3compatinstitutions',
                'name': filename,
                'materialized': '/' + filename,
                'path': '/' + file_node._id + '/' + filename,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': file_node._id,
                'nid': self.node._id,
                'dest_pạth': '/' + file_node._id + '/' + filename,
            },
            source={
                'provider': 's3compatinstitutions',
                'name': filename,
                'materialized': '/' + filename,
                'path': '/' + filename,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': file_node._id,
                'nid': self.node._id,
                'size': 1,
            },
            destination={
                'provider': 's3compatinstitutions',
                'name': filename,
                'materialized': '/' + movedfilepath,
                'path': '/' + movedfilepath,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'nid': self.node._id,
                'root_path': file_node._id,
                'size': 1,
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        renamed_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + movedfilepath, renamed_file.path)

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_folder_move_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')

        # Create file
        foldername = 'nice_folder'
        folderpath = foldername + '/'
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + folderpath + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
            'name': filename,
            'materialized': '/' + folderpath + filename,
            'path': '/' + folderpath + filename,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }, request_meta={'url': wb_log_url}, root_path=file_node._id, ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + folderpath + filename, created_file.path)

        # Move the folder
        movedfolderpath = 'trash_bin/{}/'.format(foldername)
        self.app.put_json(wb_log_url, self.build_payload(
            action='move',
            metadata={
                'provider': 's3compatinstitutions',
                'name': 'new.txt',
                'materialized': '/' + movedfolderpath,
                'path': '/' + file_node._id + '/' + movedfolderpath,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': file_node._id,
                'nid': self.node._id,
                'dest_pạth': '/' + file_node._id + '/' + movedfolderpath,
            },
            source={
                'provider': 's3compatinstitutions',
                'name': foldername,
                'materialized': '/' + folderpath,
                'path': '/' + folderpath,
                'node': {'_id': self.node._id},
                'kind': 'folder',
                'nid': self.node._id,
                'root_path': file_node._id,
                'size': 1,
            },
            destination={
                'provider': 's3compatinstitutions',
                'name': foldername,
                'materialized': '/' + movedfolderpath,
                'path': '/' + movedfolderpath,
                'node': {'_id': self.node._id},
                'kind': 'folder',
                'nid': self.node._id,
                'root_path': file_node._id,
                'size': 1
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        renamed_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + movedfolderpath + filename, renamed_file.path)

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_file_remove_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')

        # Create file
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
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
        }, request_meta={'url': wb_log_url}, root_path=file_node._id, ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + filename, created_file.path)

        # Delete the file
        self.app.put_json(wb_log_url, self.build_payload(
            request_meta={'url': wb_log_url}, root_path=file_node._id,
            action='delete',
            metadata={
                'provider': 's3compatinstitutions',
                'name': filename,
                'materialized': '/' + filename,
                'path': '/' + filename,
                'kind': 'file',
                'nid': self.node._id,
                'extra': {
                    'version': '1'
                }
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        removed_file = files_query.get()
        assert_equal(2, removed_file.inspection_result_status)

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_action_folder_remove_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')

        # Create file
        foldername = 'nice_folder'
        folderpath = foldername + '/'
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + folderpath + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
            'name': filename,
            'materialized': '/' + folderpath + filename,
            'path': '/' + folderpath + filename,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }, request_meta={'url': wb_log_url}, root_path=file_node._id, ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + folderpath + filename, created_file.path)

        # Remove the folder
        self.app.put_json(wb_log_url, self.build_payload(
            request_meta={'url': wb_log_url}, root_path=file_node._id,
            action='delete',
            metadata={
                'provider': 's3compatinstitutions',
                'name': foldername,
                'materialized': '/' + folderpath,
                'path': '/' + folderpath,
                'kind': 'folder',
                'nid': self.node._id,
                'extra': {
                    'version': '1'
                }
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        removed_file = files_query.get()
        assert_equal(2, removed_file.inspection_result_status)

    @mock.patch('requests.get')
    @mock.patch('website.util.waterbutler.download_file')
    @mock.patch('website.notifications.events.files.FileAdded.perform')
    def test_disconnect_provider_timestamp(self, mock_perform, mock_downloadfile, mock_get):
        mock_downloadfile.return_value = '/file_ver1'
        mock_get.return_value.status_code = 200
        wb_log_url = self.node.api_url_for('create_waterbutler_log')

        # Create file
        filename = 'file_ver1'
        file_node = create_test_file(node=self.node, user=self.user, filename=filename)
        file_node._path = '/' + filename
        file_node.save()
        self.app.put_json(wb_log_url, self.build_payload(metadata={
            'provider': 's3compatinstitutions',
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
        }, request_meta={'url': wb_log_url}, root_path=file_node._id, ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + filename, created_file.path)

        # Disable addon
        self.node.delete_addon('github', Auth(self.user))
        self.node.save()

        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        removed_file = files_query.get()
        assert_equal(2, removed_file.inspection_result_status)

    def test_action_downloads_contrib(self):
        url = self.node.api_url_for('create_waterbutler_log')
        download_actions=('download_file', 'download_zip')
        base_url = self.node.osfstorage_region.waterbutler_url
        wb_url = base_url + '?version=1'
        for action in download_actions:
            payload = self.build_payload(metadata={'path': '/testfile',
                                                   'nid': self.node._id},
                                         action_meta={'is_mfr_render': False},
                                         request_meta={'url': wb_url},
                                         action=action)
            nlogs = self.node.logs.count()
            res = self.app.put_json(
                url,
                payload,
                headers={'Content-Type': 'application/json'},
                expect_errors=False,
            )
            assert_equal(res.status_code, 200)

        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs)

    @mock.patch('addons.base.views.BaseFileNode')
    @mock.patch('addons.base.views.timestamp')
    def test_add_file_osfstorage_log(self, mock_timestamp, mock_basefilenode):
        self.configure_osf_addon()
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={
            'provider': 'osfstorage',
            'name': 'Hello.txt',
            'materialized': path,
            'path': path,
            'kind': 'file',
            'size': 2345,
            'created_utc': '',
            'modified_utc': '',
            'extra': {
                'version': '1'
            }
        }, request_meta={'url': url}, )
        nlogs = self.node.logs.count()
        self.app.put_json(url, payload, headers={'Content-Type': 'application/json'})
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs + 1)
        assert('urls' in self.node.logs.filter(action='osf_storage_file_added')[0].params)

    @mock.patch('addons.base.views.BaseFileNode')
    def test_add_folder_osfstorage_log(self, mock_basefilenode):
        self.configure_osf_addon()
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(metadata={'materialized': path, 'kind': 'folder', 'path': path, 'size': 1000},
                                     request_meta={'url': url}, root_path=self.file._id)
        nlogs = self.node.logs.count()
        self.app.put_json(url, payload, headers={'Content-Type': 'application/json'})
        self.node.reload()
        assert_equal(self.node.logs.count(), nlogs + 1)
        assert ('urls' not in self.node.logs.filter(action='osf_storage_file_added')[0].params)

    def test_move_folder_osfstorage_log(self):
        user = AuthUserFactory()
        user.affiliated_institutions = [InstitutionFactory()]
        project_1 = ProjectFactory(creator=user)
        project_2 = ProjectFactory(creator=user)
        file_node = create_test_file(node=project_1, user=user, filename='text001')
        path = 'pizza'
        url = self.node.api_url_for('create_waterbutler_log')
        payload = self.build_payload(
            metadata={'materialized': path, 'kind': 'folder', 'path': path, 'size': 1000},
            action='move',
            source={
                'name': 'text001',
                'materialized': 'test1',
                'provider': 'osfstorage',
                'nid': project_1._id,
                'old_root_id': file_node._id,
                'path': '/' + project_1.get_addon('osfstorage').get_root()._id,
                'kind': 'folder',
                'node': {
                    '_id': project_1._id,
                    'url': project_1.url,
                    'title': project_1.title,
                }
            },
            destination={
                'name': 'text001',
                'materialized': 'test1',
                'provider': 'osfstorage',
                'nid': project_2._id,
                'path': '/' + project_2.get_addon('osfstorage').get_root()._id,
                'kind': 'folder',
                'node': {
                    '_id': project_2._id,
                    'url': project_2.url,
                    'title': project_2.title,
                }
            })
        with pytest.raises(Exception):
            self.app.put_json(url, payload, headers={'Content-Type': 'application/json'})
            self.node.reload()


class TestAddonLogsDifferentProvider(OsfTestCase):

    def setUp(self):
        super(TestAddonLogsDifferentProvider, self).setUp()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
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

        self.user.add_addon('googledrive')
        self.user_addon2 = self.user.get_addon('googledrive')
        self.oauth_settings2 = GoogleDriveAccountFactory(display_name='john')
        self.oauth_settings2.save()
        self.user.external_accounts.add(self.oauth_settings2)
        self.user.save()
        self.node.add_addon('googledrive', self.auth_obj)
        self.node_addon2 = self.node.get_addon('googledrive')
        self.node_addon2.user = 'john'
        self.node_addon2.repo = 'youre-my-best-friend'
        self.node_addon2.user_settings = self.user_addon2
        self.node_addon2.external_account = self.oauth_settings2
        self.node_addon2.save()
        self.user_addon2.oauth_grants[self.node._id] = {self.oauth_settings._id: []}
        self.user_addon2.save()

    def configure_osf_addon(self):
        self.project = ProjectFactory(creator=self.user)
        self.node_addon = self.project.get_addon('osfstorage')
        self.node_addon.save()

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
        src_provider = 's3compatinstitutions'
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
        }, request_meta={'url': wb_log_url}, root_path=file_node._id), headers={'Content-Type': 'application/json'})

        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        assert_equal(1, files_query.count())
        created_file = files_query.get()
        assert_equal('/' + file_node._id + '/' + filename, created_file.path)

        # Move the file
        movedfilepath = 'cool_folder/' + filename
        self.app.put_json(wb_log_url, self.build_payload(
            request_meta={'url': wb_log_url},
            root_path=file_node._id,
            action='move',
            metadata={
                'provider': src_provider,
                'name': filename,
                'materialized': '/' + movedfilepath,
                'path': '/' + movedfilepath,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': file_node._id,
                'nid': self.node._id,
                'dest_pạth': '/' + file_node._id + '/' + movedfilepath,
            },
            source={
                'provider': dest_provider,
                'name': filename,
                'materialized': '/' + filename,
                'path': '/' + filename,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': file_node._id,
                'nid': self.node._id,
            },
            destination={
                'provider': src_provider,
                'name': filename,
                'materialized': '/' + movedfilepath,
                'path': '/' + movedfilepath,
                'node': {'_id': self.node._id},
                'kind': 'file',
                'root_path': file_node._id,
                'nid': self.node._id,
                'dest_pạth': '/' + file_node._id + '/' + movedfilepath,
                'size': 1,
            },
        ), headers={'Content-Type': 'application/json'})
        files_query = RdmFileTimestamptokenVerifyResult.objects.filter(project_id=self.node._id)
        import logging
        logging.critical(files_query)
        assert_equal(2, files_query.count())
        renamed_file = files_query.last()
        assert_equal('/' + file_node._id + '/' + movedfilepath, renamed_file.path)


class TestCheckAuth(OsfTestCase):

    def setUp(self):
        super(TestCheckAuth, self).setUp()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
        self.node = ProjectFactory(creator=self.user)

    def test_has_permission(self):
        res = views.check_access(self.node, Auth(user=self.user), 'upload', None)
        assert_true(res)

    def test_not_has_permission_read_public(self):
        self.node.is_public = True
        self.node.save()
        views.check_access(self.node, Auth(), 'download', None)

    def test_not_has_permission_read_has_link(self):
        link = new_private_link('red-special', self.user, [self.node], anonymous=False)
        views.check_access(self.node, Auth(private_key=link.key), 'download', None)

    def test_not_has_permission_logged_in(self):
        user2 = AuthUserFactory()
        with assert_raises(HTTPError) as exc_info:
            views.check_access(self.node, Auth(user=user2), 'download', None)
        assert_equal(exc_info.exception.code, 403)

    def test_not_has_permission_not_logged_in(self):
        with assert_raises(HTTPError) as exc_info:
            views.check_access(self.node, Auth(), 'download', None)
        assert_equal(exc_info.exception.code, 401)

    def test_has_permission_on_parent_node_upload_pass_if_registration(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        ProjectFactory(creator=component_admin, parent=self.node)
        registration = RegistrationFactory(project=self.node)

        component_registration = registration._nodes.first()

        assert_false(component_registration.has_permission(self.user, WRITE))
        res = views.check_access(component_registration, Auth(user=self.user), 'upload', None)
        assert_true(res)

    def test_has_permission_on_parent_node_metadata_pass_if_registration(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, parent=self.node, is_public=False)

        component_registration = RegistrationFactory(project=component, creator=component_admin)

        assert_false(component_registration.has_permission(self.user, READ))
        res = views.check_access(component_registration, Auth(user=self.user), 'metadata', None)
        assert_true(res)

    def test_has_permission_on_parent_node_upload_fail_if_not_registration(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, parent=self.node)

        assert_false(component.has_permission(self.user, WRITE))
        with assert_raises(HTTPError):
            views.check_access(component, Auth(user=self.user), 'upload', None)

    def test_has_permission_on_parent_node_copyfrom(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=False, parent=self.node)

        assert_false(component.has_permission(self.user, WRITE))
        res = views.check_access(component, Auth(user=self.user), 'copyfrom', None)
        assert_true(res)


class TestCheckOAuth(OsfTestCase):

    def setUp(self):
        super(TestCheckOAuth, self).setUp()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
        self.node = ProjectFactory(creator=self.user)

    def test_has_permission_private_not_authenticated(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=False, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=False)

        assert_false(component.has_permission(self.user, WRITE))
        with assert_raises(HTTPError) as exc_info:
            views.check_access(component, Auth(user=self.user), 'download', cas_resp)
        assert_equal(exc_info.exception.code, 403)

    def test_has_permission_private_no_scope_forbidden(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=False, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=True, status=None, user=self.user._id,
                                   attributes={'accessTokenScope': {}})

        assert_false(component.has_permission(self.user, WRITE))
        with assert_raises(HTTPError) as exc_info:
            views.check_access(component, Auth(user=self.user), 'download', cas_resp)
        assert_equal(exc_info.exception.code, 403)

    def test_has_permission_public_irrelevant_scope_allowed(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=True, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=True, status=None, user=self.user._id,
                                   attributes={'accessTokenScope': {'osf.users.all_read'}})

        assert_false(component.has_permission(self.user, WRITE))
        res = views.check_access(component, Auth(user=self.user), 'download', cas_resp)
        assert_true(res)

    def test_has_permission_private_irrelevant_scope_forbidden(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=False, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=True, status=None, user=self.user._id,
                                   attributes={'accessTokenScope': {'osf.users.all_read'}})

        assert_false(component.has_permission(self.user, WRITE))
        with assert_raises(HTTPError) as exc_info:
            views.check_access(component, Auth(user=self.user), 'download', cas_resp)
        assert_equal(exc_info.exception.code, 403)

    def test_has_permission_decommissioned_scope_no_error(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=False, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=True, status=None, user=self.user._id,
                                   attributes={'accessTokenScope': {
                                       'decommissioned.scope+write',
                                       'osf.nodes.data_read',
                                   }})

        assert_false(component.has_permission(self.user, WRITE))
        res = views.check_access(component, Auth(user=self.user), 'download', cas_resp)
        assert_true(res)

    def test_has_permission_write_scope_read_action(self):
        component_admin = AuthUserFactory()
        component_admin.affiliated_institutions = [InstitutionFactory()]
        component = ProjectFactory(creator=component_admin, is_public=False, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=True, status=None, user=self.user._id,
                                   attributes={'accessTokenScope': {'osf.nodes.data_write'}})

        assert_false(component.has_permission(self.user, WRITE))
        res = views.check_access(component, Auth(user=self.user), 'download', cas_resp)
        assert_true(res)

    def test_has_permission_read_scope_write_action_forbidden(self):
        component = ProjectFactory(creator=self.user, is_public=False, parent=self.node)
        cas_resp = cas.CasResponse(authenticated=True, status=None, user=self.user._id,
                                   attributes={'accessTokenScope': {'osf.nodes.data_read'}})

        assert_true(component.has_permission(self.user, WRITE))
        with assert_raises(HTTPError) as exc_info:
            views.check_access(component, Auth(user=self.user), 'upload', cas_resp)
        assert_equal(exc_info.exception.code, 403)


def assert_urls_equal(url1, url2):
    furl1 = furl.furl(url1)
    furl2 = furl.furl(url2)
    for attr in ['scheme', 'host', 'port']:
        setattr(furl1, attr, None)
        setattr(furl2, attr, None)
    # Note: furl params are ordered and cause trouble
    assert_equal(dict(furl1.args), dict(furl2.args))
    furl1.args = {}
    furl2.args = {}
    assert_equal(furl1, furl2)


def mock_touch(self, bearer, version=None, revision=None, **kwargs):
    if version:
        if self.versions:
            try:
                return self.versions[int(version) - 1]
            except (IndexError, ValueError):
                return None
        else:
            return None
    return file_models.FileVersion()


@mock.patch('addons.github.models.GithubFileNode.touch', mock_touch)
@mock.patch('addons.github.models.GitHubClient.repo', mock.Mock(side_effect=ApiError))
class TestAddonFileViews(OsfTestCase):

    def setUp(self):
        super(TestAddonFileViews, self).setUp()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
        self.project = ProjectFactory(creator=self.user)

        self.user.add_addon('github')
        self.project.add_addon('github', auth=Auth(self.user))

        self.user_addon = self.user.get_addon('github')
        self.node_addon = self.project.get_addon('github')
        self.oauth = GitHubAccountFactory()
        self.oauth.save()

        self.user.external_accounts.add(self.oauth)
        self.user.save()

        self.node_addon.user_settings = self.user_addon
        self.node_addon.external_account = self.oauth
        self.node_addon.repo = 'Truth'
        self.node_addon.user = 'E'
        self.node_addon.save()

        self.user_addon.oauth_grants[self.project._id] = {self.oauth._id: []}
        self.user_addon.save()

    def set_sentry(status):
        def wrapper(func):
            @functools.wraps(func)
            def wrapped(*args, **kwargs):
                enabled, sentry.enabled = sentry.enabled, status
                func(*args, **kwargs)
                sentry.enabled = enabled

            return wrapped

        return wrapper

    with_sentry = set_sentry(True)

    def get_test_file(self):
        version = file_models.FileVersion(identifier='1')
        version.save()
        ret = GithubFile(
            name='Test',
            target=self.project,
            path='/test/Test',
            materialized_path='/test/Test',
        )
        ret.save()
        ret.add_version(version)
        return ret

    def get_second_test_file(self):
        version = file_models.FileVersion(identifier='1')
        version.save()
        ret = GithubFile(
            name='Test2',
            target=self.project,
            path='/test/Test2',
            materialized_path='/test/Test2',
        )
        ret.save()
        ret.add_version(version)
        return ret

    def get_uppercased_ext_test_file(self):
        version = file_models.FileVersion(identifier='1')
        version.save()
        ret = GithubFile(
            name='Test2.pdf',
            target=self.project,
            path='/test/Test2',
            materialized_path='/test/Test2',
        )
        ret.save()
        ret.add_version(version)
        return ret

    def get_ext_test_file(self):
        version = file_models.FileVersion(identifier='1')
        version.save()
        ret = GithubFile(
            name='Test2.pdf',
            target=self.project,
            path='/test/Test2',
            materialized_path='/test/Test2',
        )
        ret.save()
        ret.add_version(version)
        return ret

    def get_mako_return(self):
        ret = serialize_node(self.project, Auth(self.user), primary=True)
        ret.update({
            'error': '',
            'provider': '',
            'file_path': '',
            'sharejs_uuid': '',
            'private': '',
            'urls': {
                'files': '',
                'render': '',
                'sharejs': '',
                'mfr': '',
                'profile_image': '',
                'external': '',
                'archived_from': '',
            },
            'size': '',
            'extra': '',
            'file_name': '',
            'materialized_path': '',
            'file_id': '',
        })
        ret.update(rubeus.collect_addon_assets(self.project))
        return ret

    def test_redirects_to_guid(self):
        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path=file_node.path.strip('/'),
                provider='github'
            ),
            auth=self.user.auth
        )

        assert_equals(resp.status_code, 302)
        assert_equals(resp.location, 'http://localhost/{}/'.format(guid._id))

    def test_action_download_redirects_to_download_with_param(self):
        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.get('/{}/?action=download'.format(guid._id), auth=self.user.auth)

        assert_equals(resp.status_code, 302)
        location = furl.furl(resp.location)
        assert_urls_equal(location.url, file_node.generate_waterbutler_url(action='download', direct=None, version=''))

    def test_action_download_redirects_to_download_with_path(self):
        file_node = self.get_uppercased_ext_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.get('/{}/download?format=pdf'.format(guid._id), auth=self.user.auth)

        assert_equals(resp.status_code, 302)
        location = furl.furl(resp.location)
        assert_equal(location.url, file_node.generate_waterbutler_url(format='pdf', action='download', direct=None, version=''))


    def test_action_download_redirects_to_download_with_path_uppercase(self):
        file_node = self.get_uppercased_ext_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.get('/{}/download?format=pdf'.format(guid._id), auth=self.user.auth)

        assert_equals(resp.status_code, 302)
        location = furl.furl(resp.location)
        assert_equal(location.url, file_node.generate_waterbutler_url( format='pdf', action='download', direct=None, version=''))


    def test_action_download_redirects_to_download_with_version(self):
        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.get('/{}/?action=download&revision=1'.format(guid._id), auth=self.user.auth)

        assert_equals(resp.status_code, 302)
        location = furl.furl(resp.location)
        # Note: version is added but us but all other url params are added as well
        assert_urls_equal(location.url, file_node.generate_waterbutler_url(action='download', direct=None, revision=1, version=''))

    @mock.patch('addons.base.views.addon_view_file')
    @pytest.mark.enable_bookmark_creation
    def test_action_view_calls_view_file(self, mock_view_file):
        self.user.reload()
        self.project.reload()

        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        mock_view_file.return_value = self.get_mako_return()

        self.app.get('/{}/?action=view'.format(guid._id), auth=self.user.auth)

        args, kwargs = mock_view_file.call_args
        assert_equals(args[0].user._id, self.user._id)
        assert_equals(args[1], self.project)
        assert_equals(args[2], file_node)
        assert_true(isinstance(args[3], file_node.touch(None).__class__))

    @mock.patch('addons.base.views.addon_view_file')
    @pytest.mark.enable_bookmark_creation
    def test_no_action_calls_view_file(self, mock_view_file):
        self.user.reload()
        self.project.reload()

        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        mock_view_file.return_value = self.get_mako_return()

        self.app.get('/{}/'.format(guid._id), auth=self.user.auth)

        args, kwargs = mock_view_file.call_args
        assert_equals(args[0].user._id, self.user._id)
        assert_equals(args[1], self.project)
        assert_equals(args[2], file_node)
        assert_true(isinstance(args[3], file_node.touch(None).__class__))

    def test_download_create_guid(self):
        file_node = self.get_test_file()
        assert_is(file_node.get_guid(), None)

        self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path=file_node.path.strip('/'),
                provider='github',
            ),
            auth=self.user.auth
        )

        assert_true(file_node.get_guid())

    @pytest.mark.enable_bookmark_creation
    def test_view_file_does_not_delete_file_when_requesting_invalid_version(self):
        with mock.patch('addons.github.models.NodeSettings.is_private',
                        new_callable=mock.PropertyMock) as mock_is_private:
            mock_is_private.return_value = False

            file_node = self.get_test_file()
            assert_is(file_node.get_guid(), None)

            url = self.project.web_url_for(
                'addon_view_or_download_file',
                path=file_node.path.strip('/'),
                provider='github',
            )
            # First view generated GUID
            self.app.get(url, auth=self.user.auth)

            self.app.get(url + '?version=invalid', auth=self.user.auth, expect_errors=True)

            assert_is_not_none(BaseFileNode.load(file_node._id))
            assert_is_none(TrashedFileNode.load(file_node._id))

    def test_unauthorized_addons_raise(self):
        path = 'cloudfiles'
        self.node_addon.user_settings = None
        self.node_addon.save()

        resp = self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path=path,
                provider='github',
                action='download'
            ),
            auth=self.user.auth,
            expect_errors=True
        )

        assert_equals(resp.status_code, 401)

    def test_nonstorage_addons_raise(self):
        resp = self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path='sillywiki',
                provider='wiki',
                action='download'
            ),
            auth=self.user.auth,
            expect_errors=True
        )

        assert_equals(resp.status_code, 400)

    def test_head_returns_url_and_redriect(self):
        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.head('/{}/'.format(guid._id), auth=self.user.auth)
        location = furl.furl(resp.location)
        assert_equals(resp.status_code, 302)
        assert_urls_equal(location.url, file_node.generate_waterbutler_url(direct=None, version=''))

    def test_head_returns_url_with_version_and_redirect(self):
        file_node = self.get_test_file()
        guid = file_node.get_guid(create=True)

        resp = self.app.head('/{}/?revision=1&foo=bar'.format(guid._id), auth=self.user.auth)
        location = furl.furl(resp.location)
        # Note: version is added but us but all other url params are added as well
        assert_equals(resp.status_code, 302)
        assert_urls_equal(location.url, file_node.generate_waterbutler_url(direct=None, revision=1, version='', foo='bar'))

    def test_nonexistent_addons_raise(self):
        path = 'cloudfiles'
        self.project.delete_addon('github', Auth(self.user))
        self.project.save()

        resp = self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path=path,
                provider='github',
                action='download'
            ),
            auth=self.user.auth,
            expect_errors=True
        )

        assert_equals(resp.status_code, 400)

    def test_unauth_addons_raise(self):
        path = 'cloudfiles'
        self.node_addon.user_settings = None
        self.node_addon.save()

        resp = self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path=path,
                provider='github',
                action='download'
            ),
            auth=self.user.auth,
            expect_errors=True
        )

        assert_equals(resp.status_code, 401)

    def test_resolve_folder_raise(self):
        folder = OsfStorageFolder(
            name='folder',
            target=self.project,
            path='/test/folder/',
            materialized_path='/test/folder/',
        )
        folder.save()
        resp = self.app.get(
            self.project.web_url_for(
                'addon_view_or_download_file',
                path=folder._id,
                provider='osfstorage',
            ),
            auth=self.user.auth,
            expect_errors=True
        )

        assert_equals(resp.status_code, 400)

    def test_delete_action_creates_trashed_file_node(self):
        file_node = self.get_test_file()
        payload = {
            'provider': file_node.provider,
            'metadata': {
                'path': '/test/Test',
                'materialized': '/test/Test'
            }
        }
        views.addon_delete_file_node(self=None, target=self.project, user=self.user, event_type='file_removed', payload=payload)
        assert_false(GithubFileNode.load(file_node._id))
        assert_true(TrashedFileNode.load(file_node._id))

    def test_delete_action_no_file_node(self):
        file_node = self.get_test_file()
        payload = {
            'provider': file_node.provider,
            'metadata': {
                'path': '/test/FileThatDoesNotExists',
                'materialized': '/test/FileThatDoesNotExists'
            }
        }
        views.addon_delete_file_node(self=None, target=self.project, user=self.user, event_type='file_removed', payload=payload)
        assert_false(TrashedFileNode.load(file_node._id))

    def test_delete_action_for_folder_deletes_subfolders_and_creates_trashed_file_nodes(self):
        file_node = self.get_test_file()
        subfolder = GithubFolder(
            name='folder',
            target=self.project,
            path='/test/folder/',
            materialized_path='/test/folder/',
        )
        subfolder.save()
        payload = {
            'provider': file_node.provider,
            'metadata': {
                'path': '/test/',
                'materialized': '/test/'
            }
        }
        views.addon_delete_file_node(self=None, target=self.project, user=self.user, event_type='file_removed', payload=payload)
        assert_false(GithubFileNode.load(subfolder._id))
        assert_true(TrashedFileNode.load(file_node._id))

    @mock.patch('website.archiver.tasks.archive')
    def test_archived_from_url(self, mock_archive):
        file_node = self.get_test_file()
        second_file_node = self.get_second_test_file()
        file_node.copied_from = second_file_node

        registered_node = self.project.register_node(
            schema=get_default_metaschema(),
            auth=Auth(self.user),
            draft_registration=DraftRegistrationFactory(branched_from=self.project),
        )

        archived_from_url = views.get_archived_from_url(registered_node, file_node)
        view_url = self.project.web_url_for('addon_view_or_download_file', provider=file_node.provider, path=file_node.copied_from._id)
        assert_true(archived_from_url)
        assert_urls_equal(archived_from_url, view_url)

    @mock.patch('website.archiver.tasks.archive')
    def test_archived_from_url_without_copied_from(self, mock_archive):
        file_node = self.get_test_file()

        registered_node = self.project.register_node(
            schema=get_default_metaschema(),
            auth=Auth(self.user),
            draft_registration=DraftRegistrationFactory(branched_from=self.project),
        )
        archived_from_url = views.get_archived_from_url(registered_node, file_node)
        assert_false(archived_from_url)

    @mock.patch('website.archiver.tasks.archive')
    def test_copied_from_id_trashed(self, mock_archive):
        file_node = self.get_test_file()
        second_file_node = self.get_second_test_file()
        file_node.copied_from = second_file_node
        self.project.register_node(
            schema=get_default_metaschema(),
            auth=Auth(self.user),
            draft_registration=DraftRegistrationFactory(branched_from=self.project),
        )
        trashed_node = second_file_node.delete()
        assert_false(trashed_node.copied_from)

    @mock.patch('website.archiver.tasks.archive')
    def test_missing_modified_date_in_file_data(self, mock_archive):
        file_node = self.get_test_file()
        file_data = {
            'name': 'Test File Update',
            'materialized': file_node.materialized_path,
            'modified': None
        }
        file_node.update(revision=None, data=file_data)
        assert_equal(len(file_node.history), 1)
        assert_equal(file_node.history[0], file_data)

    @mock.patch('website.archiver.tasks.archive')
    def test_missing_modified_date_in_file_history(self, mock_archive):
        file_node = self.get_test_file()
        file_node.history.append({'modified': None})
        file_data = {
            'name': 'Test File Update',
            'materialized': file_node.materialized_path,
            'modified': None
        }
        file_node.update(revision=None, data=file_data)
        assert_equal(len(file_node.history), 2)
        assert_equal(file_node.history[1], file_data)

    @with_sentry
    @mock.patch('framework.sentry.sentry.captureMessage')
    def test_update_logs_to_sentry_when_called_with_disordered_metadata(self, mock_capture):
        file_node = self.get_test_file()
        file_node.history.append({'modified': parse_date(
                '2017-08-22T13:54:32.100900',
                ignoretz=True,
                default=timezone.now()  # Just incase nothing can be parsed
            )})
        data = {
            'name': 'a name',
            'materialized': 'materialized',
            'modified': '2016-08-22T13:54:32.100900'
        }
        file_node.update(revision=None, user=None, data=data)
        mock_capture.assert_called_with(str('update() receives metatdata older than the newest entry in file history.'), extra={'session': {}})


@pytest.mark.django_db
class TestLegacyViews(OsfTestCase):

    def setUp(self):
        super(TestLegacyViews, self).setUp()
        from api_tests.utils import create_test_file
        self.path = 'mercury.png'
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
        self.project = ProjectFactory(creator=self.user)
        self.node_addon = self.project.get_addon('osfstorage')
        file_record = self.node_addon.get_root().append_file(self.path)
        self.expected_path = file_record._id
        file_record.save()
        self.file = create_test_file(target=self.project, user=self.user)
        self.file_path = self.node_addon.get_root().append_file(self.file._id)
        self.file_path.save()
        self.node_addon.save()
        self.user_addon = self.user.get_or_add_addon('twofactor')
        self.user_addon.is_confirmed = True
        self.user_addon.save()

    def test_view_file_redirect(self):
        mock_request = mock.MagicMock()
        mock_request.args.to_dict.return_value = {'action': 'view'}
        mock_request.path = 'view'
        url = '/{0}/osffiles/{1}/'.format(self.project._id, self.file._id)
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        action='view',
                        path=self.file_path._id,
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_download_file_redirect(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123', 'action': 'view'}
        url = '/{0}/osffiles/{1}/download/'.format(self.project._id, self.file._id)
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        path=self.file_path._id,
                        action='download',
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_download_file_version_redirect(self):
        mock_request = mock.MagicMock()
        mock_request.args.to_dict.return_value = {'action': 'view', 'version': '3'}
        url = '/{0}/osffiles/{1}/version/3/download/'.format(
            self.project._id,
            self.file._id,
        )
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        version=3,
                        path=self.file_path._id,
                        action='download',
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_api_download_file_redirect(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123', 'action': 'view'}
        url = '/api/v1/project/{0}/osffiles/{1}/'.format(self.project._id, self.file._id)
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        path=self.file_path._id,
                        action='download',
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_api_download_file_version_redirect(self):
        mock_request = mock.MagicMock()
        mock_request.args.to_dict.return_value = {'action': 'view', 'version': '3'}
        url = '/api/v1/project/{0}/osffiles/{1}/version/3/'.format(
            self.project._id,
            self.file._id,
        )
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        version=3,
                        path=self.file_path._id,
                        action='download',
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_no_provider_name(self):
        mock_request = mock.MagicMock()
        mock_request.args.to_dict.return_value = {'action': 'view'}
        mock_request.path = 'view'
        url = '/{0}/files/{1}'.format(
            self.project._id,
            self.file._id,
        )
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        action='view',
                        path=self.file_path._id,
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_action_as_param(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123', 'action': 'view'}
        url = '/{}/osfstorage/files/{}/?action=download'.format(
            self.project._id,
            self.file._id,
        )
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        path=self.file_path._id,
                        action='download',
                        provider='osfstorage',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_other_addon_redirect(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123', 'action': 'view'}
        url = '/project/{0}/mycooladdon/files/{1}/'.format(
            self.project._id,
            self.file._id,
        )
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        path=self.file._id,
                        action='download',
                        provider='mycooladdon',
                    )
                    assert_urls_equal(res.location, expected_url)

    def test_other_addon_redirect_download(self):
        mock_request = mock.MagicMock()
        mock_request.return_value = {'region_id': '123', 'action': 'view'}
        url = '/project/{0}/mycooladdon/files/{1}/download/'.format(
            self.project._id,
            self.file._id,
        )
        with mock.patch('addons.twofactor.models.UserSettings.verify_code', return_value=True):
            with mock.patch('addons.base.views.request', mock_request):
                with mock.patch('osf.models.mixins.AddonModelMixin.get_addon',
                                side_effect=[self.user_addon, self.node_addon]):
                    res = self.app.get(
                        url,
                        auth=self.user.auth,
                        headers={'X-OSF-OTP': 'fake_otp'},
                        expect_errors=True
                    )
                    assert_equal(res.status_code, 301)
                    expected_url = self.project.web_url_for(
                        'addon_view_or_download_file',
                        path=self.file._id,
                        action='download',
                        provider='mycooladdon',
                    )
                    assert_urls_equal(res.location, expected_url)


class TestViewUtils(OsfTestCase):

    def setUp(self):
        super(TestViewUtils, self).setUp()
        self.user = AuthUserFactory()
        self.user.affiliated_institutions = [InstitutionFactory()]
        self.auth_obj = Auth(user=self.user)
        self.node = ProjectFactory(creator=self.user)
        self.session = Session(data={'auth_user_id': self.user._id})
        self.session.save()
        self.cookie = itsdangerous.Signer(settings.SECRET_KEY).sign(self.session._id)
        self.configure_addon()
        self.JWE_KEY = jwe.kdf(settings.WATERBUTLER_JWE_SECRET.encode('utf-8'), settings.WATERBUTLER_JWE_SALT.encode('utf-8'))
        self.mock_api_credentials_are_valid = mock.patch('addons.github.api.GitHubClient.check_authorization', return_value=True)
        self.mock_api_credentials_are_valid.start()

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

    @mock.patch('addons.github.models.NodeSettings.get_folders', return_value=[])
    def test_serialize_addons(self, mock_folders):
        addon_dicts = serialize_addons(self.node, self.auth_obj)

        enabled_addons = [addon for addon in addon_dicts if addon['enabled']]
        assert len(enabled_addons) == 2
        assert enabled_addons[0]['short_name'] == 'github'
        assert enabled_addons[1]['short_name'] == 'osfstorage'

        default_addons = [addon for addon in addon_dicts if addon['default']]
        assert len(default_addons) == 1
        assert default_addons[0]['short_name'] == 'osfstorage'

    @mock.patch('addons.github.models.NodeSettings.get_folders', return_value=[])
    def test_include_template_json(self, mock_folders):
        """ Some addons (github, gitlab) need more specialized template infomation so we want to
        ensure we get those extra variables that when the addon is enabled.
        """
        addon_dicts = serialize_addons(self.node, self.auth_obj)

        enabled_addons = [addon for addon in addon_dicts if addon['enabled']]
        assert len(enabled_addons) == 2
        assert enabled_addons[1]['short_name'] == 'osfstorage'
        assert enabled_addons[0]['short_name'] == 'github'
        assert 'node_has_auth' in enabled_addons[0]
        assert 'valid_credentials' in enabled_addons[0]

    @mock.patch('addons.github.models.NodeSettings.get_folders', return_value=[])
    def test_collect_node_config_js(self, mock_folders):

        addon_dicts = serialize_addons(self.node, self.auth_obj)

        asset_paths = collect_node_config_js(addon_dicts)

        # Default addons should be in addon dicts, but they have no js assets because you can't
        # connect/disconnect from them, think osfstorage, there's no node-cfg for that.
        default_addons = [addon['short_name'] for addon in addon_dicts if addon['default']]
        assert not any('/{}/'.format(addon) in asset_paths for addon in default_addons)

    def test_get_first_addon(self):
        res = AddonModelMixin.get_first_addon(self.node, 'osfstorage')
        assert_is_instance(res, NodeSettings)

    def test_get_first_addon_not_correct_addon_name(self):
        res = AddonModelMixin.get_first_addon(self.node, 'not_correct_name')
        assert res is None

    @mock.patch('osf.models.mixins.AddonModelMixin._settings_model')
    def test_get_first_addon_settings_model_is_none(self, mock_settings_model):
        mock_settings_model.return_value = None
        res = AddonModelMixin.get_first_addon(self.node, 'osfstorage')
        assert res is None

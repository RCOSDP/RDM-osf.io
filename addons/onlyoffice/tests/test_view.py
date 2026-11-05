# -*- coding: utf-8 -*-
"""Views tests for the onlyoffice addon."""
import pytest
import mock
from waffle.testutils import override_switch

from addons.onlyoffice.util import _ext_to_app_name_onlyoffice, get_onlyoffice_url, get_file_info
from addons.onlyoffice.views import onlyoffice_edit_by_onlyoffice, onlyoffice_check_file_info
from addons.onlyoffice.proof_key import ProofKeyHelper
from framework.auth import Auth
from osf import features
from osf.exceptions import ValidationError
from osf.models import Guid, NodeLog
from osf.models.filelog import FileLog
from osf_tests.factories import AuthUserFactory, UserFactory, ProjectFactory, NodeFactory
from tests.base import OsfTestCase

from flask import request
import requests
# from datetime import datetime, timezone, timedelta
from osf.models import BaseFileNode
from .. import settings
from .. import util as onlyoffice_util
from .. import token as onlyoffice_token
from .. import proof_key as onlyoffice_proof_key
from .. import views as onlyoffice_views
from website import settings as websettings

#class Response():
#    status_code = 0
#    text = ''
#    content = ''
#    def raise_for_status(self):
#        return 1

class Filenode():
    name = ''

#class Pkhelper():
#    def hasKey():
#        return True


class TestOnlyofficeAddon(OsfTestCase):
    def setup(self):
        self.project = ProjectFactory()
        self.user = AuthUserFactory()
        self.auth = Auth(user=self.user)
        self.node = NodeFactory(creator=self.user, parent=self.project)

    def test_ext_to_app(self):
        assert _ext_to_app_name_onlyoffice('docx') == 'Word'
        assert _ext_to_app_name_onlyoffice('xlsx') == 'Excel'
        assert _ext_to_app_name_onlyoffice('pptx') == 'PowerPoint'

    def test_get_onlyoffice_url(self):
        mock_discovery = '<?xml version="1.0" encoding="utf-8"?><wopi-discovery><net-zone name="external-http"><app name="Word" favIconUrl="http://192.168.1.1:8002/web-apps/apps/documenteditor/main/resources/img/favicon.ico"><action name="edit" ext="docx" urlsrc="http://192.168.1.1:8002/hosting/wopi/word/view?&amp;&lt;rs=DC_LLCC&amp;&gt;&lt;dchat=DISABLE_CHAT&amp;&gt;&lt;embed=EMBEDDED&amp;&gt;&lt;fs=FULLSCREEN&amp;&gt;&lt;hid=HOST_SESSION_ID&amp;&gt;&lt;rec=RECORDING&amp;&gt;&lt;sc=SESSION_CONTEXT&amp;&gt;&lt;thm=THEME_ID&amp;&gt;&lt;ui=UI_LLCC&amp;&gt;&lt;wopisrc=WOPI_SOURCE&amp;&gt;&amp;" /></app></net-zone></wopi-discovery>'

        with mock.patch.object(onlyoffice_util, '_get_onlyoffice_discovery', return_value=mock_discovery):
            url = get_onlyoffice_url('server', 'edit', 'docx')
        assert url == 'http://192.168.1.1:8002/hosting/wopi/word/view?'

    '''
    def test_edit_by_onlyoffice(self):
        mock_pkhelper = Pkhelper()
        mock_filenode = Filenode()
        mock_filenode.name = 'filename1.docx'
        #mock_pkhelper = True
        mock_encrypt = 'Cookie String'
        mock_get_url_value = 'http://192.168.1.1:8002/onlyoffice/'
        settings.WOPI_SRC_HOST = 'http://srchost'

        with mock.patch.object(request.cookies, 'get', return_value='Cookie String'):
            with mock.patch.object(BaseFileNode, 'load', return_value=mock_filenode):
                with mock.patch.object(onlyoffice_views, 'pkhelper', return_value=mock_pkhelper):
                    with mock.patch.object(onlyoffice_util, 'get_onlyoffice_url', return_value=mock_get_url_value):
                        with mock.patch.object(onlyoffice_token, 'encrypt', return_value=mock_encrypt):
                            context = onlyoffice_edit_by_onlyoffice(file_id='ABCDEFG')
        assert context['wopi_url'] == 'http://192.168.1.1:8002/onlyoffice/rs=ja-jp&ui=ja-jp&wopisrc=http://srchost/wopi/files/ABCDEFG'
        assert context['access_token'] == 'Cookie String'
    '''

    def test_check_file_info(self):
        mock_jsonobj = {
                         'data' :
                            { 'auth' : 'cookie string',
                              'file_id' : 'ABCDEFG'
                            }
                       }
        mock_check_token = True
        mock_proof_key = True
        mock_filenode = Filenode()
        mock_filenode.name = 'filename.docx'
        mock_user_info = {'user_id': 'userid', 'full_name': 'fullname', 'display_name': 'dispname'}
        mock_file_info = {'name': 'filename.docx', 'mtime': '202501010000'}
        mock_file_version = ''
        mock_access_token = {websettings.COOKIE_NAME: 'cookie'}

        with mock.patch.object(BaseFileNode.objects, 'get', return_value=mock_filenode):
            with mock.patch.object(request.args, 'get', return_value=mock_access_token):
                with mock.patch.object(onlyoffice_util, 'get_user_info', return_value=mock_user_info):
                    with mock.patch.object(onlyoffice_token, 'decrypt', return_value=mock_jsonobj):
                        with mock.patch.object(onlyoffice_token, 'check_token', return_value=mock_check_token):
                            with mock.patch.object(onlyoffice_util, 'get_file_info', return_value=mock_file_info):
                                with mock.patch.object(onlyoffice_util, 'get_file_version', return_value=mock_file_version):
                                    with mock.patch.object(onlyoffice_util, 'check_proof_key', return_value=mock_proof_key):
                                        res = onlyoffice_check_file_info(file_id='ABCDEFG')
        assert res['BaseFileName'] == 'filename.docx'


class TestONLYOFFICEWOPICallbackLogSuppression(OsfTestCase):
    """addons/onlyoffice/views.py: onlyoffice_file_content_view.
    WOPI GetFile (GET) is Group A of the Callback Log Policy: ONLYOFFICE's own fetch of
    the file must pass callback_log=False, so that it is not recorded as a user download.
    WOPI PutFile (POST) keeps callback_log='true' explicit, so that saves keep creating
    their FILE_UPDATED Recent Activity log."""

    def test_getfile_specifies_callback_log_false(self):
        mock_jsonobj = {'data': {'auth': 'cookie string', 'file_id': 'ABCDEFG'}}
        mock_filenode = mock.MagicMock()
        mock_filenode.name = 'filename.docx'
        mock_filenode.generate_waterbutler_url = mock.MagicMock(
            return_value='http://waterbutler.example/v1/resources/abc12/providers/osfstorage/xyz?callback_log=False'
        )
        mock_user_info = {'user_id': 'userid', 'full_name': 'fullname', 'display_name': 'dispname'}
        mock_file_info = {'name': 'filename.docx', 'mtime': '202501010000'}

        mock_request = mock.MagicMock()
        mock_request.method = 'GET'
        mock_request.args.get = mock.MagicMock(return_value='access-token-value')

        mock_get_response = mock.MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.iter_content.return_value = [b'content']

        with mock.patch('addons.onlyoffice.views.request', mock_request):
            with mock.patch.object(BaseFileNode.objects, 'get', return_value=mock_filenode):
                with mock.patch.object(onlyoffice_util, 'get_user_info', return_value=mock_user_info):
                    with mock.patch.object(onlyoffice_token, 'decrypt', return_value=mock_jsonobj):
                        with mock.patch.object(onlyoffice_token, 'check_token', return_value=True):
                            with mock.patch.object(onlyoffice_token, 'get_cookie', return_value='cookie'):
                                with mock.patch.object(onlyoffice_util, 'get_file_info', return_value=mock_file_info):
                                    with mock.patch.object(onlyoffice_util, 'get_file_version', return_value='1'):
                                        with mock.patch.object(onlyoffice_util, 'check_proof_key', return_value=True):
                                            with mock.patch('addons.onlyoffice.views.requests.get', return_value=mock_get_response) as mock_get:
                                                res = onlyoffice_views.onlyoffice_file_content_view(file_id='ABCDEFG')

        mock_filenode.generate_waterbutler_url.assert_called_once_with(
            version='1', action='download', direct=None, _internal=True, callback_log=False
        )
        called_url = mock_get.call_args[1]['url']
        assert 'callback_log=False' in called_url
        assert res.status_code == 200

    def test_edit_by_onlyoffice_putfile_suppresses_callback_log_optout(self):
        mock_jsonobj = {'data': {'auth': 'cookie string', 'file_id': 'ABCDEFG'}}
        mock_filenode = mock.MagicMock()
        mock_filenode.name = 'filename.docx'
        mock_filenode.generate_waterbutler_url = mock.MagicMock(
            return_value='http://waterbutler.example/v1/resources/abc12/providers/osfstorage/xyz?callback_log=true'
        )
        mock_user_info = {'user_id': 'userid', 'full_name': 'fullname', 'display_name': 'dispname'}
        mock_file_info = {'name': 'filename.docx', 'mtime': '202501010000'}
        mock_file_version = ''

        mock_request = mock.MagicMock()
        mock_request.method = 'POST'
        mock_request.args.get = mock.MagicMock(return_value='access-token-value')
        mock_request.headers.get = mock.MagicMock(return_value='10')

        mock_put_response = mock.MagicMock()
        mock_put_response.status_code = 200

        with mock.patch('addons.onlyoffice.views.request', mock_request):
            with mock.patch.object(BaseFileNode.objects, 'get', return_value=mock_filenode):
                with mock.patch.object(onlyoffice_util, 'get_user_info', return_value=mock_user_info):
                    with mock.patch.object(onlyoffice_token, 'decrypt', return_value=mock_jsonobj):
                        with mock.patch.object(onlyoffice_token, 'check_token', return_value=True):
                            with mock.patch.object(onlyoffice_token, 'get_cookie', return_value='cookie'):
                                with mock.patch.object(onlyoffice_util, 'get_file_info', return_value=mock_file_info):
                                    with mock.patch.object(onlyoffice_util, 'get_file_version', return_value=mock_file_version):
                                        with mock.patch.object(onlyoffice_util, 'check_proof_key', return_value=True):
                                            with mock.patch('addons.onlyoffice.views.requests.put', return_value=mock_put_response) as mock_put:
                                                res = onlyoffice_views.onlyoffice_file_content_view(file_id='ABCDEFG')

        mock_filenode.generate_waterbutler_url.assert_called_once_with(
            direct=None, _internal=True, callback_log='true', kind='file'
        )
        called_url = mock_put.call_args[1]['url']
        assert 'callback_log=true' in called_url
        assert res.status_code == 200


class TestOnlyofficeOpenLog(OsfTestCase):
    """addons/onlyoffice/views.py: onlyoffice_edit_by_onlyoffice records a new
    'onlyoffice_file_opened' Recent Activity log once the user is granted access
    to the editor screen and wopi_url is not empty, gated by the same switch as
    the download-history feature, and must never let a failure to record that
    log stop the editor screen from opening."""

    WOPI_CLIENT_URL = 'http://onlyoffice.example/hosting/wopi/word/edit?'

    def setUp(self):
        super(TestOnlyofficeOpenLog, self).setUp()
        self.user = AuthUserFactory()
        self.project = ProjectFactory(creator=self.user)

    def _make_filenode(self):
        mock_filenode = mock.MagicMock()
        mock_filenode.name = 'file.docx'
        mock_filenode._id = 'fileid123'
        mock_filenode.materialized_path = '/file.docx'
        mock_filenode.target = self.project
        mock_filenode.touch = mock.MagicMock(return_value='version1')
        return mock_filenode

    def _call_edit(self, mock_filenode, wopi_client_url=WOPI_CLIENT_URL):
        from osf.models import OSFUser, BaseFileNode
        with mock.patch('addons.onlyoffice.views.request') as mock_request:
            mock_request.cookies.get.return_value = 'cookie-value'
            mock_request.headers.get.return_value = None
            with mock.patch.object(Guid, 'load', return_value=mock.MagicMock(referent=self.project)):
                with mock.patch.object(BaseFileNode, 'resolve_class') as mock_resolve:
                    mock_resolve.return_value.get_or_create.return_value = mock_filenode
                    with mock.patch.object(OSFUser, 'from_cookie', return_value=self.user):
                        with mock.patch.object(onlyoffice_util, 'check_permission', return_value=True):
                            with mock.patch.object(onlyoffice_util, 'get_onlyoffice_url', return_value=wopi_client_url):
                                with mock.patch.object(settings, 'WOPI_SRC_HOST', 'http://srchost'):
                                    with mock.patch.object(onlyoffice_views.pkhelper, 'hasKey', return_value=True):
                                        with mock.patch.object(onlyoffice_token, 'encrypt', return_value='token-value'):
                                            return onlyoffice_edit_by_onlyoffice.__wrapped__(
                                                guid=self.project._id, provider='osfstorage', path='/file.docx'
                                            )

    def test_records_open_log_when_switch_on(self):
        with override_switch(features.ENABLE_DOWNLOAD_HISTORY_LOG, active=True):
            context = self._call_edit(self._make_filenode())

        assert context['access_token'] == 'token-value'
        assert context['wopi_url'] == self.WOPI_CLIENT_URL + 'rs=ja-jp&ui=ja-jp&WOPISrc=http://srchost/wopi/files/fileid123'
        log = NodeLog.objects.get(action='onlyoffice_file_opened', node=self.project)
        assert log.user == self.user
        assert log.params['path'] == '/file.docx'
        assert log.params['addon'] == 'NII Storage'
        assert 'view' in log.params['urls']
        # Same key as the other file logs (None for a top-level project).
        assert 'project' in log.params
        assert log.params['project'] == self.project.parent_id

    def test_records_file_log_with_path_when_switch_on(self):
        # add_log() writes FileLog (and the RdmLogger output) only when params['path']
        # exists; otherwise the KeyError is swallowed and only NodeLog is saved.
        with override_switch(features.ENABLE_DOWNLOAD_HISTORY_LOG, active=True):
            self._call_edit(self._make_filenode())

        filelog = FileLog.objects.get(action='onlyoffice_file_opened', project_id=self.project._id)
        assert filelog.user == self.user
        assert filelog.path == '/file.docx'

    def test_does_not_record_open_log_when_wopi_url_is_empty(self):
        # The ONLYOFFICE server did not return an editor URL (e.g. no response to the
        # discovery request): the editor cannot be opened, so nothing is recorded.
        with override_switch(features.ENABLE_DOWNLOAD_HISTORY_LOG, active=True):
            context = self._call_edit(self._make_filenode(), wopi_client_url=None)

        assert context['wopi_url'] == ''
        assert not NodeLog.objects.filter(action='onlyoffice_file_opened', node=self.project).exists()
        assert not FileLog.objects.filter(action='onlyoffice_file_opened', project_id=self.project._id).exists()

    def test_does_not_record_open_log_when_switch_off(self):
        with override_switch(features.ENABLE_DOWNLOAD_HISTORY_LOG, active=False):
            self._call_edit(self._make_filenode())

        assert not NodeLog.objects.filter(action='onlyoffice_file_opened', node=self.project).exists()

    def test_open_log_failure_does_not_block_editor_and_logs_warning(self):
        with override_switch(features.ENABLE_DOWNLOAD_HISTORY_LOG, active=True):
            with mock.patch.object(self.project, 'add_log', side_effect=Exception('boom')):
                with mock.patch.object(onlyoffice_views, 'logger') as mock_logger:
                    context = self._call_edit(self._make_filenode())

        # The editor screen still opens.
        assert context['access_token'] == 'token-value'
        # ... but the failure is surfaced as a warning.
        assert mock_logger.warning.called
        warning_message = mock_logger.warning.call_args[0][0]
        assert 'failed to record the open log' in warning_message
        assert 'fileid123' in warning_message
        assert not NodeLog.objects.filter(action='onlyoffice_file_opened', node=self.project).exists()

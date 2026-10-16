# -*- coding: utf-8 -*-
"""Views tests for the onlyoffice addon."""
import pytest
import mock

from addons.onlyoffice.util import _ext_to_app_name_onlyoffice, get_onlyoffice_url, get_file_info
from addons.onlyoffice.views import onlyoffice_edit_by_onlyoffice, onlyoffice_check_file_info
from addons.onlyoffice.proof_key import ProofKeyHelper
from framework.auth import Auth
from osf.exceptions import ValidationError
from osf.models import Guid
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
    """addons/onlyoffice/views.py: WOPI PutFile (POST) must pass callback_log='true'
    explicitly, opting out of the URL-builder's default _internal=True suppression -
    otherwise ONLYOFFICE saves would silently stop creating their FILE_UPDATED Recent
    Activity log. Zero test coverage existed for this view before (verified via
    repo-wide grep for onlyoffice_file_content_view/callback_log)."""

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

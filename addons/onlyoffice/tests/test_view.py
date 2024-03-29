# -*- coding: utf-8 -*-
"""Views tests for the onlyoffice addon."""
import pytest
import mock

from addons.onlyoffice.util import _ext_to_app_name_onlyoffice, get_onlyoffice_url, get_file_info
from addons.onlyoffice.views import onlyoffice_edit_by_onlyoffice, onlyoffice_check_file_info
from framework.auth import Auth
from osf.exceptions import ValidationError
from osf.models import Guid
from osf_tests.factories import AuthUserFactory, UserFactory, ProjectFactory, NodeFactory
from tests.base import OsfTestCase

from flask import request
import requests
from osf.models import BaseFileNode
from .. import settings
from .. import util as onlyoffice_util
from website import settings as websettings


class Response():
    status_code = 0
    text = ''
    content = ''

class Filenode():
    name = ''


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
        mock_response = Response()
        mock_response.text = '<?xml version="1.0" encoding="utf-8"?><wopi-discovery><net-zone name="external-http"><app name="Word" favIconUrl="http://192.168.1.1:8002/web-apps/apps/documenteditor/main/resources/img/favicon.ico"><action name="edit" ext="docx" urlsrc="http://192.168.1.1:8002/hosting/wopi/word/view?&amp;&lt;rs=DC_LLCC&amp;&gt;&lt;dchat=DISABLE_CHAT&amp;&gt;&lt;embed=EMBEDDED&amp;&gt;&lt;fs=FULLSCREEN&amp;&gt;&lt;hid=HOST_SESSION_ID&amp;&gt;&lt;rec=RECORDING&amp;&gt;&lt;sc=SESSION_CONTEXT&amp;&gt;&lt;thm=THEME_ID&amp;&gt;&lt;ui=UI_LLCC&amp;&gt;&lt;wopisrc=WOPI_SOURCE&amp;&gt;&amp;" /></app></net-zone></wopi-discovery>'

        with mock.patch.object(requests, 'get', return_value=mock_response):
            url = get_onlyoffice_url('server', 'edit', 'docx')
        assert url == 'http://192.168.1.1:8002/hosting/wopi/word/view?'

    def test_edit_by_onlyoffice(self):
        mock_filenode = Filenode()
        mock_filenode.name = 'filename1.docx'
        mock_get_url_value = 'http://192.168.1.1:8002/onlyoffice/'
        settings.WOPI_SRC_HOST = 'http://srchost'

        with mock.patch.object(request.cookies, 'get', return_value='Cookie String'):
            with mock.patch.object(BaseFileNode, 'load', return_value=mock_filenode):
                with mock.patch.object(onlyoffice_util, 'get_onlyoffice_url', return_value=mock_get_url_value):
                    context = onlyoffice_edit_by_onlyoffice(file_id_ver='ABCDEFG')
        assert context['wopi_url'] == 'http://192.168.1.1:8002/onlyoffice/rs=ja-jp&ui=ja-jp&wopisrc=http://srchost/wopi/files/ABCDEFG-01'
        assert context['access_token'] == 'Cookie String'


    def test_check_file_info(self):
        mock_filenode = Filenode()
        mock_filenode.name = 'filename.docx'
        mock_user_info = {'user_id': 'userid', 'full_name': 'fullname', 'display_name': 'dispname'}
        mock_file_info = {'file_name': 'filename.docx'}
        mock_access_token = {websettings.COOKIE_NAME: 'cookie'}

        with mock.patch.object(BaseFileNode, 'load', return_value=mock_filenode):
            with mock.patch.object(request.args, 'get', return_value=mock_access_token):
                with mock.patch.object(onlyoffice_util, 'get_user_info', return_value=mock_user_info):
                    with mock.patch.object(onlyoffice_util, 'get_file_info', return_value=mock_file_info):
                        res = onlyoffice_check_file_info(file_id_ver='ABCDEFG')
        assert res['BaseFileName'] == 'filename.docx'

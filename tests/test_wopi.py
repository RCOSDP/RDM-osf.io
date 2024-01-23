import unittest
import pytest
import mock
from nose.tools import *

from flask import request
from flask import Flask

from osf.models import BaseFileNode
from website import settings
from website.wopi.views import check_file_info, _get_user_info, _get_file_info

class Filenode():
    name = ''

class TestCase1(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

        self.user_info = {
            'user_id':   'uid',
            'full_name': 'full name',
            'display_name': 'display_name'
        }
        self.file_info = {
            'file_name': 'filename.docx',
            'file_size':  1234,
            'file_mtime': 2023012345
        }

        self.filenode = Filenode()
        self.filenode.name = ''

    @pytest.mark.django_db
    def test_case1(self):

        with self.app.test_request_context('/wopi', headers={'Cookie': 'osf=Cookie String', 'User_Agent': 'COOLWSD'}, query_string={'access_token': 'Token'}):
            self.filenode.name = 'filename1.docx'
            settings.WOPI_SRC_HOST = 'http://srchost'

            mock_base_file_node = mock.MagicMock()
            mock_base_file_node.load.return_value = self.filenode
            with mock.patch('website.wopi.views.BaseFileNode', mock_base_file_node):
                mock_get_user_info = mock.MagicMock()
                mock_get_user_info.return_value = self.user_info
                with mock.patch('website.wopi.views._get_user_info', mock_get_user_info):
                    mock_get_file_info = mock.MagicMock()
                    mock_get_file_info.return_value = self.file_info
                    with mock.patch('website.wopi.views._get_file_info', mock_get_file_info):
                        res = check_file_info(file_id_ver='ABCDEFG-01')
                        assert_equal(res['BaseFileName'], 'filename.docx')

    @pytest.mark.django_db
    def test_case2(self):

        with self.app.test_request_context('/wopi', headers={'Cookie': 'osf=Cookie String', 'User_Agent': 'Node.js'}, query_string={'access_token': 'Token'}):
            self.filenode.name = 'filename1.docx'
            settings.WOPI_SRC_HOST = 'http://srchost'

            mock_base_file_node = mock.MagicMock()
            mock_base_file_node.load.return_value = self.filenode
            with mock.patch('website.wopi.views.BaseFileNode', mock_base_file_node):
                mock_get_user_info = mock.MagicMock()
                mock_get_user_info.return_value = self.user_info
                with mock.patch('website.wopi.views._get_user_info', mock_get_user_info):
                    mock_get_file_info = mock.MagicMock()
                    mock_get_file_info.return_value = self.file_info
                    with mock.patch('website.wopi.views._get_file_info', mock_get_file_info):
                        res = check_file_info(file_id_ver='ABCDEFG-01')
                        assert_equal(res['BaseFileName'], 'filename.docx')
                        assert_equal(res['Version'], '01')

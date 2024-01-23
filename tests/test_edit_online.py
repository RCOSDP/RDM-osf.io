#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
from nose.tools import *  # noqa; PEP8 asserts
import mock
import pytest

from flask import request
from flask import Flask

from osf.models import BaseFileNode
from website.edit_online.views import edit_by_onlyoffice, edit_by_collabora
from website.edit_online.util import get_onlyoffice_url, get_collabora_url
from website import settings


class Response():
    status_code = 0
    text = ''
    content = ''

class Filenode():
    name = ''


class TestCase1(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)

        self.resp = Response()
        self.resp.status_code = 200
        self.resp.text = ''
        self.resp.content = b''

        self.filenode = Filenode()
        self.filenode.name = ''


    @mock.patch('website.edit_online.util.requests.get')
    def test_case1(self, mock_requests):

        self.resp.text = '<?xml version="1.0" encoding="utf-8"?><wopi-discovery><net-zone name="external-http"><app name="Word" favIconUrl="http://192.168.1.1:8002/web-apps/apps/documenteditor/main/resources/img/favicon.ico"><action name="edit" ext="docx" urlsrc="http://192.168.1.1:8002/hosting/wopi/word/view?&amp;&lt;rs=DC_LLCC&amp;&gt;&lt;dchat=DISABLE_CHAT&amp;&gt;&lt;embed=EMBEDDED&amp;&gt;&lt;fs=FULLSCREEN&amp;&gt;&lt;hid=HOST_SESSION_ID&amp;&gt;&lt;rec=RECORDING&amp;&gt;&lt;sc=SESSION_CONTEXT&amp;&gt;&lt;thm=THEME_ID&amp;&gt;&lt;ui=UI_LLCC&amp;&gt;&lt;wopisrc=WOPI_SOURCE&amp;&gt;&amp;" /></app></net-zone></wopi-discovery>'

        mock_requests.return_value = self.resp
        url = get_onlyoffice_url('server', 'edit', 'docx')
        assert_equal(url, 'http://192.168.1.1:8002/hosting/wopi/word/view?', 'get_onlyoffice_url test1')


    @mock.patch('website.edit_online.util.requests.get')
    def test_case2(self, mock_requests):

        self.resp.text = '<wopi-discovery><net-zone name="external-http"><app favIconUrl="http://192.168.1.1:9980/browser/abd9205/images/x-office-document.svg" name="writer"><action default="true" ext="docx" name="edit" urlsrc="http://192.168.1.1:9980/browser/abd9205/cool.html?"/></app></net-zone></wopi-discovery>'

        mock_requests.return_value = self.resp
        url = get_collabora_url('server', 'edit', 'docx')
        assert_equal(url, 'http://192.168.1.1:9980/browser/abd9205/cool.html?', 'get_collabora test1')


    @pytest.mark.django_db
    def test_case3(self):
        #mock_request.cookies.get.return_value = 'Cookie String'
        # mock_cookies.get.return_value = 'Cookie String'
        # mock_cookies = mock.MagicMock()
        # mock_request = mock_cookies
        with self.app.test_request_context('/wopi', headers={'Cookie': 'osf=Cookie String'}):
            self.filenode.name = 'filename1.docx'
            settings.WOPI_SRC_HOST = 'http://srchost'

            mock_base_file_node = mock.MagicMock()
            mock_base_file_node.load.return_value = self.filenode
            #with mock.patch('osf.models.BaseFileNode', mock_base_file_node):
            with mock.patch('website.edit_online.views.BaseFileNode', mock_base_file_node):
                #mock_base_file_node.load.return_value = self.filenode
                mock_get_onlyoffice_url = mock.MagicMock()
                mock_get_onlyoffice_url.return_value = 'http://192.168.1.1:8002/onlyoffice/'
                # with mock.patch('website.edit_online.url.get_onlyoffice_url', mock_get_onlyoffice_url):
                with mock.patch('website.edit_online.views.get_onlyoffice_url', mock_get_onlyoffice_url):
                    context = edit_by_onlyoffice(file_id_ver='ABCDEFG-01')
                    assert_equal(context['wopi_url'], 'http://192.168.1.1:8002/onlyoffice/rs=ja-jp&ui=ja-jp&wopisrc=http://srchost/wopi/files/ABCDEFG-01', 'edit_by_onlyoffice test1')
                    assert_equal(context['access_token'], 'Cookie String', 'edit_by_onlyoffice test2')


    @pytest.mark.django_db
    def test_case4(self):

        with self.app.test_request_context('/wopi', headers={'Cookie': 'osf=Cookie String'}):
            self.filenode.name = 'filename1.docx'
            settings.WOPI_SRC_HOST = 'http://srchost'

            mock_base_file_node = mock.MagicMock()
            mock_base_file_node.load.return_value = self.filenode
            with mock.patch('website.edit_online.views.BaseFileNode', mock_base_file_node):
                mock_get_collabora_url = mock.MagicMock()
                mock_get_collabora_url.return_value = 'http://192.168.1.1:9980/collabora/'
                with mock.patch('website.edit_online.views.get_collabora_url', mock_get_collabora_url):
                    context = edit_by_collabora(file_id_ver='ABCDEFG-01')
                    assert_equal(context['wopi_url'], 'http://192.168.1.1:9980/collabora/access_token=Cookie String&WOPISrc=http://srchost/wopi/files/ABCDEFG-01', 'edit_by_collabora test1')
                    assert_equal(context['access_token'], 'Cookie String', 'edit_by_collabora test2')

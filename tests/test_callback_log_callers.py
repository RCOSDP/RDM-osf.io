# -*- coding: utf-8 -*-
"""Tests for each caller in the "Callback Log Policy" (api/base/utils.py, waterbutler_api_url_for).

The URL builder no longer sets callback_log=false automatically for _internal=True.
- Group A: a download the system performs for its own processing passes callback_log=False
  explicitly, so that it is not recorded as a user download in the Recent Activity log.
- Group B: an internal upload / copy does not pass callback_log, so that WaterButler sends
  the completion callback as before this feature (log, timestamp, storage usage,
  notification, completion of the archive).

Group A No.1 (ONLYOFFICE GetFile) is tested in addons/onlyoffice/tests/test_view.py.
"""
import io
import shutil
import tempfile

import mock
import pytest
from furl import furl

from addons.metadata import suggestion
from addons.wiki import views as wiki_views
from osf.management.commands import export_user_account, force_archive
from osf.models import ExportData
from osf_tests.factories import (
    ExportDataFactoryAddon,
    ExportDataRestoreAddonFactory,
    InstitutionFactory,
)
from tests.base import OsfTestCase
from website.archiver import tasks as archiver_tasks
from website.conferences import utils as conferences_utils
from website.util import waterbutler as waterbutler_util


def _args(url):
    return furl(url).args


def _make_addon_file():
    # A file of an add-on storage, so that the version list is fetched from WaterButler
    file = mock.MagicMock()
    file.provider = 's3compatinstitutions'
    file.path = '/file.txt'
    file.target._id = 'abc12'
    file._id = 'fileid'
    file.checkout_id = None
    return file


@pytest.mark.django_db
class TestGroupAInternalDownloadsSpecifyCallbackLogFalse(OsfTestCase):

    def setUp(self):
        super(TestGroupAInternalDownloadsSpecifyCallbackLogFalse, self).setUp()
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(TestGroupAInternalDownloadsSpecifyCallbackLogFalse, self).tearDown()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # No.2 website/util/waterbutler.py: download_file (timestamp, etc.)
    def test_02_download_file(self):
        file_node = mock.MagicMock()
        file_node.name = 'file.txt'
        with mock.patch.object(waterbutler_util, 'get_node_info', return_value={'data': {}}):
            with mock.patch('website.util.waterbutler.requests.get', side_effect=Exception('stop')):
                res = waterbutler_util.download_file('cookie', file_node, self.tmp_dir)

        assert res is None
        file_node.generate_waterbutler_url.assert_called_once_with(
            action='download', direct=None, _internal=True, callback_log=False
        )

    # No.3 addons/wiki/views.py: _get_md_content_from_wb (wiki import)
    def test_03_wiki_import(self):
        node = mock.MagicMock()
        node.guids.first.return_value._id = 'abc12'
        task = mock.MagicMock()
        task.is_aborted.return_value = False
        response = mock.MagicMock()
        response._content = b'wiki content'
        data = [{'_id': 'fileid', 'wiki_name': 'page'}]

        with mock.patch('addons.wiki.views.requests.get', return_value=response) as mock_get:
            res = wiki_views._get_md_content_from_wb(data, node, {'Authorization': 'token'}, task)

        assert res[0]['wiki_content'] == 'wiki content'
        assert _args(mock_get.call_args[0][0])['callback_log'] == 'False'

    # No.4 addons/metadata/suggestion.py: suggestion_file_metadata_get_value
    def test_04_metadata_suggestion(self):
        node = mock.MagicMock()
        node._id = 'abc12'
        with mock.patch.object(suggestion, 'request') as mock_request:
            mock_request.cookies.get.return_value = 'cookie'
            with mock.patch.object(suggestion, 'get_file_size_and_extension', side_effect=Exception('stop')) as mock_size:
                suggestion.suggestion_file_metadata_get_value('get-text-row-count', '', 'osfstorage/file.csv', node)

        assert _args(mock_size.call_args[0][0])['callback_log'] == 'False'

    # No.5 osf/management/commands/export_user_account.py: export_files
    def test_05_account_export(self):
        node = mock.MagicMock()
        node._id = 'abc12'
        node.osfstorage_region.waterbutler_url = 'http://waterbutler.example'
        user = mock.MagicMock()
        user.get_or_create_cookie.return_value = 'cookie'
        response = mock.MagicMock()
        response.status_code = 200
        response.content = b'zip'

        with mock.patch('osf.management.commands.export_user_account.requests.get', return_value=response) as mock_get:
            export_user_account.export_files(node, user, self.tmp_dir)

        args = _args(mock_get.call_args[1]['url'])
        assert args['callback_log'] == 'False'
        assert 'zip' in args

    # No.6 osf/models/export_data.py: ExportData.extract_file_information_json_from_source_storage
    def test_06_export_file_versions(self):
        export_data = ExportDataFactoryAddon()
        InstitutionFactory(_id=export_data.source.guid)
        mock_requests = mock.MagicMock()
        mock_requests.get.return_value.status_code = 404

        with mock.patch('osf.models.export_data.requests', mock_requests):
            with mock.patch.object(ExportData, 'process_directory'):
                with mock.patch('osf.models.export_data.BaseFileNode') as mock_base_file_node:
                    mock_base_file_node.objects.filter.return_value.exclude.return_value = [_make_addon_file()]
                    export_data.extract_file_information_json_from_source_storage()

        assert mock_requests.get.called
        args = _args(mock_requests.get.call_args_list[0][0][0])
        assert 'versions' in args
        assert args['callback_log'] == 'False'

    # No.7 osf/models/export_data_restore.py: ExportDataRestore.extract_file_information_json_from_destination_storage
    def test_07_restore_file_versions(self):
        data_restore = ExportDataRestoreAddonFactory()
        InstitutionFactory(_id=data_restore.destination.guid)
        mock_requests = mock.MagicMock()
        mock_requests.get.return_value.status_code = 404

        with mock.patch('osf.models.export_data_restore.requests', mock_requests):
            with mock.patch('osf.models.export_data_restore.BaseFileNode') as mock_base_file_node:
                mock_base_file_node.objects.filter.return_value.exclude.return_value = [_make_addon_file()]
                data_restore.extract_file_information_json_from_destination_storage()

        assert mock_requests.get.called
        args = _args(mock_requests.get.call_args_list[0][0][0])
        assert 'versions' in args
        assert args['callback_log'] == 'False'

    # No.8 osf/models/export_data.py: ExportData.read_data_file_from_source
    def test_08_export_read_source_file(self):
        mock_requests = mock.MagicMock()
        with mock.patch('osf.models.export_data.requests', mock_requests):
            ExportData.read_data_file_from_source(mock.MagicMock(), {'osf': 'cookie'}, 'abc12', 'osfstorage', '/file.txt')

        assert _args(mock_requests.get.call_args[0][0])['callback_log'] == 'False'


@pytest.mark.django_db
class TestGroupBInternalUploadCopyDoNotSpecifyCallbackLog(OsfTestCase):

    # No.1 website/archiver/tasks.py: archive_addon (registration archive)
    def test_01_registration_archive(self):
        src = mock.MagicMock()
        src._id = 'src12'
        src.osfstorage_region.waterbutler_url = 'http://waterbutler.example'
        src.get_addon.return_value.archive_folder_name = 'Archive of NII Storage'
        dst = mock.MagicMock()
        dst._id = 'dst12'
        user = mock.MagicMock()
        user.get_or_create_cookie.return_value.decode.return_value = 'cookie'

        with mock.patch.object(archiver_tasks, 'create_app_context'):
            with mock.patch.object(archiver_tasks, 'ArchiveJob') as mock_archive_job:
                mock_archive_job.load.return_value.info.return_value = (src, dst, user)
                with mock.patch.object(archiver_tasks, 'make_copy_request') as mock_make_copy_request:
                    archiver_tasks.archive_addon('osfstorage', 'job_pk')

        url = mock_make_copy_request.delay.call_args[1]['url']
        assert 'callback_log' not in _args(url)

    # No.2 osf/management/commands/force_archive.py: perform_wb_copy
    def test_02_force_archive(self):
        src = mock.MagicMock()
        src._id = 'src12'
        src.osfstorage_region.waterbutler_url = 'http://waterbutler.example'
        dst = mock.MagicMock()
        dst._id = 'dst12'
        dst.files.filter.return_value.exists.return_value = False
        user = mock.MagicMock()
        user.get_or_create_cookie.return_value = 'cookie'
        reg = mock.MagicMock()
        reg.archive_job.info.return_value = (src, dst, user)
        node_settings = mock.MagicMock()
        node_settings.short_name = 'osfstorage'
        node_settings.archive_folder_name = 'Archive of NII Storage'
        response = mock.MagicMock()
        response.status_code = 201

        with mock.patch('osf.management.commands.force_archive.requests.post', return_value=response) as mock_post:
            force_archive.perform_wb_copy(reg, node_settings)

        assert 'callback_log' not in _args(mock_post.call_args[0][0])

    # No.3 website/util/waterbutler.py: upload_file (metadata add-on)
    def test_03_metadata_upload_file(self):
        with mock.patch('website.util.waterbutler.requests.put') as mock_put:
            waterbutler_util.upload_file('cookie', 'abc12', io.BytesIO(b'data'), 'file.txt', 'osfstorage')

        assert 'callback_log' not in _args(mock_put.call_args[0][0])

    # No.4 website/conferences/utils.py: upload_attachment (conference mail)
    def test_04_conference_attachment(self):
        user = mock.MagicMock()
        user.get_or_create_cookie.return_value.decode.return_value = 'cookie'
        node = mock.MagicMock()
        node._id = 'abc12'
        node.osfstorage_region.waterbutler_url = 'http://waterbutler.example'
        attachment = mock.MagicMock()
        attachment.filename = 'poster.pdf'
        attachment.read.return_value = b'data'

        with mock.patch('website.conferences.utils.requests.put') as mock_put:
            conferences_utils.upload_attachment(user, node, attachment)

        assert 'callback_log' not in _args(mock_put.call_args[0][0])

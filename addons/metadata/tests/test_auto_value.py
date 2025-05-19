import logging
import pytest
from addons.metadata.suggestion import suggestion_file_metadata_get_value
from osf_tests.factories import ProjectFactory
from osf_tests import factories
from tests.base import OsfTestCase
from addons.osfstorage.tests.utils import StorageTestCase
from addons.osfstorage.models import OsfStorageFileNode
from osf.models import (
    Session,
)
import itsdangerous
import os
import requests

import tempfile
import mock

from website import settings

logger = logging.getLogger(__name__)

@pytest.mark.django_db
class TestSuggestionFileMetadataAutoValue(StorageTestCase, OsfTestCase):
    def set_up(self):
        super(TestSuggestionFileMetadataAutoValue, self).set_up()
        self.mock_fetch_metadata_asset_files = mock.patch('addons.metadata.models.fetch_metadata_asset_files')
        self.mock_fetch_metadata_asset_files.start()
        self.work_dir = tempfile.mkdtemp()
        self.user = factories.AuthUserFactory()
        self.node = ProjectFactory(creator=self.user)
        self.osfstorage = self.node.get_addon('osfstorage')

    def test_txt_file(self):
        file_name = 'test_file.txt'
        self.file = OsfStorageFileNode.create(
            target=self.node,
            path='/testfile',
            _id=file_name,
            name=file_name,
            materialized_path='/testfile/test_file.txt',
        )

        self.file.save()
        assert self.file is not None
        assert OsfStorageFileNode.load(self.file._id)
        assert self.file.name == file_name
        self.session = Session(data={'auth_user_id': self.user._id})
        self.session.save()
        self.cookie = itsdangerous.Signer(settings.SECRET_KEY).sign(self.session._id)

        node_id = self.node._id
        file_id = self.file._id

        testpath = f'osfstorage/{self.file.name}'

        data = suggestion_file_metadata_get_value('auto-file-number-of-rows-text', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-number-of-rows-text'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-number-of-columns-text', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-number-of-columns-text'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-delimiter', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-delimiter'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-character-code', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-character-code'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-text/binary', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-text/binary'
        assert data[0]['error'] == ''

    def test_excel_file(self):
        file_name = 'test_file.xls'
        self.file = OsfStorageFileNode.create(
            target=self.node,
            path='/testfile',
            _id=file_name,
            name=file_name,
            materialized_path='/testfile',
        )

        self.file.save()
        assert self.file is not None
        assert OsfStorageFileNode.load(self.file._id)
        assert self.file.name == file_name
        self.session = Session(data={'auth_user_id': self.user._id})
        self.session.save()
        self.cookie = itsdangerous.Signer(settings.SECRET_KEY).sign(self.session._id)

        node_id = self.node._id
        file_id = self.file._id

        testpath = f'osfstorage/{self.file.name}'

        data = suggestion_file_metadata_get_value('auto-file-number-of-rows-excel', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-number-of-rows-excel'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-number-of-columns-excel', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-number-of-columns-excel'
        assert data[0]['error'] == ''

    def test_image_file(self):
        file_name = 'test_file.png'
        self.file = OsfStorageFileNode.create(
            target=self.node,
            path='/testfile',
            _id=file_name,
            name=file_name,
            materialized_path='/testfile',
        )

        self.file.save()
        assert self.file is not None
        assert OsfStorageFileNode.load(self.file._id)
        assert self.file.name == file_name
        self.session = Session(data={'auth_user_id': self.user._id})
        self.session.save()
        self.cookie = itsdangerous.Signer(settings.SECRET_KEY).sign(self.session._id)

        node_id = self.node._id
        file_id = self.file._id

        testpath = f'osfstorage/{self.file.name}'

        data = suggestion_file_metadata_get_value('auto-file-image-type', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-image-type'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-color-b&w', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-color-b&w'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-resolution', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-resolution'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-data-size', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-data-size'
        assert data[0]['error'] == ''

        data = suggestion_file_metadata_get_value('auto-file-text/binary', '', testpath, self.node)
        assert data[0]['key'] == 'auto-file-text/binary'
        assert data[0]['error'] == ''

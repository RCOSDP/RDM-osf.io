import pytest
from addons.base.utils import get_mfr_url, get_root_institutional_storage

from addons.osfstorage.tests.utils import StorageTestCase
from tests.base import OsfTestCase
from osf_tests.factories import ProjectFactory, UserFactory, RegionFactory, CommentFactory, AuthUserFactory
from website.settings import MFR_SERVER_URL

from tests.test_websitefiles import TestFolder, TestFile
from framework.exceptions import HTTPError
from unittest import mock

class MockFolder(dict, object):

    def __init__(self):
        self.name = 'Fake Folder'
        self.json = {'id': 'Fake Key', 'parent_id': 'cba321', 'name': 'Fake Folder'}
        self['data'] = {'name': 'Fake Folder', 'key': 'Fake Key', 'parentCollection': False}
        self['library'] = {'type': 'personal', 'id': '34241'}
        self['name'] = 'Fake Folder'
        self['id'] = 'Fake Key'


class MockLibrary(dict, object):

    def __init__(self):
        self.name = 'Fake Library'
        self.json = {'id': 'Fake Library Key', 'parent_id': 'cba321'}
        self['data'] = {'name': 'Fake Library', 'key': 'Fake Key', 'id': '12345' }
        self['name'] = 'Fake Library'
        self['id'] = 'Fake Library Key'


@pytest.mark.django_db
class TestAddonsBaseUtils(OsfTestCase):

    def setUp(self):
        super(TestAddonsBaseUtils, self).setUp()
        self.user = AuthUserFactory()
        self.node = ProjectFactory(creator=self.user)
        self.parent = TestFolder(
            _path='aparent',
            name='parent',
            target=self.node,
            provider='osf_storage',
            materialized_path='/long/path/to/name',
            is_root=True,
        )
        self.parent.save()
        self.file_child = TestFile(
            _path='afile',
            name='child',
            target=self.node,
            parent_id=self.parent.id,
            provider='osf_storage',
            materialized_path='/long/path/to/name',
        )
        self.file_child.save()

    def test_mfr_url(self):
        user = UserFactory()
        project = ProjectFactory(creator=user)
        comment = CommentFactory()
        assert get_mfr_url(project, 'github') == MFR_SERVER_URL
        assert get_mfr_url(project, 'osfstorage') == project.osfstorage_region.mfr_url
        assert get_mfr_url(comment, 'osfstorage') == MFR_SERVER_URL

    def test_get_root_institutional_storage_exception(self):
        with pytest.raises(HTTPError):
            get_root_institutional_storage(self.file_child.id)

    def test_get_root_institutional_storage(self):
        with mock.patch('osf.models.files.BaseFileNode.objects.get', side_effect=[self.file_child, self.parent]):
            res = get_root_institutional_storage(self.file_child.id)
            assert res.name == self.parent.name
            assert res.target == self.parent.target

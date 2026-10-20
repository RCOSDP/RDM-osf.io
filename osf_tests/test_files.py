import datetime

import pytest
from django.utils import timezone

from django.contrib.contenttypes.models import ContentType

from addons.osfstorage.models import NodeSettings
from addons.osfstorage import settings as osfstorage_settings
from osf.models import BaseFileNode, Folder, File
from osf_tests.factories import (
    UserFactory,
    ProjectFactory,
    RegionFactory,
    FileVersionFactory,
)

pytestmark = pytest.mark.django_db

@pytest.fixture()
def user():
    return UserFactory()

@pytest.fixture()
def project(user):
    return ProjectFactory(creator=user)


@pytest.fixture()
def create_test_file(fake):
    # TODO: Copied from api_tests/utils.py. DRY this up.
    def _create_test_file(target, user=None, filename=None, create_guid=True):
        filename = filename or fake.file_name()
        user = user or target.creator
        osfstorage = target.get_addon('osfstorage')
        root_node = osfstorage.get_root()
        test_file = root_node.append_file(filename)

        if create_guid:
            test_file.get_guid(create=True)

        test_file.create_version(user, {
            'object': '06d80e',
            'service': 'cloud',
            osfstorage_settings.WATERBUTLER_RESOURCE: 'osf',
        }, {
            'size': 1337,
            'contentType': 'img/png'
        }).save()
        return test_file
    return _create_test_file


def test_active_manager_does_not_return_trashed_file_nodes(project, create_test_file):
    create_test_file(target=project)
    deleted_file = create_test_file(target=project)
    deleted_file.delete(user=project.creator, save=True)
    content_type_for_query = ContentType.objects.get_for_model(project)
    # root folder + file + deleted_file = 3 BaseFileNodes
    assert BaseFileNode.objects.filter(target_object_id=project.id, target_content_type=content_type_for_query).count() == 3
    # root folder + file = 2 BaseFileNodes
    assert BaseFileNode.active.filter(target_object_id=project.id, target_content_type=content_type_for_query).count() == 2

def test_folder_update_calls_folder_update_method(project, create_test_file):
    file = create_test_file(target=project)
    parent_folder = file.parent
    # the folder update method should be the Folder.update method
    assert parent_folder.__class__.update == Folder.update
    # the folder update method should not be the File update method
    assert parent_folder.__class__.update != File.update
    # the file update method should be the File update method
    assert file.__class__.update == File.update


def test_file_update_respects_region(project, user, create_test_file):
    test_file = create_test_file(target=project)
    version = test_file.versions.first()
    original_region = project.osfstorage_region
    assert version.region == original_region

    # update the region on the project, ensure the new version has the new region
    node_settings = NodeSettings.objects.get(owner=project.id)
    new_region = RegionFactory()
    node_settings.region = new_region
    node_settings.save()
    test_file.save()

    new_version = test_file.create_version(
        user, {
            'service': 'cloud',
            osfstorage_settings.WATERBUTLER_RESOURCE: 'osf',
            'object': '07d80a',
        }, {
            'sha256': 'existing',
        }
    )
    assert new_region != original_region
    assert new_version.region == new_region


def test_file_serialize_no_versions(project):
    from addons.googledrive.models import GoogleDriveFile

    # GoogleDriveFile uses File.serialize directly (no override)
    gd_file = GoogleDriveFile(name='empty.txt', target=project)
    gd_file.save()

    result = gd_file.serialize()

    # newest_version is None → all version-derived fields are None
    assert result['size'] is None
    assert result['version'] is None
    assert result['modified'] is None
    assert result['created'] is None
    assert result['contentType'] is None


def test_file_serialize_newest_version(project):
    from addons.googledrive.models import GoogleDriveFile

    # GoogleDriveFile uses File.serialize directly (no override)
    gd_file = GoogleDriveFile(name='multi_version.txt', target=project)
    gd_file.save()

    # Create v1 first (older DB timestamp), smaller size
    older_time = timezone.now() - datetime.timedelta(days=1)
    v1 = FileVersionFactory(identifier='1', size=1000)
    v1.external_modified = older_time
    v1.save()
    gd_file.add_version(v1)

    # Create v2 second (newer DB timestamp), larger size
    newer_time = timezone.now()
    v2 = FileVersionFactory(identifier='2', size=5000)
    v2.external_modified = newer_time
    v2.save()
    gd_file.add_version(v2)

    result = gd_file.serialize()

    # newest_version = versions.all().first() ordered by -created → v2
    assert result['size'] == 5000
    assert result['version'] == '2'
    assert result['modified'] == newer_time.isoformat()
    # created comes from oldest_version (versions.all().last()) → v1
    assert result['created'] == older_time.isoformat()

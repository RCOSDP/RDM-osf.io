import pytest
from unittest import mock
from website.util import quota
from django.db import IntegrityError

@pytest.fixture
def mock_user():
    user = mock.Mock()
    user.id = 1
    user._id = 'abc123'
    user.userquota_set.get.side_effect = quota.UserQuota.DoesNotExist
    return user

@pytest.fixture
def mock_node():
    node = mock.Mock(spec=quota.AbstractNode)
    node.id = 42
    node.creator = mock.Mock()
    node.type = 'osf.node'
    return node

def test_get_file_size_file():
    children = {'children': [{'kind': 'file', 'size': 100}, {'kind': 'file', 'size': 200}]}
    assert quota.get_file_size(children) == 300

def test_get_file_size_nested():
    children = {
        'children': [
            {'kind': 'file', 'size': 100},
            {'kind': 'folder', 'children': [{'kind': 'file', 'size': 50}]}
        ]
    }
    assert quota.get_file_size(children) == 150

@mock.patch('website.util.quota.ProjectStorageType.objects.get')
@mock.patch('website.util.quota.AbstractNode.objects.get')
@mock.patch('website.util.quota.update_quota')
def test_handle_move_copy_dest_osfstorage(mock_update_quota, mock_node_get, mock_pst_get, mock_node):
    # Mock ProjectStorageType.objects.get to return a mock with storage_type
    mock_pst_get.return_value = mock.Mock(storage_type=1)
    # Mock AbstractNode.objects.get to return a mock node
    mock_node_get.return_value = mock_node

    payload = {
        'destination': {'provider': 's3compatinstitutions', 'size': 123, 'children': None},
        'source': {'nid': 'nid1', 'provider': 'osfstorage'}
    }
    quota._handle_move_copy(quota.FileLog.FILE_MOVED, mock_node, mock.Mock(), payload)
    mock_update_quota.assert_called_once()

@mock.patch('website.util.quota.ProjectStorageType.objects.get')
@mock.patch('website.util.quota.AbstractNode.objects.get')
@mock.patch('website.util.quota.update_quota')
@pytest.mark.django_db
def test_handle_move_copy_source_osfstorage(mock_update_quota, mock_node_get, mock_pst_get, mock_user):
    mock_node = mock.create_autospec(quota.AbstractNode, instance=True)
    mock_node.type = 'osf.node'
    mock_pst_get.return_value = mock.Mock(storage_type=1)
    mock_node_get.return_value = mock_node

    payload = {
        'destination': {'provider': 's3compatinstitutions', 'size': 123},  # <-- thêm size
        'source': {'provider': 'osfstorage', 'size': 123, 'nid': 'nid1'}
    }
    quota._handle_move_copy(quota.FileLog.FILE_MOVED, mock_node, mock_user, payload)
    mock_update_quota.assert_called_once()

@mock.patch('website.util.quota.update_quota')
@pytest.mark.django_db
def test_handle_move_copy_no_osfstorage(mock_update_quota, mock_node, mock_user):
    payload = {
        'destination': {'provider': 's3compatinstitutions'},
        'source': {'provider': 's3compatinstitutions'}
    }
    quota._handle_move_copy(quota.FileLog.FILE_MOVED, mock_node, mock_user, payload)
    mock_update_quota.assert_not_called()

@mock.patch('website.util.quota.ProjectStorageType.objects.get')
@mock.patch('website.util.quota.AbstractNode.objects.get')
@mock.patch('website.util.quota.update_quota')
@pytest.mark.django_db
def test_file_moved_file(mock_update_quota, mock_node_get, mock_pst_get, mock_node):
    mock_pst_get.return_value = mock.Mock(storage_type=1)
    mock_node_get.return_value = mock_node
    payload = {
        'destination': {'size': 123, 'children': None},
        'source': {'nid': 'nid1', 'provider': 'osfstorage'}
    }
    quota.file_moved(mock_node, payload)
    mock_update_quota.assert_called_once()

@mock.patch('website.util.quota.ProjectStorageType.objects.get')
@mock.patch('website.util.quota.AbstractNode.objects.get')
@mock.patch('website.util.quota.update_quota')
@pytest.mark.django_db
def test_file_moved_folder(mock_update_quota, mock_node_get, mock_pst_get, mock_node):
    mock_pst_get.return_value = mock.Mock(storage_type=1)
    mock_node_get.return_value = mock_node
    payload = {
        'destination': {'children': [{'kind': 'file', 'size': 100}]},
        'source': {'nid': 'nid1', 'provider': 'osfstorage'}
    }
    quota.file_moved(mock_node, payload)
    mock_update_quota.assert_called_once()

@mock.patch('website.util.quota.ProjectStorageType.objects.get', side_effect=Exception)
@mock.patch('website.util.quota.AbstractNode.objects.get')
@mock.patch('website.util.quota.update_quota')
@pytest.mark.django_db
def test_file_moved_exception(mock_update_quota, mock_node_get, mock_pst_get, mock_node):
    mock_node_get.return_value = mock_node
    payload = {
        'destination': {'size': 123, 'children': None},
        'source': {'nid': 'nid1', 'provider': 'osfstorage'}
    }
    with pytest.raises(Exception):
        quota.file_moved(mock_node, payload)
    mock_update_quota.assert_not_called()

@mock.patch('website.util.quota.UserQuota.objects.get')
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_add(mock_filter, mock_get, mock_node):
    uq = mock.Mock()
    uq.used = 0
    mock_get.return_value = uq
    mock_filter.return_value.select_for_update.return_value.get.return_value = uq
    quota.update_quota(mock_node, 100, 1, add=True)
    assert uq.used == 100

@mock.patch('website.util.quota.UserQuota.objects.get')
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_subtract(mock_filter, mock_get, mock_node):
    uq = mock.Mock()
    uq.used = 200
    mock_get.return_value = uq
    mock_filter.return_value.select_for_update.return_value.get.return_value = uq
    quota.update_quota(mock_node, 50, 1, add=False)
    assert uq.used == 150

@mock.patch('website.util.quota.check_select_for_update', return_value=False)
@mock.patch('website.util.quota.transaction.atomic')
@mock.patch('website.util.quota.UserQuota.objects.create')
@mock.patch('website.util.quota.UserQuota.objects.filter')
@mock.patch('website.util.quota.UserQuota.objects.get', side_effect=quota.UserQuota.DoesNotExist)
@pytest.mark.django_db
def test_update_quota_userquota_not_exist(mock_get, mock_filter, mock_create, mock_atomic, mock_node):
    mock_filter.return_value.select_for_update.return_value.get.side_effect = quota.UserQuota.DoesNotExist
    quota.update_quota(mock_node, 50, 1, add=True)
    mock_get.assert_called_once()

@mock.patch('website.util.quota.UserQuota.objects.get', side_effect=Exception)
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_other_exception(mock_filter, mock_get, mock_node):
    mock_filter.return_value.select_for_update.return_value.get.side_effect = Exception
    with pytest.raises(Exception):
        quota.update_quota(mock_node, 50, 1, add=True)
    mock_get.assert_not_called()

@mock.patch('website.util.quota._handle_move_copy')
def test_update_used_quota_move_event(mock_handle_move_copy, mock_node, mock_user):
    payload = {
        'destination': {'provider': 's3compatinstitutions'},
        'source': {'provider': 'osfstorage'}
    }
    quota.update_used_quota(None, mock_node, mock_user, quota.FileLog.FILE_MOVED, payload)
    mock_handle_move_copy.assert_called_once()

@mock.patch('website.util.quota._handle_move_copy')
def test_update_used_quota_dest_osfstorage_returns_early(mock_handle_move_copy, mock_node, mock_user):
    payload = {
        'destination': {'provider': 'osfstorage'}
    }
    result = quota.update_used_quota(None, mock_node, mock_user, quota.FileLog.FILE_MOVED, payload)
    assert result is None
    mock_handle_move_copy.assert_not_called()

@mock.patch('website.util.quota.check_select_for_update', return_value=True)
@mock.patch('website.util.quota.transaction.atomic')
@mock.patch('website.util.quota.UserQuota.objects.create', side_effect=IntegrityError)
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_integrityerror_select_for_update_add(
    mock_filter, mock_create, mock_atomic, mock_check, mock_node
):
    uq = mock.Mock()
    uq.used = 10
    mock_filter.return_value.select_for_update.return_value.get.side_effect = [
        quota.UserQuota.DoesNotExist,
        uq
    ]
    quota.update_quota(mock_node, 5, 1, add=True)
    assert mock_filter.return_value.select_for_update.return_value.get.call_count == 2
    assert uq.used == 15
    uq.save.assert_called_once()

@mock.patch('website.util.quota.check_select_for_update', return_value=True)
@mock.patch('website.util.quota.transaction.atomic')
@mock.patch('website.util.quota.UserQuota.objects.create', side_effect=IntegrityError)
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_integrityerror_select_for_update_subtract(
    mock_filter, mock_create, mock_atomic, mock_check, mock_node
):
    uq = mock.Mock()
    uq.used = 10
    mock_filter.return_value.select_for_update.return_value.get.side_effect = [
        quota.UserQuota.DoesNotExist,
        uq
    ]
    quota.update_quota(mock_node, 3, 1, add=False)
    assert mock_filter.return_value.select_for_update.return_value.get.call_count == 2
    assert uq.used == 7
    uq.save.assert_called_once()

@mock.patch('website.util.quota.check_select_for_update', return_value=False)
@mock.patch('website.util.quota.transaction.atomic')
@mock.patch('website.util.quota.UserQuota.objects.create', side_effect=IntegrityError)
@mock.patch('website.util.quota.UserQuota.objects.get')
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_integrityerror_get_add(
    mock_filter, mock_get, mock_create, mock_atomic, mock_check, mock_node
):
    uq = mock.Mock()
    uq.used = 20
    mock_get.side_effect = [quota.UserQuota.DoesNotExist, uq]
    quota.update_quota(mock_node, 8, 1, add=True)
    assert uq.used == 28
    uq.save.assert_called_once()

@mock.patch('website.util.quota.check_select_for_update', return_value=False)
@mock.patch('website.util.quota.transaction.atomic')
@mock.patch('website.util.quota.UserQuota.objects.create', side_effect=IntegrityError)
@mock.patch('website.util.quota.UserQuota.objects.get')
@mock.patch('website.util.quota.UserQuota.objects.filter')
@pytest.mark.django_db
def test_update_quota_integrityerror_get_subtract(
    mock_filter, mock_get, mock_create, mock_atomic, mock_check, mock_node
):
    uq = mock.Mock()
    uq.used = 30
    mock_get.side_effect = [quota.UserQuota.DoesNotExist, uq]
    quota.update_quota(mock_node, 12, 1, add=False)
    assert uq.used == 18
    uq.save.assert_called_once()

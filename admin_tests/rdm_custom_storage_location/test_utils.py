import mock
import pytest
from nose import tools as nt

from addons.osfstorage.models import Region
from admin.rdm_custom_storage_location.utils import get_providers, save_s3compatb3_credentials, wd_info_for_institutions
from rest_framework import status as http_status
from admin.rdm_custom_storage_location.utils import update_nodes_storage


@pytest.mark.feature_202210
class TestUtils:
    def test_get_providers(self):
        provider_list = get_providers()
        assert provider_list
        provider_list_short_name = [p.short_name for p in provider_list]
        nt.assert_in('s3', provider_list_short_name, 's3')
        nt.assert_in('dropboxbusiness', provider_list_short_name, 'dropboxbusiness')
        nt.assert_in('nextcloudinstitutions', provider_list_short_name, 'nextcloudinstitutions')
        nt.assert_in('osfstorage', provider_list_short_name, 'osfstorage')
        nt.assert_in('onedrivebusiness', provider_list_short_name, 'onedrivebusiness')
        nt.assert_in('swift', provider_list_short_name, 'swift')
        nt.assert_in('ociinstitutions', provider_list_short_name, 'ociinstitutions')
        nt.assert_in('s3compat', provider_list_short_name, 's3compat')
        nt.assert_in('s3compatinstitutions', provider_list_short_name, 's3compatinstitutions')

        provider_list = get_providers(available_list=[])
        nt.assert_equal(len(provider_list), 0)

        available_list = ['s3', 's3compat']
        provider_list = get_providers(available_list=available_list)
        provider_list_short_name = [p.short_name for p in provider_list]
        nt.assert_list_equal(provider_list_short_name, available_list)

    @mock.patch('osf.utils.external_util.remove_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.update_storage')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_s3compatb3_connection')
    def test_save_s3compatb3_credentials(self, mock_testconnection, mock_update_storage, mock_remove_region_external_account):
        mock_testconnection.return_value = {'message': 'Nice'}, http_status.HTTP_200_OK
        mock_update_storage.return_value = {}
        mock_remove_region_external_account.return_value = None
        response, status = save_s3compatb3_credentials('guid_test', 'My storage', 's3.compat.co.jp', 'Non-empty-access-key', 'Non-empty-secret-key', 'Cute bucket')
        nt.assert_equal(response, {'message': 'Saved credentials successfully!!'})
        nt.assert_equal(status, http_status.HTTP_200_OK)

    def test_wd_info_for_institutions(self):
        for_institution_providers = [
            's3compatinstitutions',
            'nextcloudinstitutions',
            'ociinstitutions',
            'dropboxbusiness',
            'onedrivebusiness',
        ]
        test_wd_credentials = {
            'storage': {
            },
        }
        for provider_name in for_institution_providers:
            wd_credentials, wd_settings = wd_info_for_institutions(provider_name)
            test_wb_settings = {
                'disabled': True,
                'storage': {
                    'provider': provider_name,
                    'type': Region.INSTITUTIONS,
                },
            }
            if provider_name == 's3compatinstitutions':
                test_wb_settings['encrypt_uploads'] = False
            nt.assert_equal(wd_credentials, test_wd_credentials)
            nt.assert_equal(wd_settings, test_wb_settings)



class TestUpdateNodesStorage:
    @mock.patch('admin.rdm_custom_storage_location.utils.Node')
    @mock.patch('admin.rdm_custom_storage_location.utils.ProjectStorageType')
    @mock.patch('admin.rdm_custom_storage_location.utils.update_node_storage')
    @mock.patch('admin.rdm_custom_storage_location.utils.OSFUser')
    @mock.patch('admin.rdm_custom_storage_location.utils.update_user_used_quota')
    def test_update_nodes_storage(
        self,
        mock_update_user_used_quota,
        mock_OSFUser,
        mock_update_node_storage,
        mock_ProjectStorageType,
        mock_Node
    ):
        # Setup mocks
        institution = mock.Mock()
        institution.id = 'inst_id'
        mock_node1 = mock.Mock()
        mock_node2 = mock.Mock()
        mock_Node.objects.filter.return_value = [mock_node1, mock_node2]

        mock_storage_type_qs = mock.Mock()
        mock_ProjectStorageType.objects.filter.return_value = mock_storage_type_qs

        mock_user1 = mock.Mock()
        mock_user2 = mock.Mock()
        mock_OSFUser.objects.filter.return_value = [mock_user1, mock_user2]

        # Call function
        mock_user = mock.Mock()
        update_nodes_storage(institution, mock_user)

        # Assert update_node_storage called for each node
        assert mock_update_node_storage.call_count == 2
        mock_update_node_storage.assert_any_call(mock_node1, mock_user)
        mock_update_node_storage.assert_any_call(mock_node2, mock_user)

        # Assert ProjectStorageType.objects.filter called for each node
        assert mock_ProjectStorageType.objects.filter.call_count == 2
        mock_ProjectStorageType.objects.filter.assert_any_call(node=mock_node1)
        mock_ProjectStorageType.objects.filter.assert_any_call(node=mock_node2)

        # Assert update called on storage_type queryset
        assert mock_storage_type_qs.update.call_count == 2

        # Assert update_user_used_quota called for each user
        assert mock_update_user_used_quota.call_count == 2
        mock_update_user_used_quota.assert_any_call(mock_user1, storage_type=mock.ANY, is_recalculating_quota=True)
        mock_update_user_used_quota.assert_any_call(mock_user2, storage_type=mock.ANY, is_recalculating_quota=True)
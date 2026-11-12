import mock
import pytest
from nose import tools as nt

from addons.osfstorage.models import Region
from admin.rdm_custom_storage_location.utils import (
    get_providers,
    add_node_settings_to_projects,
    save_s3compatb3_credentials,
    save_s3compatsigv4_credentials,
    wd_info_for_institutions,
    create_storage_info_template,
    get_osfstorage_info,
    get_institution_addon_info,
    get_s3_info,
    get_s3compat_info,
    get_s3compatsigv4_info,
    get_s3compatinstitutions_info,
    get_ociinstitutions_info,
    get_nextcloudinstitutions_info,
    get_dropboxbusiness_info,
    get_institutional_storage_information,
    is_institution_using_nii_storage,
    upsert_user_quota_for_institution,
)
from mock import patch, MagicMock
from osf_tests.factories import (
    InstitutionFactory,
    ProjectFactory,
    RegionFactory,
    UserFactory,
    bulkmount_waterbutler_settings,
    addon_waterbutler_settings,
    AuthUserFactory
)
from tests.base import AdminTestCase
from api.base import settings as api_settings
from osf.models import UserQuota
from osf.models.institution_default_max_quota import InstitutionDefaultMaxQuota
from rest_framework import status as http_status


@pytest.mark.feature_202210
@pytest.mark.django_db
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
        nt.assert_in('s3compatsigv4', provider_list_short_name, 's3compatsigv4')
        nt.assert_in('s3compatinstitutions', provider_list_short_name, 's3compatinstitutions')

        provider_list = get_providers(available_list=[])
        nt.assert_equal(len(provider_list), 0)

        available_list = ['s3', 's3compat', 's3compatsigv4']
        provider_list = get_providers(available_list=available_list)
        provider_list_short_name = [p.short_name for p in provider_list]
        nt.assert_list_equal(provider_list_short_name, available_list)

    @patch('osf.utils.external_util.remove_region_external_account')
    @patch('admin.rdm_custom_storage_location.utils.update_storage')
    @patch('admin.rdm_custom_storage_location.utils.test_s3compatb3_connection')
    def test_save_s3compatb3_credentials(self,
                                         mock_testconnection, mock_update_storage,
                                         mock_remove_region_external_account):
        mock_testconnection.return_value = {'message': 'Nice'}, http_status.HTTP_200_OK
        mock_update_storage.return_value = {}
        mock_remove_region_external_account.return_value = None
        response, status = save_s3compatb3_credentials('guid_test', 'My storage', 's3.compat.co.jp',
                                                       'Non-empty-access-key', 'Non-empty-secret-key', 'Cute bucket')
        nt.assert_equal(response, {'message': 'Saved credentials successfully!!'})
        nt.assert_equal(status, http_status.HTTP_200_OK)

    @patch('osf.utils.external_util.remove_region_external_account')
    @patch('admin.rdm_custom_storage_location.utils.update_storage')
    @patch('admin.rdm_custom_storage_location.utils.test_s3compatsigv4_connection')
    def test_save_s3compatsigv4_credentials(self,
                                         mock_testconnection, mock_update_storage,
                                         mock_remove_region_external_account):
        mock_testconnection.return_value = {'message': 'Nice'}, http_status.HTTP_200_OK
        mock_update_storage.return_value = {}
        mock_remove_region_external_account.return_value = None
        response, status = save_s3compatsigv4_credentials('guid_test', 'My storage', 's3.compat.co.jp',
                                                       'Non-empty-access-key', 'Non-empty-secret-key', 'Cute bucket')
        nt.assert_equal(response, {'message': 'Saved credentials successfully!!'})
        nt.assert_equal(status, http_status.HTTP_200_OK)

    @patch('osf.utils.external_util.remove_region_external_account')
    @patch('admin.rdm_custom_storage_location.utils.update_storage')
    @patch('admin.rdm_custom_storage_location.utils.test_s3compatsigv4_connection')
    def test_save_s3compatsigv4_credentials_with_region(self,
                                         mock_testconnection, mock_update_storage,
                                         mock_remove_region_external_account):
        mock_testconnection.return_value = {'message': 'Nice'}, http_status.HTTP_200_OK
        mock_update_storage.return_value = {}
        mock_remove_region_external_account.return_value = None
        response, status = save_s3compatsigv4_credentials('guid_test', 'My storage', 's3.compat.co.jp',
                                                       'Non-empty-access-key', 'Non-empty-secret-key', 'Cute bucket',
                                                       region='us-east-1')
        nt.assert_equal(response, {'message': 'Saved credentials successfully!!'})
        nt.assert_equal(status, http_status.HTTP_200_OK)
        # Verify region is included in wb_settings
        call_args = mock_update_storage.call_args
        wb_settings = call_args[0][3]  # 4th positional arg
        nt.assert_in('region', wb_settings['storage'])
        nt.assert_equal(wb_settings['storage']['region'], 'us-east-1')

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

    def test_add_node_settings_to_projects_bulk_mount_storage(self):
        user = AuthUserFactory()
        project = ProjectFactory(creator=user)
        region = RegionFactory(waterbutler_settings=bulkmount_waterbutler_settings)
        institution = InstitutionFactory.create(_id=region.guid)
        institution.nodes.set([project])
        user.affiliated_institutions.add(institution)

        mock_dropboxbusiness_post_save = MagicMock()
        mock_onedrivebusiness_post_save = MagicMock()
        mock_node_post_save = MagicMock()
        with patch('admin.rdm_custom_storage_location.utils.dropboxbusiness_post_save', mock_dropboxbusiness_post_save):
            with patch('admin.rdm_custom_storage_location.utils.onedrivebusiness_post_save',
                       mock_onedrivebusiness_post_save):
                with patch('admin.rdm_custom_storage_location.utils.node_post_save', mock_node_post_save):
                    add_node_settings_to_projects(institution, 'osfstorage')
                    mock_dropboxbusiness_post_save.assert_not_called()
                    mock_onedrivebusiness_post_save.assert_not_called()
                    mock_node_post_save.assert_not_called()

    def test_add_node_settings_to_projects_dropboxbusiness(self):
        user = AuthUserFactory()
        project = ProjectFactory(creator=user)
        region = RegionFactory(waterbutler_settings=addon_waterbutler_settings)
        institution = InstitutionFactory.create(_id=region.guid)
        institution.nodes.set([project])
        user.affiliated_institutions.add(institution)

        mock_dropboxbusiness_post_save = MagicMock()
        mock_onedrivebusiness_post_save = MagicMock()
        mock_node_post_save = MagicMock()
        with patch('admin.rdm_custom_storage_location.utils.dropboxbusiness_post_save', mock_dropboxbusiness_post_save):
            with patch('admin.rdm_custom_storage_location.utils.onedrivebusiness_post_save',
                       mock_onedrivebusiness_post_save):
                with patch('admin.rdm_custom_storage_location.utils.node_post_save', mock_node_post_save):
                    add_node_settings_to_projects(institution, 'dropboxbusiness')
                    mock_dropboxbusiness_post_save.assert_called()
                    mock_onedrivebusiness_post_save.assert_not_called()
                    mock_node_post_save.assert_not_called()

    def test_add_node_settings_to_projects_onedrivebusiness(self):
        user = AuthUserFactory()
        project = ProjectFactory(creator=user)
        project.add_addon('onedrivebusiness', None)
        project.save()
        region = RegionFactory(waterbutler_settings=addon_waterbutler_settings)
        institution = InstitutionFactory.create(_id=region.guid)
        institution.nodes.set([project])
        user.affiliated_institutions.add(institution)

        mock_dropboxbusiness_post_save = MagicMock()
        mock_onedrivebusiness_post_save = MagicMock()
        mock_node_post_save = MagicMock()
        with patch('admin.rdm_custom_storage_location.utils.dropboxbusiness_post_save', mock_dropboxbusiness_post_save):
            with patch('admin.rdm_custom_storage_location.utils.onedrivebusiness_post_save',
                       mock_onedrivebusiness_post_save):
                with patch('admin.rdm_custom_storage_location.utils.node_post_save', mock_node_post_save):
                    add_node_settings_to_projects(institution, 'onedrivebusiness')
                    mock_dropboxbusiness_post_save.assert_not_called()
                    mock_onedrivebusiness_post_save.assert_called()
                    mock_node_post_save.assert_not_called()

    def test_add_node_settings_to_projects_other_add_on_storage(self):
        user = AuthUserFactory()
        project = ProjectFactory(creator=user)
        region = RegionFactory(waterbutler_settings=addon_waterbutler_settings)
        institution = InstitutionFactory.create(_id=region.guid)
        institution.nodes.set([project])
        user.affiliated_institutions.add(institution)

        mock_dropboxbusiness_post_save = MagicMock()
        mock_onedrivebusiness_post_save = MagicMock()
        mock_node_post_save = MagicMock()
        with patch('admin.rdm_custom_storage_location.utils.dropboxbusiness_post_save', mock_dropboxbusiness_post_save):
            with patch('admin.rdm_custom_storage_location.utils.onedrivebusiness_post_save',
                       mock_onedrivebusiness_post_save):
                with patch('admin.rdm_custom_storage_location.utils.node_post_save', mock_node_post_save):
                    add_node_settings_to_projects(institution, 'nextcloudinstitutions')
                    mock_dropboxbusiness_post_save.assert_not_called()
                    mock_onedrivebusiness_post_save.assert_not_called()
                    mock_node_post_save.assert_called()


class TestStorageInformationUtils(AdminTestCase):
    def setUp(self):
        # Create mock objects
        self.mock_institution = mock.Mock()
        self.mock_institution.id = 'test_institution_id'

        self.mock_external_account = mock.Mock()
        self.mock_external_account.profile_url = 'https://test.com'
        self.mock_external_account.display_name = 'test_display_name'
        self.mock_external_account.oauth_key = 'test_oauth_key'

        self.mock_rdm_addon_option = mock.Mock()
        self.mock_rdm_addon_option.external_accounts.first.return_value = self.mock_external_account
        self.mock_rdm_addon_option.extended = {
            'base_folder': 'test_folder',
            'notification_secret': 'test_secret',
            'team_folder_id': 'test_team_folder'
        }

    def test_create_storage_info_template(self):
        """Test create_storage_info_template function"""
        result = create_storage_info_template('Test Title', 'Test Value')
        expected = {'field_name': 'Test Title', 'value': 'Test Value'}
        nt.assert_equal(result, expected)

    @mock.patch('admin.rdm_custom_storage_location.utils.get_rdm_addon_option')
    def test_get_institution_addon_info(self, mock_get_rdm_addon_option):
        """Test get_institution_addon_info function"""
        mock_get_rdm_addon_option.return_value = self.mock_rdm_addon_option

        rdm_addon_option, external_account = get_institution_addon_info(
            'test_institution_id', 'test_provider'
        )

        nt.assert_equal(external_account, self.mock_external_account)
        nt.assert_equal(rdm_addon_option, self.mock_rdm_addon_option)
        mock_get_rdm_addon_option.assert_called_once_with(
            'test_institution_id', 'test_provider', create=False
        )

    def test_get_osfstorage_info(self):
        """Test get_osfstorage_info function"""
        wb_settings = {'folder': 'test_folder'}
        result = get_osfstorage_info(wb_settings)

        expected = {
            'folder': {'field_name': 'Folder', 'value': 'test_folder'}
        }
        nt.assert_equal(result, expected)

    def test_get_s3_info(self):
        """Test get_s3_info function"""
        wb_credentials = {'access_key': 'test_key'}
        wb_settings = {
            'bucket': 'test_bucket',
            'encrypt_uploads': True
        }

        result = get_s3_info(wb_credentials, wb_settings)

        expected = {
            'access_key': {'field_name': 'Access Key', 'value': 'test_key'},
            'bucket': {'field_name': 'Bucket', 'value': 'test_bucket'},
            'encrypt_uploads': {'field_name': 'Enable Server Side Encryption', 'value': True}
        }
        nt.assert_equal(result, expected)

    def test_get_s3compat_info(self):
        """Test get_s3compat_info function"""
        wb_credentials = {
            'host': 'test_host',
            'access_key': 'test_key'
        }
        wb_settings = {
            'bucket': 'test_bucket',
            'encrypt_uploads': True
        }

        result = get_s3compat_info(wb_credentials, wb_settings)

        expected = {
            'host': {'field_name': 'Endpoint URL', 'value': 'test_host'},
            'access_key': {'field_name': 'Access Key', 'value': 'test_key'},
            'bucket': {'field_name': 'Bucket', 'value': 'test_bucket'},
            'encrypt_uploads': {'field_name': 'Enable Server Side Encryption', 'value': True}
        }
        nt.assert_equal(result, expected)

    def test_get_s3compatsigv4_info(self):
        """Test get_s3compatsigv4_info function"""
        wb_credentials = {
            'host': 'test_host',
            'access_key': 'test_key',
            'secret_key': 'test_secret'
        }
        wb_settings = {
            'bucket': 'test_bucket',
            'encrypt_uploads': True
        }

        result = get_s3compatsigv4_info(wb_credentials, wb_settings)

        expected = {
            'host': {'field_name': 'Endpoint URL', 'value': 'test_host'},
            'access_key': {'field_name': 'Access Key', 'value': 'test_key'},
            'bucket': {'field_name': 'Bucket', 'value': 'test_bucket'},
            'encrypt_uploads': {'field_name': 'Enable Server Side Encryption', 'value': True}
        }
        nt.assert_equal(result, expected)

    @mock.patch('admin.rdm_custom_storage_location.utils.get_institution_addon_info')
    def test_get_s3compatinstitutions_info(self, mock_get_institution_addon_info):
        """Test get_s3compatinstitutions_info function"""
        mock_get_institution_addon_info.return_value = (self.mock_rdm_addon_option, self.mock_external_account)
        mock_region = mock.Mock()
        mock_region.waterbutler_settings = {'encrypt_uploads': True}

        result = get_s3compatinstitutions_info(
            self.mock_institution, 'test_provider', mock_region
        )

        expected = {
            'host': {'field_name': 'Endpoint URL', 'value': 'https://test.com'},
            'access_key': {'field_name': 'Access Key', 'value': 'test_display_name'},
            'bucket': {'field_name': 'Bucket', 'value': 'test_folder'},
            'encrypt_uploads': {'field_name': 'Enable Server Side Encryption', 'value': True}
        }
        nt.assert_equal(result, expected)

    @mock.patch('admin.rdm_custom_storage_location.utils.get_institution_addon_info')
    def test_get_ociinstitutions_info(self, mock_get_institution_addon_info):
        """Test get_ociinstitutions_info function"""
        mock_get_institution_addon_info.return_value = (self.mock_rdm_addon_option, self.mock_external_account)

        result = get_ociinstitutions_info(self.mock_institution, 'test_provider')

        expected = {
            'host': {'field_name': 'Endpoint URL', 'value': 'https://test.com'},
            'access_key': {'field_name': 'Access Key', 'value': 'test_display_name'},
            'bucket': {'field_name': 'Bucket', 'value': 'test_folder'}
        }
        nt.assert_equal(result, expected)

    @mock.patch('admin.rdm_custom_storage_location.utils.get_institution_addon_info')
    def test_get_nextcloudinstitutions_info(self, mock_get_institution_addon_info):
        """Test get_nextcloudinstitutions_info function"""
        mock_get_institution_addon_info.return_value = (self.mock_rdm_addon_option, self.mock_external_account)

        result = get_nextcloudinstitutions_info(self.mock_institution, 'test_provider')

        expected = {
            'host': {'field_name': 'Host URL', 'value': 'https://test.com'},
            'username': {'field_name': 'Username', 'value': 'test_display_name'},
            'folder': {'field_name': 'Folder', 'value': 'test_folder'},
            'notification_secret': {
                'field_name': 'Connection common key from File Upload Notification App',
                'value': 'test_secret'
            }
        }
        nt.assert_equal(result, expected)

    @mock.patch('admin.rdm_custom_storage_location.utils.get_institution_addon_info')
    def test_get_dropboxbusiness_info(self, mock_get_institution_addon_info):
        """Test get_dropboxbusiness_info function"""
        mock_get_institution_addon_info.return_value = (self.mock_rdm_addon_option, self.mock_external_account)

        result = get_dropboxbusiness_info(self.mock_institution, 'test_provider')

        expected = {
            'authorized_by': {'field_name': 'authorized_by', 'value': 'test_display_name'},
        }
        nt.assert_equal(result, expected)

    def test_get_institutional_storage_information(self):
        """Test get_institutional_storage_information function"""
        region = RegionFactory()
        region.waterbutler_credentials = {
            'storage': {
                'access_key': 'test_key'
            }
        }
        region.waterbutler_settings = {
            'storage': {
                'bucket': 'test_bucket',
                'encrypt_uploads': True
            }
        }
        region.save()

        result = get_institutional_storage_information(
            's3', region, InstitutionFactory()
        )

        expected = {
            'access_key': {'field_name': 'Access Key', 'value': 'test_key'},
            'bucket': {'field_name': 'Bucket', 'value': 'test_bucket'},
            'encrypt_uploads': {'field_name': 'Enable Server Side Encryption', 'value': True}
        }
        nt.assert_equal(result, expected)

    def test_get_institutional_storage_information_unknown_provider(self):
        """Test get_institutional_storage_information function with unknown provider"""
        region = RegionFactory()
        region.waterbutler_credentials = {
            'storage': {
                'access_key': 'test_key'
            }
        }
        region.waterbutler_settings = {
            'storage': {
                'bucket': 'test_bucket',
                'encrypt_uploads': True
            }
        }
        region.save()

        result = get_institutional_storage_information(
            'unknown_provider', region, InstitutionFactory()
        )

        nt.assert_equal(result, {})


@pytest.mark.feature_202210
class TestIsInstitutionUsingNiiStorage(AdminTestCase):

    def setUp(self):
        super(TestIsInstitutionUsingNiiStorage, self).setUp()
        self.institution = InstitutionFactory()

    def test_returns_true_when_no_region_configured(self):
        """Return True when institution has no region (no storage configured yet)."""
        result = is_institution_using_nii_storage(self.institution)
        nt.assert_true(result)

    def test_returns_true_when_region_is_nii_storage(self):
        """Return True when institution's region is NII_STORAGE type."""
        from addons.osfstorage.models import Region
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        result = is_institution_using_nii_storage(self.institution)
        nt.assert_true(result)

    def test_returns_false_when_region_is_custom_storage(self):
        """Return False when institution's region is custom (non-NII) storage."""
        from addons.osfstorage.models import Region
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.INSTITUTIONS
        region.save()

        result = is_institution_using_nii_storage(self.institution)
        nt.assert_false(result)


@pytest.mark.feature_202210
class TestUpsertUserQuotaForInstitution(AdminTestCase):

    def setUp(self):
        super(TestUpsertUserQuotaForInstitution, self).setUp()
        self.institution = InstitutionFactory()
        self.user = UserFactory()
        self.user.affiliated_institutions.add(self.institution)
        self.user.save()

    def test_nii_to_custom_creates_custom_storage_quota_with_default_max(self):
        """NII → custom storage: upsert CUSTOM_STORAGE UserQuota with DEFAULT_MAX_QUOTA."""
        result = upsert_user_quota_for_institution(
            self.institution, provider_short_name='s3', old_is_nii=True
        )
        nt.assert_is_none(result)

        user_quota = UserQuota.objects.get(
            user=self.user, storage_type=UserQuota.CUSTOM_STORAGE
        )
        nt.assert_equal(user_quota.max_quota, api_settings.DEFAULT_MAX_QUOTA)

    def test_nii_to_custom_uses_institution_default_max_quota(self):
        """NII → custom storage: upsert CUSTOM_STORAGE UserQuota with InstitutionDefaultMaxQuota value."""
        InstitutionDefaultMaxQuota.objects.update_or_create(
            institution_id=self.institution.id,
            defaults={'default_max_quota': 500}
        )

        upsert_user_quota_for_institution(
            self.institution, provider_short_name='s3', old_is_nii=True
        )

        user_quota = UserQuota.objects.get(
            user=self.user, storage_type=UserQuota.CUSTOM_STORAGE
        )
        nt.assert_equal(user_quota.max_quota, 500)

    def test_nii_to_custom_updates_existing_quota(self):
        """NII → custom storage: update max_quota when UserQuota already exists."""
        UserQuota.objects.create(
            user=self.user,
            storage_type=UserQuota.CUSTOM_STORAGE,
            max_quota=100,
            used=50,
        )
        InstitutionDefaultMaxQuota.objects.update_or_create(
            institution_id=self.institution.id,
            defaults={'default_max_quota': 300}
        )

        upsert_user_quota_for_institution(
            self.institution, provider_short_name='s3', old_is_nii=True
        )

        user_quota = UserQuota.objects.get(
            user=self.user, storage_type=UserQuota.CUSTOM_STORAGE
        )
        nt.assert_equal(user_quota.max_quota, 300)
        nt.assert_equal(user_quota.used, 50)

    def test_custom_to_nii_creates_quota_with_default_max(self):
        """Custom → NII storage: upsert UserQuota using get_user_quota_type_for_nii_storage."""
        from addons.osfstorage.models import Region
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        upsert_user_quota_for_institution(
            self.institution, provider_short_name='osfstorage', old_is_nii=False
        )

        user_quota = UserQuota.objects.get(
            user=self.user, storage_type=UserQuota.CUSTOM_STORAGE
        )
        nt.assert_equal(user_quota.max_quota, api_settings.DEFAULT_MAX_QUOTA)

    def test_custom_to_nii_resets_existing_quota_to_default(self):
        """Custom → NII storage: existing CUSTOM_STORAGE quota is overwritten with DEFAULT_MAX_QUOTA."""
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        UserQuota.objects.create(
            user=self.user,
            storage_type=UserQuota.CUSTOM_STORAGE,
            max_quota=500,
            used=30,
        )

        upsert_user_quota_for_institution(
            self.institution, provider_short_name='osfstorage', old_is_nii=False
        )

        user_quota = UserQuota.objects.get(user=self.user, storage_type=UserQuota.CUSTOM_STORAGE)
        nt.assert_equal(user_quota.max_quota, api_settings.DEFAULT_MAX_QUOTA)
        nt.assert_equal(user_quota.used, 30)

    def test_no_change_when_already_nii_to_nii(self):
        """NII re-save (2nd+ time): existing CUSTOM_STORAGE quota must NOT be overwritten."""
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        UserQuota.objects.create(
            user=self.user,
            storage_type=UserQuota.CUSTOM_STORAGE,
            max_quota=500,
        )

        upsert_user_quota_for_institution(
            self.institution,
            provider_short_name='osfstorage',
            old_is_nii=True,
            old_quota_type=UserQuota.CUSTOM_STORAGE,
        )

        user_quota = UserQuota.objects.get(user=self.user, storage_type=UserQuota.CUSTOM_STORAGE)
        nt.assert_equal(user_quota.max_quota, 500)

    def test_no_change_when_custom_to_custom(self):
        """No quota upsert when switching custom → custom (old_is_nii=False)."""
        upsert_user_quota_for_institution(
            self.institution, provider_short_name='s3', old_is_nii=False
        )

        nt.assert_false(UserQuota.objects.filter(user=self.user).exists())

    def test_nii_quota_type_changed_preserves_existing_user_quota(self):
        """NII quota type changed (no-region → NII-region): existing quota of each user is preserved."""
        from addons.osfstorage.models import Region
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        UserQuota.objects.create(
            user=self.user,
            storage_type=UserQuota.NII_STORAGE,
            max_quota=200,
        )

        upsert_user_quota_for_institution(
            self.institution,
            provider_short_name='osfstorage',
            old_is_nii=True,
            old_quota_type=UserQuota.NII_STORAGE,
        )

        # new_quota_type = CUSTOM_STORAGE (institution now has NII region)
        user_quota = UserQuota.objects.get(user=self.user, storage_type=UserQuota.CUSTOM_STORAGE)
        nt.assert_equal(user_quota.max_quota, 200)

    def test_nii_quota_type_changed_uses_default_for_users_without_existing_quota(self):
        """NII quota type changed: users with no existing quota record receive system default."""
        from addons.osfstorage.models import Region
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        # No existing UserQuota for user
        upsert_user_quota_for_institution(
            self.institution,
            provider_short_name='osfstorage',
            old_is_nii=True,
            old_quota_type=UserQuota.NII_STORAGE,
        )

        user_quota = UserQuota.objects.get(user=self.user, storage_type=UserQuota.CUSTOM_STORAGE)
        nt.assert_equal(user_quota.max_quota, api_settings.DEFAULT_MAX_QUOTA)

    def test_no_change_when_old_and_new_quota_type_are_same(self):
        """No quota upsert when old_quota_type equals new_quota_type (NII quota type unchanged)."""
        # No region → new_quota_type = NII_STORAGE, old_quota_type = NII_STORAGE → same → return
        upsert_user_quota_for_institution(
            self.institution,
            provider_short_name='osfstorage',
            old_is_nii=True,
            old_quota_type=UserQuota.NII_STORAGE,
        )

        nt.assert_false(UserQuota.objects.filter(user=self.user).exists())

    def test_nii_quota_type_changed_mixed_users(self):
        """B3: user with existing quota gets preserved value; user without quota gets DEFAULT."""
        region = RegionFactory(_id=self.institution._id)
        region.waterbutler_settings['storage']['type'] = Region.NII_STORAGE
        region.save()

        user2 = UserFactory()
        user2.affiliated_institutions.add(self.institution)
        user2.save()

        UserQuota.objects.create(
            user=self.user,
            storage_type=UserQuota.NII_STORAGE,
            max_quota=300,
        )
        # user2 has no NII_STORAGE quota

        upsert_user_quota_for_institution(
            self.institution,
            provider_short_name='osfstorage',
            old_is_nii=True,
            old_quota_type=UserQuota.NII_STORAGE,
        )

        quota1 = UserQuota.objects.get(user=self.user, storage_type=UserQuota.CUSTOM_STORAGE)
        quota2 = UserQuota.objects.get(user=user2, storage_type=UserQuota.CUSTOM_STORAGE)
        nt.assert_equal(quota1.max_quota, 300)
        nt.assert_equal(quota2.max_quota, api_settings.DEFAULT_MAX_QUOTA)

    def test_non_affiliated_user_quota_not_affected(self):
        """Users not affiliated with the institution must not have their quota created or modified."""
        non_affiliated_user = UserFactory()
        # non_affiliated_user is deliberately NOT added to self.institution

        InstitutionDefaultMaxQuota.objects.update_or_create(
            institution_id=self.institution.id,
            defaults={'default_max_quota': 400}
        )

        upsert_user_quota_for_institution(
            self.institution, provider_short_name='s3', old_is_nii=True
        )

        nt.assert_false(
            UserQuota.objects.filter(user=non_affiliated_user).exists()
        )

    @patch('admin.rdm_custom_storage_location.utils.UserQuota.objects.update_or_create')
    def test_integrity_error_falls_back_to_filter_update(self, mock_uoc):
        """On IntegrityError, fall back to filter().update() to set max_quota."""
        from django.db import IntegrityError
        InstitutionDefaultMaxQuota.objects.update_or_create(
            institution_id=self.institution.id,
            defaults={'default_max_quota': 200}
        )
        mock_uoc.side_effect = IntegrityError('duplicate key')

        UserQuota.objects.create(
            user=self.user,
            storage_type=UserQuota.CUSTOM_STORAGE,
            max_quota=50,
            used=10,
        )

        upsert_user_quota_for_institution(
            self.institution, provider_short_name='s3', old_is_nii=True
        )

        user_quota = UserQuota.objects.get(
            user=self.user, storage_type=UserQuota.CUSTOM_STORAGE
        )
        nt.assert_equal(user_quota.max_quota, 200)

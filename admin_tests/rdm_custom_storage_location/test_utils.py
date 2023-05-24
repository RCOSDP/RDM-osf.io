import mock
from django.core.exceptions import ValidationError
from nose import tools as nt
from nose.tools import assert_raises

from addons.osfstorage.settings import DEFAULT_REGION_NAME
from addons.s3compatinstitutions.models import S3CompatInstitutionsProvider
from admin.rdm_custom_storage_location import utils
from osf.models import RdmAddonOption
from osf.models.external import ExternalAccountTemporary
from osf_tests.factories import (
    RegionFactory,
    InstitutionFactory,
    UserFactory,
    ExternalAccountFactory
)
from tests.base import AdminTestCase
from django.db import IntegrityError

class TestUtils(AdminTestCase):
    def setUp(self):
        self.institution = InstitutionFactory()
        self.storage_name = 'test_storage_name'
        self.new_storage_name = 'test_new_storage_name'
        self.access_key = 'fake_access_key'
        self.secret_key = 'fake_secret_key'
        self.bucket = 'fake_bucket'
        self.wb_credentials = {
            'storage': {
                'access_key': self.access_key,
                'secret_key': self.secret_key,
            },
        }
        self.wb_settings = {
            'storage': {
                'folder': {
                    'encrypt_uploads': True,
                },
                'bucket': self.bucket,
                'provider': 's3',
            },
        }

    def test_update_storage(self):
        res = utils.update_storage(self.institution.id,
                                   self.storage_name,
                                   self.wb_credentials,
                                   self.wb_settings,
                                   self.new_storage_name)

        nt.assert_equal(res.name, self.storage_name)
        nt.assert_equal(res.waterbutler_credentials, self.wb_credentials)

    def test_update_storage_have_region(self):
        RegionFactory(_id=self.institution._id, name=self.storage_name)
        res = utils.update_storage(self.institution._id,
                                   self.storage_name,
                                   self.wb_credentials,
                                   self.wb_settings,
                                   self.new_storage_name)

        nt.assert_equal(res.name, self.new_storage_name)
        nt.assert_equal(res.waterbutler_credentials, self.wb_credentials)

    def test_update_storage_have_no_new_storage_name(self):
        RegionFactory(_id=self.institution._id, name=self.storage_name)
        with assert_raises(IntegrityError):
            res = utils.update_storage(self.institution._id,
                                       self.storage_name,
                                       self.wb_credentials,
                                       self.wb_settings,
                                       None)

            nt.assert_equal(res.name, self.storage_name)
            nt.assert_equal(res.waterbutler_credentials, self.wb_credentials)

    def test_save_s3_credentials(self):
        storage_name = 'test_storage_name'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_s3_credentials(self.institution._id,
                                        storage_name, access_key,
                                        secret_key,
                                        bucket,
                                        new_storage_name)

        nt.assert_equal(res[1], 400)

    @mock.patch('admin.rdm_custom_storage_location.utils.test_s3_connection')
    @mock.patch('osf.utils.external_util.remove_region_external_account')
    def test_save_s3_credentials_successfully(self, mock_external_util, mock_test_s3_connection, ):
        mock_test_s3_connection.return_value = ({'message': 'Credentials are valid',
                                                 'data': 's3_response'}, 200)
        mock_external_util.return_value = None
        storage_name = 'test_storage_name'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_s3_credentials(self.institution._id,
                                        storage_name, access_key,
                                        secret_key,
                                        bucket,
                                        new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_s3compat_credentials(self):
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_s3compat_credentials(self.institution._id,
                                              storage_name, host_url,
                                              access_key,
                                              secret_key,
                                              bucket,
                                              new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('admin.rdm_custom_storage_location.utils.test_s3compat_connection')
    @mock.patch('osf.utils.external_util.remove_region_external_account')
    def test_save_s3compat_credentials_successfully(self, mock_external_util, mock_test_s3compat_connection, ):
        mock_test_s3compat_connection.return_value = ({'message': 'Credentials are valid',
                                                       'data': {'id': 2, 'display_name': 'fake_display_name', }}, 200)
        mock_external_util.return_value = None
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        server_side_encryption = False
        new_storage_name = 'test_new_storage_name'
        res = utils.save_s3compat_credentials(self.institution._id,
                                              storage_name, host_url,
                                              access_key,
                                              secret_key,
                                              bucket,
                                              server_side_encryption,
                                              new_storage_name, )
        nt.assert_equal(res[1], 200)

    def test_save_s3compatb3_credentials(self):
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_s3compatb3_credentials(self.institution._id,
                                                storage_name, host_url,
                                                access_key,
                                                secret_key,
                                                bucket,
                                                new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('admin.rdm_custom_storage_location.utils.test_s3compatb3_connection')
    @mock.patch('osf.utils.external_util.remove_region_external_account')
    def test_save_s3compatb3_credentials_successfully(self, mock_external_util, mock_test_s3compatb3_connection, ):
        mock_test_s3compatb3_connection.return_value = ({'message': 'Credentials are valid',
                                                         'data': {'id': 2, 'display_name': 'fake_display_name', }}, 200)
        mock_external_util.return_value = None
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_s3compatb3_credentials(self.institution._id,
                                                storage_name, host_url,
                                                access_key,
                                                secret_key,
                                                bucket,
                                                new_storage_name, )
        nt.assert_equal(res[1], 200)

    def test_save_box_credentials(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        storage_name = 'test_storage_name'
        folder_id = 'folder_id'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_box_credentials(user,
                                         storage_name,
                                         folder_id,
                                         new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.set_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_box_connection')
    @mock.patch('admin.rdm_custom_storage_location.utils.transfer_to_external_account')
    def test_save_box_credentials_successfully(self, mock_transfer_to_external_account, mock_test_box_connection,
                                               mock_set_region_external_account):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        mock_test_box_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        mock_transfer_to_external_account.return_value = ExternalAccountTemporary.objects.create(
            _id=institution._id, provider='box', oauth_key='fake_oauth_key')
        mock_set_region_external_account.return_value = None
        storage_name = 'test_storage_name'
        folder_id = 'folder_id'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_box_credentials(user,
                                         storage_name,
                                         folder_id,
                                         new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_googledrive_credentials(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        storage_name = 'test_storage_name'
        folder_id = 'folder_id'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_googledrive_credentials(user,
                                                 storage_name,
                                                 folder_id,
                                                 new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.set_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_googledrive_connection')
    @mock.patch('admin.rdm_custom_storage_location.utils.transfer_to_external_account')
    def test_save_googledrive_credentials_successfully(self, mock_transfer_to_external_account, mock_test_googledrive_connection,
                                                       mock_set_region_external_account):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        mock_test_googledrive_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        mock_transfer_to_external_account.return_value = ExternalAccountTemporary.objects.create(
            _id=institution._id, provider='googledrive', oauth_key='fake_oauth_key')
        mock_set_region_external_account.return_value = None
        storage_name = 'test_storage_name'
        folder_id = 'folder_id'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_googledrive_credentials(user,
                                                 storage_name,
                                                 folder_id,
                                                 new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_nextcloud_credentials(self):
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        username = 'fake_username'
        password = 'fake_password'
        folder = 'fake_folder'
        provider = 'nextcloud'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_nextcloud_credentials(self.institution._id,
                                               storage_name, host_url,
                                               username,
                                               password,
                                               folder,
                                               provider,
                                               new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.remove_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_owncloud_connection')
    def test_save_nextcloud_credentials_successfully(self, mock_test_owncloud_connection, mock_remove_region_external_account):
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        username = 'fake_username'
        password = 'fake_password'
        folder = 'fake_folder'
        provider = 'nextcloud'
        new_storage_name = 'test_new_storage_name'

        mock_test_owncloud_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        mock_remove_region_external_account.return_value = None

        res = utils.save_nextcloud_credentials(self.institution._id,
                                               storage_name, host_url,
                                               username,
                                               password,
                                               folder,
                                               provider,
                                               new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_swift_credentials(self):
        storage_name = 'test_storage_name'
        auth_version = 'fake_auth_version'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        tenant_name = 'fake_tenant_name'
        user_domain_name = 'fake_user_domain_name'
        project_domain_name = 'fake_project_domain_name'
        auth_url = 'fake_auth_url'
        container = 'fake_container'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_swift_credentials(self.institution._id,
                                           storage_name,
                                           auth_version,
                                           access_key,
                                           secret_key,
                                           tenant_name,
                                           user_domain_name,
                                           project_domain_name,
                                           auth_url,
                                           container,
                                           new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.remove_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_swift_connection')
    def test_save_swift_credentials_successfully(self, mock_test_swift_connection,
                                                 mock_remove_region_external_account):
        mock_test_swift_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        mock_remove_region_external_account.return_value = None
        storage_name = 'test_storage_name'
        auth_version = 'fake_auth_version'
        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        tenant_name = 'fake_tenant_name'
        user_domain_name = 'fake_user_domain_name'
        project_domain_name = 'fake_project_domain_name'
        auth_url = 'fake_auth_url'
        container = 'fake_container'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_swift_credentials(self.institution._id,
                                           storage_name,
                                           auth_version,
                                           access_key,
                                           secret_key,
                                           tenant_name,
                                           user_domain_name,
                                           project_domain_name,
                                           auth_url,
                                           container,
                                           new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_owncloud_credentials(self):
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        username = 'fake_username'
        password = 'fake_password'
        folder = 'fake_folder'
        provider = 'owncloud'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_owncloud_credentials(self.institution._id,
                                              storage_name,
                                              host_url,
                                              username,
                                              password,
                                              folder,
                                              provider,
                                              new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.remove_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_owncloud_connection')
    def test_save_owncloud_credentials_successfully(self, mock_test_owncloud_connection,
                                                    mock_remove_region_external_account):
        mock_test_owncloud_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        mock_remove_region_external_account.return_value = None
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        username = 'fake_username'
        password = 'fake_password'
        folder = 'fake_folder'
        provider = 'owncloud'
        new_storage_name = 'test_new_storage_name'
        res = utils.save_owncloud_credentials(self.institution._id,
                                              storage_name,
                                              host_url,
                                              username,
                                              password,
                                              folder,
                                              provider,
                                              new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_onedrivebusiness_credentials(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        storage_name = 'test_storage_name'
        provider_name = 'onedrivebusiness'
        folder_id_or_path = 'fake_folder_id_or_path'
        new_storage_name = 'fake_new_storage_name'
        res = utils.save_onedrivebusiness_credentials(user,
                                                      storage_name,
                                                      provider_name,
                                                      folder_id_or_path,
                                                      new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.set_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.validate_onedrivebusiness_connection')
    @mock.patch('admin.rdm_custom_storage_location.utils.transfer_to_external_account')
    def test_save_onedrivebusiness_credentials_successfully(self, mock_transfer_to_external_account,
                                                            mock_validate_onedrivebusiness_connection,
                                                            mock_set_region_external_account):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)
        folder_id = 12
        mock_validate_onedrivebusiness_connection.return_value = ({'message': 'Credentials are valid'},
                                                                  200), folder_id
        mock_set_region_external_account.return_value = None
        mock_transfer_to_external_account.return_value = ExternalAccountTemporary.objects.create(_id=institution._id,
                                                                                                 provider='box',
                                                                                                 oauth_key='fake_oauth_key')

        storage_name = 'test_storage_name'
        provider_name = 'onedrivebusiness'
        folder_id_or_path = 'fake_folder_id_or_path'
        new_storage_name = 'fake_new_storage_name'
        res = utils.save_onedrivebusiness_credentials(user,
                                                      storage_name,
                                                      provider_name,
                                                      folder_id_or_path,
                                                      new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_dropboxbusiness_credentials(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        storage_name = 'test_storage_name'
        provider_name = 'onedrivebusiness'
        new_storage_name = 'fake_new_storage_name'
        res = utils.save_dropboxbusiness_credentials(institution,
                                                     storage_name,
                                                     provider_name,
                                                     new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('osf.utils.external_util.remove_region_external_account')
    @mock.patch('admin.rdm_custom_storage_location.utils.test_dropboxbusiness_connection')
    def test_save_dropboxbusiness_credentials_successfully(self, mock_test_dropboxbusiness_connection,
                                                           mock_remove_region_external_account):
        mock_test_dropboxbusiness_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        mock_remove_region_external_account.return_value = None
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        storage_name = 'test_storage_name'
        provider_name = 'onedrivebusiness'
        new_storage_name = 'fake_new_storage_name'
        res = utils.save_dropboxbusiness_credentials(institution,
                                                     storage_name,
                                                     provider_name,
                                                     new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_basic_storage_institutions_credentials_common(self):
        context = mock.MagicMock()
        context.save_basic_storage_institutions_credentials_common.side_effect = ValidationError

        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        host = 'https://fake_host'
        username = 'fake_username'
        password = 'fake_password'

        storage_name = 'test_storage_name'
        folder = 'fake_folder'
        provider_name = 'onedrivebusiness'
        separator = ':'
        provider = S3CompatInstitutionsProvider(account=None, host=host, username=username,
                                                password=password, separator=separator)
        new_storage_name = 'fake_new_storage_name'
        extended_data = None

        res = utils.save_basic_storage_institutions_credentials_common(institution, storage_name,
                                                                       folder, provider_name,
                                                                       provider, separator,
                                                                       extended_data, new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_basic_storage_institutions_credentials_common_rdm_addon_option_is_not_none(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)
        host = 'https://fake_host'
        username = 'fake_username'
        password = 'fake_password'

        storage_name = 'test_storage_name'
        folder = 'fake_folder'
        provider_name = 'onedrivebusiness'
        separator = ':'
        provider = S3CompatInstitutionsProvider(
            account=None, host=host,
            username=username, password=password, separator=separator)
        extended_data = None
        external_account = ExternalAccountFactory(provider=provider_name)
        new_storage_name = 'fake_new_storage_name'
        rdm_addoon_option = RdmAddonOption.objects.create(provider=provider_name, institution_id=institution.id)
        rdm_addoon_option.external_accounts.set([external_account])

        res = utils.save_basic_storage_institutions_credentials_common(institution, storage_name,
                                                                       folder, provider_name,
                                                                       provider, separator,
                                                                       extended_data, new_storage_name)
        nt.assert_equal(res[1], 200)

    @mock.patch('admin.rdm_custom_storage_location.utils.ExternalAccount.objects.get')
    @mock.patch('osf.models.external.ExternalAccount.save')
    def test_save_basic_storage_institutions_credentials_common_exception(self, mock_save, mock_external_account):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        host = 'http://wutwut.com/'
        username = 'user-0'
        password = 'fake_password'
        storage_name = 'test_storage_name'
        folder = 'fake_folder'
        provider_name = 'S3 Compatible Storage for Institutions'
        separator = ':'
        new_storage_name = 'fake_new_storage_name'
        extended_data = None

        external_account = ExternalAccountFactory(provider=provider_name, provider_id='{}{}{}'.format(host, separator, username))
        provider = S3CompatInstitutionsProvider(account=None, host=host, username=username,
                                                password=password, separator=separator)

        RdmAddonOption.objects.create(provider=provider_name, institution_id=institution.id)
        mock_external_account.return_value = external_account
        mock_save.side_effect = ValidationError('ERROR')
        with assert_raises(ValidationError)as e:
            utils.save_basic_storage_institutions_credentials_common(institution, storage_name,
                                                                     folder, provider_name,
                                                                     provider, separator,
                                                                     extended_data, new_storage_name)
        nt.assert_equal(str(e.exception), "['ERROR']")

    @mock.patch('admin.rdm_custom_storage_location.utils.test_owncloud_connection')
    def test_save_nextcloudinstitutions_credentials(self, mock_test_dropboxbusiness_connection, ):
        mock_test_dropboxbusiness_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        username = 'fake_username'
        password = 'fake_password'
        folder = 'fake_folder'
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        notification_secret = 'fake_notification_secret'
        new_storage_name = 'fake_new_storage_name'
        provider_name = 'fake_provider_name'
        res = utils.save_nextcloudinstitutions_credentials(institution, storage_name,
                                                           host_url, username,
                                                           password, folder,
                                                           notification_secret,
                                                           provider_name, new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_nextcloudinstitutions_credentials_invalid(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        username = 'fake_username'
        password = 'fake_password'
        folder = 'fake_folder'
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        notification_secret = 'fake_notification_secret'
        new_storage_name = 'fake_new_storage_name'
        provider_name = 'owncloud'
        res = utils.save_nextcloudinstitutions_credentials(institution, storage_name,
                                                           host_url, username,
                                                           password, folder,
                                                           notification_secret,
                                                           provider_name, new_storage_name)
        nt.assert_equal(res[1], 400)

    def test_save_s3compatinstitutions_credentials(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        new_storage_name = 'fake_new_storage_name'
        provider_name = 'fake_provider_name'
        res = utils.save_s3compatinstitutions_credentials(institution, storage_name,
                                                          host_url, access_key,
                                                          secret_key, bucket,
                                                          provider_name, new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('admin.rdm_custom_storage_location.utils.test_s3compat_connection')
    def test_save_s3compatinstitutions_credentials_successfully(self, mock_test_s3compat_connection):
        mock_test_s3compat_connection.return_value = ({'message': 'Credentials are valid'}, 200)
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        new_storage_name = 'fake_new_storage_name'
        provider_name = 'fake_provider_name'
        res = utils.save_s3compatinstitutions_credentials(institution, storage_name,
                                                          host_url, access_key,
                                                          secret_key, bucket,
                                                          provider_name, new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_save_ociinstitutions_credentials(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        new_storage_name = 'fake_new_storage_name'
        provider_name = 'fake_provider_name'
        res = utils.save_ociinstitutions_credentials(institution, storage_name,
                                                     host_url, access_key,
                                                     secret_key, bucket,
                                                     provider_name, new_storage_name)
        nt.assert_equal(res[1], 400)

    @mock.patch('admin.rdm_custom_storage_location.utils.test_s3compatb3_connection')
    def test_save_ociinstitutions_credentials_successfully(self, mock_test_s3compatb3_connection):
        mock_test_s3compatb3_connection.return_value = ({'message': 'Credentials are valid',
                                                         'data': {'id': 'user_info.id', 'display_name': 'user_info.display_name', }}, 200)
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        access_key = 'fake_access_key'
        secret_key = 'fake_secret_key'
        bucket = 'fake_bucket'
        storage_name = 'test_storage_name'
        host_url = 'https://fake_host'
        new_storage_name = 'fake_new_storage_name'
        provider_name = 'fake_provider_name'
        res = utils.save_ociinstitutions_credentials(institution, storage_name,
                                                     host_url, access_key,
                                                     secret_key, bucket,
                                                     provider_name, new_storage_name)
        nt.assert_equal(res[1], 200)

    def test_set_default_storage_have_region(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        RegionFactory(_id=institution._id, name=DEFAULT_REGION_NAME)
        res = utils.set_default_storage(institution._id)

        nt.assert_equal(res.name, DEFAULT_REGION_NAME)
        nt.assert_equal(res._id, institution._id)

    def test_set_default_storage_have_no_region(self):
        user = UserFactory()
        institution = InstitutionFactory()
        user.affiliated_institutions.add(institution)

        res = utils.set_default_storage(institution._id)

        nt.assert_equal(res.name, DEFAULT_REGION_NAME)
        nt.assert_equal(res._id, institution._id)

    def test_validate_logic_expression_operator_invalid(self):
        region = RegionFactory(allow_expression='')
        res = utils.validate_logic_expression(region.allow_expression)
        region_1 = RegionFactory(allow_expression='1&2')
        res_1 = utils.validate_logic_expression(region_1.allow_expression)
        region_2 = RegionFactory(allow_expression='1&2&3')
        res_2 = utils.validate_logic_expression(region_2.allow_expression)
        region_3 = RegionFactory(allow_expression='(1|2)|3')
        res_3 = utils.validate_logic_expression(region_3.allow_expression)
        region_4 = RegionFactory(allow_expression='(1&&&&3')
        res_4 = utils.validate_logic_expression(region_4.allow_expression)
        nt.assert_true(res)
        nt.assert_false(res_1)
        nt.assert_false(res_2)
        nt.assert_false(res_3)
        nt.assert_false(res_4)

    def test_check_index_number_exists(self):
        region = RegionFactory(allow_expression='(1&&2)||3')
        res = utils.check_index_number_exists(region.allow_expression, '2')
        nt.assert_true(res)

    def test_validate_index_number_not_found_return_true(self):
        region = RegionFactory(allow_expression='(1&&2)||3')
        index_list = [1, 2, 3, 4, 5]
        res = utils.validate_index_number_not_found(region.allow_expression, index_list)
        nt.assert_true(res)

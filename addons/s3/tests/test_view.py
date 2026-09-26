from rest_framework import status as http_status

from botocore.exceptions import NoCredentialsError
from unittest import mock
import pytest

from framework.auth import Auth
from tests.base import OsfTestCase, get_default_metaschema
from osf_tests.factories import ProjectFactory, AuthUserFactory, DraftRegistrationFactory, InstitutionFactory

from addons.base.tests.views import (
    OAuthAddonConfigViewsTestCaseMixin
)
from addons.s3.tests.utils import S3AddonTestCase
from addons.s3.utils import validate_bucket_name, validate_bucket_location
from website.util import api_url_for
from admin.rdm_addons.utils import get_rdm_addon_option
from osf.models import ExternalAccount

pytestmark = pytest.mark.django_db

class TestS3Views(S3AddonTestCase, OAuthAddonConfigViewsTestCaseMixin, OsfTestCase):
    def setUp(self):
        self.mock_can_list = mock.patch('addons.s3.views.utils.can_list')
        self.mock_can_list.return_value = True
        self.mock_can_list.start()
        self.mock_uid = mock.patch('addons.s3.views.utils.get_user_info',
                                   return_value=mock.Mock(id='1234567890', display_name='s3.user'))
        self.mock_uid.start()
        self.mock_exists = mock.patch('addons.s3.views.utils.bucket_exists')
        self.mock_exists.return_value = True
        self.mock_exists.start()
        super().setUp()

    def tearDown(self):
        self.mock_can_list.stop()
        self.mock_uid.stop()
        self.mock_exists.stop()
        super().tearDown()

    def test_s3_settings_input_empty_keys(self):
        url = self.project.api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {
            'access_key': '',
            'secret_key': ''
        }, auth=self.user.auth, expect_errors=True)
        assert rv.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'All the fields above are required.' in rv.text

    def test_s3_settings_input_empty_access_key(self):
        url = self.project.api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {
            'access_key': '',
            'secret_key': 'Non-empty-secret-key'
        }, auth=self.user.auth, expect_errors=True)
        assert rv.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'All the fields above are required.' in rv.text

    def test_s3_settings_input_empty_secret_key(self):
        url = self.project.api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {
            'access_key': 'Non-empty-access-key',
            'secret_key': ''
        }, auth=self.user.auth, expect_errors=True)
        assert rv.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'All the fields above are required.' in rv.text

    def test_s3_settings_rdm_addons_denied(self):
        institution = InstitutionFactory()
        self.user.affiliated_institutions.add(institution)
        self.user.save()
        rdm_addon_option = get_rdm_addon_option(institution.id, self.ADDON_SHORT_NAME)
        rdm_addon_option.is_allowed = False
        rdm_addon_option.save()
        url = self.project.api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {
            'access_key': 'aldkjf',
            'secret_key': 'las'
        }, auth=self.user.auth, expect_errors=True)
        assert rv.status_code == http_status.HTTP_403_FORBIDDEN
        assert 'You are prohibited from using this add-on.' in rv.text

    # G5: GRDM-53044 provider_id = "{aws_account_id}\t{access_key}"
    # setUp already patches get_user_info/can_list as truthy MagicMocks.
    # Note: oauth_key/oauth_secret are EncryptedTextField (JWE, non-deterministic),
    # so we query by provider_id (plain CharField) and verify via attribute access.
    def test_provider_id_format(self):
        url = self.project.api_url_for('s3_add_user_account')
        access_key = 'AKIAIOSFODNN7EXAMPLE'
        rv = self.app.post_json(url, {
            'access_key': access_key,
            'secret_key': 'wJalrXUtnFEMI/K7MDENG',
        }, auth=self.user.auth)
        assert rv.status_code == http_status.HTTP_200_OK
        # provider_id is not encrypted — safe to query
        provider_id = f'1234567890\t{access_key}'
        account = ExternalAccount.objects.get(provider='s3', provider_id=provider_id)
        # provider_id must be "{aws_account_id}\t{access_key}" (GRDM-53044)
        assert account.provider_id.endswith(f'\t{access_key}')
        assert '\t' in account.provider_id
        assert account.oauth_key == access_key

    def test_provider_id_dedup(self):
        url = self.project.api_url_for('s3_add_user_account')
        access_key = 'AKIAIOSFODNN7EXAMPLE'
        provider_id = f'1234567890\t{access_key}'
        rv1 = self.app.post_json(url, {
            'access_key': access_key,
            'secret_key': 'secret1',
        }, auth=self.user.auth)
        assert rv1.status_code == http_status.HTTP_200_OK
        # Same AWS account (same provider_id) with new secret → update, no duplicate
        rv2 = self.app.post_json(url, {
            'access_key': access_key,
            'secret_key': 'secret2',
        }, auth=self.user.auth)
        assert rv2.status_code == http_status.HTTP_200_OK
        # Query by provider_id (plain CharField) — oauth_key is encrypted (JWE)
        accounts = ExternalAccount.objects.filter(provider='s3', provider_id=provider_id)
        assert accounts.count() == 1
        assert accounts.first().oauth_secret == 'secret2'

    # G1: missing key field → KeyError → 400
    def test_s3_settings_missing_key_field(self):
        url = self.project.api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {}, auth=self.user.auth, expect_errors=True)
        assert rv.status_code == http_status.HTTP_400_BAD_REQUEST

    # G2: get_user_info returns None → 400 + "Unable to access account."
    @mock.patch('addons.s3.views.utils.get_user_info', return_value=None)
    def test_s3_settings_invalid_account(self, mock_get_user_info):
        url = self.project.api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {
            'access_key': 'aldkjf',
            'secret_key': 'las',
        }, auth=self.user.auth, expect_errors=True)
        assert rv.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'Unable to access account.' in rv.text

    def test_s3_set_bucket_no_settings(self):
        user = AuthUserFactory()
        self.project.add_contributor(user, save=True)
        url = self.project.api_url_for('s3_set_config')
        res = self.app.put_json(
            url, {'s3_bucket': 'hammertofall'}, auth=user.auth,
            expect_errors=True,
        )
        assert res.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_s3_set_bucket_no_auth(self):

        user = AuthUserFactory()
        user.add_addon('s3')
        self.project.add_contributor(user, save=True)
        url = self.project.api_url_for('s3_set_config')
        res = self.app.put_json(
            url, {'s3_bucket': 'hammertofall'}, auth=user.auth,
            expect_errors=True,
        )
        assert res.status_code == http_status.HTTP_403_FORBIDDEN

    def test_s3_set_bucket_registered(self):
        registration = self.project.register_node(
            get_default_metaschema(), Auth(self.user), DraftRegistrationFactory(branched_from=self.project), ''
        )

        url = registration.api_url_for('s3_set_config')
        res = self.app.put_json(
            url, {'s3_bucket': 'hammertofall'}, auth=self.user.auth,
            expect_errors=True,
        )

        assert res.status_code == http_status.HTTP_400_BAD_REQUEST

    @mock.patch('addons.s3.views.utils.can_list', return_value=False)
    def test_user_settings_cant_list(self, mock_can_list):
        url = api_url_for('s3_add_user_account')
        rv = self.app.post_json(url, {
            'access_key': 'aldkjf',
            'secret_key': 'las'
        }, auth=self.user.auth, expect_errors=True)

        assert 'Unable to list buckets.' in rv.text
        assert rv.status_code == http_status.HTTP_400_BAD_REQUEST

    def test_s3_remove_node_settings_owner(self):
        url = self.node_settings.owner.api_url_for('s3_deauthorize_node')
        self.app.delete(url, auth=self.user.auth)
        result = self.Serializer().serialize_settings(node_settings=self.node_settings, current_user=self.user)
        assert result['nodeHasAuth'] == False

    def test_s3_remove_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('s3_deauthorize_node')
        ret = self.app.delete(url, auth=None, expect_errors=True)

        assert ret.status_code == 401

    def test_s3_get_node_settings_owner(self):
        self.node_settings.set_auth(self.external_account, self.user)
        self.node_settings.folder_id = 'bucket'
        self.node_settings.save()
        url = self.node_settings.owner.api_url_for('s3_get_config')
        res = self.app.get(url, auth=self.user.auth)

        result = res.json['result']
        assert result['nodeHasAuth'] == True
        assert result['userIsOwner'] == True
        assert result['folder']['path'] == self.node_settings.folder_id

    def test_s3_get_node_settings_unauthorized(self):
        url = self.node_settings.owner.api_url_for('s3_get_config')
        unauthorized = AuthUserFactory()
        ret = self.app.get(url, auth=unauthorized.auth, expect_errors=True)

        assert ret.status_code == 403

    ## Overrides ##

    @mock.patch('addons.s3.models.get_bucket_names')
    def test_folder_list(self, mock_names):
        mock_names.return_value = ['bucket1', 'bucket2']
        super().test_folder_list()

    @mock.patch('addons.s3.models.bucket_exists')
    @mock.patch('addons.s3.models.get_bucket_location_or_error')
    def test_set_config(self, mock_location, mock_exists):
        mock_exists.return_value = True
        mock_location.return_value = ''
        self.node_settings.set_auth(self.external_account, self.user)
        url = self.project.api_url_for(f'{self.ADDON_SHORT_NAME}_set_config')
        res = self.app.put_json(url, {
            'selected': self.folder
        }, auth=self.user.auth)
        assert res.status_code == http_status.HTTP_200_OK
        self.project.reload()
        self.node_settings.reload()
        assert self.project.logs.latest().action == f'{self.ADDON_SHORT_NAME}_bucket_linked'
        assert res.json['result']['folder']['name'] == self.node_settings.folder_name


class TestCreateBucket(S3AddonTestCase, OsfTestCase):

    def setUp(self):

        super().setUp()

        self.user = AuthUserFactory()
        self.consolidated_auth = Auth(user=self.user)
        self.auth = self.user.auth
        self.project = ProjectFactory(creator=self.user)

        self.project.add_addon('s3', auth=self.consolidated_auth)
        self.project.creator.add_addon('s3')

        self.user_settings = self.user.get_addon('s3')
        self.user_settings.access_key = 'We-Will-Rock-You'
        self.user_settings.secret_key = 'Idontknowanyqueensongs'
        self.user_settings.save()

        self.node_settings = self.project.get_addon('s3')
        self.node_settings.bucket = 'Sheer-Heart-Attack'
        self.node_settings.user_settings = self.project.creator.get_addon('s3')

        self.node_settings.save()

    def test_bad_names(self):
        assert not validate_bucket_name('')
        assert not validate_bucket_name('no')
        assert not validate_bucket_name('a' * 64)
        assert not validate_bucket_name(' leadingspace')
        assert not validate_bucket_name('trailingspace ')
        assert not validate_bucket_name('bogus naMe')
        assert not validate_bucket_name('.cantstartwithp')
        assert not validate_bucket_name('or.endwith.')
        assert not validate_bucket_name('..nodoubles')
        assert not validate_bucket_name('no_unders_in')
        assert not validate_bucket_name('-leadinghyphen')
        assert not validate_bucket_name('trailinghyphen-')
        assert not validate_bucket_name('Mixedcase')
        assert not validate_bucket_name('empty..label')
        assert not validate_bucket_name('label-.trailinghyphen')
        assert not validate_bucket_name('label.-leadinghyphen')
        assert not validate_bucket_name('8.8.8.8')
        assert not validate_bucket_name('600.9000.0.28')
        assert not validate_bucket_name('no_underscore')
        assert not validate_bucket_name('_nounderscoreinfront')
        assert not validate_bucket_name('no-underscore-in-back_')
        assert not validate_bucket_name('no-underscore-in_the_middle_either')

    def test_names(self):
        assert validate_bucket_name('imagoodname')
        assert validate_bucket_name('still.passing')
        assert validate_bucket_name('can-have-dashes')
        assert validate_bucket_name('kinda.name.spaced')
        assert validate_bucket_name('a-o.valid')
        assert validate_bucket_name('11.12.m')
        assert validate_bucket_name('a--------a')
        assert validate_bucket_name('a' * 63)

    def test_bad_locations(self):
        assert not validate_bucket_location('Venus')
        assert not validate_bucket_location('AlphaCentauri')
        assert not validate_bucket_location('CostaRica')

    def test_locations(self):
        assert validate_bucket_location('')
        assert validate_bucket_location('eu-central-1')
        assert validate_bucket_location('ca-central-1')
        assert validate_bucket_location('us-west-1')
        assert validate_bucket_location('us-west-2')
        assert validate_bucket_location('ap-northeast-1')
        assert validate_bucket_location('ap-northeast-2')
        assert validate_bucket_location('ap-southeast-1')
        assert validate_bucket_location('ap-southeast-2')
        assert validate_bucket_location('sa-east-1')
        assert validate_bucket_location('eu-west-1')
        assert validate_bucket_location('eu-west-2')

    @mock.patch('addons.s3.views.utils.create_bucket')
    @mock.patch('addons.s3.views.utils.get_bucket_names')
    def test_create_bucket_pass(self, mock_names, mock_make):
        mock_make.return_value = True
        mock_names.return_value = [
            'butintheend',
            'it',
            'doesntevenmatter'
        ]
        url = self.project.api_url_for('create_bucket')
        ret = self.app.post_json(
            url,
            {
                'bucket_name': 'doesntevenmatter',
                'bucket_location': '',
            },
            auth=self.user.auth
        )

        assert ret.status_code == http_status.HTTP_200_OK
        assert ret.json == {}

    @mock.patch('addons.s3.views.utils.create_bucket')
    def test_create_bucket_fail(self, mock_make):
        error = NoCredentialsError(operation_name='create_bucket')
        mock_make.side_effect = error

        url = f'/api/v1/project/{self.project._id}/s3/newbucket/'
        ret = self.app.post_json(url, {'bucket_name': 'doesntevenmatter'}, auth=self.user.auth,
                                 expect_errors=True)

        assert ret.text == '{"message": "Unable to locate credentials", "title": "Problem connecting to S3"}'

    @mock.patch('addons.s3.views.utils.create_bucket')
    def test_bad_location_fails(self, mock_make):
        url = f'/api/v1/project/{self.project._id}/s3/newbucket/'
        ret = self.app.post_json(
            url,
            {
                'bucket_name': 'doesntevenmatter',
                'bucket_location': 'not a real bucket location',
            },
            auth=self.user.auth,
            expect_errors=True,
        )
        assert ret.text == '{"message": "That bucket location is not valid.", "title": "Invalid bucket location"}'

    # G4: invalid bucket name → 400 (name check fires before any S3 call)
    def test_create_bucket_bad_name(self):
        url = f'/api/v1/project/{self.project._id}/s3/newbucket/'
        ret = self.app.post_json(
            url,
            {
                'bucket_name': 'no',
                'bucket_location': '',
            },
            auth=self.user.auth,
            expect_errors=True,
        )
        assert ret.status_code == http_status.HTTP_400_BAD_REQUEST
        assert 'That bucket name is not valid.' in ret.text

    @mock.patch('addons.s3.views.utils.create_bucket')
    def test_create_bucket_client_error(self, mock_make):
        from botocore.exceptions import ClientError
        error = ClientError(
            {'Error': {'Code': 'BucketAlreadyExists', 'Message': 'The requested bucket name is not available.'}},
            'CreateBucket'
        )
        mock_make.side_effect = error
        url = f'/api/v1/project/{self.project._id}/s3/newbucket/'
        ret = self.app.post_json(
            url,
            {'bucket_name': 'valid-bucket-name', 'bucket_location': ''},
            auth=self.user.auth,
            expect_errors=True,
        )
        assert ret.status_code == http_status.HTTP_400_BAD_REQUEST
        assert ret.json['title'] == "Problem creating bucket 'valid-bucket-name'"
        assert 'BucketAlreadyExists' in ret.json['message']


class TestS3Utils:
    """Pure unit tests for utility functions — no DB required."""

    def test_owner_from_dict_without_display_name(self):
        from addons.s3.utils import Owner
        owner = Owner.from_dict({'ID': 'owner-id'})
        assert owner.id == 'owner-id'
        assert owner.display_name == 'owner-id'

    # G7: bucket_exists with empty name → False (early exit, no S3 call)
    def test_bucket_exists_empty_name(self):
        from addons.s3.utils import bucket_exists
        assert bucket_exists('key', 'secret', '') is False

    # G8: can_list(None, None) → False (early exit, no S3 call)
    def test_can_list_no_keys(self):
        from addons.s3.utils import can_list
        assert can_list(None, None) is False

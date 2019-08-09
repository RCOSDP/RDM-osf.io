# -*- coding: utf-8 -*-

from boxsdk import Client as BoxClient, OAuth2
from boxsdk.exception import BoxAPIException
from furl import furl
import httplib
import requests
import os
import owncloud

from addons.googledrive.client import GoogleDriveClient
from addons.osfstorage.models import Region
from addons.box import settings as box_settings
from addons.owncloud import settings as owncloud_settings
from addons.nextcloud import settings as nextcloud_settings
from addons.s3 import utils as s3_utils
from addons.s3compat import utils as s3compat_utils
from addons.swift import utils as swift_utils
from addons.swift.provider import SwiftProvider
from framework.exceptions import HTTPError
from website import settings as osf_settings
from osf.models.external import ExternalAccountTemporary, ExternalAccount
import datetime


providers = None
enabled_providers_list = [
    's3', 'box', 'googledrive', 'osfstorage',
    'nextcloud', 'swift', 'owncloud', 's3compat'
]

def get_providers():
    provider_list = []
    for provider in osf_settings.ADDONS_AVAILABLE:
        if 'storage' in provider.categories and provider.short_name in enabled_providers_list:
            provider.icon_url_admin = \
                '/custom_storage_location/icon/{}/comicon.png'.format(provider.short_name)
            provider.modal_path = get_modal_path(provider.short_name)
            provider_list.append(provider)
    provider_list.sort(key=lambda x: x.full_name.lower())
    return provider_list

def get_addon_by_name(addon_short_name):
    """get Addon object from Short Name."""
    for addon in osf_settings.ADDONS_AVAILABLE:
        if addon.short_name == addon_short_name:
            return addon
    return None

def get_modal_path(short_name):
    base_path = os.path.join('rdm_custom_storage_location', 'providers')
    return os.path.join(base_path, '{}_modal.html'.format(short_name))

def get_oauth_info_notification(institution_id, provider_short_name):
    temp_external_account = ExternalAccountTemporary.objects.filter(
        _id=institution_id, provider=provider_short_name
    ).first()
    if temp_external_account and \
            temp_external_account.modified >= datetime.datetime.now(
                temp_external_account.modified.tzinfo
            ) - datetime.timedelta(seconds=60 * 30):
        return {
            'display_name': temp_external_account.display_name,
            'oauth_key': temp_external_account.oauth_key,
            'provider': temp_external_account.provider,
            'provider_id': temp_external_account.provider_id,
            'provider_name': temp_external_account.provider_name,
        }

def update_storage(institution_id, storage_name, wb_credentials, wb_settings):
    default_region = Region.objects.first()
    Region.objects.update_or_create(
        _id=institution_id,
        defaults={
            'name': storage_name,
            'waterbutler_credentials': wb_credentials,
            'waterbutler_url': default_region.waterbutler_url,
            'mfr_url': default_region.mfr_url,
            'waterbutler_settings': wb_settings
        }
    )

def transfer_to_external_account(user, institution_id, provider_short_name):
    temp_external_account = ExternalAccountTemporary.objects.filter(_id=institution_id, provider=provider_short_name).first()
    account, _ = ExternalAccount.objects.get_or_create(
        provider=temp_external_account.provider,
        provider_id=temp_external_account.provider_id,
    )

    # ensure that provider_name is correct
    account.provider_name = temp_external_account.provider_name
    # required
    account.oauth_key = temp_external_account.oauth_key
    # only for OAuth1
    account.oauth_secret = temp_external_account.oauth_secret
    # only for OAuth2
    account.expires_at = temp_external_account.expires_at
    account.refresh_token = temp_external_account.refresh_token
    account.date_last_refreshed = temp_external_account.date_last_refreshed
    # additional information
    account.display_name = temp_external_account.display_name
    account.profile_url = temp_external_account.profile_url
    account.save()

    # add it to the user's list of ``ExternalAccounts``
    if not user.external_accounts.filter(id=account.id).exists():
        user.external_accounts.add(account)
        user.save()
    return account

def test_s3_connection(access_key, secret_key):
    """Verifies new external account credentials and adds to user's list"""
    if not (access_key and secret_key):
        return ({
            'message': 'All the fields above are required.'
        }, httplib.BAD_REQUEST)
    user_info = s3_utils.get_user_info(access_key, secret_key)
    if not user_info:
        return ({
            'message': 'Unable to access account.\n'
            'Check to make sure that the above credentials are valid,'
            'and that they have permission to list buckets.'
        }, httplib.BAD_REQUEST)

    if not s3_utils.can_list(access_key, secret_key):
        return ({
            'message': 'Unable to list buckets.\n'
            'Listing buckets is required permission that can be changed via IAM'
        }, httplib.BAD_REQUEST)
    s3_response = {
        'id': user_info.id,
        'display_name': user_info.display_name,
        'Owner': user_info.Owner,
    }

    return ({
        'message': 'Credentials are valid',
        'data': s3_response
    }, httplib.OK)

def test_s3compat_connection(host_url, access_key, secret_key):
    host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    if not (host and access_key and secret_key):
        return ({
            'message': 'All the fields above are required.'
        }, httplib.BAD_REQUEST)

    user_info = s3compat_utils.get_user_info(host, access_key, secret_key)
    if not user_info:
        return {
            'message': 'Unable to access account.\n'
            'Check to make sure that the above credentials are valid, '
            'and that they have permission to list buckets.'
        }, httplib.BAD_REQUEST

    if not s3compat_utils.can_list(host, access_key, secret_key):
        return {
            'message': 'Unable to list buckets.\n'
            'Listing buckets is required permission that can be changed via IAM'
        }, httplib.BAD_REQUEST

    return ({
        'message': 'Credentials are valid',
        'data': {
            'id': user_info.id,
            'display_name': user_info.display_name,
        }
    }, httplib.OK)

def test_googledrive_connection(institution_id, folder_id):
    if not folder_id:
        return ({
            'message': 'Folder ID is missing.'
        }, httplib.BAD_REQUEST)

    try:
        access_token = ExternalAccountTemporary.objects.get(
            _id=institution_id, provider='googledrive'
        ).oauth_key
    except ExternalAccountTemporary.DoesNotExist:
        return ({
            'message': 'Oauth data was not found. Please reload the page and try again.'
        }, httplib.BAD_REQUEST)

    client = GoogleDriveClient(access_token)

    try:
        client.folders(folder_id)
    except HTTPError:
        return ({
            'message': 'Invalid folder ID.'
        }, httplib.BAD_REQUEST)

    return ({
        'message': 'Credentials are valid'
    }, httplib.OK)

def test_box_connection(institution_id, folder_id):
    if not folder_id:
        return ({
            'message': 'Folder ID is missing.'
        }, httplib.BAD_REQUEST)

    try:
        access_token = ExternalAccountTemporary.objects.get(
            _id=institution_id, provider='box'
        ).oauth_key
    except ExternalAccountTemporary.DoesNotExist:
        return ({
            'message': 'Oauth data was not found. Please reload the page and try again.'
        }, httplib.BAD_REQUEST)

    oauth = OAuth2(
        client_id=box_settings.BOX_KEY,
        client_secret=box_settings.BOX_SECRET,
        access_token=access_token
    )
    client = BoxClient(oauth)

    try:
        client.folder(folder_id).get()
    except BoxAPIException:
        return ({
            'message': 'Invalid folder ID.'
        }, httplib.BAD_REQUEST)

    return ({
        'message': 'Credentials are valid'
    }, httplib.OK)

def test_owncloud_connection(host_url, username, password, folder, provider):
    """ This method is valid for both ownCloud and Nextcloud """
    provider_name = None
    provider_setting = None
    if provider == 'owncloud':
        provider_name = 'ownCloud'
        provider_setting = owncloud_settings
    elif provider == 'nextcloud':
        provider_name = 'Nextcloud'
        provider_setting = nextcloud_settings

    host = furl()
    host.host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    host.scheme = 'https'

    try:
        oc = owncloud.Client(host.url, verify_certs=provider_setting.USE_SSL)
        oc.login(username, password)
        oc.logout()
    except requests.exceptions.ConnectionError:
        return ({
            'message': 'Invalid {} server.'.format(provider_name) + host.url
        }, httplib.BAD_REQUEST)
    except owncloud.owncloud.HTTPResponseError:
        return ({
            'message': '{} Login failed.'.format(provider_name)
        }, httplib.UNAUTHORIZED)

    return ({
        'message': 'Credentials are valid'
    }, httplib.OK)

def test_swift_connection(auth_version, auth_url, access_key, secret_key, tenant_name,
                          user_domain_name, project_domain_name, folder, container):
    """Verifies new external account credentials and adds to user's list"""
    if not (auth_version and auth_url and access_key and secret_key and tenant_name and folder and container):
        return ({
            'message': 'All the fields above are required.'
        }, httplib.BAD_REQUEST)
    if auth_version == '3' and not user_domain_name:
        return ({
            'message': 'The field `user_domain_name` is required when you choose identity V3.'
        }, httplib.BAD_REQUEST)
    if auth_version == '3' and not project_domain_name:
        return ({
            'message': 'The field `project_domain_name` is required when you choose identity V3.'
        }, httplib.BAD_REQUEST)

    user_info = swift_utils.get_user_info(auth_version, auth_url, access_key,
                                    user_domain_name, secret_key, tenant_name,
                                    project_domain_name)

    if not user_info:
        return ({
            'message': 'Unable to access account.\n'
            'Check to make sure that the above credentials are valid, '
            'and that they have permission to list containers.'
        }, httplib.BAD_REQUEST)

    if not swift_utils.can_list(auth_version, auth_url, access_key, user_domain_name,
                          secret_key, tenant_name, project_domain_name):
        return ({
            'message': 'Unable to list containers.\n'
            'Listing containers is required permission.'
        }, httplib.BAD_REQUEST)

    provider = SwiftProvider(account=None, auth_version=auth_version,
                             auth_url=auth_url, tenant_name=tenant_name,
                             project_domain_name=project_domain_name,
                             username=access_key,
                             user_domain_name=user_domain_name,
                             password=secret_key)
    swift_response = {
        'id': provider.account.id,
        'display_name': provider.account.display_name,
    }
    return ({
        'message': 'Credentials are valid',
        'data': swift_response
    }, httplib.OK)

def save_s3_credentials(institution_id, storage_name, access_key, secret_key, bucket):
    test_connection_result = test_s3_connection(access_key, secret_key)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    wb_credentials = {
        'storage': {
            'access_key': access_key,
            'secret_key': secret_key,
        },
    }
    wb_settings = {
        'storage': {
            'folder': {
                'encrypt_uploads': True,
            },
            'bucket': bucket,
            'provider': 's3',
        },
    }

    update_storage(institution_id, storage_name, wb_credentials, wb_settings)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_s3compat_credentials(institution_id, storage_name, host_url, access_key, secret_key,
                              bucket):

    test_connection_result = test_s3compat_connection(host_url, access_key, secret_key)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    host = host_url.rstrip('/').replace('https://', '').replace('http://', '')

    wb_credentials = {
        'storage': {
            'access_key': access_key,
            'secret_key': secret_key,
            'host': host,
        }
    }
    wb_settings = {
        'storage': {
            'folder': {
                'encrypt_uploads': True,
            },
            'bucket': bucket,
            'provider': 's3compat',
        }
    }

    update_storage(institution_id, storage_name, wb_credentials, wb_settings)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_box_credentials(user, storage_name, folder_id):
    institution_id = user.affiliated_institutions.first()._id

    test_connection_result = test_box_connection(institution_id, folder_id)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    account = transfer_to_external_account(user, institution_id, 'box')
    wb_credentials = {
        'storage': {
            'token': account.oauth_key,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': folder_id,
            'provider': 'box',
        }
    }
    update_storage(institution_id, storage_name, wb_credentials, wb_settings)
    ExternalAccountTemporary.objects.filter(_id=institution_id).delete()

    return ({
        'message': 'OAuth was set successfully'
    }, httplib.OK)

def save_googledrive_credentials(user, storage_name, folder_id):
    institution_id = user.affiliated_institutions.first()._id

    test_connection_result = test_googledrive_connection(institution_id, folder_id)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    account = transfer_to_external_account(user, institution_id, 'googledrive')
    ExternalAccountTemporary.objects.filter(_id=institution_id).delete()
    wb_credentials = {
        'storage': {
            'token': account.oauth_key,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': {
                'id': folder_id
            },
            'provider': 'googledrive',
        }
    }
    update_storage(institution_id, storage_name, wb_credentials, wb_settings)

    return ({
        'message': 'OAuth was set successfully'
    }, httplib.OK)

def save_nextcloud_credentials(institution_id, storage_name, host_url, username, password,
                              folder, provider):
    test_connection_result = test_owncloud_connection(host_url, username, password, folder,
                                                      provider)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    host = furl()
    host.host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    host.scheme = 'https'

    wb_credentials = {
        'storage': {
            'host': host.url,
            'username': username,
            'password': password,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': '/{}/'.format(folder.strip('/')),
            'verify_ssl': False,
            'provider': provider
        },
    }

    update_storage(institution_id, storage_name, wb_credentials, wb_settings)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_osfstorage_credentials(institution_id):
    Region.objects.filter(_id=institution_id).delete()
    return ({
        'message': 'NII storage was set successfully'
    }, httplib.OK)

def save_swift_credentials(institution_id, storage_name, auth_version, access_key, secret_key,
                           tenant_name, user_domain_name, project_domain_name, auth_url,
                           folder, container):

    test_connection_result = test_swift_connection(auth_version, auth_url, access_key, secret_key,
        tenant_name, user_domain_name, project_domain_name, folder, container)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    wb_credentials = {
        'storage': {
            'auth_version': auth_version,
            'username': access_key,
            'password': secret_key,
            'tenant_name': tenant_name,
            'user_domain_name': user_domain_name,
            'project_domain_name': project_domain_name,
            'auth_url': auth_url,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': folder,
            'container': container,
            'provider': 'swift',
        }

    }

    update_storage(institution_id, storage_name, wb_credentials, wb_settings)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

def save_owncloud_credentials(institution_id, storage_name, host_url, username, password,
                              folder, provider):
    test_connection_result = test_owncloud_connection(host_url, username, password, folder,
                                                      provider)
    if test_connection_result[1] != httplib.OK:
        return test_connection_result

    host = furl()
    host.host = host_url.rstrip('/').replace('https://', '').replace('http://', '')
    host.scheme = 'https'

    wb_credentials = {
        'storage': {
            'host': host.url,
            'username': username,
            'password': password,
        },
    }
    wb_settings = {
        'storage': {
            'bucket': '',
            'folder': '/{}/'.format(folder.strip('/')),
            'verify_ssl': True,
            'provider': provider
        },
    }

    update_storage(institution_id, storage_name, wb_credentials, wb_settings)

    return ({
        'message': 'Saved credentials successfully!!'
    }, httplib.OK)

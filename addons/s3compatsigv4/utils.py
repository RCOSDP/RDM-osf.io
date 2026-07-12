# -*- coding: utf-8 -*-
import re
import logging
from rest_framework import status as http_status

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from botocore.client import Config

import addons.s3compatsigv4.settings as settings
from framework.exceptions import HTTPError
from addons.base.exceptions import InvalidAuthError, InvalidFolderError

logger = logging.getLogger(__name__)


def connect_s3compatsigv4(host=None, access_key=None, secret_key=None, node_settings=None):
    """Helper to build an S3 client object using boto3 with Signature V4

    Args:
        host: S3 compatible storage host (e.g., 's3.amazonaws.com' or 'storage.example.com')
        access_key: AWS access key ID
        secret_key: AWS secret access key
        node_settings: NodeSettings object containing external account info

    Returns:
        boto3.client: Configured S3 client with Signature V4
    """
    if node_settings is not None:
        if node_settings.external_account is not None:
            host = node_settings.external_account.provider_id.split('\t')[0]
            access_key = node_settings.external_account.oauth_key
            secret_key = node_settings.external_account.oauth_secret

    if not all([host, access_key, secret_key]):
        raise ValueError('Host, access_key, and secret_key are required')

    # Parse host and port
    port = 443
    use_ssl = True
    m = re.match(r'^(.+):([0-9]+)$', host)
    if m is not None:
        host = m.group(1)
        port = int(m.group(2))
        use_ssl = (port == 443)

    # Construct endpoint URL
    protocol = 'https' if use_ssl else 'http'
    endpoint_url = f'{protocol}://{host}:{port}'

    # Configure boto3 client with Signature V4
    config = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'auto'},  # Use auto-style addressing for compatibility
    )

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
            config=config,
            use_ssl=use_ssl,
            verify=use_ssl,  # Verify SSL certificates in production
        )
        return s3_client
    except Exception as e:
        logger.error(f'Failed to create S3 client: {e}')
        raise InvalidAuthError(f'Failed to connect to S3: {str(e)}')


def get_bucket_names(node_settings):
    """Get list of all bucket names accessible by the user

    Args:
        node_settings: NodeSettings object

    Returns:
        list: List of bucket names
    """
    try:
        s3_client = connect_s3compatsigv4(node_settings=node_settings)
        response = s3_client.list_buckets()
        return [bucket['Name'] for bucket in response.get('Buckets', [])]
    except NoCredentialsError:
        raise HTTPError(http_status.HTTP_403_FORBIDDEN)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 500)
        logger.error(f'Failed to list buckets: {error_code}')
        raise HTTPError(status_code)
    except Exception as e:
        logger.error(f'Unexpected error listing buckets: {e}')
        raise HTTPError(http_status.HTTP_500_INTERNAL_SERVER_ERROR)


def find_service_by_host(host):
    """Find service configuration by host

    Args:
        host: Host name

    Returns:
        dict: Service configuration

    Raises:
        KeyError: If service not found
    """
    services = [s for s in settings.AVAILABLE_SERVICES if s['host'] == host]
    if len(services) == 0:
        raise KeyError(f'Service not found for host: {host}')
    return services[0]


def validate_bucket_location(node_settings, location):
    """Validate that the bucket location is supported by the service

    Args:
        node_settings: NodeSettings object
        location: Bucket location/region

    Returns:
        bool: True if valid, False otherwise
    """
    if location == '':
        return True

    try:
        host = node_settings.external_account.provider_id.split('\t')[0]
        service = find_service_by_host(host)
        return location in service.get('bucketLocations', [])
    except (KeyError, AttributeError) as e:
        logger.warning(f'Failed to validate bucket location: {e}')
        return False


def validate_bucket_name(name):
    """Validate bucket name according to S3 naming rules

    Rules:
    - Between 3 and 63 characters long
    - Lowercase letters, numbers, hyphens, and periods only
    - Must start and end with letter or number
    - Cannot be formatted as an IP address

    Args:
        name: Bucket name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not name or not isinstance(name, str):
        return False

    label = r'[a-z0-9]+(?:[a-z0-9\-]*[a-z0-9])?'
    validate_name = re.compile('^' + label + '(?:\\.' + label + ')*$')
    is_ip_address = re.compile(r'^[0-9]+(?:\.[0-9]+){3}$')

    return (
        3 <= len(name) <= 63 and
        bool(validate_name.match(name)) and
        not bool(is_ip_address.match(name))
    )


def create_bucket(node_settings, bucket_name, location=''):
    """Create a new bucket

    Args:
        node_settings: NodeSettings object
        bucket_name: Name for the new bucket
        location: Bucket location/region (optional)

    Returns:
        dict: Response from create_bucket operation
    """
    try:
        s3_client = connect_s3compatsigv4(node_settings=node_settings)

        if location and location != '':
            create_bucket_config = {'LocationConstraint': location}
            response = s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration=create_bucket_config
            )
        else:
            response = s3_client.create_bucket(Bucket=bucket_name)

        return response
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f'Failed to create bucket {bucket_name}: {error_code}')
        raise
    except Exception as e:
        logger.error(f'Unexpected error creating bucket: {e}')
        raise


def bucket_exists(host, access_key, secret_key, bucket_name):
    """Test if a bucket exists and is accessible

    Args:
        host: S3 compatible storage host
        access_key: AWS access key ID
        secret_key: AWS secret access key
        bucket_name: Bucket name to check

    Returns:
        bool: True if bucket exists and is accessible, False otherwise
    """
    if not bucket_name:
        return False

    try:
        s3_client = connect_s3compatsigv4(host, access_key, secret_key)
        s3_client.head_bucket(Bucket=bucket_name)
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        # 301/302 redirects indicate bucket exists but in different region
        if error_code in ['301', '302', 'PermanentRedirect', 'TemporaryRedirect']:
            return True
        logger.debug(f'Bucket {bucket_name} not accessible: {error_code}')
        return False
    except Exception as e:
        logger.error(f'Error checking bucket existence: {e}')
        return False


def can_list(host, access_key, secret_key):
    """Check if user can list all accessible buckets

    Args:
        host: S3 compatible storage host
        access_key: AWS access key ID
        secret_key: AWS secret access key

    Returns:
        bool: True if user can list buckets, False otherwise
    """
    if not all([host, access_key, secret_key]):
        return False

    try:
        s3_client = connect_s3compatsigv4(host, access_key, secret_key)
        s3_client.list_buckets()
        return True
    except (ClientError, NoCredentialsError, BotoCoreError) as e:
        logger.debug(f'Cannot list buckets: {e}')
        return False
    except Exception as e:
        logger.error(f'Unexpected error checking list permission: {e}')
        return False


def get_user_info(host, access_key, secret_key):
    """Get S3 user information

    Args:
        host: S3 compatible storage host
        access_key: AWS access key ID
        secret_key: AWS secret access key

    Returns:
        dict: User info with 'DisplayName' and 'ID', or None if unavailable
    """
    if not all([access_key, secret_key]):
        return None

    try:
        s3_client = connect_s3compatsigv4(host, access_key, secret_key)
        response = s3_client.list_buckets()
        owner = response.get('Owner', {})

        if owner:
            return {
                'display_name': owner.get('DisplayName', ''),
                'id': owner.get('ID', '')
            }
        return None
    except (ClientError, NoCredentialsError) as e:
        logger.error(f'Cannot get user info: {e}')
        return None
    except Exception as e:
        logger.error(f'Unexpected error getting user info: {e}')
        return None


def get_bucket_location_or_error(host, access_key, secret_key, bucket_name):
    """Get bucket location/region or raise appropriate error

    Args:
        host: S3 compatible storage host
        access_key: AWS access key ID
        secret_key: AWS secret access key
        bucket_name: Bucket name

    Returns:
        str: Bucket location/region

    Raises:
        InvalidAuthError: If authentication fails
        InvalidFolderError: If bucket doesn't exist or isn't accessible
    """
    try:
        s3_client = connect_s3compatsigv4(host, access_key, secret_key)
    except Exception as e:
        logger.error(f'Failed to connect: {e}')
        raise InvalidAuthError('Invalid credentials or connection failed')

    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.error(f'Bucket {bucket_name} not accessible: {error_code}')
        raise InvalidFolderError(f'Bucket not found or not accessible: {bucket_name}')

    try:
        # Get bucket location
        response = s3_client.get_bucket_location(Bucket=bucket_name)
        bucket_location = response.get('LocationConstraint', '')

        # AWS returns None for us-east-1, convert to empty string
        if bucket_location is None:
            bucket_location = ''

        return bucket_location
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.warning(f'Could not get bucket location for {bucket_name}: {error_code}')
        # Return empty string as default location if we can't determine it
        return ''
    except Exception as e:
        logger.error(f'Unexpected error getting bucket location: {e}')
        return ''

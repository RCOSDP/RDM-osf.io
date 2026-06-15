# -*- coding: utf-8 -*-
from nose.tools import (assert_equals, assert_true, assert_false)

from addons.base.tests.base import OAuthAddonTestCaseMixin, AddonTestCase
from addons.s3compatsigv4.tests.factories import S3CompatSigV4AccountFactory
from addons.s3compatsigv4.provider import S3CompatSigV4Provider
from addons.s3compatsigv4.serializer import S3CompatSigV4Serializer
from addons.s3compatsigv4 import utils

class S3CompatSigV4AddonTestCase(OAuthAddonTestCaseMixin, AddonTestCase):

    ADDON_SHORT_NAME = 's3compatsigv4'
    ExternalAccountFactory = S3CompatSigV4AccountFactory
    Provider = S3CompatSigV4Provider
    Serializer = S3CompatSigV4Serializer
    client = None
    folder = {
        'path': 'bucket',
        'name': 'bucket',
        'id': 'bucket'
    }

    def test_https(self):
        connection = utils.connect_s3compatsigv4(host='securehost',
                                            access_key='a',
                                            secret_key='s')
        assert_equals(connection.meta.endpoint_url, 'https://securehost:443')

        connection = utils.connect_s3compatsigv4(host='securehost:443',
                                            access_key='a',
                                            secret_key='s')
        assert_equals(connection.meta.endpoint_url, 'https://securehost:443')

    def test_http(self):
        connection = utils.connect_s3compatsigv4(host='normalhost:80',
                                            access_key='a',
                                            secret_key='s')
        assert_equals(connection.meta.endpoint_url, 'http://normalhost:80')

        connection = utils.connect_s3compatsigv4(host='normalhost:8080',
                                            access_key='a',
                                            secret_key='s')
        assert_equals(connection.meta.endpoint_url, 'http://normalhost:8080')

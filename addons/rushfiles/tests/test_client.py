import re
import unittest

import mock
from nose.tools import assert_equal  # noqa (PEP8 asserts)
from addons.rushfiles.client import RushFilesClient
import jwt
import copy

class FakeSharesResponse():
    def __init__(self, domain = 'example.com'):
        self.response =  {
        'Data': [
            {
                'Id': 'fake',
                'Name': 'fakeName',
                'CompanyId': 'fakeCompanyId_'+domain
            }
        ],
        'Message': 'string',
        'ResponseInfo': {
            'ResponseCode': 1000,
            'Reference': 'string'
        }
    }

    def json(self):
        return copy.deepcopy(self.response)

class FakeCompaniesResponse():
    def __init__(self, domain = 'example.com'):
        self.response =  {
        'Data': [
            {
                'Id': 'fakeCompanyId_'+domain,
                'Name': 'fakeCompanyName_'+domain
            }
        ],
        'Message': 'string',
        'ResponseInfo': {
            'ResponseCode': 1000,
            'Reference': 'string'
        }
    }

    def json(self):
        return copy.deepcopy(self.response)

def args_based_response(method, url, **kwargs):
    domain = re.findall(r'clientgateway.(.*)/api', url)[0]
    if url.endswith('shares'):
        return FakeSharesResponse(domain)
    else:
        return FakeCompaniesResponse(domain)

class TestClient(unittest.TestCase):

    def setUp(self):
        super(TestClient, self).setUp()
        self.client = RushFilesClient()

    @mock.patch.object(jwt, 'decode')
    @mock.patch.object(RushFilesClient, '_make_request')
    def test_shares_only_primary_domain(self, mock_response, mock_access_token):
        mock_access_token.return_value = {
            'primary_domain': 'fake.net',
        }
        mock_response.side_effect = args_based_response
        res = self.client.shares('fakeId')

        assert_equal(len(res), 1)
        assert_equal(res[0]['Id'], 'fake@fake.net')
        assert_equal(res[0]['Name'], 'fakeName @ fakeCompanyName_fake.net')

    @mock.patch.object(jwt, 'decode')
    @mock.patch.object(RushFilesClient, '_make_request')
    def test_shares_one_domain(self,mock_response, mock_payload):
        mock_payload.return_value = {
            'primary_domain': 'fake.net',
            'domains': 'fake.com'
        }
        mock_response.side_effect = args_based_response
        res = self.client.shares('fakeId')

        assert_equal(len(res), 2)
        assert_equal(res[0]['Id'], 'fake@fake.com')
        assert_equal(res[0]['Name'], 'fakeName @ fakeCompanyName_fake.com')

    @mock.patch.object(jwt, 'decode')
    @mock.patch.object(RushFilesClient, '_make_request')
    def test_shares_some_domains(self,mock_response, mock_payload):
        mock_payload.return_value = {
            'primary_domain': 'fake.net',
            'domains': [
                'fake.com',
                'fake.jp'
            ]
        }
        mock_response.side_effect = args_based_response
        res = self.client.shares('fakeId')

        assert_equal(len(res), 3)
        assert_equal(res[1]['Id'], 'fake@fake.jp')
        assert_equal(res[1]['Name'], 'fakeName @ fakeCompanyName_fake.jp')

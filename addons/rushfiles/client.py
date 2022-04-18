# -*- coding: utf-8 -*-
from website.util.client import BaseClient

import jwt

class RushFilesAuthClient(BaseClient):
    def userinfo(self, access_token, user_main_domain):
        '''
        Fetch user profile from GET /api/client/fullprofile
        '''
        res = self._make_request(
            'GET',
            self._build_url('https://clientgateway.' + user_main_domain, 'api', 'client', 'fullprofile'),
            headers={'Authorization': 'Bearer ' + access_token},
            params={'tick': 1, 'api': 1, 'associationRequired': False},
            expects=(200, )
        ).json()

        return res['Data']


class RushFilesClient(BaseClient):
    def __init__(self, access_token=None):
        self.access_token = access_token

    @property
    def _default_headers(self):
        if self.access_token:
            return {'authorization': 'Bearer {}'.format(self.access_token)}
        return {}

    def shares(self, user_id):
        '''
        Fetch share list from https://clientgateway.rushfiles.com/swagger/ui/index#!/User/User_GetUserShares
        '''
        domain_list = []
        payload = jwt.decode(self.access_token, verify=False)

        domain_list.append(payload['primary_domain'])

        if 'domains' in payload:
            if type(payload['domains']) is str:
                domain_list.append(payload['domains'])
            else:
                for domain in payload['domains']:
                    domain_list.append(domain)

        share_list = []

        for domain in domain_list:
            api_base_domain = 'https://clientgateway.' + domain

            res = self._make_request(
                'GET',
                self._build_url(api_base_domain, 'api', 'users', user_id, 'shares'),
                expects=(200, )
            ).json()

            shares = res['Data']

            for share in shares:
                share['Id'] = share['Id'] + '@' + domain
                share_list.append(share)

        return share_list

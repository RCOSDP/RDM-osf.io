from addons.microsoftteams.serializer import MicrosoftTeamsSerializer
from addons.microsoftteams import SHORT_NAME, FULL_NAME
from addons.microsoftteams import settings
from oauthlib.common import generate_token
from website.util import web_url_for
import urllib.parse
from framework.sessions import session
from osf.models.external import ExternalProvider
import requests
import logging
logger = logging.getLogger(__name__)

OAUTH2 = 2

class MicrosoftTeamsProvider(ExternalProvider):
    name = FULL_NAME
    short_name = SHORT_NAME
    serializer = MicrosoftTeamsSerializer
    client_id = settings.MICROSOFT_365_KEY
    client_secret = settings.MICROSOFT_365_SECRET
    auth_url_base = '{}{}{}'.format(settings.MICROSOFT_ONLINE_BASE_URL, settings.MICROSOFT_TENANT, '/oauth2/v2.0/authorize')
    callback_url = '{}{}{}'.format(settings.MICROSOFT_ONLINE_BASE_URL, settings.MICROSOFT_TENANT, '/oauth2/v2.0/token')
    auto_refresh_url = callback_url
    refresh_time = settings.REFRESH_TIME
    expiry_time = settings.EXPIRY_TIME

    def handle_callback(self, response):
        url = '{}{}'.format(settings.MICROSOFT_GRAPH_API_BASE_URL, 'v1.0/me')
        requestToken = 'Bearer ' + response['access_token']
        requestHeaders = {
            'Authorization': requestToken,
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=requestHeaders, timeout=60)
        info = response.json()
        return {
            'provider_id': info['id'],
            'display_name': '{}({})'.format(info['mail'], info['displayName'])
        }

    def fetch_access_token(self, force_refresh=False):
        refreshed = self.refresh_oauth_key(force=force_refresh)
        logger.info('{} refresh_oauth_key returns {}'.format(settings.MICROSOFT_TEAMS, refreshed))
        return self.account.oauth_key

    def get_authorization_url(self, client_id):
        # create a dict on the session object if it's not already there
        if session.data.get('oauth_states') is None:
            session.data['oauth_states'] = {}

        assert self._oauth_version == OAUTH2

        response_type = 'code'
        response_mode = 'query'
        redirect_uri = web_url_for(
            'oauth_callback',
            service_name=self.short_name,
            _absolute=True
        )
        redirect_uri_encoded = urllib.parse.quote(redirect_uri, safe='*')
        scope_encoded = urllib.parse.quote(settings.MICROSOFT_API_SCOPE, safe='*')
        state = generate_token()

        oauth_authorization_url = '{}?client_id={}&response_type={}&redirect_uri={}&response_mode={}&scope={}&state={}'.format(self.auth_url_base, client_id, response_type, redirect_uri_encoded, response_mode, scope_encoded, state)

        # save state token to the session for confirmation in the callback
        session.data['oauth_states'][self.short_name] = {'state': state}

        session.save()
        return oauth_authorization_url

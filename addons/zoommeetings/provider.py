import requests
from addons.zoommeetings.serializer import ZoomMeetingsSerializer
from addons.zoommeetings import SHORT_NAME, FULL_NAME
from oauthlib.common import generate_token
from website.util import web_url_for
import urllib.parse
from framework.sessions import session
from osf.models.external import ExternalProvider
from addons.zoommeetings import settings
import logging
logger = logging.getLogger(__name__)

OAUTH2 = 2

class ZoomMeetingsProvider(ExternalProvider):
    name = FULL_NAME
    short_name = SHORT_NAME
    serializer = ZoomMeetingsSerializer
    client_id = settings.ZOOM_MEETINGS_KEY
    client_secret = settings.ZOOM_MEETINGS_SECRET
    auth_url_base = '{}{}'.format(settings.ZOOM_BASE_URL, 'oauth/authorize')
    callback_url = '{}{}'.format(settings.ZOOM_BASE_URL, 'oauth/token')
    auto_refresh_url = callback_url
    refresh_time = settings.REFRESH_TIME
    expiry_time = settings.EXPIRY_TIME

    def handle_callback(self, response):
        url = '{}{}'.format(settings.ZOOM_API_BASE_URL, 'v2/users/me')
        requestToken = 'Bearer ' + response['access_token']
        requestHeaders = {
            'Authorization': requestToken,
            'Content-Type': 'application/json'
        }
        response = requests.get(url, headers=requestHeaders, timeout=60)
        info = response.json()
        return {
            'provider_id': info['id'],
            'display_name': '{}({} {})'.format(info['email'], info['first_name'], info['last_name'])
        }

    def fetch_access_token(self, force_refresh=False):
        refreshed = self.refresh_oauth_key(force=force_refresh)
        logger.info('{} refresh_oauth_key returns {}'.format(settings.ZOOM_MEETINGS, refreshed))
        return self.account.oauth_key

    def get_authorization_url(self, client_id):
        # create a dict on the session object if it's not already there
        if session.data.get('oauth_states') is None:
            session.data['oauth_states'] = {}

        assert self._oauth_version == OAUTH2

        response_type = 'code'
        redirect_uri = web_url_for(
            'oauth_callback',
            service_name=self.short_name,
            _absolute=True
        )
        redirect_uri_encoded = urllib.parse.quote(redirect_uri, safe='*')
        state = generate_token()

        oauth_authorization_url = '{}?response_type={}&client_id={}&redirect_uri={}&state={}'.format(self.auth_url_base, response_type, client_id, redirect_uri_encoded, state)

        # save state token to the session for confirmation in the callback
        session.data['oauth_states'][self.short_name] = {'state': state}

        session.save()
        return oauth_authorization_url

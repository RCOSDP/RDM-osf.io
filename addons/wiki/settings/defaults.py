import datetime
import os
import pytz

from website import settings

SHAREJS_HOST = 'localhost'
SHAREJS_PORT = 7007
SHAREJS_URL = '{}:{}'.format(SHAREJS_HOST, SHAREJS_PORT)

Y_WEBSOCKET_SECRET = os.environ.get('Y_WEBSOCKET_SECRET', '')
Y_WEBSOCKET_JWT_ALGORITHM = 'HS256'
# Token validity for WebSocket connection (seconds). Not enforced after connection is established.
Y_WEBSOCKET_TOKEN_TTL = int(os.environ.get('Y_WEBSOCKET_TOKEN_TTL', 8 * 60 * 60))

Y_WEBSOCKET_HOST = 'localhost'
Y_WEBSOCKET_PORT = 1234
Y_WEBSOCKET_URL = '{}:{}'.format(Y_WEBSOCKET_HOST, Y_WEBSOCKET_PORT)

SHAREJS_DB_NAME = 'sharejs'
SHAREJS_DB_URL = os.environ.get('SHAREJS_DB_URL', 'mongodb://{}:{}/{}'.format(settings.DB_HOST, settings.DB_PORT, SHAREJS_DB_NAME))

# TODO: Change to release date for wiki change
WIKI_CHANGE_DATE = datetime.datetime.utcfromtimestamp(1423760098).replace(tzinfo=pytz.utc)

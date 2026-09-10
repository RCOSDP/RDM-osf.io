# -*- coding: utf-8 -*-
"""GakuNin RDM アクセスログ 操作者識別フィールド

各アクセスログに以下の 3 フィールドを追記し、Elasticsearch 上で
「未ログイン操作の区別」と「操作者の追跡」を可能にする。

    auth : 認証方式と結果          (必須)
    user : 認証済みユーザの GUID   (認証済みのみ。未認証時はキーを出さない)
    cred : 資格情報の識別子        (取得できた場合のみ)

cred の形式:
    Cookie  : "sess:<HMAC-SHA256(SALT, 'sess:' + osf_session._id)[:16]>"
    PAT     : "pat:<ApiOAuth2PersonalToken.pk>"        (連番。平文)
    OAuth2  : "oauth:<ApiOAuth2Application.client_id>" (平文)

osf_session._id は 24 桁 16 進 (bson.ObjectId) であり、SALT が既知でも
総当たりは不可能。よって SALT に秘匿性は要求されない。要求されるのは
「全ホスト・全ワーカプロセス間での一貫性」のみ。
"""

import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import sys

# ---------------------------------------------------------------------------
# auth の値域
# ---------------------------------------------------------------------------
AUTH_NONE = 'none'
AUTH_COOKIE_OK = 'cookie:ok'
AUTH_COOKIE_ANON = 'cookie:anon'        # セッションはあるが auth_user_id なし
AUTH_COOKIE_EXPIRED = 'cookie:expired'  # 署名は正当だが使えるセッションがない
AUTH_COOKIE_INVALID = 'cookie:invalid'  # itsdangerous 署名検証失敗
AUTH_PAT_OK = 'pat:ok'
AUTH_OAUTH_OK = 'oauth:ok'
AUTH_BEARER_UNKNOWN = 'bearer:unknown'  # CAS 認証済みだが PAT/OAuth2 判別不能
AUTH_BASIC_OK = 'basic:ok'
AUTH_BASIC_INVALID = 'basic:invalid'
AUTH_VIEWONLY_OK = 'viewonly:ok'
AUTH_UNKNOWN = 'unknown'


# ---------------------------------------------------------------------------
# ロガー
#
# RDM-osf.io は framework/logging でルートロガーに StreamHandler を
# 付けているだけで LOGGING dict を持たない。そのためここで専用ロガーを
# 組み立て、propagate=False でアプリログへの二重出力を防ぐ。
# ---------------------------------------------------------------------------
_LOG_PREFIX = 'RDM_ACCESS_LOG '

logger = logging.getLogger('rdm.accesslog')


def _init_logger():
    if getattr(logger, '_rdm_configured', False):
        return logger
    path = os.environ.get('RDM_ACCESS_LOG_PATH')
    if path:
        handler = logging.handlers.WatchedFileHandler(path)
    else:
        # 既定は stdout。既存のコンテナログ収集経路に載せる。
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger._rdm_configured = True
    return logger


# ---------------------------------------------------------------------------
# SALT
# ---------------------------------------------------------------------------
_SALT = None


def _get_salt():
    global _SALT
    if _SALT is not None:
        return _SALT

    env = os.environ.get('RDM_ACCESS_LOG_SALT')
    if env:
        _SALT = env.encode('utf-8')
        return _SALT

    # 既定: SECRET_KEY からの派生。全アプリホストで共有済みのため
    # 一貫性が自動的に担保され、新規の設定項目が不要。
    # HMAC 経由なので出力値から SECRET_KEY は復元できない。
    secret = None
    try:
        from website import settings as website_settings
        secret = getattr(website_settings, 'SECRET_KEY', None)
    except Exception:
        pass
    if not secret:
        logger.warning('rdm_access_log: SECRET_KEY unavailable; cred disabled')
        _SALT = b''
        return _SALT
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    _SALT = hmac.new(secret, b'rdm-access-log-salt-v1', hashlib.sha256).digest()
    return _SALT


# ---------------------------------------------------------------------------
# cred 生成
# ---------------------------------------------------------------------------
def session_cred(session_id):
    """osf_session._id から cred を生成する。逆引きは行わない。"""
    if not session_id:
        return None
    salt = _get_salt()
    if not salt:
        return None
    if isinstance(session_id, bytes):
        session_id = session_id.decode('utf-8', 'replace')
    digest = hmac.new(
        salt, ('sess:' + session_id).encode('utf-8'), hashlib.sha256,
    ).hexdigest()[:16]
    return 'sess:' + digest


def cookie_cred(cookie_val):
    """署名付き Cookie 値から cred を生成する。DB 参照なし。

    Returns:
        (cred, ok)  ok=False は署名検証失敗 (cookie:invalid)
    """
    if not cookie_val:
        return None, False
    try:
        import itsdangerous
        from website import settings
        from osf.utils.fields import ensure_str
        session_id = ensure_str(
            itsdangerous.Signer(settings.SECRET_KEY).unsign(cookie_val))
    except Exception:
        return None, False
    return session_cred(session_id), True


def bearer_cred(cas_resp):
    """CasResponse から (auth, cred) を判別して返す。

    OSFCASAuthentication は PAT と OAuth2 の両方を処理する。
    framework/auth/cas.py の _parse_profile() が
    attributes['accessToken'] に生アクセストークンを格納している。

    判別:
      1. osf_apioauth2personaltoken.token_id を索引検索 (unique=True)
         -> ヒットすれば PAT
      2. ミスすれば OAuth2 (developer app)。OAuth2 のアクセストークンは
         CAS 側にのみ存在し OSF の DB には保存されていないため、
         client_id は CAS レスポンスからのみ取得できる。
    """
    if cas_resp is None:
        return AUTH_BEARER_UNKNOWN, None

    attrs = getattr(cas_resp, 'attributes', None) or {}
    raw_token = attrs.get('accessToken')
    if not raw_token:
        return AUTH_BEARER_UNKNOWN, None

    try:
        from osf.models import ApiOAuth2PersonalToken
        pk = (ApiOAuth2PersonalToken.objects
              .filter(token_id=raw_token)
              .values_list('id', flat=True)
              .first())
    except Exception:
        logger.exception('rdm_access_log: PAT lookup failed')
        return AUTH_BEARER_UNKNOWN, None

    if pk is not None:
        return AUTH_PAT_OK, 'pat:{}'.format(pk)

    return AUTH_OAUTH_OK, 'oauth:{}'.format(_oauth_client_id(attrs) or '-')


# CAS の /oauth2/profile が client_id を返すかは環境依存。
# RDM_ACCESS_LOG_DEBUG_CAS_ATTRS=1 で属性キーを 1 度だけ出力し、
# 実環境で確認する (設計書 検証項目 V-3)。
_CAS_ATTR_KEYS_LOGGED = False
_CLIENT_ID_KEYS = ('clientId', 'client_id', 'accessTokenClientId', 'service')


def _oauth_client_id(attrs):
    global _CAS_ATTR_KEYS_LOGGED
    if os.environ.get('RDM_ACCESS_LOG_DEBUG_CAS_ATTRS') and not _CAS_ATTR_KEYS_LOGGED:
        _CAS_ATTR_KEYS_LOGGED = True
        logger.warning('rdm_access_log: CAS profile attribute keys = %s',
                       sorted(attrs.keys()))
    for key in _CLIENT_ID_KEYS:
        val = attrs.get(key)
        if val:
            return val
    return None


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------
def emit(auth, user=None, cred=None):
    """アクセスログ 1 行を JSON Lines で出力する。

    user は未認証時にキーごと省略する (null を入れない)。
    Elasticsearch の exists クエリで未認証を判別できるようにするため。

    この関数は例外を投げない。ログ出力の失敗がリクエスト処理を
    妨げてはならない。
    """
    try:
        rec = {'auth': auth or AUTH_UNKNOWN}
        if user:
            rec['user'] = user
        if cred:
            rec['cred'] = cred
        _init_logger().info(
            _LOG_PREFIX + json.dumps(rec, ensure_ascii=False, sort_keys=True))
    except Exception:
        try:
            logging.getLogger(__name__).exception('rdm_access_log: emit failed')
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 経路別の判定
# ---------------------------------------------------------------------------
def fields_for_flask(request, user_session):
    """OSF Flask (Web UI 経路) の (auth, user, cred) を返す。

    framework/sessions/before_request() の挙動に対応させている。

    NOTE: framework.sessions.session プロキシは get_session() 経由で
          セッションを **新規作成してしまう** ため使用しない。
          呼び出し側が sessions.get(...) の結果を渡すこと。
    """
    guid = None
    if user_session is not None:
        guid = (user_session.data or {}).get('auth_user_id')

    view_only = request.args.get('view_only')

    # Basic 認証 (before_request の request.authorization 分岐)
    if request.authorization:
        if guid:
            return AUTH_BASIC_OK, guid, None
        return AUTH_BASIC_INVALID, None, None

    from website import settings
    cookie_val = request.cookies.get(settings.COOKIE_NAME)

    if not cookie_val:
        if view_only:
            return AUTH_VIEWONLY_OK, None, None
        return AUTH_NONE, None, None

    cred, sig_ok = cookie_cred(cookie_val)
    if not sig_ok:
        return AUTH_COOKIE_INVALID, None, None

    if user_session is None:
        # before_request が set_session しなかった。
        # OSF_SESSION_TIMEOUT 超過、または osf_session に該当行なし
        # (throttle_period_expired(None) が True を返すため同じ枝に入る)。
        return AUTH_COOKIE_EXPIRED, None, cred

    if guid:
        return AUTH_COOKIE_OK, guid, cred

    # OSF 独自セッションは未認証状態でも作成される
    # (CSRF / view_only / 外部ID連携の途中状態など)。
    # 「Cookie がある = ログイン済み」ではない。
    if view_only:
        return AUTH_VIEWONLY_OK, None, cred
    return AUTH_COOKIE_ANON, None, cred


def fields_for_drf(request):
    """OSF API (DRF 経路) の (auth, user, cred) を返す。

    api/base/settings/defaults.py で AuthenticationMiddleware が
    無効化されているため、django の request.user は DRF の
    Request.user setter が設定したものだけである
    (rest_framework 3.8.2 は setter で self._request.user にも伝搬する)。
    """
    drf_user = getattr(request, 'user', None)
    guid = None
    if drf_user is not None and getattr(drf_user, 'is_authenticated', False):
        guid = getattr(drf_user, '_id', None)

    drf_auth = getattr(request, 'auth', None)

    # OSFCASAuthentication は (user, cas_auth_response) を返す
    if drf_auth is not None and hasattr(drf_auth, 'attributes'):
        auth, cred = bearer_cred(drf_auth)
        return auth, guid, cred

    header = request.META.get('HTTP_AUTHORIZATION') or ''

    if header.startswith('Basic '):
        return (AUTH_BASIC_OK if guid else AUTH_BASIC_INVALID), guid, None

    if header.startswith('Bearer '):
        # CAS 認証が成立しなかった Bearer
        return AUTH_BEARER_UNKNOWN, guid, None

    from website import settings
    cookie_val = request.COOKIES.get(settings.COOKIE_NAME)
    view_only = request.GET.get('view_only')

    if not cookie_val:
        if view_only:
            return AUTH_VIEWONLY_OK, None, None
        return AUTH_NONE, None, None

    cred, sig_ok = cookie_cred(cookie_val)
    if not sig_ok:
        return AUTH_COOKIE_INVALID, None, None
    if guid:
        return AUTH_COOKIE_OK, guid, cred
    if view_only:
        return AUTH_VIEWONLY_OK, None, cred
    return AUTH_COOKIE_ANON, None, cred


def fields_for_waterbutler(user, cas_resp, cookie_val, view_only):
    """addons/base/views.py:get_auth() から呼び、WaterButler へ渡す
    フィールドを組み立てる。

    WaterButler は独立サービスであり、ファイルの実体転送は WB を
    経由する。OSF 側だけを改修しても「誰がどのファイルを取得したか」
    は不明のまま残るため、ここで求めた値を認可レスポンスに同梱し、
    WB 側で同じ 3 フィールドを出力させる。
    """
    guid = getattr(user, '_id', None) if user is not None else None

    if cas_resp is not None:
        auth, cred = bearer_cred(cas_resp)
        return {'auth': auth, 'user': guid, 'cred': cred}

    if cookie_val:
        cred, sig_ok = cookie_cred(cookie_val)
        if not sig_ok:
            return {'auth': AUTH_COOKIE_INVALID, 'user': None, 'cred': None}
        if guid:
            return {'auth': AUTH_COOKIE_OK, 'user': guid, 'cred': cred}
        if view_only:
            return {'auth': AUTH_VIEWONLY_OK, 'user': None, 'cred': cred}
        return {'auth': AUTH_COOKIE_ANON, 'user': None, 'cred': cred}

    if view_only:
        return {'auth': AUTH_VIEWONLY_OK, 'user': None, 'cred': None}
    return {'auth': AUTH_NONE, 'user': guid, 'cred': None}

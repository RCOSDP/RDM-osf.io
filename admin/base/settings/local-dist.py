# session:
# TODO: Uncomment SESSION_COOKIE_DOMAIN if OSFAdmin and OSF domains are different.then set up a shared domain.
#   ex. OSFAdmin: admin.shared.domain , OSF: web.shared.domain
#         website/settings/local.py    OSF_COOKIE_DOMAIN = '.shared.domain'
#         admin/base/settings/local.py SESSION_COOKIE_DOMAIN = '.shared.domain'
#SESSION_COOKIE_DOMAIN = '.shared.domain'
SESSION_COOKIE_DOMAIN = '.perfin.rdm.nii.ac.jp'
from .defaults import *

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,osf.io').split(',')

XRAY_RECORDER = {
    'AUTO_INSTRUMENT': True,
    'AWS_XRAY_CONTEXT_MISSING': 'LOG_ERROR',
    'AWS_XRAY_DAEMON_ADDRESS': '192.168.168.167:2000',
    'AWS_XRAY_TRACING_NAME': 'osf-admin',
    'PLUGINS': ('EC2Plugin'),
    'SAMPLING': False,
    'DYNAMIC_NAMING': '*.perfin.rdm.nii.ac.jp',
}

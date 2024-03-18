# session:
# TODO: Uncomment SESSION_COOKIE_DOMAIN if OSFAdmin and OSF domains are different.then set up a shared domain.
#   ex. OSFAdmin: admin.shared.domain , OSF: web.shared.domain
#         website/settings/local.py    OSF_COOKIE_DOMAIN = '.shared.domain'
#         admin/base/settings/local.py SESSION_COOKIE_DOMAIN = '.shared.domain'
#SESSION_COOKIE_DOMAIN = '.shared.domain'
SESSION_COOKIE_DOMAIN = '.perfin.rdm.nii.ac.jp'
from .defaults import *

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,osf.io').split(',')
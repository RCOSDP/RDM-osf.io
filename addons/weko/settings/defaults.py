REPOSITORIES = {}
REPOSITORY_IDS = list(sorted(REPOSITORIES.keys()))
REFRESH_TIME = 5 * 60  # 5 minutes

PUBLISH_TASK_EXPIRATION = 60 * 60 * 24  # 24 hours

# Maximum size of files that can be uploaded ... 1GB
MAX_UPLOAD_SIZE = 1024 * 1024 * 1024
DEFAULT_TIMEOUT = 30  # seconds

# Default OAuth2 scopes for WEKO repositories
# Can be a list of scopes or a callable that takes repo_settings and returns a list
DEFAULT_APPLICATION_SCOPES = ['item:create deposit:actions deposit:write index:create user:activity user:email']

ENABLE_CSV_GENERATION = True
ENABLE_RO_CRATE_GENERATION = True

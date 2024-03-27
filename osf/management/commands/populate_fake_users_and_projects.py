import logging
from django.core.exceptions import ValidationError

import django
django.setup()

from django.core.management.base import BaseCommand
from django.db import transaction

from osf.models import Contributor, Node, QuickFilesNode, ExternalAccount
from osf.models.user import OSFUser
from framework.auth import Auth
from website.project import new_node
from scripts import utils as script_utils
from addons.s3 import utils as s3_utils

logger = logging.getLogger(__name__)

categories = ['analysis','communication', 'data', 'hypothesis',
              'instrumentation', 'methods and measures', 'procedure',
              'software', 'other', '']
SHORT_NAME = 's3'
FULL_NAME = 'Amazon S3'

ACCESS_KEY = 'NEEDED TO ADD AWS KEY'
SECRET_KEY = 'NEEDED TO ADD AWS KEY'

def create_user(username, fullname):
    mail = f'{username}@osf.io'
    
    # Check if the user already exists
    existing_user = OSFUser.objects.filter(username=mail).first()
    if existing_user:
        return existing_user
    
    # Create the OSFUser
    user = OSFUser.create_confirmed(
        username=mail,
        password='Test@123',
        fullname=fullname,
    )
    user.date_confirmed = user.date_registered
    user.have_email = True
    user.save()
    return user
        
def populate_users():
    create_user('test', 'Test User')
    for i in range(10):
       create_user(f'contributor{i+1:02}', f'Test Contributor {i+1:02}')

def get_all_contributors():
    return OSFUser.objects.filter(fullname__startswith='Test Contributor')

def get_all_users():
    return OSFUser.objects.filter(fullname__startswith='Test User')

def remove_users():
    for user in get_all_users():
        logger.info('Removing user: {}'.format(user.username))
        user.delete()
    
    for contributor in get_all_contributors():
        Contributor.objects.filter(user=contributor).delete()
        logger.info('Removing user: {}'.format(contributor.username))
        contributor.delete()

def add_external_account(user, access_key, secret_key):
    user_info = s3_utils.get_user_info(access_key, secret_key)
    if not user_info:
        logger.error('Unable to access account.\n'
                'Check to make sure that the above credentials are valid, '
                'and that they have permission to list buckets.')

    if not s3_utils.can_list(access_key, secret_key):
        logger.error('Unable to list buckets.\n'
                'Listing buckets is required permission that can be changed via IAM')

    account = None
    try:
        account = ExternalAccount(
            provider=SHORT_NAME,
            provider_name=FULL_NAME,
            oauth_key=access_key,
            oauth_secret=secret_key,
            provider_id=user_info.id,
            display_name=user_info.display_name,
        )
        account.save()
    except ValidationError:
        account = ExternalAccount.objects.get(
            provider=SHORT_NAME,
            provider_id=user_info.id
        )
        if account.oauth_key != access_key or account.oauth_secret != secret_key:
            account.oauth_key = access_key
            account.oauth_secret = secret_key
            account.save()
    assert account is not None

    if not user.external_accounts.filter(id=account.id).exists():
        user.external_accounts.add(account)

    # Ensure S3 is enabled.
    user.get_or_add_addon('s3', auth=Auth(user))
    user.save()
    return account

def create_node(category, title, user, external_account, description='', parent=None):
    node = Node.objects.filter(category=category, title=title, creator=user).first()
    if node:
        return node
    
    node = new_node(category, title, user, description, parent)
    # if category == 'project':
    for contributor in get_all_contributors():
        Contributor.objects.create(user=contributor, node=node, visible=True)
    node_settings = node.get_or_add_addon('s3', auth=Auth(user))
    node_settings.set_auth(external_account, user)
    node_settings.set_folder('aws-xray-evaluation', auth=Auth(user))
    node_settings.save()
    return node

def populate_projects():
    user = get_all_users().first()
    external_account = add_external_account(user, ACCESS_KEY, SECRET_KEY)
    
    for i in range(10):
        node = create_node('project', f'Test project {i+1:02}', user, external_account)
        for category in categories:
            title = f'{category} component of project {i+1:02}' if category != '' else f'Uncategorized component of project {i+1:02}'
            create_node(category, title, user, external_account=external_account, parent=node)
            
            
def remove_projects():
    QuickFilesNode.objects.filter(creator=None).delete()
    for contributor in get_all_contributors():
        QuickFilesNode.objects.filter(creator=contributor).delete()
    for user in get_all_users():
        QuickFilesNode.objects.filter(creator=user).delete()
        for node in Node.objects.filter(creator=user):
            # node.get_addon('s3').delete()
            # node.creator.get_addon('s3').delete()
            node.delete()

class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Run migration and roll back changes to db',
        )
        parser.add_argument(
            '--reverse',
            action='store_true',
            dest='reverse',
            help='Removes users'
        )

    def handle(self, *args, **options):
        reverse = options.get('reverse', False)
        dry_run = options.get('dry_run', False)
        if not dry_run:
            script_utils.add_file_logger(logger, __file__)
        with transaction.atomic():
            if reverse:
                remove_projects()
                remove_users()
            else:
                populate_users()
                populate_projects()
            if dry_run:
                raise RuntimeError('Dry run, transaction rolled back.')
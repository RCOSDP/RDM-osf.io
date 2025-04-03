from framework.auth.decorators import must_be_signed
from osf.models import AbstractNode
from website.project.decorators import must_be_contributor_or_public
from website.util import quota
from api.base import settings as api_settings
import datetime
import time
import logging
logger = logging.getLogger(__name__)

@must_be_signed
def waterbutler_creator_quota(pid, **kwargs):
    begin = time.time()
    logger.info(
        f"--------------Begin waterbutler_creator_quota : {datetime.datetime.fromtimestamp(begin).strftime('%H:%M:%S.%f')[:-3]}--------------")
    data = get_quota_from_pid(pid)
    logger.info(
        f"--------------End waterbutler_creator_quota : {datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')[:-3]}--------------")
    logger.info(
        f"--------------Total time waterbutler_creator_quota : {datetime.datetime.fromtimestamp(time.time() - begin).strftime('%H:%M:%S.%f')[:-3]}--------------")
    return data

@must_be_contributor_or_public
def get_creator_quota(pid, **kwargs):
    begin = time.time()
    logger.info(
        f"--------------Begin get_creator_quota : {datetime.datetime.fromtimestamp(begin).strftime('%H:%M:%S.%f')[:-3]}--------------")
    data = get_quota_from_pid(pid)
    logger.info(
        f"--------------End get_creator_quota : {datetime.datetime.fromtimestamp(time.time()).strftime('%H:%M:%S.%f')[:-3]}--------------")
    logger.info(
        f"--------------Total time get_creator_quota : {datetime.datetime.fromtimestamp(time.time() - begin).strftime('%H:%M:%S.%f')[:-3]}--------------")

    return data

def get_quota_from_pid(pid):
    """Auxiliary function for getting the quota from a project ID.
    Used on requests by waterbutler and the user (from browser)."""
    node = AbstractNode.load(pid)
    max_quota, used_quota = quota.get_quota_info(
        node.creator, quota.get_project_storage_type(node)
    )
    return {
        'max': max_quota * api_settings.SIZE_UNIT_GB,
        'used': used_quota
    }

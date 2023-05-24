# -*- coding: utf-8 -*-
import logging

from addons.base import signals as file_signals
from addons.base.utils import get_root_institutional_storage
from addons.osfstorage.models import OsfStorageFileNode, Region
from api.base import settings as api_settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.db.models.functions import Coalesce
from osf.models import (
    AbstractNode, BaseFileNode, FileLog, FileInfo, Guid, OSFUser, UserQuota,
    ProjectStorageType
)
from django.utils import timezone
from osf.models.user_storage_quota import UserStorageQuota
from rest_framework import status as http_status
from framework.exceptions import HTTPError

PROVIDERS = ['s3', 's3compat']

# import inspect
logger = logging.getLogger(__name__)


def used_quota(user_id, storage_type=UserQuota.NII_STORAGE):
    guid = Guid.objects.get(
        _id=user_id,
        content_type_id=ContentType.objects.get_for_model(OSFUser).id
    )
    projects_ids = AbstractNode.objects.filter(
        projectstoragetype__storage_type=storage_type,
        is_deleted=False,
        creator_id=guid.object_id
    ).values_list('id', flat=True)
    if storage_type != UserQuota.NII_STORAGE:
        files_ids = BaseFileNode.objects.filter(
            target_object_id__in=projects_ids,
            target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
            deleted_on=None,
            deleted_by_id=None,
        ).values_list('id', flat=True)
    else:
        files_ids = OsfStorageFileNode.objects.filter(
            target_object_id__in=projects_ids,
            target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
            deleted_on=None,
            deleted_by_id=None,
        ).values_list('id', flat=True)
    db_sum = FileInfo.objects.filter(file_id__in=files_ids).aggregate(
        filesize_sum=Coalesce(Sum('file_size'), 0))
    return db_sum['filesize_sum'] if db_sum['filesize_sum'] is not None else 0


def update_user_used_quota(user, storage_type=UserQuota.NII_STORAGE):
    used = used_quota(user._id, storage_type)

    try:
        user_quota = UserQuota.objects.get(
            user=user,
            storage_type=storage_type,
        )
        user_quota.used = used
        user_quota.save()
    except UserQuota.DoesNotExist:
        UserQuota.objects.create(
            user=user,
            storage_type=storage_type,
            max_quota=api_settings.DEFAULT_MAX_QUOTA,
            used=used,
        )


def abbreviate_size(size):
    size = float(size)
    abbr_dict = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}

    power = 0
    while size > api_settings.BASE_FOR_METRIC_PREFIX and power < 4:
        size /= api_settings.BASE_FOR_METRIC_PREFIX
        power += 1

    return (size, abbr_dict[power])

def get_quota_info(user, storage_type=UserQuota.NII_STORAGE):
    try:
        user_quota = user.userquota_set.get(storage_type=storage_type)
        return (user_quota.max_quota, user_quota.used)
    except UserQuota.DoesNotExist:
        return (api_settings.DEFAULT_MAX_QUOTA, used_quota(user._id, storage_type))


def get_storage_quota_info(institution, user, region):
    """ Get the per-user-per-storage info of institution

    :param Object institution: Institution of user
    :param Object user: User is using the storage
    :param Object region: Institution storage
    :return tuple: Tuple of storage's quota and used quota

    """
    try:
        user_storage_quota = user.userstoragequota_set.get(region=region)
        return user_storage_quota.max_quota, user_storage_quota.used
    except UserStorageQuota.DoesNotExist:
        return (
            api_settings.DEFAULT_MAX_QUOTA,
            user_per_storage_used_quota(institution, user, region)
        )


def get_project_storage_type(node):
    try:
        return ProjectStorageType.objects.get(node=node).storage_type
    except ProjectStorageType.DoesNotExist:
        return ProjectStorageType.NII_STORAGE

@file_signals.file_updated.connect
def update_used_quota(self, target, user, event_type, payload):
    if event_type == FileLog.FILE_RENAMED:
        destination = dict(payload).get('destination')
        source = dict(payload).get('source')
        if dict(destination).get('provider') in PROVIDERS:
            nodes_filter = []
            if dict(destination).get('kind') == 'file':

                nodes_filter = BaseFileNode.objects.filter(
                    _path=dict(source).get('path'),
                    provider=dict(destination).get('provider'),
                    target_object_id=target.id,
                    deleted=None,
                    target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
                )
            elif dict(destination).get('kind') == 'folder':

                nodes_filter = BaseFileNode.objects.filter(
                    _path__startswith=dict(source).get('path'),
                    provider=dict(destination).get('provider'),
                    target_object_id=target.id,
                    deleted=None,
                    target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
                )
            for node in nodes_filter:
                node._path = node._path.replace(dict(source).get('path'), dict(destination).get('path'))
                node._materialized_path = node._path.replace(dict(source).get('path'), dict(destination).get('path'))
                node.save()
            lastest_node = BaseFileNode.objects.filter(
                _path=dict(destination).get('path'),
                provider=dict(destination).get('provider'),
                target_object_id=target.id,
                deleted=None,
                target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
            ).order_by('-id').first()
            lastest_node.is_deleted = True
            lastest_node.deleted = timezone.now()
            lastest_node.deleted_on = lastest_node.deleted
            lastest_node.type = 'osf.trashedfile' if dict(destination).get('kind') == 'file' else 'osf.trashedfolder'
            lastest_node.deleted_by_id = user.id
            lastest_node.save()
    data = dict(payload.get('metadata')) if payload.get('metadata') else None
    metadata_provider = data.get('provider') if payload.get('metadata') else None
    if metadata_provider in PROVIDERS or metadata_provider == 'osfstorage':
        file_node = None
        action_payload = dict(payload).get('action')
        try:
            if metadata_provider in PROVIDERS:
                if data.get('kind') == 'folder' and action_payload == 'create_folder':
                    base_file_node = BaseFileNode(
                        type='osf.{}folder'.format(metadata_provider),
                        provider=metadata_provider,
                        _path=data.get('materialized'),
                        _materialized_path=data.get('materialized'),
                        parent_id=target.id,
                        target_object_id=target.id,
                        target_content_type=ContentType.objects.get_for_model(AbstractNode)
                    )
                    base_file_node.save()
                else:
                    file_node = BaseFileNode.objects.filter(
                        _path=data.get('materialized'),
                        provider=metadata_provider,
                        target_object_id=target.id,
                        deleted=None,
                        target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
                    ).order_by('-id').first()
            else:
                file_node = BaseFileNode.objects.get(
                    _id=data.get('path').strip('/'),
                    target_object_id=target.id,
                    target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
                )
        except BaseFileNode.DoesNotExist:
            logging.error('FileNode not found, cannot update used quota!')
            return
        storage_type = get_project_storage_type(target)
        if event_type == FileLog.FILE_ADDED:
            file_added(target, payload, file_node, storage_type)
        elif event_type == FileLog.FILE_REMOVED:
            if metadata_provider in PROVIDERS and data.get('kind') == 'file':
                file_node.is_deleted = True
                file_node.deleted = timezone.now()
                file_node.deleted_on = file_node.deleted
                file_node.type = 'osf.trashedfile'
                file_node.deleted_by_id = user.id
                file_node.save()
                node_removed(target, user, payload, file_node, storage_type)
            elif metadata_provider in PROVIDERS and data.get('kind') == 'folder':
                list_file_node = BaseFileNode.objects.filter(
                    _path__startswith=data.get('materialized'),
                    target_object_id=target.id,
                    provider=metadata_provider,
                    deleted=None,
                    target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
                ).all()
                for file_node_remove in list_file_node:
                    file_node_remove.is_deleted = True
                    if file_node_remove.type == 'osf.{}file'.format(metadata_provider):
                        file_node_remove.type = 'osf.trashedfile'
                    elif file_node_remove.type == 'osf.{}folder'.format(metadata_provider):
                        file_node_remove.type = 'osf.trashedfolder'
                    file_node_remove.deleted = timezone.now()
                    file_node_remove.deleted_on = file_node_remove.deleted
                    file_node_remove.deleted_by_id = user.id
                    file_node_remove.save()
                    if file_node_remove.type == 'osf.trashedfile':
                        node_removed(target, user, payload, file_node_remove, storage_type)
            else:
                node_removed(target, user, payload, file_node, storage_type)
        elif event_type == FileLog.FILE_UPDATED:
            file_modified(target, user, payload, file_node, storage_type)
    elif event_type == FileLog.FILE_MOVED:
        file_moved(target, payload)
    else:
        return


def file_added(target, payload, file_node, storage_type):
    file_size = int(payload['metadata']['size'])
    if file_size < 0:
        return
    try:
        user_quota = UserQuota.objects.get(
            user=target.creator,
            storage_type=storage_type
        )
        user_quota.used += file_size
        user_quota.save()
    except UserQuota.DoesNotExist:
        UserQuota.objects.create(
            user=target.creator,
            storage_type=storage_type,
            max_quota=api_settings.DEFAULT_MAX_QUOTA,
            used=file_size
        )

    if payload['provider'] == 'osfstorage' and storage_type == ProjectStorageType.CUSTOM_STORAGE:
        node_addon = get_addon_osfstorage_by_path(target, payload['metadata']['path'], payload['provider'])
        if node_addon is not None:
            update_institutional_storage_used_quota(target.creator, node_addon.region, payload['provider'], file_size)

    FileInfo.objects.create(file=file_node, file_size=file_size)

def node_removed(target, user, payload, file_node, storage_type):
    user_quota = UserQuota.objects.filter(
        user=target.creator,
        storage_type=storage_type
    ).first()

    user_storage_quota = None
    if payload['provider'] == 'osfstorage' and storage_type == ProjectStorageType.CUSTOM_STORAGE:
        node_addon = get_addon_osfstorage_by_path(target, payload['metadata']['path'], payload['provider'])
        user_storage_quota = UserStorageQuota.objects.filter(
            user=target.creator,
            region=node_addon.region
        ).select_for_update().first()

    if user_quota is not None:
        if 'osf.trashed' not in file_node.type:
            logging.error('FileNode is not trashed, cannot update used quota!')
            return

        for removed_file in get_node_file_list(file_node):
            try:
                file_info = FileInfo.objects.get(file=removed_file)
            except FileInfo.DoesNotExist:
                logging.error('FileInfo not found, cannot update used quota!')
                continue

            if user_storage_quota is not None:
                file_size = min(file_info.file_size, user_storage_quota.used)
                user_storage_quota.used -= file_size
            file_size = min(file_info.file_size, user_quota.used)
            user_quota.used -= file_size
        user_quota.save()
        if user_storage_quota is not None:
            user_storage_quota.save()

def file_modified(target, user, payload, file_node, storage_type):
    file_size = int(payload['metadata']['size'])
    if file_size < 0:
        return

    user_quota, _ = UserQuota.objects.get_or_create(
        user=target.creator,
        storage_type=storage_type,
        defaults={'max_quota': api_settings.DEFAULT_MAX_QUOTA}
    )

    try:
        file_info = FileInfo.objects.get(file=file_node)
    except FileInfo.DoesNotExist:
        file_info = FileInfo(file=file_node, file_size=0)

    used = file_size - file_info.file_size

    if payload['provider'] == 'osfstorage' and storage_type == ProjectStorageType.CUSTOM_STORAGE:
        node_addon = get_addon_osfstorage_by_path(target, payload['metadata']['path'], payload['provider'])
        if node_addon is not None:
            update_institutional_storage_used_quota(target.creator, node_addon.region, payload['provider'], used)

    user_quota.used += used
    if user_quota.used < 0:
        user_quota.used = 0
    user_quota.save()

    file_info.file_size = file_size
    file_info.save()

def file_moved(target, payload):
    """Update per-user-per-storage used quota when moving file

    :param Object target: Id of project
    :param str path: _Id of file or folder
    :param str provider: The addon name
    :return Object: The addon is found

    """
    if isinstance(target, AbstractNode):
        storage_type = get_project_storage_type(target)
        if storage_type == ProjectStorageType.CUSTOM_STORAGE:
            file_size = int(payload['destination']['size'])
            if file_size < 0:
                return

            if payload['destination']['provider'] == 'osfstorage':
                node_addon_destination = get_addon_osfstorage_by_path(
                    target,
                    payload['destination']['path'],
                    payload['destination']['provider']
                )

                if node_addon_destination is not None:
                    update_institutional_storage_used_quota(
                        target.creator,
                        node_addon_destination.region,
                        payload['destination']['provider'],
                        file_size
                    )

            source_node_id = payload['source']['nid']
            source_node = AbstractNode.objects.get(guids___id=source_node_id)
            if payload['source']['provider'] == 'osfstorage' \
                    and source_node.type != 'osf.quickfilesnode':
                node_addon_source = get_addon_osfstorage_by_path(
                    target,
                    payload['source']['old_root_id'],
                    payload['source']['provider']
                )

                if node_addon_source is not None:
                    update_institutional_storage_used_quota(
                        target.creator,
                        node_addon_source.region,
                        payload['source']['provider'],
                        file_size, add=False
                    )

def update_default_storage(user):
    # logger.info('----{}::{}({})from:{}::{}({})'.format(inspect.getframeinfo(inspect.currentframe())[0], inspect.getframeinfo(inspect.currentframe())[2], inspect.getframeinfo(inspect.currentframe())[1], inspect.stack()[1][1], inspect.stack()[1][3], inspect.stack()[1][2]))
    # logger.info(user)
    if user is not None:
        user_settings = user.get_addon('osfstorage')
        if user_settings is None:
            user_settings = user.add_addon('osfstorage')
        institution = user.affiliated_institutions.first()
        if institution is not None:
            region = Region.objects.filter(_id=institution._id).first()
            if region is None:
                # logger.info('Inside update_default_storage: region does not exist.')
                pass
            else:
                if user_settings.default_region._id != region._id:
                    user_settings.set_region(region.id)
                    logger.info(u'user={}, institution={}, user_settings.set_region({})'.format(user, institution.name, region.name))

def get_node_file_list(file_node):
    if 'file' in file_node.type:
        return [file_node]

    file_list = []
    folder_list = [file_node]

    while len(folder_list) > 0:
        folder_id_list = list(map(lambda f: f.id, folder_list))
        folder_list = []
        for child_file_node in BaseFileNode.objects.filter(parent_id__in=folder_id_list):
            if 'folder' in child_file_node.type:
                folder_list.append(child_file_node)
            else:  # file
                file_list.append(child_file_node)

    return file_list

def get_addon_osfstorage_by_path(target, path, provider):
    """Get addon of project by path and provider name

    :param Object target: Project owns addon
    :param str path: _Id of file or folder
    :param str provider: The addon name
    :return Object: The addon is found

    """
    root_folder_id = get_root_institutional_storage(path.strip('/').split('/')[0])
    if root_folder_id is not None:
        root_folder_id = root_folder_id.id
    if hasattr(target, 'get_addon'):
        node_addon = target.get_addon(provider, root_id=root_folder_id)
        if node_addon is None:
            raise HTTPError(http_status.HTTP_400_BAD_REQUEST)
        return node_addon
    else:
        return None

def update_institutional_storage_used_quota(creator, region, provider, size, add=True):
    """Update used per-user-per-storage

    :param Object creator: User is updated
    :param Object region: Institutional storage is updated
    :param str provider: Provider name of storage
    :param int size: Size of file
    :param bool add: Add or subtract

    """
    try:
        user_storage_quota = UserStorageQuota.objects.select_for_update().get(
            user=creator,
            region=region
        )
        if add:
            user_storage_quota.used += size
        else:
            user_storage_quota.used -= size

        if user_storage_quota.used < 0:
            user_storage_quota.used = 0

        user_storage_quota.save()
    except UserStorageQuota.DoesNotExist:
        storage_max_quota = api_settings.DEFAULT_MAX_QUOTA

        UserStorageQuota.objects.create(
            user=creator,
            region=region,
            max_quota=storage_max_quota,
            used=size
        )

        # Add max quota of user-per-storage to max quota of user
        user_quota = UserQuota.objects.get(
            user=creator,
            storage_type=UserQuota.CUSTOM_STORAGE
        )
        user_quota.max_quota += storage_max_quota
        user_quota.save()

def recalculate_used_quota_by_user(user_id):
    """Recalculate used per-user-per-storage

    :param str user_id: The user is recalculated

    """
    guid = Guid.objects.get(
        _id=user_id,
        content_type_id=ContentType.objects.get_for_model(OSFUser).id
    )
    projects = AbstractNode.objects.filter(
        projectstoragetype__storage_type=UserQuota.CUSTOM_STORAGE,
        is_deleted=False,
        creator_id=guid.object_id
    )

    if projects is not None:
        # Dict with key=region_id and value=used_quota
        used_quota_result = {}
        for project in projects:
            addons = project.get_osfstorage_addons()
            for addon in addons:
                sum = calculate_used_quota_by_institutional_storage(
                    project.id,
                    addon.root_node_id
                )
                if addon.region_id in used_quota_result.keys():
                    used_quota_result[addon.region_id] += sum
                else:
                    used_quota_result[addon.region_id] = sum

        # Update used quota for each institutional storage
        for id in used_quota_result:
            try:
                storage_quota = UserStorageQuota.objects.select_for_update().get(
                    user_id=guid.object_id,
                    region_id=id
                )
                storage_quota.used = used_quota_result[id]
                storage_quota.save()
            except UserStorageQuota.DoesNotExist:
                pass

def get_file_ids_by_institutional_storage(result, project_id, root_id):
    """ Get all file ids of institutional storage in a project

    :param list result: Array of file id
    :param str project_id: Id of project
    :param str root_id: Id of storage root folder

    """
    children = BaseFileNode.objects.filter(
        target_object_id=project_id,
        target_content_type_id=ContentType.objects.get_for_model(AbstractNode),
        deleted_on=None,
        deleted_by_id=None,
        parent_id=root_id
    )
    if children is None:
        return
    else:
        for item in children:
            if item.type == 'osf.osfstoragefile':
                result.append(item.id)
            elif item.type == 'osf.osfstoragefolder':
                get_file_ids_by_institutional_storage(
                    result,
                    project_id, item.id
                )

def calculate_used_quota_by_institutional_storage(project_id, root_id):
    """Calculate the total size of institutional storage in a project

    :param str project_id: Id of project
    :param str root_id: Id of storage root folder
    :return int: Total size of all files in storage

    """
    files_ids = []
    get_file_ids_by_institutional_storage(files_ids, project_id, root_id)

    db_sum = FileInfo.objects.filter(file_id__in=files_ids).aggregate(
        filesize_sum=Coalesce(Sum('file_size'), 0))
    return db_sum['filesize_sum'] if db_sum['filesize_sum'] is not None else 0

def user_per_storage_used_quota(institution, user, region_id):
    """Calculate per-user-per-storage used quota

    :param Institution institution: The institution of user
    :param Object user: The user are using the storage
    :param str region_id: Id of institutional storage
    :return int: Result

    """
    projects = institution.nodes.filter(creator_id=user.id)
    result = 0
    for project in projects:
        addon = project.get_addon('osfstorage', region_id=region_id)
        if addon is not None:
            result += calculate_used_quota_by_institutional_storage(
                project.id,
                addon.root_node_id
            )
    return result

def update_institutional_storage_max_quota(user, region, max_quota):
    """ Update max quota for per-user-per-storage

    :param Object user: The user are using the storage
    :param Object region: The storage needs to be updated
    :param int max_quota: New max quota

    """
    old_max_quota = 0

    # Update user-per-storage max quota
    try:
        user_storage_quota = UserStorageQuota.objects.select_for_update().get(
            user=user,
            region=region
        )
        old_max_quota = user_storage_quota.max_quota
        user_storage_quota.max_quota = max_quota
        user_storage_quota.save()
    except UserStorageQuota.DoesNotExist:
        UserStorageQuota.objects.create(
            user=user,
            region=region,
            max_quota=max_quota,
        )

    # Update CUSTOM_STORAGE max quota of user
    try:
        user_quota = UserQuota.objects.select_for_update().get(
            user=user,
            storage_type=UserQuota.CUSTOM_STORAGE,
        )
        user_quota.max_quota += max_quota - old_max_quota

        if user_quota.max_quota < 0:
            user_quota.max_quota = 0
        user_quota.save()
    except UserQuota.DoesNotExist:
        UserQuota.objects.create(
            user=user,
            storage_type=UserQuota.CUSTOM_STORAGE,
            max_quota=max_quota,
        )

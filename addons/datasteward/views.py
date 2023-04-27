"""Views for the add-on's user settings page."""
import asyncio
import logging
from itertools import islice

from bulk_update.helper import bulk_update
# -*- coding: utf-8 -*-
from django.apps import apps
from django.db import transaction
from django.db.models import Max
from django.db.models.functions import Coalesce
from flask import request
from rest_framework import status as http_status

from addons.base.institutions_utils import sync_contributors
from addons.osfstorage.listeners import checkin_files_task
from framework.auth.decorators import must_be_logged_in
from framework.celery_tasks import app
from framework.postcommit_tasks.handlers import enqueue_postcommit_task
from osf.exceptions import UserStateError, ValidationValueError
from osf.models import Contributor, OSFUser
from osf.models.node import AbstractNode
from osf.models.nodelog import NodeLog
from osf.utils.permissions import ADMIN, READ
from website import language
from website.notifications.utils import remove_contributor_from_subscriptions
from website.project import signals as project_signals
from timeit import default_timer as timer

logger = logging.getLogger(__name__)

SHORT_NAME = 'datasteward'
OSF_NODE = 'osf.node'
BATCH_SIZE = 1000


@must_be_logged_in
def datasteward_user_config_get(auth, **kwargs):
    """View for getting a JSON representation of DataSteward user settings"""
    user = auth.user
    addon_user_settings = user.get_addon(SHORT_NAME)
    addon_user_settings_enabled = addon_user_settings.enabled if addon_user_settings else False

    # If user is not a data steward and does not have add-on enabled before, return HTTP 403
    if not user.is_data_steward and not addon_user_settings_enabled:
        return {}, http_status.HTTP_403_FORBIDDEN

    return {
        'enabled': addon_user_settings_enabled,
    }, http_status.HTTP_200_OK


@must_be_logged_in
def datasteward_user_config_post(auth, **kwargs):
    """View for post DataSteward user settings with enabled value"""
    data = request.get_json()
    enabled = data.get('enabled', None)
    if enabled is None or not isinstance(enabled, bool):
        # If request's 'enabled' field is not valid, return HTTP 400
        return {}, http_status.HTTP_400_BAD_REQUEST

    user = auth.user
    # If user is not a DataSteward when enabling DataSteward add-on, return HTTP 403
    if not user.is_data_steward and enabled:
        return {}, http_status.HTTP_403_FORBIDDEN

    # Update add-on user settings
    addon_user_settings = user.get_addon(SHORT_NAME)
    addon_user_settings.enabled = enabled
    addon_user_settings.save()

    if enabled:
        # Enable DataSteward addon process
        enable_result = enable_datasteward_addon(auth)

        if not enable_result:
            return {}, http_status.HTTP_500_INTERNAL_SERVER_ERROR

        return {}, http_status.HTTP_200_OK
    else:
        # Disable DataSteward addon process
        skipped_projects = disable_datasteward_addon(auth)

        if skipped_projects is None:
            return {}, http_status.HTTP_500_INTERNAL_SERVER_ERROR

        response_body = {
            'skipped_projects': [
                {
                    'guid': project._id,
                    'name': project.title
                }
                for project in skipped_projects
            ]
        }

        return response_body, http_status.HTTP_200_OK


@transaction.atomic
def enable_datasteward_addon(auth, is_authenticating=False, **kwargs):
    """Start enable DataSteward add-on process"""
    # Check if user has any affiliated institutions
    affiliated_institutions = auth.user.affiliated_institutions.all()
    if not affiliated_institutions:
        return False
    try:
        user = auth.user.merged_by if auth.user.is_merged else auth.user

        projects = AbstractNode.objects.filter(type=OSF_NODE, affiliated_institutions__in=affiliated_institutions, is_deleted=False)
        contributors = Contributor.objects.filter(node__in=projects)

        add_contributor_list = []
        update_contributor_list = []
        update_permission_project_list = []
        for project in projects:
            related_contributors = contributors.filter(node=project)
            if related_contributors.filter(user=user).exists():
                contributor = related_contributors.first()

                # check if need to save old permission
                if not contributor.is_data_steward:
                    contributor.data_steward_old_permission = contributor.permission
                    contributor.is_data_steward = True
                    update_contributor_list.append(contributor)

                # check if need to update permission
                if contributor.permission != ADMIN:
                    update_permission_project_list.append(project)
            else:
                # add contributor
                kwargs = project.contributor_kwargs
                kwargs['_order'] = related_contributors.aggregate(**{'_order__max': Coalesce(Max('_order'), -1)}).get('_order__max') + 1
                new_contributor = Contributor(**kwargs)
                new_contributor.user = user
                new_contributor.is_data_steward = True
                new_contributor.visible = True
                add_contributor_list.append((project, new_contributor))

        # add contributor
        if add_contributor_list:
            if user.is_disabled:
                raise ValidationValueError('Deactivated users cannot be added as contributors.')

            if not user.is_registered and not user.unclaimed_records:
                raise UserStateError('This contributor cannot be added. If the problem persists please report it '
                                     'to ' + language.SUPPORT_LINK)

            new_contributors = [new_contributor for _, new_contributor in add_contributor_list]
            added_projects = [project for project, _ in add_contributor_list]
            bulk_create_contributors(new_contributors)

            # Bulk create NodeLog
            add_project_logs(added_projects, user, NodeLog.CONTRIB_ADDED)

            # send signal.
            loop = asyncio.new_event_loop()
            coroutines = [loop.create_task(add_contributor_permission(project=project, auth=auth)) for project, contributor in add_contributor_list]
            loop.run_until_complete(asyncio.wait(coroutines))
            loop.close()

        # save contributor's old permission
        if update_contributor_list:
            bulk_update(update_contributor_list, batch_size=BATCH_SIZE)

        # update contributor permission
        if update_permission_project_list:
            # set permission and send signal
            loop = asyncio.new_event_loop()
            coroutines = [loop.create_task(update_contributor_permission(project=project, auth=auth)) for project in update_permission_project_list]
            loop.run_until_complete(asyncio.wait(coroutines))
            loop.close()
    except Exception as e:
        # If error is raised while running on "Configure add-on accounts" screen, raise error
        # Otherwise, do nothing
        logger.error('Project {}: error raised while enabling DataSteward add-on with message "{}"'.format(project._id, e))
        if not is_authenticating:
            raise e
    return True


def bulk_create_contributors(contributors, batch_size=BATCH_SIZE):
    it = iter(contributors)
    while True:
        batch = list(islice(it, batch_size))
        if not batch:
            break
        Contributor.objects.bulk_create(batch, batch_size)


async def add_contributor_permission(project, auth):
    project.add_permission(auth.user, ADMIN, save=False)
    project_signals.contributors_updated.send(project)

    # enqueue on_node_updated/on_preprint_updated to update DOI metadata when a contributor is added
    if getattr(project, 'get_identifier_value', None) and project.get_identifier_value('doi'):
        project.update_or_enqueue_on_resource_updated(auth.user._id, first_save=False, saved_fields=['contributors'])


async def update_contributor_permission(project, auth, permission=ADMIN):
    if not project.get_group(permission).user_set.filter(id=auth.user.id).exists():
        project.set_permissions(auth.user, permission, save=False)
        permissions_changed = {
            auth.user._id: permission
        }
        params = project.log_params
        params['contributors'] = permissions_changed
        project.add_log(
            action=project.log_class.PERMISSIONS_UPDATED,
            params=params,
            auth=auth,
            save=False
        )
        if permission == READ:
            project_signals.write_permissions_revoked.send(project)

        project_signals.contributors_updated.send(project)


@transaction.atomic
def disable_datasteward_addon(auth):
    """Start disable DataSteward add-on process"""
    start = timer()
    # Check if user has any affiliated institutions
    affiliated_institutions = auth.user.affiliated_institutions.all()
    if not affiliated_institutions:
        return None

    user = auth.user
    skipped_projects = []

    projects = AbstractNode.objects.filter(type=OSF_NODE, affiliated_institutions__in=affiliated_institutions, is_deleted=False)
    logger.info(f'institution projects total: {len(projects)}')

    # query admin contributors
    start_contributor_query = timer()
    contributors = Contributor.objects.filter(node__in=projects, is_data_steward=True, user__is_active=True, user__groups__name__in=[project.format_group(ADMIN) for project in projects]).distinct()
    end_contributor_query = timer()
    logger.info(f'-- Contributor query runtime: {end_contributor_query - start_contributor_query}(s)')
    all_project_contributors = []
    user_project_id_list = []
    start_iterator = timer()
    for c in contributors:
        all_project_contributors.append(c)
        if c.node.id not in user_project_id_list and c.user.id == user.id:
            user_project_id_list.append(c.node.id)
    end_iterator = timer()
    logger.info(f'-- Contributor iterator runtime: {end_iterator - start_iterator}(s)')

    # filter out project does not have user as contributor.
    if len(user_project_id_list) != projects.count():
        projects = projects.filter(id__in=user_project_id_list)

    update_permission_list = []
    bulk_update_contributors = []
    bulk_delete_contributor_id_list = []
    remove_permission_projects = []
    update_user = False
    start_prepare = timer()
    logger.info(f'disable_datasteward_addon before prepare runtime: {start_prepare - start}(s)')
    logger.info(f'all_project_contributors total: {len(all_project_contributors)}')
    logger.info(f'user contributing projects total: {len(projects)}')
    for project in projects:
        all_project_contributors, project_contributors, contributor = get_project_contributors(all_project_contributors, user, project)

        # can not be None
        if contributor.data_steward_old_permission is not None:
            if len(project_contributors) <= 1:
                # has only one admin
                if ADMIN != contributor.data_steward_old_permission:
                    # if update to other permission than ADMIN then skip.
                    # else do nothing.
                    error_msg = '{} is the only admin.'.format(user.fullname)
                    logger.warning('Project {}: error raised while disabling DataSteward add-o with message "{}"'.format(project._id, error_msg))
                    skipped_projects.append(project)
            else:
                update_permission_list.append((project, contributor.data_steward_old_permission))
                contributor.is_data_steward = False
                contributor.data_steward_old_permission = None
                bulk_update_contributors.append(contributor)
        else:
            not_current_user_admins = [contributor for contributor in project_contributors if contributor.user.id != user.id and contributor.visible is True]
            if not not_current_user_admins:
                # If user is the only visible contributor then skip
                logger.warning('Cannot remove user from project {}'.format(project._id))
                skipped_projects.append(project)
            else:
                # remove unclaimed record if necessary
                if project._id in user.unclaimed_records:
                    del user.unclaimed_records[project._id]
                    update_user = True
                bulk_delete_contributor_id_list.append(contributor.id)
                remove_permission_projects.append(project)

    start_update = timer()
    logger.info(f'disable_datasteward_addon prepare runtime: {start_update - start_prepare}(s)')
    # update contributor permission
    if update_permission_list:
        logger.info(f'begin update permission len={len(update_permission_list)}')
        # update to DB
        bulk_update(bulk_update_contributors, update_fields=['is_data_steward', 'data_steward_old_permission'], batch_size=BATCH_SIZE)

        # set permission and send signal
        loop = asyncio.new_event_loop()
        coroutines = [loop.create_task(update_contributor_permission(project=project, auth=auth, permission=contributor_old_permission)) for
                      project, contributor_old_permission in update_permission_list]
        loop.run_until_complete(asyncio.wait(coroutines))
        loop.close()

    start_remove = timer()
    logger.info(f'disable_datasteward_addon update contributors runtime: {start_remove - start_update}(s)')
    # remove contributor
    if remove_permission_projects:
        logger.info(f'begin remove permission len={len(remove_permission_projects)}')
        if update_user:
            # save after delete unclaimed_records
            user.save()

        # delete contributors
        Contributor.objects.filter(id__in=bulk_delete_contributor_id_list).delete()

        # clear permission and send signal
        clear_permissions(remove_permission_projects, user)

        add_project_logs(remove_permission_projects, user, NodeLog.CONTRIB_REMOVED)

        start_disconnect = timer()
        logger.info(f'-- delete contributor + permissions + add logs runtime: {start_disconnect - start_remove}(s)')
        disconnect_addons_multiple_projects(remove_permission_projects, user)
        end_disconnect = timer()
        logger.info(f'-- disconnect_addons_multiple_projects runtime: {end_disconnect - start_disconnect}(s)')

        loop = asyncio.new_event_loop()
        coroutines = [loop.create_task(after_remove_contributor_permission(project=project, auth=auth)) for project in remove_permission_projects]
        loop.run_until_complete(asyncio.wait(coroutines))
        loop.close()
        end_after_remove = timer()
        logger.info(f'-- after_remove_contributor_permission runtime: {end_after_remove - end_disconnect}(s)')

    end = timer()
    logger.info(f'disable_datasteward_addon remove contributors runtime: {end - start_remove}(s)')
    logger.info(f'disable_datasteward_addon overall runtime: {end - start}(s)')
    return skipped_projects


def get_project_contributors(contributors, user, project):
    new_list = []
    project_contributors = []
    user_contributor = None
    for contributor in contributors:
        if contributor.node.id == project.id:
            project_contributors.append(contributor)

            if contributor.user.id == user.id:
                user_contributor = contributor
        else:
            new_list.append(contributor)

    return new_list, project_contributors, user_contributor


def clear_permissions(projects, user):
    """ Clear permission of multiple projects for user """
    project_group_names = [name for project in projects for name in project.group_names]
    OSFUserGroup = apps.get_model('osf', 'osfuser_groups')
    OSFUserGroup.objects.filter(osfuser_id=user.id, group__name__in=project_group_names).delete()


def add_project_logs(projects, user, action):
    """ Add multiple project activity logs for user """
    logs = []
    for project in projects:
        params = project.log_params
        params['contributors'] = [user._id]
        params['node'] = params.get('node') or params.get('project') or project._id
        original_node = project if project._id == params['node'] else AbstractNode.load(params.get('node'))
        log = NodeLog(
            action=action, user=user, foreign_user=None,
            params=params, node=project, original_node=original_node
        )
        logs.append(log)

    it = iter(logs)
    while True:
        batch = list(islice(it, BATCH_SIZE))
        if not batch:
            break
        NodeLog.objects.bulk_create(batch, BATCH_SIZE)


async def after_remove_contributor_permission(project, auth):
    # send signal to remove this user from project subscriptions
    enqueue_postcommit_task(checkin_files_task, (project._id, auth.user._id,), {}, celery=True)
    enqueue_postcommit_task(task_sync_contributors, (project.id, auth.user.id), {}, celery=True)

    # enqueue on_node_updated/on_preprint_updated to update DOI metadata when a contributor is removed
    if getattr(project, 'get_identifier_value', None) and project.get_identifier_value('doi'):
        project.update_or_enqueue_on_resource_updated(auth.user._id, first_save=False, saved_fields=['contributors'])


def disconnect_addons_multiple_projects(projects, user):
    """ Disconnect addons for multiple project at same time """
    ADDONS_AVAILABLE = sorted([config for config in apps.get_app_configs() if config.name.startswith('addons.') and
                               config.label != 'base'], key=lambda config: config.name)
    project_ids = [project.id for project in projects if not project.is_contributor_or_group_member(user)]

    # If there is no add-on or project then returns
    if not ADDONS_AVAILABLE or not project_ids:
        return

    for config in ADDONS_AVAILABLE:
        # Get addon's node settings model
        node_settings_model = get_node_settings_model(config)
        if not node_settings_model:
            continue

        # Get project's node settings for each add-on
        project_node_settings = node_settings_model.objects.filter(owner__id__in=project_ids)

        update_node_settings = False
        for setting in project_node_settings:
            if not hasattr(setting, 'user_settings'):
                continue

            update_node_settings = True
            if hasattr(setting.user_settings, 'oauth_grants'):
                # Remove user's external account guid from node's oauth_grants
                setting.user_settings.oauth_grants[setting.owner._id].pop(setting.external_account._id)

            # Disconnect user settings from node settings
            setting.user_settings = None

        if update_node_settings:
            # Bulk update multiple node settings
            bulk_update(project_node_settings, batch_size=BATCH_SIZE)


def get_node_settings_model(config):
    """ Get addon's node settings"""
    try:
        settings_model = getattr(config, '{}_settings'.format('node'))
    except LookupError:
        return None
    return settings_model


@app.task(max_retries=5, default_retry_delay=60)
def task_sync_contributors(node_id, user_id):
    node = AbstractNode.objects.get(pk=node_id)
    user = OSFUser.objects.get(pk=user_id)

    # website/notifications/utils.py
    remove_contributor_from_subscriptions(node, user)
    # addons/base/institutions_utils.py
    sync_contributors(node)

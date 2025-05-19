# -*- coding: utf-8 -*-
import logging

from flask import request
from rest_framework import status as http_status

from . import SHORT_NAME
from .models import NodeSettings
# from .models import WorkflowProcessRegistration
from framework.exceptions import HTTPError
from website.ember_osf_web.views import use_ember_app
from website.project.decorators import (
    must_be_valid_project,
    must_have_addon,
)

logger = logging.getLogger(__name__)


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def workflow_get_config(**kwargs):
    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    return {'param_1': addon.get_param_1()}


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def workflow_set_config(**kwargs):
    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    try:
        param_1 = request.json['param_1']
    except KeyError:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)
    logger.info('param_1: {}'.format(param_1))
    addon.set_param_1(param_1)
    return {}


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def project_workflow(**kwargs):
    return use_ember_app()


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def workflow_get_config_ember(**kwargs):
    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    return {
        'data': {
            'id': node._id,
            'type': 'workflow-config',
            'attributes': {'param1': addon.get_param_1()},
        }
    }


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def workflow_set_config_ember(**kwargs):
    node = kwargs['node'] or kwargs['project']
    addon = node.get_addon(SHORT_NAME)
    try:
        config = request.json['data']['attributes']
        param_1 = config['param1']
    except KeyError:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)

    addon.set_param_1(param_1)
    return {
        'data': {
            'id': node._id,
            'type': 'workflow-config',
            'attributes': {'param1': param_1},
        }
    }


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def register_workflow_data(**kwargs):
    from framework.auth import Auth
    try:
        node = kwargs['node'] or kwargs['project']
        data = request.json
        workflow_registration = NodeSettings(
            workflow_engine=data['workflowEngine'],
            workflow_name=data['workflowName'],
            workflow_id=data['workflowID'],
            creator_token=data['creatorToken'],
            admin_token=data['adminToken'],
            executor_token=data['executorToken'],
            workflow_project_id=node._id,
            workflow_userid=node.creator,
            workflow_valid_userid=node.creator,
        )
        workflow_registration.save()

        node.add_log(
            action='workflow_file_added',
            params={
                'project': node.parent_id,
                'node': node._id,
                'filename': workflow_registration.workflow_name,
            },
            auth=Auth(user=node.creator),
        )

        return {'message': 'Workflow registration successful'}
    except KeyError as e:
        logger.error(f'KeyError: {e}, Request data: {request.json}')
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def update_workflow_data(workflow_id, **kwargs):
    from framework.auth import Auth
    try:
        data = request.json
        workflow = NodeSettings.objects.get(
            workflow_id=workflow_id,
            is_deleted=False
        )
        workflow.workflow_name = data['workflowName']
        workflow.creator_token = data['creatorToken']
        workflow.admin_token = data['adminToken']
        workflow.executor_token = data['executorToken']
        workflow.save()

        node = kwargs['node'] or kwargs['project']
        node.add_log(
            action='workflow_file_updated',
            params={
                'project': node.parent_id,
                'node': node._id,
                'filename': data['workflowName'],
            },
            auth=Auth(user=node.creator),
        )
        return {'message': 'Workflow update successful'}
    except NodeSettings.DoesNotExist:
        raise HTTPError(http_status.HTTP_404_NOT_FOUND)
    except KeyError as e:
        logger.error(f'KeyError: {e}, Request data: {request.json}')
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)


def get_registered_workflows(**kwargs):
    workflows = NodeSettings.objects.filter(is_deleted=False)
    workflow_list = [
        {
            'engine': workflow.workflow_engine,
            'name': workflow.workflow_name,
            'id': workflow.workflow_id,
            'creatorToken': workflow.creator_token,
            'adminToken': workflow.admin_token,
            'executorToken': workflow.executor_token,
            'processId': workflow.process_id,
            'process_name': workflow.process_name,
            'workflow_project_id': workflow.workflow_project_id,
            'process_project_id': workflow.process_project_id,
            'workflow_userid': workflow.workflow_userid,
            'workflow_valid_userid': workflow.workflow_valid_userid,
            'admin_mailaddr': workflow.admin_mailaddr,
            'researcher_mailaddr': workflow.researcher_mailaddr,
            'filePath': workflow.file_path,
        }
        for workflow in workflows
    ]
    return {'data': workflow_list}


def get_all_registered_workflows(**kwargs):
    workflows = NodeSettings.objects.all()
    workflow_list = [
        {
            'engine': workflow.workflow_engine,
            'name': workflow.workflow_name,
            'id': workflow.workflow_id,
            'creator_token': workflow.creator_token,
            'admin_token': workflow.admin_token,
            'executor_token': workflow.executor_token,
            'process_id': workflow.process_id,
            'process_name': workflow.process_name,
            'workflow_project_id': workflow.workflow_project_id,
            'process_project_id': workflow.process_project_id,
            'workflow_userid': workflow.workflow_userid,
            'workflow_valid_userid': workflow.workflow_valid_userid,
            'admin_mailaddr': workflow.admin_mailaddr,
            'researcher_mailaddr': workflow.researcher_mailaddr,
            'file_path': workflow.file_path,
        }
        for workflow in workflows
    ]
    return {'data': workflow_list}


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def remove_workflow_data(workflow_id, **kwargs):
    from framework.auth import Auth
    try:
        workflow = NodeSettings.objects.filter(
            workflow_id=workflow_id,
            is_deleted=False
        ).first()

        if workflow:
            workflow.delete()

            node = kwargs['node'] or kwargs['project']
            node.add_log(
                action='workflow_file_deleted',
                params={
                    'project': node.parent_id,
                    'node': node._id,
                    'filename': workflow.workflow_name,
                },
                auth=Auth(user=node.creator),
            )
            return {'message': 'Workflow removed successfully'}
        else:
            raise HTTPError(
                http_status.HTTP_404_NOT_FOUND,
                detail='Workflow not found'
            )

    except Exception as e:
        logger.error(f'Error removing workflow: {e}')
        raise HTTPError(
            http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to remove workflow'
        )


@must_be_valid_project
@must_have_addon(SHORT_NAME, 'node')
def workflow_connection(**kwargs):
    import os
    import json

    path = os.path.join(os.path.dirname(__file__), 'settings', 'workflow_connection.json')

    with open(path, 'r', encoding='utf-8') as file:
        data = json.load(file)

        extracted_data = [
            {
                'name': engine['name'],
                'url': engine['url'],
                'account': engine['account'],
                'password': engine['password']
            }
            for engine in data.values()
        ]

    return {'data': extracted_data}


def start_workflow_data(**kwargs):

    try:
        data = request.json

        workflowProcess_registration = NodeSettings(
            workflow_engine=data['workflow_engine'],
            workflow_name=data['workflow_name'],
            workflow_id=data['workflow_id'],
            creator_token=data['creator_token'],
            admin_token=data['admin_token'],
            executor_token=data['executor_token'],
            process_id=data['process_id'],
            process_name=data['process_name'],
            workflow_project_id=data['workflow_project_id'],
            process_project_id=data['process_project_id'],
            file_path=data['file_path'],
            admin_mailaddr=data['admin_mailaddr'],
            researcher_mailaddr=data['researcher_mailaddr'],
        )

        workflowProcess_registration.save()
        return {
            'status': 'OK',
            'message': 'Workflow process registration successful'
        }
    except KeyError as e:
        logger.error(f'KeyError: {e}, Request data: {request.json}')
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)

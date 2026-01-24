# -*- coding: utf-8 -*-
import mock
import pytest

from framework.exceptions import HTTPError


@pytest.mark.usefixtures('request_context')
def test_publish_project_metadata_mebyo_allows_empty_files_and_enqueues_task():
    """When MEBYO schema and no files, it should continue (not 400) and enqueue deposit task."""
    from addons.weko import views

    auth = mock.MagicMock()
    auth.user._id = 'user123'

    node = mock.MagicMock()
    node._id = 'node123'

    addon = mock.MagicMock()
    addon.owner._id = 'node123'
    addon.validate_index_id.return_value = True

    index_id = '100'
    metadata_type = 'draft_registration'
    metadata_id = 'md123'
    schema_id = 'schema-mebyo'
    project_metadata = {}  # no "grdm-files" => empty files

    signature = object()

    with mock.patch.object(views, 'is_mebyo_schema', return_value=True) as m_is_mebyo, \
            mock.patch.object(views, 'find_missing_required_fields', return_value=[]) as m_missing, \
            mock.patch.object(views.RegistrationSchema.objects, 'get') as m_get_schema, \
            mock.patch('addons.weko.views.deposit_metadata.s', return_value=signature, create=True) as m_sig, \
            mock.patch.object(views, 'enqueue_task') as m_enqueue:

        m_get_schema.return_value = mock.MagicMock(schema={})

        ret = views._publish_project_metadata(
            auth, node, addon,
            index_id=index_id,
            metadata_type=metadata_type,
            metadata_id=metadata_id,
            schema_id=schema_id,
            project_metadata=project_metadata,
        )

    # called twice: once for the "no files" branch, once for required-field check
    assert m_is_mebyo.call_count == 2
    m_missing.assert_called_once()  # required-field check was executed

    addon.set_publish_task_id.assert_called_once_with(f'/_/{metadata_type}/{metadata_id}', None)

    # file_metadatas and metadata_paths should be empty lists in the MEBYO/no-file case
    m_sig.assert_called_once_with(
        auth.user._id, index_id, node._id, metadata_id,
        schema_id, [], [project_metadata], [], f'/_/{metadata_type}/{metadata_id}',
    )
    m_enqueue.assert_called_once_with(signature)

    assert isinstance(ret, dict)
    assert ret['data']['attributes']['metadata_type'] == metadata_type
    assert ret['data']['attributes']['metadata_id'] == metadata_id
    # progress_url depends on request context; just ensure it exists
    assert 'progress_url' in ret['data']['attributes']


@pytest.mark.usefixtures('request_context')
def test_publish_project_metadata_mebyo_missing_required_fields_returns_400():
    """When required fields are missing (MEBYO schema), it should return HTTPError(400) with messages."""
    from addons.weko import views

    auth = mock.MagicMock()
    auth.user._id = 'user123'

    node = mock.MagicMock()
    node._id = 'node123'

    addon = mock.MagicMock()
    addon.owner._id = 'node123'
    addon.validate_index_id.return_value = True

    index_id = '100'
    metadata_type = 'draft_registration'
    metadata_id = 'md123'
    schema_id = 'schema-mebyo'
    project_metadata = {}  # doesn't matter; we'll force missing required

    with mock.patch.object(views, 'is_mebyo_schema', return_value=True), \
            mock.patch.object(views, 'find_missing_required_fields', return_value=['qid-a', 'qid-b']), \
            mock.patch.object(views.RegistrationSchema.objects, 'get', return_value=mock.MagicMock(schema={})), \
            mock.patch('addons.weko.views.deposit_metadata.s', create=True), \
            mock.patch.object(views, 'enqueue_task') as m_enqueue:

        ret = views._publish_project_metadata(
            auth, node, addon,
            index_id=index_id,
            metadata_type=metadata_type,
            metadata_id=metadata_id,
            schema_id=schema_id,
            project_metadata=project_metadata,
        )

    assert isinstance(ret, HTTPError)
    assert ret.code == 400
    assert ret.data['message_short'] == 'Missing required fields'
    assert 'Required fields are missing' in ret.data['message_long']
    assert 'qid-a' in ret.data['message_long']
    assert 'qid-b' in ret.data['message_long']
    m_enqueue.assert_not_called()


import pytest
from unittest.mock import MagicMock, patch

@pytest.mark.django_db
def test_groups_get_config_returns_expected_structure():
    mock_addon = MagicMock()
    mock_node = MagicMock()
    mock_node.get_addon.return_value = mock_addon
    mock_node._id = 'abc123'
    mock_node.is_deleted = False
    mock_node.is_public = True
    mock_node.is_collection = False
    mock_node.is_quickfiles = False

    kwargs = {'node': mock_node, 'project': None}
    auth = MagicMock()

    with patch('website.project.decorators.must_be_valid_project', lambda f: f), \
         patch('framework.auth.decorators.must_be_logged_in', lambda f: f), \
         patch('website.project.decorators.must_have_permission', lambda *a, **kw: lambda f: f), \
         patch('website.project.decorators.must_have_addon', lambda *a, **kw: lambda f: f):
        from addons.groups import views as groups_views
        import importlib
        importlib.reload(groups_views)

        response = groups_views.groups_get_config(auth, **kwargs)

    assert 'data' in response
    assert response['data']['type'] == 'groups-config'
    assert isinstance(response['data']['attributes'], dict)

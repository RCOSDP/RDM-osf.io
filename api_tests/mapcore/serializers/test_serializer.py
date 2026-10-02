import pytest

from api.mapcore.serializers import MapCoreGroupSerializer
from osf.models.mapcore_group import MapCoreGroup
from tests.utils import make_drf_request_with_version
from website import settings as website_settings


@pytest.mark.django_db
def test_mapcore_group_serializer_basic():
    mg = MapCoreGroup.objects.create(_id='test-group-serializer')

    req = make_drf_request_with_version(version='2.0')
    serializer = MapCoreGroupSerializer(mg, context={'request': req})
    result = serializer.data
    # JSONAPI serializers in the project produce a top-level 'data' key
    data = result['data'] if 'data' in result else result

    assert data['type'] == 'mapcore-groups'
    assert data['id'] == mg.id

    attrs = data['attributes']
    assert attrs['mapcore_group_id'] == mg.id
    assert attrs['name'] == mg._id
    assert 'created' in attrs
    assert 'modified' in attrs

    expected_url = f'{website_settings.MAPCORE_GROUP_HOSTNAME}{website_settings.MAPCORE_GROUP_API_PATH}{mg._id}/'
    assert data['links']['self'] == expected_url

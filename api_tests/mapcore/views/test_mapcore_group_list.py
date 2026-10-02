import pytest

from api.base.settings.defaults import API_BASE
from osf.models.mapcore_group import MapCoreGroup
from osf.models.mapcore_user_group import MapCoreUserGroup
from osf_tests.factories import AuthUserFactory
from tests.base import ApiTestCase


@pytest.mark.django_db
class TestMapCoreGroupList(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = AuthUserFactory()

        # Create MapCoreGroups and link them to the user via MapCoreUserGroup
        self.mapcore_group1 = MapCoreGroup.objects.create(_id='test-mapcore-1')
        self.mapcore_group2 = MapCoreGroup.objects.create(_id='another-group')

        MapCoreUserGroup.objects.create(
            mapcore_group=self.mapcore_group1,
            user=self.user
        )
        MapCoreUserGroup.objects.create(
            mapcore_group=self.mapcore_group2,
            user=self.user
        )

        self.url = f'/{API_BASE}map_core/groups/'

    def test_list_mapcore_groups_for_authenticated_user(self):
        res = self.app.get(self.url, auth=self.user.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 2

        item = res.json['data'][0]
        assert 'id' in item
        assert 'attributes' in item
        assert 'links' in item
        assert item['type'] == 'mapcore-groups'

    def test_search_param_filters_results(self):
        # Create an extra group that won't match the search term
        MapCoreGroup.objects.create(_id='zzz-unmatched')

        # Search for 'another' should only return the matching group(s)
        res = self.app.get(f'{self.url}?search=another', auth=self.user.auth)
        assert res.status_code == 200
        data = res.json['data']
        assert len(data) == 1
        assert data[0]['attributes']['name'] == 'another-group'

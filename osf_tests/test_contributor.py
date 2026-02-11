import pytest

from osf_tests.factories import ContributorFactory

pytestmark = pytest.mark.django_db


class TestContributor:

    @pytest.fixture()
    def contributor(self):
        return ContributorFactory()

    def test_is_data_steward_default_false(self, contributor):
        assert contributor.is_data_steward is False

    def test_data_steward_old_permission_default_none(self, contributor):
        assert contributor.data_steward_old_permission is None

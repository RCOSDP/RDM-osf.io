import unittest
import pytest

from addons.datasteward.models import UserSettings, DataStewardProvider
from osf_tests.factories import AuthUserFactory

pytestmark = pytest.mark.django_db


class TestDataStewardProvider(unittest.TestCase):
    def setUp(self):
        self.provider = DataStewardProvider()

    def test_account_none(self):
        assert self.provider.account is None

    def test_oauth_provider_repr(self):
        assert repr(self.provider) == '<DataStewardProvider: anonymous>'


class TestUserSettings(unittest.TestCase):
    def setUp(self):
        self.user = AuthUserFactory()
        self.user_settings = UserSettings(owner=self.user)

    def test_enabled_default_false(self):
        assert self.user_settings.enabled is False

    def test_to_json(self):
        expected_json = {
            'addon_short_name': 'datasteward',
            'addon_full_name': 'DataSteward',
            'has_auth': False,
            'nodes': []
        }
        assert self.user_settings.to_json(self.user) == expected_json

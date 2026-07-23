import pytest
from addons.groups.models import UserSettings, NodeSettings

@pytest.mark.django_db
def test_user_settings_creation():
    user_settings = UserSettings.objects.create()
    assert isinstance(user_settings, UserSettings)

@pytest.mark.django_db
def test_node_settings_user_settings_fk():
    user_settings = UserSettings.objects.create()
    node_settings = NodeSettings.objects.create(user_settings=user_settings)
    assert node_settings.user_settings == user_settings

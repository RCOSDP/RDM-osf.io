from addons.base.models import BaseUserSettings, BaseNodeSettings
from django.db import models


class UserSettings(BaseUserSettings):
    pass


class NodeSettings(BaseNodeSettings):
    user_settings = models.ForeignKey(UserSettings, null=True, blank=True, on_delete=models.CASCADE)

import logging

from addons.base.models import BaseNodeSettings
from django.db import models
from . import settings

logger = logging.getLogger(__name__)

class NodeSettings(BaseNodeSettings):
    param_1 = models.TextField(blank=True, null=True)

    def get_param_1(self):
        if self.param_1 is None or self.param_1 == '':
            return settings.DEFAULT_PARAM_1
        return self.param_1

    def set_param_1(self, param_1):
        self.param_1 = param_1
        self.save()

    workflow_engine = models.CharField(max_length=255, blank=True, null=True)
    workflow_name = models.CharField(max_length=255, blank=True, null=True)
    workflow_id = models.CharField(max_length=255, blank=True, null=True)
    creator_token = models.CharField(max_length=255, blank=True, null=True)
    admin_token = models.CharField(max_length=255, blank=True, null=True)
    executor_token = models.CharField(max_length=255, blank=True, null=True)

    process_id = models.CharField(max_length=255, blank=True, null=True)
    process_name = models.CharField(max_length=255, blank=True, null=True)
    workflow_project_id = models.CharField(max_length=255, blank=True, null=True)
    process_project_id = models.CharField(max_length=255, blank=True, null=True)
    workflow_userid = models.CharField(max_length=255, blank=True, null=True)
    workflow_valid_userid = models.CharField(max_length=255, blank=True, null=True)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    admin_mailaddr = models.CharField(max_length=255, blank=True, null=True)
    researcher_mailaddr = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.workflow_name

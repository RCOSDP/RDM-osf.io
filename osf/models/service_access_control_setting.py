from django.db import models
from osf.models.base import BaseModel


class ServiceAccessControlSetting(BaseModel):
    institution_id = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    is_ial2_or_aal2 = models.BooleanField()
    user_domain = models.CharField(max_length=255)
    project_limit_number = models.IntegerField(null=True)
    is_whitelist = models.BooleanField()
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'osf_service_access_control_setting'
        ordering = ['pk']
        indexes = [
            models.Index(fields=['institution_id', 'domain', 'is_ial2_or_aal2', 'user_domain']),
        ]

from django.db import models

from osf.models.base import BaseModel
from osf.models.service_access_control_setting import ServiceAccessControlSetting


class Function(BaseModel):
    function_code = models.CharField(max_length=255)
    service_access_control_setting = models.ForeignKey(ServiceAccessControlSetting, related_name='functions', on_delete=models.CASCADE)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['pk']

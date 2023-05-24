from django.db import models

from addons.osfstorage.models import Region
from osf.models.base import BaseModel


class UserStorageQuota(BaseModel):
    class Meta:
        unique_together = ('user', 'region')

    user = models.ForeignKey('OSFUser', on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    max_quota = models.IntegerField(default=0)
    used = models.BigIntegerField(default=0)

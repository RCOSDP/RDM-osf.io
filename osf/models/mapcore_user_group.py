from django.db import models
from osf.models.base import BaseModel
from osf.models.mapcore_group import MapCoreGroup


class MapCoreUserGroup(BaseModel):
    mapcore_group = models.ForeignKey(MapCoreGroup, on_delete=models.CASCADE, related_name='mapcore_user_groups')
    user = models.ForeignKey('osf.OSFUser', related_name='mapcore_user_groups', on_delete=models.CASCADE)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'osf_mapcore_user_group'

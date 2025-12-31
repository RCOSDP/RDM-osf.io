from django.db import models
from osf.models.base import BaseModel
from website.settings import MAPCORE_GROUP_HOSTNAME, MAPCORE_GROUP_API_PATH


class MapCoreGroup(BaseModel):
    _id = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'osf_mapcore_group'

    @property
    def absolute_url(self):
        return f'{MAPCORE_GROUP_HOSTNAME}{MAPCORE_GROUP_API_PATH}{self._id}/'

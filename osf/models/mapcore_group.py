from django.db import models
from osf.models.base import BaseModel


class MapCoreGroup(BaseModel):
    _id = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'osf_mapcore_group'

from django.db import models
from osf.models.base import BaseModel
from osf.models.mapcore_group import MapCoreGroup
from django.contrib.auth.models import Group as AuthGroup
import logging

logger = logging.getLogger(__name__)

class MapCoreNodeGroup(BaseModel):
    node = models.ForeignKey('osf.Node', on_delete=models.CASCADE, related_name='mapcore_node_groups')
    group = models.ForeignKey(AuthGroup, on_delete=models.CASCADE, related_name='auth_group_mapcore_nodes')
    mapcore_group = models.ForeignKey(MapCoreGroup, on_delete=models.CASCADE, related_name='mapcore_group_nodes')
    creator = models.ForeignKey('osf.OSFUser', related_name='mapcore_node_group_creator', on_delete=models.CASCADE)
    is_deleted = models.BooleanField(default=False)
    visible = models.BooleanField(default=False)
    class Meta:
        db_table = 'osf_mapcore_node_group'
        order_with_respect_to = 'mapcore_group'

    @property
    def get_permission(self):
        """
        If the auth group name matches patterns like:
          - node_<node_id>_admin
          - node_<node_id>_read
          - node_<node_id>_write
        return the permission string: 'admin', 'read', or 'write'.
        Otherwise return None.
        """
        import re
        name = getattr(self.group, 'name', '') or ''
        m = re.match(r'^node_[^_]+_(admin|read|write)$', name)
        if m:
            return m.group(1)
        return None

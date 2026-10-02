from django.apps import apps
from rest_framework import serializers as ser
from api.base.serializers import JSONAPISerializer, LinksField, TypeField, VersionedDateTimeField
from website.settings import MAPCORE_GROUP_HOSTNAME, MAPCORE_GROUP_API_PATH


MapCoreGroup = apps.get_model('osf.MapCoreGroup')

class MapCoreGroupSerializer(JSONAPISerializer):
    """
    JSONAPI serializer for MapCoreGroup model.
    Keep fields minimal — expand if the model exposes more attributes that should be surfaced.
    """
    id = ser.IntegerField(read_only=True)
    mapcore_group_id = ser.IntegerField(source='id', read_only=True)
    name = ser.CharField(source='_id', read_only=True)
    created = VersionedDateTimeField(read_only=True)
    modified = VersionedDateTimeField(read_only=True)
    links = LinksField({
        'self': 'get_absolute_url',
    })
    type = TypeField()

    class Meta:
        type_ = 'mapcore-groups'

    def get_absolute_url(self, obj):
        return f'{MAPCORE_GROUP_HOSTNAME}{MAPCORE_GROUP_API_PATH}{obj._id}/'

from django.apps import apps
from rest_framework import generics
from rest_framework import permissions as drf_permissions
from api.base.views import JSONAPIBaseView
from framework.auth.oauth_scopes import CoreScopes
from api.mapcore.serializers import MapCoreGroupSerializer
from api.base import permissions as base_permissions
from api.base.utils import get_user_auth
from api.base.pagination import MapCoreGroupPagination


class MapCoreGroupList(JSONAPIBaseView, generics.ListAPIView):
    """
    List of MapCoreGroups
    """
    permission_classes = (
        drf_permissions.IsAuthenticated,
        base_permissions.TokenHasScope,
    )
    required_read_scopes = [CoreScopes.NODE_CONTRIBUTORS_READ]
    model_class = apps.get_model('osf.MapCoreGroup')

    serializer_class = MapCoreGroupSerializer
    view_category = 'mapcore_groups'
    view_name = 'mapcore-group-list'

    ordering = ('_id', )  # default ordering
    pagination_class = MapCoreGroupPagination

    def get_queryset(self):
        auth = get_user_auth(self.request)
        if not auth or not auth.user or not auth.user.is_authenticated:
            return self.model_class.objects.none()

        qs = self.model_class.objects.filter(mapcore_user_groups__user=auth.user, is_deleted=False)
        q = self.request.GET.get('search') or self.request.query_params.get('search')
        if q:
            q = q.strip()
            if q:
                qs = qs.filter(_id__icontains=q)

        return qs

    def get(self, request, *args, **kwargs):
        result = super().get(request, *args, **kwargs)
        return result

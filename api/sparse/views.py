from rest_framework.exceptions import MethodNotAllowed
from api.sparse.serializers import SparseNodeSerializer, SparseRegistrationSerializer
from api.nodes.views import (
    NodeDetail,
    NodeChildrenList,
    NodeList,
    LinkedNodesList,
)

from api.registrations.views import (
    RegistrationDetail,
    RegistrationChildrenList,
    RegistrationList,
    RegistrationMixin,
    RegistrationLinkedRegistrationsList,
)

from api.users.views import UserNodes, UserRegistrations
import logging

logger = logging.getLogger(__name__)

class BaseSparseMixin(object):
    view_category = 'sparse'
    serializer_class = None

    # overrides NodeList because these endpoints don't allow writing
    def perform_create(self, *args):
        logger.info('103')
        logger.info('104')
        logger.info('105')
        logger.info('106')
        logger.info('107')
        logger.info('108')
        logger.info('109')
        logger.info('110')
        raise MethodNotAllowed(method=self.request.method)

    # overrides NodeList because these endpoints don't allow writing
    def perform_update(self, *args):
        logger.info('103')
        logger.info('104')
        logger.info('105')
        logger.info('106')
        logger.info('107')
        logger.info('108')
        logger.info('109')
        logger.info('110')
        raise MethodNotAllowed(method=self.request.method)

    # overrides NodeDetail because these endpoints don't allow writing
    def perform_destroy(self, *args):
        logger.info('103')
        logger.info('104')
        logger.info('105')
        logger.info('106')
        logger.info('107')
        logger.info('108')
        logger.info('109')
        logger.info('110')
        raise MethodNotAllowed(method=self.request.method)

    # overrides NodeList because these endpoints don't allow writing
    def allow_bulk_destroy_resources(self, *args):
        logger.info('103')
        logger.info('104')
        logger.info('105')
        logger.info('106')
        logger.info('107')
        logger.info('108')
        logger.info('109')
        logger.info('110')
        raise MethodNotAllowed(method=self.request.method)

    def get_serializer_class(self):
        logger.info('103')
        logger.info('104')
        logger.info('105')
        logger.info('106')
        logger.info('107')
        logger.info('108')
        logger.info('109')
        logger.info('110')
        return self.serializer_class


class SparseNodeMixin(BaseSparseMixin):
    serializer_class = SparseNodeSerializer


class SparseRegistrationMixin(BaseSparseMixin):
    serializer_class = SparseRegistrationSerializer


class SparseNodeList(SparseNodeMixin, NodeList):
    logger.info('111')
    pass


class SparseLinkedNodesList(RegistrationMixin, SparseNodeMixin, LinkedNodesList):
    pass


class SparseLinkedRegistrationsList(SparseRegistrationMixin, RegistrationLinkedRegistrationsList):
    pass


class SparseUserNodeList(SparseNodeMixin, UserNodes):
    logger.info('112')
    pass


class SparseNodeDetail(SparseNodeMixin, NodeDetail):
    pass


class SparseNodeChildrenList(SparseNodeMixin, NodeChildrenList):
    pass


class SparseRegistrationDetail(SparseRegistrationMixin, RegistrationDetail):
    pass


class SparseRegistrationList(SparseRegistrationMixin, RegistrationList):
    pass


class SparseRegistrationChildrenList(SparseRegistrationMixin, RegistrationChildrenList):
    pass


class SparseUserRegistrationList(SparseRegistrationMixin, UserRegistrations):
    pass

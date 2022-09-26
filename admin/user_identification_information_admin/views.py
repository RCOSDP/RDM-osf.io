from django.http import Http404

from admin.user_identification_information.views import (
    UserIdentificationListView,
    UserIdentificationDetailView,
)


class UserIdentificationAdminListView(UserIdentificationListView):

    def get_user_list(self):
        if self.is_super_admin or not self.is_authenticated:
            raise Http404('Page not found')
        return self.user_list()


class UserIdentificationDetailAdminView(UserIdentificationDetailView):

    def get_object(self):
        if self.is_super_admin or not self.is_authenticated:
            raise Http404('Page not found')
        return self.user_details()
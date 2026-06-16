from django.conf.urls import url
from . import views

app_name = 'admin'

urlpatterns = [
    url(r'^$', views.LoginAccessControlListView.as_view(), name='list'),
    url(r'^login_availability_default$', views.UpdateLoginAvailabilityDefaultView.as_view(), name='update_login_availability_default'),
    url(r'^authentication_attribute/save$', views.SaveAuthenticationAttributeListView.as_view(), name='save_authentication_attribute_list'),
    url(r'^authentication_attribute/update$', views.UpdateAuthenticationAttributeView.as_view(), name='update_authentication_attribute'),
    url(r'^authentication_attribute/delete$', views.DeleteAuthenticationAttributeView.as_view(), name='delete_authentication_attribute'),
    url(r'^authentication_attribute/logic_condition$', views.UpdateLoginLogicConditionView.as_view(), name='update_login_logic_condition'),
    url(r'^mail_address/save$', views.SaveMailAddressListView.as_view(), name='save_mail_address_list'),
    url(r'^mail_address/update$', views.UpdateMailAddressView.as_view(), name='update_mail_address'),
    url(r'^mail_address/delete$', views.DeleteMailAddressView.as_view(), name='delete_mail_address'),
]

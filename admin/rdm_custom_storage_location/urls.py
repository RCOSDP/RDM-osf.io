from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^external_acc_update/(?P<access_token>-?\w+)/$', views.external_acc_update, name='external_acc_update'),
    url(r'^institutional_storage/$', views.InstitutionalStorageView.as_view(), name='institutional_storage'),
    url(r'^icon/(?P<addon_name>\w+)/(?P<icon_filename>\w+\.\w+)$', views.IconView.as_view(), name='icon'),
    url(r'^test_connection/$', views.TestConnectionView.as_view(), name='test_connection'),
    url(r'^save_credentials/$', views.SaveCredentialsView.as_view(), name='save_credentials'),
    url(r'^credentials/$', views.FetchCredentialsView.as_view(), name='credentials'),
    url(r'^fetch_temporary_token/$', views.FetchTemporaryTokenView.as_view(), name='fetch_temporary_token'),
    url(r'^remove_auth_data_temporary/$', views.RemoveTemporaryAuthData.as_view(), name='remove_auth_data_temporary'),
    url(r'^usermap/$', views.UserMapView.as_view(), name='usermap'),
    url(r'^change_allow/$', views.ChangeAllowedViews.as_view(), name='change_allow'),
    url(r'^change_readonly/$', views.ChangeReadonlyViews.as_view(), name='change_readonly'),
    url(r'^change_attribute_authentication/$', views.ChangeAuthenticationAttributeView.as_view(),
        name='change_attribute_authentication'),
    url(r'^add_attribute_form/$', views.AddAttributeFormView.as_view(), name='add_attribute_form'),
    url(r'^delete_attribute_form/$', views.DeleteAttributeFormView.as_view(), name='delete_attribute_form'),
    url(r'^save_attribute_form/$', views.SaveAttributeFormView.as_view(), name='save_attribute_form'),
    url(r'^save_institutional_storage/$', views.SaveInstitutionalStorageView.as_view(),
        name='save_institutional_storage'),
]

from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.ServiceAccessControlSettingView.as_view(), name='list'),
    url(r'^setting$', views.ServiceAccessControlSettingCreateView.as_view(), name='create_setting'),
]

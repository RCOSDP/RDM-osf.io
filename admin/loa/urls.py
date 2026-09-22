from django.conf.urls import url
from . import views

app_name = 'admin'

urlpatterns = [
    url(r'^$', views.ListLoA.as_view(), name='list'),
    url(r'^bulk_add/$', views.BulkAddLoA.as_view(), name='bulk_add'),
]

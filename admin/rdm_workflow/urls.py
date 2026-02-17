from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.WorkflowEngineInstitutionListView.as_view(), name='home'),
    url(r'^(?P<institution_id>\d+)/$', views.WorkflowEngineListView.as_view(), name='engine-list'),
    url(r'^(?P<institution_id>\d+)/(?P<engine_id>[^/]+)/edit/$', views.WorkflowEngineEditView.as_view(), name='engine-edit'),
    url(r'^(?P<institution_id>\d+)/(?P<engine_id>[^/]+)/keys/$', views.WorkflowEngineKeyView.as_view(), name='engine-keys'),
]

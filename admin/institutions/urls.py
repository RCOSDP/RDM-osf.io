from django.conf.urls import url
from . import views

app_name = 'admin'

urlpatterns = [
    url(r'^$', views.InstitutionList.as_view(), name='list'),
    url(r'^institution_list/$', views.InstitutionUserList.as_view(), name='institution_list'),
    url(r'^create/$', views.CreateInstitution.as_view(), name='create'),
    url(r'^import/$', views.ImportInstitution.as_view(), name='import'),
    url(r'^quota_recalc/all/$', views.quota_recalc_all, name='quota_recalc_all'),
    url(r'^(?P<institution_id>[0-9]+)/$', views.InstitutionDetail.as_view(), name='detail'),
    url(r'^(?P<institution_id>[0-9]+)/export/$', views.InstitutionExport.as_view(), name='export'),
    url(r'^(?P<institution_id>[0-9]+)/delete/$', views.DeleteInstitution.as_view(), name='delete'),
    url(r'^(?P<institution_id>[0-9]+)/cannot_delete/$', views.CannotDeleteInstitution.as_view(), name='cannot_delete'),
    url(r'^(?P<institution_id>[0-9]+)/nodes/$', views.InstitutionNodeList.as_view(), name='nodes'),
    url(r'^(?P<institution_id>[0-9]+)/register/$', views.InstitutionalMetricsAdminRegister.as_view(), name='register_metrics_admin'),
    url(r'^user_list_by_institution_id/(?P<institution_id>.*)/$', views.UserListByInstitutionID.as_view(), name='institution_user_list'),
    url(r'^statistical_status_default_storage/$', views.StatisticalStatusDefaultStorage.as_view(), name='statistical_status_default_storage'),
]

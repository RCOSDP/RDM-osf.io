from django.conf.urls import include, url
from admin.project_limit_number.settings import views

app_name = 'admin'

urlpatterns = [
    url(r'^settings/', include('admin.project_limit_number.settings.urls', namespace='settings')),
    url(r'^templates/', include('admin.project_limit_number.templates.urls', namespace='templates')),
]

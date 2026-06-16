from django.conf.urls import url

from api.mapcore import views

app_name = 'osf'

urlpatterns = [
    # Examples:
    # url(r'^$', 'api.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^groups/$', views.MapCoreGroupList.as_view(), name=views.MapCoreGroupList.view_name),
]

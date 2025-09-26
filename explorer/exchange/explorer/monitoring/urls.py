from django.urls import path
from ..monitoring.views import MonitorApiView
app_name = 'monitoring'

urlpatterns = [
    path(
        '',
        MonitorApiView.as_view(),
        name='monitor'
    ),
]

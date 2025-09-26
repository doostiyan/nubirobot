from django.urls import path
from ..basis.views import WelcomeView

app_name = 'basis'

urlpatterns = [
    path(
        '',
        WelcomeView.as_view(),
        name='welcome'
    ),
]

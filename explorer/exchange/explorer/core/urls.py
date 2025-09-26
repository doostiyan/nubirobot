from django.urls import path
from .language.views import language_view

app_name = 'core'

urlpatterns = [
    path(
        'languages',
        language_view,
        name='language'
    )
]

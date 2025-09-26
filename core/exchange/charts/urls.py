from django.urls import path

from exchange.charts.views import chart, study

urlpatterns = [
    path('charts', chart.process_request),
    path('study_templates', study.process_request),
]

from django.urls import path

from exchange.explorer.networkproviders.views import (NetworkListView,
                                                      NetworkDetailByIdView,
                                                      NetworkDetailByNameView,
                                                      ProviderListView,
                                                      ProviderDetailByIdView,
                                                      CheckProviderByIdView,
                                                      ProviderDetailByNetworkView,
                                                      NetworkDefaultProviderListView,
                                                      NetworkDefaultProviderDetailByNameView)
from exchange.explorer.networkproviders.views.provider_view import URLListByProviderIdView, URLDetailByProviderIdView
from exchange.explorer.networkproviders.views.url_view import URLListView, URLDetailView

app_name = 'networkproviders'

urlpatterns = [
    path('networks', NetworkListView.as_view(), name='network_list'),
    path('networks/<int:network_id>', NetworkDetailByIdView.as_view(), name='network_detail_by_id'),
    path('networks/<str:network_name>', NetworkDetailByNameView.as_view(), name='network_detail_by_name'),

    path('providers', ProviderListView.as_view(), name='provider_list'),
    path('providers/<int:provider_id>', ProviderDetailByIdView.as_view(), name='provider_detail_by_id'),
    path('providers/<int:provider_id>/check', CheckProviderByIdView.as_view(), name='check_provider_by_id'),
    path('providers/<str:network_name>', ProviderDetailByNetworkView.as_view(), name='provider_detail_by_network'),
    path('providers/<int:provider_id>/urls', URLListByProviderIdView.as_view(),
         name='url_list_by_provider_id'),
    path('providers/<int:provider_id>/urls/<int:url_id>', URLDetailByProviderIdView.as_view(),
         name='url_detail_by_provider_id'),

    path('defaultproviders', NetworkDefaultProviderListView.as_view(), name='default_provider_list'),
    path('defaultproviders/<str:network_name>', NetworkDefaultProviderDetailByNameView.as_view(),
         name='default_provider_detail_by_network'),

    path('urls', URLListView.as_view(), name='urls_list'),
    path('urls/<int:url_id>', URLDetailView.as_view(), name='url_detail')
]

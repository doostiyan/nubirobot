from django.urls import path

from .views import sandbox_gateway, wallets_deposit_shetab_callback

urlpatterns = [
    path('shetab-callback', wallets_deposit_shetab_callback, name='shetab_callback'),
    path('sandbox-gateway', sandbox_gateway, name='sandbox_gateway'),
]

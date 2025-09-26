from django.urls import path, register_converter
from exchange.explorer.utils.url_handler import UrlConverter
from .views import (BatchWalletBalanceView, WalletBalanceView,
                    WalletTransactionsView, WalletATAView)

app_name = 'wallets'
register_converter(UrlConverter, 'everything')
urlpatterns = [
    path(
        '<everything:address>/balance',
        WalletBalanceView.as_view(),
        name='wallet_balance'
    ),
    path(
        'balance',
        BatchWalletBalanceView.as_view(),
        name='batch_wallet_balance'
    ),
    path(
        '<everything:address>/transactions',
        WalletTransactionsView.as_view(),
        name='wallet_transactions'
    ),
    path(
        '<everything:address>/ata/',
        WalletATAView.as_view(),
        name='wallet_ata'
    ),
]

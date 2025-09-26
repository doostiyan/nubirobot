from django.urls import path, register_converter
from exchange.explorer.utils.url_handler import UrlConverter

from .views import BatchTransactionDetailsView, TransactionDetailsView, ConfirmedTransactionDetailsView

app_name = 'transactions'

register_converter(UrlConverter, 'everything')
urlpatterns = [
    path(
        'confirmed/<everything:tx_hash>',
        ConfirmedTransactionDetailsView.as_view(),
        name='confirmed_transaction_details'
    ),
    path(
        '<everything:tx_hash>',
        TransactionDetailsView.as_view(),
        name='transaction_details'
    ),
    path(
        '',
        BatchTransactionDetailsView.as_view(),
        name='batch_transaction_details'
    )
]
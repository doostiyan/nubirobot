import jdatetime
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.asset_backed_credit.api.mixins import FiltersMixin
from exchange.asset_backed_credit.api.serializers import DebitCardSettlementSchema, DebitCardTransactionSchema
from exchange.asset_backed_credit.api.views import InternalABCView, user_eligibility_api
from exchange.asset_backed_credit.exceptions import ServiceNotFoundError
from exchange.asset_backed_credit.models import Card
from exchange.asset_backed_credit.services.debit.transaction import get_debit_card_settlements, get_debit_card_transfers
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.api import NobitexAPIError
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import paginate
from exchange.features.utils import require_feature


class DebitCardTransferTransactionListView(FiltersMixin, InternalABCView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='abcDebitCardTransferTransactionList'))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def get(self, request, card_id: int):
        """
        This API returns users debit card transactions
        GET /asset-backed-credit/debit/cards/<int:id>/transfers
        """

        user = request.user
        filters = self.get_filters(request=request)

        try:
            transfer_transactions = get_debit_card_transfers(
                user=user,
                card_id=card_id,
                filters=filters,
            )
        except ServiceNotFoundError as e:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=e.__class__.__name__, description=str(e)
            )
        except Card.DoesNotExist:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardNotFound',
                description='card not found.',
            )

        transfers, has_next = paginate(
            transfer_transactions, page=filters.page, page_size=filters.page_size, check_next=True
        )
        transfers = [
            DebitCardTransactionSchema(
                created_at=trx['created_at'].strftime('%Y-%m-%dT%H:%M:%S'),
                type=self._get_transfer_type(trx),
                amount=abs(trx['amount']),
                balance=trx['balance'],
                currency=trx['currency'],
            ).model_dump(by_alias=True)
            for trx in transfers
        ]
        return self.response({'status': 'ok', 'transfers': transfers, 'hasNext': has_next})

    @staticmethod
    def _get_transfer_type(transaction):
        return 'برداشت' if transaction['amount'] < 0 else 'واریز'


class DebitCardSettlementTransactionListView(FiltersMixin, InternalABCView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='abcDebitCardSettlementTransactionList'))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def get(self, request, card_id: int):
        """
        This API returns users debit card transactions
        GET /asset-backed-credit/debit/cards/<int:id>/settlements
        """

        user = request.user
        filters = self.get_filters(request=request)

        try:
            settlements = get_debit_card_settlements(
                user=user,
                card_id=card_id,
                filters=filters,
            )
        except ServiceNotFoundError as e:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=e.__class__.__name__, description=str(e)
            )
        except Card.DoesNotExist:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardNotFound',
                description='card not found.',
            )

        settlements, has_next = paginate(settlements, page=filters.page, page_size=filters.page_size, check_next=True)
        settlements = [
            DebitCardSettlementSchema(
                created_at=item['created_at'].strftime('%Y-%m-%dT%H:%M:%S'),
                type='خرید',
                amount=int(item['amount']),
                balance=int(item['remaining_rial_wallet_balance']),
            ).model_dump(by_alias=True)
            for item in settlements
        ]
        return self.response({'status': 'ok', 'settlements': settlements, 'hasNext': has_next})

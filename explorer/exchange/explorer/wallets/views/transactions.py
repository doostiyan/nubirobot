from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema

from ...authentication.permissions import UserHasAPIKey
from ...authentication.services.throttling import APIKeyRateThrottle
from ..serializers import TransactionSerializer, WalletTransactionSerializer
from ..services import WalletExplorerService
from ...transactions.services import TransactionExplorerService
from ...utils.prometheus import histogram_observer

currency_param = openapi.Parameter('currency', openapi.IN_QUERY, type=openapi.TYPE_STRING)


class WalletTransactionsView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        operation_id='wallet_transactions',
        operation_description="Retrieve the transactions(including details of them) of an address at using network, currency and address itself.",
        manual_parameters=[currency_param],
        responses={200: TransactionSerializer(many=False)},
    )
    @histogram_observer
    def get(self, request, network, address):
        network = network.upper()
        currency = request.query_params.get('currency')
        contract_address = request.query_params.get('contract_address')
        contract_address = None if contract_address in ["''", 'None'] else contract_address
        tx_direction = request.query_params.get('tx_direction', '')
        tx_hash = request.query_params.get('tx_hash')
        data = {'address': address,
                'network': network,
                'currency': currency}
        if tx_direction:
            data['tx_direction'] = tx_direction

        serializer = WalletTransactionSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        wallet_transactions_dto = None
        if tx_hash:
            wallet_transactions_dto = TransactionExplorerService.get_confirmed_transaction_details(network=network,
                                                                                                   tx_hash=tx_hash,
                                                                                                   address=address,
                                                                                                   )
        if not wallet_transactions_dto:
            wallet_transactions_dto = (
                WalletExplorerService.get_wallet_transactions_dto(network=network,
                                                                  address=address,
                                                                  currency=currency,
                                                                  contract_address=contract_address,
                                                                  tx_hash=tx_hash,
                                                                  tx_direction_filter=tx_direction))

        wallet_transaction_serializer = TransactionSerializer(instance=wallet_transactions_dto, many=True)
        wallet_transactions_data = wallet_transaction_serializer.data
        return Response(data=wallet_transactions_data)

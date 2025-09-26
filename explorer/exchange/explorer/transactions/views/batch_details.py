from drf_yasg.utils import swagger_auto_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from exchange.explorer.authentication.permissions import UserHasAPIKey
from exchange.explorer.authentication.services.throttling import APIKeyRateThrottle
from exchange.explorer.transactions.serializers import BatchTransactionDetailSerializer
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.utils.prometheus import histogram_observer


class BatchTransactionDetailsView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        responses={200: BatchTransactionDetailSerializer(many=False)},
        request_body=BatchTransactionDetailSerializer(many=False),
        operation_id='batch_transaction_details',
        operation_description=(
                "Retrieve the details of transactions (Multiple transactions at once) "
                "by network and transactions' hash."
        )
    )
    @histogram_observer
    def post(self, request: Request, network: str) -> Response:
        currency = request.query_params.get('currency')
        provider_name: str = request.query_params.get('provider')
        base_url: str = request.query_params.get('base_url')
        base_url = None if base_url in ["''", 'None'] else base_url
        provider_name = None if provider_name in ["''", 'None'] else provider_name
        currency = None if currency in ["''", 'None'] else currency
        data = request.data.copy()
        serializer = BatchTransactionDetailSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        network = network.upper()
        transactions_details_dto = TransactionExplorerService.get_transaction_details_based_on_provider_name_and_url(
            tx_hashes=serializer.validated_data.get('tx_hashes'),
            provider_name=provider_name,
            base_url=base_url,
            network=network,
            currency=currency,
        )
        data['transactions'] = transactions_details_dto
        transaction_details_serializer = BatchTransactionDetailSerializer(instance=data)
        transaction_details_data = transaction_details_serializer.data
        return Response(data=transaction_details_data)

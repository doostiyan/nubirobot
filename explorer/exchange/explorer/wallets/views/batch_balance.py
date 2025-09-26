from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema

from ...authentication.permissions import UserHasAPIKey
from ...authentication.services.throttling import APIKeyRateThrottle
from ..serializers import BatchWalletBalanceSerializer
from ..services import WalletExplorerService
from ...utils.prometheus import histogram_observer


class BatchWalletBalanceView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        responses={201: BatchWalletBalanceSerializer(many=False)},
        request_body=BatchWalletBalanceSerializer(many=False),
        operation_id='batch_wallet_balance',
        operation_description = "Retrieve the balances of multiple addresses at once using network, currency and addresses."
    )
    @histogram_observer
    def post(self, request, network):
        data = request.data
        network = network.upper()
        serializer = BatchWalletBalanceSerializer(data=data, context={'network': network})
        serializer.is_valid(raise_exception=True)
        wallet_balances_dto = WalletExplorerService.get_wallet_balance_dtos(addresses=data.get('addresses'),
                                                                            network=network,
                                                                            currency=data.get('currency'))
        data['wallet_balances'] = wallet_balances_dto
        wallet_balances_serializer = BatchWalletBalanceSerializer(instance=data)
        wallet_balances_data = wallet_balances_serializer.data
        return Response(data=wallet_balances_data)

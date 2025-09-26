from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema

from ...authentication.permissions import UserHasAPIKey
from ...authentication.services.throttling import APIKeyRateThrottle
from ..serializers import WalletBalanceSerializer
from ..services import WalletExplorerService
from ...utils.prometheus import histogram_observer


class WalletBalanceView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        operation_id='wallet_balance',
        operation_description = "Retrieve the balance of an address using network, currency and the address itself."
    )
    @histogram_observer
    def get(self, request, network, address):
        currency = request.query_params.get('currency')
        network = network.upper()
        serializer = WalletBalanceSerializer(data={'address': address},
                                             context={'network': network, 'currency': currency})
        serializer.is_valid(raise_exception=True)
        wallet_balances_dto = WalletExplorerService.get_wallet_balance_dtos(addresses=[address, ],
                                                                            network=network,
                                                                            currency=currency)
        wallet_balances_serializer = WalletBalanceSerializer(instance=wallet_balances_dto, many=True)
        wallet_balances_data = wallet_balances_serializer.data
        return Response(data=wallet_balances_data)

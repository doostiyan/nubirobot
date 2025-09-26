from drf_yasg import openapi
from rest_framework.response import Response
from rest_framework.views import APIView
from exchange.blockchain.contracts_conf import sol_contract_info
from exchange.blockchain.models import get_token_code
from ...authentication.permissions import UserHasAPIKey
from ...authentication.services.throttling import APIKeyRateThrottle


currency_param = openapi.Parameter('currency', openapi.IN_QUERY, type=openapi.TYPE_STRING)


class WalletATAView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    def get(self, request, network, address):
        from solders.pubkey import Pubkey
        from spl.token.instructions import get_associated_token_address

        currency = request.query_params.get('currency').lower()

        token_code = get_token_code(currency, 'spl_token')
        mint = sol_contract_info.get('mainnet').get(token_code).get('address')

        wallet = Pubkey.from_string(address)
        mint = Pubkey.from_string(mint)

        ata = str(get_associated_token_address(wallet, mint))

        return Response(data=ata, status=200)

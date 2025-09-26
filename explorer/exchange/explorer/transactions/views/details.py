from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from exchange.blockchain.api.general.utilities import Utilities
from exchange.explorer.authentication.permissions import UserHasAPIKey
from exchange.explorer.authentication.services.throttling import APIKeyRateThrottle
from exchange.explorer.transactions.serializers import TransactionSerializer
from exchange.explorer.transactions.serializers.details import TransactionQueryParamsSerializer
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.transactions.utils.exceptions import TransactionNotFoundException
from exchange.explorer.utils.blockchain import parse_currency2code_and_symbol
from exchange.explorer.utils.prometheus import histogram_observer
from exchange.explorer.wallets.services import WalletExplorerService
from exchange.explorer.wallets.utils.exceptions import AddressNotFoundException

contract_address_param = openapi.Parameter('contract_address', openapi.IN_QUERY, type=openapi.TYPE_STRING)
currency_param = openapi.Parameter('currency', openapi.IN_QUERY, type=openapi.TYPE_STRING)
network_param = openapi.Parameter('network', openapi.IN_QUERY, type=openapi.TYPE_STRING)
base_url_param = openapi.Parameter('base_url', openapi.IN_QUERY, type=openapi.TYPE_STRING)
address_param = openapi.Parameter('address', openapi.IN_QUERY, type=openapi.TYPE_STRING)


class TransactionDetailsView(APIView):
    renderer_classes = (JSONRenderer,)
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        operation_id='transaction_details',
        operation_description='Retrieve the details of a transaction by network and transaction hash.',
        manual_parameters=[currency_param, network_param, base_url_param],
        responses={200: TransactionSerializer(many=False)},
    )
    @histogram_observer
    def get(self, request: APIView, network: str, tx_hash: str) -> Response:
        serializer_data = request.query_params.copy()
        serializer_data['network'] = network
        serializer = TransactionQueryParamsSerializer(data=serializer_data)
        serializer.is_valid(raise_exception=True)

        validated_data = request.query_params
        currency = validated_data.get('currency')
        provider_name = validated_data.get('provider_name')
        base_url = validated_data.get('base_url')
        currency = None if currency in ["''", 'None'] else currency
        network = network.upper()

        result = TransactionExplorerService().get_transaction_details_based_on_provider_name_and_url(
            provider_name=provider_name,
            base_url=base_url,
            network=network,
            tx_hashes=[tx_hash],
            currency=currency,
        )
        data_response = [
            TransactionSerializer(instance=tx).data for tx in result
        ]
        return Response(data=data_response)


class ConfirmedTransactionDetailsView(APIView):
    renderer_classes = (JSONRenderer,)
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        operation_id='confirmed_transaction_details',
        operation_description='Retrieve the details of a confirmed transaction by network and transaction hash.',
        manual_parameters=[contract_address_param, currency_param, address_param],
        responses={200: TransactionSerializer(many=False)},
    )
    @histogram_observer
    def get(self, request: APIView, network: str, tx_hash: str) -> Response:
        network = network.upper()
        contract_address = request.query_params.get('contract_address')
        currency = request.query_params.get('currency')
        currency = None if currency in ["''", 'None'] else currency
        address = request.query_params.get('address')
        address = None if address in ["''", 'None'] else address

        if not currency:
            currency = network.lower()
        parsed_currency, _ = parse_currency2code_and_symbol(currency)
        tx_hash = Utilities.normalize_hash(network, parsed_currency, [tx_hash])[0]

        wallet_transactions_in_db = WalletExplorerService.get_wallet_transactions_dto_from_db(
            network=network,
            symbol=currency,
            address=address,
            contract_address=contract_address)
        wallet_transactions_dto = list(filter(lambda tx_dto: tx_dto.tx_hash == tx_hash, wallet_transactions_in_db))

        if len(wallet_transactions_dto) == 0 and address:
            if WalletExplorerService.is_nobitex_deposit_wallet(network, address):
                wallet_transactions_dto = WalletExplorerService.get_wallet_transactions_dto_around_tx(
                    network=network,
                    currency=currency,
                    tx_hash=tx_hash,
                    address=address,
                    contract_address=contract_address
                )
                wallet_transactions_dto = list(
                    filter(lambda tx_dto: tx_dto.tx_hash == tx_hash, wallet_transactions_dto))
            else:
                raise AddressNotFoundException
        if not wallet_transactions_dto:
            raise TransactionNotFoundException
        wallet_transaction_serializer = TransactionSerializer(instance=wallet_transactions_dto, many=True)
        wallet_transactions_data = wallet_transaction_serializer.data
        return Response(data=wallet_transactions_data)

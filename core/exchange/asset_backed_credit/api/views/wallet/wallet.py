from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.response import Response

from exchange.asset_backed_credit.api.views import InternalABCView
from exchange.asset_backed_credit.models import Wallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.api_v2_1 import InternalAPIView, internal_get_api
from exchange.base.decorators import measure_api_execution
from exchange.base.internal.permissions import AllowedServices
from exchange.base.internal.services import Services


class WalletListAPIView(InternalABCView):
    WALLET_TYPE: Wallet.WalletType

    def get(self, request):
        wallets = WalletService.get_user_wallets_with_rial_balance(user=request.user, wallet_type=self.WALLET_TYPE)
        return self.response(
            {
                'status': 'ok',
                'wallets': [wallet.model_dump(by_alias=True) for wallet in wallets],
            }
        )


class DebitWalletListAPIView(WalletListAPIView):
    WALLET_TYPE = Wallet.WalletType.DEBIT


class CollateralWalletListAPIView(WalletListAPIView):
    WALLET_TYPE = Wallet.WalletType.COLLATERAL


class DebitWalletsBalanceListInternalAPI(InternalAPIView):
    """
    url: 'internal/asset-backed-credit/wallets/debit/balances'
    """

    permission_classes = [AllowedServices((Services.CORE,))]

    @method_decorator(measure_api_execution(api_label='abcDebitWalletsBalanceListInternal'))
    @method_decorator(ratelimit(key='ip', rate='10/m', method='GET', block=True))
    def get(self, request):
        user_id = request.GET.get('user_id')
        if not user_id:
            return Response({'status': 'failed', 'message': 'missing user_id.'}, status=status.HTTP_400_BAD_REQUEST)

        wallets = WalletService.get_user_wallets_with_balances(user_id=user_id, wallet_type=Wallet.WalletType.DEBIT)
        return self.response({'status': 'ok', 'wallets': {wallet.currency: wallet.balance for wallet in wallets}})

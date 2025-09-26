from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from pydantic import ValidationError
from rest_framework import status

from exchange.asset_backed_credit.api.views import InternalABCView
from exchange.asset_backed_credit.exceptions import DepositAPIError, WalletValidationError
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.asset_backed_credit.types import WalletDepositInput
from exchange.base.decorators import measure_api_execution
from exchange.base.serializers import serialize


class WalletDepositView(InternalABCView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST'))
    @method_decorator(measure_api_execution(api_label='abcWalletDepositView'))
    def post(self, request):
        """
        API for transferring balance between user wallets
        POST /asset-backed-credit/wallets/deposit
        """
        data = request.data

        try:
            deposit_input = WalletDepositInput.model_validate(data)
            bulk_transfer_result = WalletService.deposit(request.user, deposit_input)
            return self.response(
                {
                    'status': 'ok',
                    'result': serialize(bulk_transfer_result, opts={'no_deposit_addresses': True}),
                }
            )
        except ValidationError as e:
            description = f"{e.errors()[0]['loc'][0]} {e.errors()[0]['msg']}".lower()
            raise DepositAPIError(
                code='ParseError', description=description, status_code=status.HTTP_400_BAD_REQUEST
            ) from e
        except WalletValidationError as e:
            raise DepositAPIError(code=e.code, description=e.description) from e

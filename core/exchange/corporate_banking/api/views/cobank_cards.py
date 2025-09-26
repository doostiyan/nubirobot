from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from exchange.base.api import APIView
from exchange.corporate_banking.services.cobank_deposit_info import get_cobank_card_deposit_info
from exchange.features.utils import BetaFeatureMixin


class CoBankCardDepositInfoAPI(BetaFeatureMixin, APIView):
    feature = 'cobank_cards'

    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', block=True))
    def get(self, request):
        return self.response(get_cobank_card_deposit_info())

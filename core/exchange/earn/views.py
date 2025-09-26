from collections import defaultdict

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from exchange.base.api import APIView
from exchange.base.models import Currencies
from exchange.base.serializers import serialize_dict_key_choices
from exchange.earn.external import get_user_abc_debit_wallets_balances
from exchange.staking.exportables import get_balances_blocked_in_staking, get_balances_blocked_in_yield_aggregator
from exchange.wallet.estimator import PriceEstimator


class EarnBalances(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET'))
    def get(self, request):
        """API for transferring balance between user wallets

            GET /earn/balances
        """
        balances = defaultdict(dict)
        staking_balances = get_balances_blocked_in_staking(request.user.id)
        for currency, balance in staking_balances.items():
            balances[currency]['staking'] = {'balance': balance}

        yield_farming_balances = get_balances_blocked_in_yield_aggregator(request.user.id)
        for currency, balance in yield_farming_balances.items():
            balances[currency]['yieldFarming'] = {'balance': balance}

        pool_delegations = request.user.user_delegations.filter(closed_at=None)
        for currency, balance in pool_delegations.values_list('pool__currency', 'balance'):
            balances[currency]['liquidityPool'] = {'balance': balance}

        debit_balances = get_user_abc_debit_wallets_balances(request.user.uid)
        for currency, balance in debit_balances.items():
            balances[currency]['debit'] = {'balance': balance}

        for currency, balance_data in sorted(balances.items()):
            buy_price, sell_price = PriceEstimator.get_price_range(currency)
            for item in balance_data.values():
                item['rialBalance'] = int(buy_price * item['balance'])
                item['rialBalanceSell'] = int(sell_price * item['balance'])
        return self.response({
            'status': 'ok',
            'balances': serialize_dict_key_choices(Currencies, balances),
        })

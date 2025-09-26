from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.api.sol.sol_solanabeach import SolanaBeachAPI
from exchange.blockchain.api.sol.sol_solscan import SolScanAPI
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_models import StakingInfo


class SolStaking(BaseStaking):

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        stake_balances = Decimal('0')
        delegated_balances = Decimal('0')
        api = SolanaBeachAPI.get_api()
        free_balance = api.get_balance(address).get(Currencies.sol).get('amount')
        stake_addresses = SolScanAPI.get_api().get_stake_account_info(address)
        for stake_address in stake_addresses:
            stake_balances += api.get_balance(stake_address).get(Currencies.sol).get('amount')
            delegated_balance = api.get_delegated_balance(stake_address)
            if delegated_balance:
                delegated_balances += delegated_balance
        return StakingInfo(
            address=address,
            staked_balance=stake_balances,
            free_balance=free_balance,
            total_balance=free_balance + stake_balances,
            rewards_balance=stake_balances - delegated_balances
        )

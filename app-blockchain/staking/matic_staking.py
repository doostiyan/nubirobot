from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.blockchain.api.eth.eth_web3 import ETHWeb3
from exchange.blockchain.api.polygon.ankr_validators_share_contract import AnkrValidatorShareContract
from exchange.blockchain.contracts_conf import ERC20_contract_info
from exchange.blockchain.staking.base_staking import BaseStaking
from exchange.blockchain.staking.staking_models import StakingInfo


class MaticStaking(BaseStaking):

    @classmethod
    def get_staked_balance(cls, address):
        return AnkrValidatorShareContract.get_instance().get_staked_balance(address)

    @classmethod
    def get_rewards_balance(cls, address):
        return AnkrValidatorShareContract.get_instance().get_rewards_balance(address)

    @classmethod
    def get_free_balance(cls, address):
        return ETHWeb3.get_api().get_token_balance(address, ERC20_contract_info['mainnet'][Currencies.pol]).get(
            'amount')

    @classmethod
    def get_staking_info(cls, address, start_reward_period=None, end_reward_period=None):
        staked_balance = cls.get_staked_balance(address)
        free_balance = cls.get_free_balance(address)
        return StakingInfo(
            address=address,
            total_balance=staked_balance + free_balance,
            staked_balance=staked_balance,
            rewards_balance=cls.get_rewards_balance(address),
            free_balance=free_balance
        )

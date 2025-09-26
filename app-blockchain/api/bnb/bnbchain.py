import datetime
import math
from decimal import Decimal
from dateutil import parser

from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError, ParseError


class Bnbchain(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    BNB Chain Explorer API
    API docs: https://docs.bnbchain.org/docs/beaconchain/develop/api-reference/dex-api/staking/
    Explorer: https://explorer.bnbchain.org
    """
    symbol = 'BNB'
    REQUEST_MAX_LIMIT = 100  # maximum number of items API returned
    _base_url = 'https://explorer.bnbchain.org/v1/staking'
    supported_requests = {
        'get_staking_reward': '/chains/bsc/delegators/{address}/rewards?limit={limit}&offset={offset}',
        'get_staked_balance': '/accounts/{address}/balance',
    }

    def get_delegated_balance(self, address):
        self.validate_address(address)
        try:
            response = self.request('get_staked_balance', address=address)
        except ConnectionError:
            raise APIError(f"Failed to  get staked balance from {self.symbol} API: connection error")
        if response is None:
            raise APIError(f"Get staked balance response of {self.symbol} is None")
        try:
            balance_amount = self.parse_delegated_balance(response)
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing balance response error response is {response}.')
        return balance_amount

    def parse_delegated_balance(self, response):
        balance = response.get('delegated')
        asset = response.get('asset')
        if asset != self.symbol:
            raise APIError(f"{self.symbol} API: balance denom not matched with main denom")
        return Decimal(str(balance))

    def get_staking_reward(self, address, start_period, end_period):
        """
        get daily rewards earned by account
        ! maximum number of days return: 100 days
        ! pagination enabled
        ! for 100 day request response take up to 10 second
        ! note that both `start_period` and `end_period` are inclusive bound
        :type start_period: datetime.date()
        :type end_period: datetime.date()
        :type address: str
        """
        self.validate_address(address)
        reward_duration, start_period, end_period = self.calculate_duration(start_period, end_period)
        request_num = math.ceil(reward_duration/self.REQUEST_MAX_LIMIT)
        rewards = []
        for i in range(request_num):
            try:
                response = self.request('get_staking_reward', address=address, offset=i, limit=self.REQUEST_MAX_LIMIT)
            except ConnectionError:
                raise APIError(f"Failed to  get rewards balance from {self.symbol} API: connection error")
            if response is None:
                raise APIError(f"Get rewards balance response of {self.symbol} is None")
            try:
                rewards = rewards + self.parse_staking_reward(response)
            except AttributeError:
                raise ParseError(f'{self.symbol} parsing rewards balance response error response is {response}.')
        return self.calculate_rewards_amount(rewards, start_period, end_period)

    def parse_staking_reward(self, response):
        return response.get('rewardDetails')

    @classmethod
    def calculate_duration(cls, start_period, end_period):
        if isinstance(start_period, datetime.datetime):
            start_period = start_period.date()
        if isinstance(end_period, datetime.datetime):
            end_period = end_period.date()
        if end_period is None:
            end_period = datetime.date.today()
        if start_period is None:
            start_period = end_period - datetime.timedelta(days=cls.REQUEST_MAX_LIMIT - 1)
        return (end_period - start_period).days + 1, start_period, end_period

    def calculate_rewards_amount(self, rewards, start_period, end_period):
        total_reward_amount = Decimal(0)
        for reward in rewards:
            reward_time = parser.parse(reward.get('rewardTime')).date()
            reward_amount = Decimal(str(reward.get("reward")))
            if start_period <= reward_time <= end_period:
                total_reward_amount += reward_amount
        return total_reward_amount

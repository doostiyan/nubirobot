from django.conf import settings

from exchange.blockchain.utils import BlockchainUtilsMixin


class AnkrValidatorShareContract:
    __instance = None

    web3_url = 'https://rpc.ankr.com/eth'
    contract_address = '0x0e9e4b023f7921c6edaf824d6af934b1dbe502f0'
    PRECISION = 18

    @staticmethod
    def get_instance():
        """ Static access method. """
        if AnkrValidatorShareContract.__instance is None:
            AnkrValidatorShareContract()
        return AnkrValidatorShareContract.__instance

    def __init__(self):
        if AnkrValidatorShareContract.__instance is not None:
            raise Exception("This class is a singleton!")
        from web3 import Web3
        self.w3 = Web3(Web3.HTTPProvider(self.web3_url))
        contract_abi_path = settings.BASE_DIR + '/exchange/blockchain/contract_abis/validator_share_proxy.abi'
        try:
            with open(contract_abi_path) as contract_file:
                contract_abi = contract_file.read()
        except Exception:
            raise FileNotFoundError('validator_share_proxy.abi is missing!')
        self.contract = self.w3.eth.contract(self.w3.to_checksum_address(self.contract_address), abi=contract_abi)
        AnkrValidatorShareContract.__instance = self

    def get_rewards_balance(self, address):
        rewards_balance = self.contract.functions.getLiquidRewards(address).call()
        return BlockchainUtilsMixin.from_unit(rewards_balance, self.PRECISION)

    def get_staked_balance(self, address):
        staked_balance = self.contract.functions.balanceOf(address).call()
        return BlockchainUtilsMixin.from_unit(staked_balance, self.PRECISION)

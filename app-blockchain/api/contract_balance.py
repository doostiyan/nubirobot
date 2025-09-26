import random

from django.conf import settings

from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.api.general_api import NobitexBlockchainAPI

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import (
        CURRENCIES as Currencies, ERC20_contract_currency, ERC20_contract_info,
        polygon_ERC20_contract_currency,
        polygon_ERC20_contract_info, BEP20_contract_currency, BEP20_contract_info, opera_ftm_contract_info,
        opera_ftm_contract_currency, avalanche_ERC20_contract_currency, avalanche_ERC20_contract_info,
        harmony_ERC20_contract_currency, harmony_ERC20_contract_info
    )
else:
    from exchange.blockchain.models import (Currencies)
    from exchange.blockchain.contracts_conf import (
        ERC20_contract_info, ERC20_contract_currency,
        BEP20_contract_currency,
        BEP20_contract_info, opera_ftm_contract_currency, opera_ftm_contract_info, polygon_ERC20_contract_info,
        polygon_ERC20_contract_currency, avalanche_ERC20_contract_info, avalanche_ERC20_contract_currency,
        harmony_ERC20_contract_info, harmony_ERC20_contract_currency
    )


class ContractBalanceChecker(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Ethereum
    API docs: https://github.com/wbobeirne/eth-balance-checker
    """
    web3_url = ''
    testnet_url = ''
    contract_address = ''
    symbol = ''
    currency = 0

    def __init__(self, network='mainnet'):
        super().__init__()
        from web3 import Web3
        self.w3 = Web3(Web3.HTTPProvider(self.web3_url))
        if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
            self.network = 'mainnet' if settings.IS_PROD else 'testnet'
        else:
            self.network = network
            self.update_network()

    def get_name(self):
        return 'balance_checker_api'

    def get_balances(self, addresses):

        checksum_addresses = [self.w3.toChecksumAddress(address) for address in addresses]
        tokens = [self.w3.toChecksumAddress(address) for address in list(self.contract_currency_list.keys())]
        tokens.insert(0, self.w3.toChecksumAddress('0x0000000000000000000000000000000000000000'))

        contract = self.w3.eth.contract(self.w3.toChecksumAddress(self.contract_address), abi=self.get_contract_abi())
        balances = contract.functions.balances(checksum_addresses, tokens).call()

        return self.parse_balances(balances, addresses, tokens)

    def get_balances_for_selected_assets(self, addresses, assets):
        checksum_addresses = [self.w3.toChecksumAddress(address) for address in addresses]
        contract = self.w3.eth.contract(self.w3.toChecksumAddress(self.contract_address), abi=self.get_contract_abi())
        balances = contract.functions.balances(checksum_addresses, assets).call()
        return self.parse_balances(balances, addresses, assets)

    def parse_balances(self, balances, addresses, tokens):
        parsed_balances = {}
        index = 0
        for address in addresses:
            parsed_balances[address] = []
            for token in tokens:
                if token == '0x0000000000000000000000000000000000000000':
                    parsed_balances[address].append(
                        {
                            'currency': self.currency,
                            'symbol': self.symbol,
                            'balance': self.from_unit(balances[index], self.PRECISION)
                        }
                    )
                    index += 1
                    continue
                currency = self.contract_currency(token.lower())
                if not currency:
                    index += 1
                    continue
                contract_info = self.contract_info(currency)
                if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
                    balance = int(balances[index])
                else:
                    balance = self.from_unit(balances[index], contract_info.get('decimals'))
                parsed_balances[address].append({
                    'currency': int(currency),
                    'symbol': contract_info.get('symbol'),
                    'balance': balance
                })
                index += 1
        return parsed_balances

    @classmethod
    def get_contract_abi(cls):
        return """
               [{"payable":true,"stateMutability":"payable","type":"fallback"},
               {"constant":true,"inputs":[{"name":"user","type":"address"},{"name":"token","type":"address"}],
               "name":"tokenBalance","outputs":[{"name":"","type":"uint256"}],"payable":false,"stateMutability":
               "view","type":"function"},{"constant":true,"inputs":[{"name":"users","type":"address[]"},{"name":
               "tokens","type":"address[]"}],"name":"balances","outputs":[{"name":"","type":"uint256[]"}],
               "payable":false,"stateMutability":"view","type":"function"}]
               """

    @property
    def contract_currency_list(self):
        return {}

    @property
    def contract_info_list(self):
        return {}

    def contract_currency(self, token_address):
        return self.contract_currency_list.get(token_address)

    def contract_info(self, currency):
        return self.contract_info_list.get(currency)


class ETHContractBalanceChecker(ContractBalanceChecker):
    web3_url = f'https://{"mainnet" if settings.IS_PROD else "ropsten"}.infura.io/v3/' \
               + random.choice(settings.INFURA_PROJECT_ID)
    contract_address = '0xb1f8e55c7f64d203c1400b9d8555d050f94adf39' if settings.IS_PROD\
        else '0x344749865435e040c7c03dc8f297f9a4d1d7575c'
    symbol = 'ETH'
    currency = Currencies.eth
    PRECISION = 18
    cache_key = 'eth'

    @property
    def contract_currency_list(self):
        return ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return ERC20_contract_info.get(self.network)


class PolygonContractBalanceChecker(ContractBalanceChecker):
    web3_url = 'https://polygon-rpc.com' if settings.IS_PROD else 'https://matic-mumbai.chainstacklabs.com'
    contract_address = '0x2352c63A83f9Fd126af8676146721Fa00924d7e4' if settings.IS_PROD else '0x90c698edd1708ae966715feb3216df0d8aef737d'
    symbol = 'POL'
    currency = Currencies.pol
    PRECISION = 18
    cache_key = 'pol'

    @property
    def contract_currency_list(self):
        return polygon_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return polygon_ERC20_contract_info.get(self.network)


class BSCContractBalanceChecker(ContractBalanceChecker):
    web3_url = 'https://bsc-dataseed2.binance.org/' if settings.IS_PROD else 'https://data-seed-prebsc-2-s2.binance.org:8545'
    contract_address = '0x2352c63A83f9Fd126af8676146721Fa00924d7e4'

    symbol = 'BSC'
    if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
        currency = Currencies.bsc
    else:
        currency = Currencies.bnb
    PRECISION = 18

    def __init__(self, network='mainnet', api_key=None):
        from web3.middleware import ExtraDataToPOAMiddleware

        super().__init__()
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
            self.network = 'mainnet' if settings.IS_PROD else 'testnet'
        else:
            self.network = network
            self.update_network()

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)


class ETCContractBalanceChecker(ContractBalanceChecker):
    web3_url = 'https://www.ethercluster.com/etc' if settings.IS_PROD else 'https://rpc.slock.it/goerli'
    contract_address = '0xfC701A6b65e1BcF59fb3BDbbe5cb41f35FC7E009'
    symbol = 'ETC'
    currency = Currencies.etc
    PRECISION = 18

    @property
    def contract_currency_list(self):
        return {}

    @property
    def contract_info_list(self):
        return {}


class FtmContractBalanceChecker(ContractBalanceChecker):
    web3_url = 'https://rpc.ftm.tools' if settings.IS_PROD else 'https://rpc.testnet.fantom.network/'
    contract_address = '0xfc701a6b65e1bcf59fb3bdbbe5cb41f35fc7e009'
    symbol = 'FTM'
    currency = Currencies.ftm
    PRECISION = 18

    @property
    def contract_currency_list(self):
        return opera_ftm_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return opera_ftm_contract_info.get(self.network)


class AvalancheContractBalanceChecker(ContractBalanceChecker):
    web3_url = 'https://api.avax.network/ext/bc/C/rpc' if settings.IS_PROD else 'https://api.avax-test.network/ext/bc/C/rpc'
    contract_address = '0xe0baf851f839874141bb73327f9c606147a52358' if settings.IS_PROD else '0xA9a966B2EfB96Bc3c76456F6bb0c4A9F03D38EA8'
    symbol = 'AVAX'
    currency = Currencies.avax
    PRECISION = 18

    @property
    def contract_currency_list(self):
        return avalanche_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return avalanche_ERC20_contract_info.get(self.network)


class HarmonyContractBalanceChecker(ContractBalanceChecker):
    web3_url = 'https://rpc.s0.t.hmny.io' if settings.IS_PROD else 'https://rpc.s0.b.hmny.io'
    contract_address = '0xE0baF851F839874141bB73327f9C606147a52358' if settings.IS_PROD else ''
    symbol = 'ONE'
    currency = Currencies.one
    PRECISION = 18

    @property
    def contract_currency_list(self):
        return harmony_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return harmony_ERC20_contract_info.get(self.network)

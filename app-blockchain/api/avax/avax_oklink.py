from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == "cold_":
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.oklink import OklinkApi, OklinkResponseParser
from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_info


class OklinkAvalancheResponseParser(OklinkResponseParser):
    symbol = "AVAX"
    currency = Currencies.avax
    precision = 18

    @classmethod
    def contract_info_list(cls):
        return avalanche_ERC20_contract_info.get(cls.network_mode)


class AvalancheOkLinkApi(OklinkApi):
    parser = OklinkAvalancheResponseParser
    cache_key = "avax"
    instance = None
    SUPPORT_GET_BALANCE_BATCH = True
    SUPPORT_GET_TOKEN_BALANCE_BATCH = True

    supported_requests = {
        "get_address_txs": "/address/transaction-list?address={address}&chainShortName=avaxc",
        "get_token_txs": "/address/transaction-list?address={address}&protocolType=token_20&chainShortName=avaxc",
        "get_block_head": "/block/block-list?limit=1&chainShortName=avaxc",
        "get_block_txs": "/block/transaction-list?height={height}&chainShortName=avaxc",
        "get_tx_details": "/transaction/transaction-fills?txid={tx_hash}&chainShortName=avaxc",
        "get_balance": "/address/address-summary?address={address}&chainShortName=avaxc",
        "get_balances": "/address/balance-multi?address={addresses}&chainShortName=avaxc",
        "get_token_balance": "/address/token-balance?protocolType=token_20&tokenContractAddress={contract_address}&address={address}&chainShortName=avaxc",  # noqa
        "get_token_balances": "/address/token-balance-multi?protocolType=token_20&address={addresses}&chainShortName=avaxc",  # noqa
    }

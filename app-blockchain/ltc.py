import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from exchange.base.connections import get_electrum_ltc
from exchange.base.models import Currencies
from exchange.blockchain.api.ltc.ltc_blockbook import LitecoinBlockbookAPI
from exchange.blockchain.apis_conf import APIS_CLASSES, APIS_CONF
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.blockcypher import blockcypher_inspect
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class LitecoinBlockchainInspector(Bep20BlockchainInspector):
    """ Based on: https://chain.so/api
        Rate limit: 5 requests/sec
    """
    currency = Currencies.ltc
    currency_list = [Currencies.ltc]
    # Method to use for getting wallet balances: electrum, blockbook, blockcypher
    USE_EXPLORER_BALANCE = 'blockcypher' if settings.DEBUG else 'electrum'
    USE_EXPLORER_TRANSACTION = 'blockbook'  # Available options: blockbook, blockcypher

    get_balance_method = {
        CurrenciesNetworkName.LTC: 'get_wallets_balance_ltc',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.LTC: 'get_wallet_transactions_ltc',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.LTC: 'get_transaction_details_ltc',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }

    @classmethod
    def get_transaction_details_ltc(cls, tx_hash, network=None, raise_error=False):
        tx_details = None
        try:
            tx_details = LitecoinBlockbookAPI.get_api().get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut, Exception) as e:
            if raise_error:
                raise e
        return tx_details

    @classmethod
    def get_wallets_balance_ltc(cls, address_list):
        if cls.USE_EXPLORER_BALANCE == 'electrum':
            return cls.get_wallets_balance_electrum(address_list)
        elif cls.USE_EXPLORER_BALANCE == 'blockbook':
            return cls.get_wallets_balance_blockbook(address_list)
        elif cls.USE_EXPLORER_BALANCE == 'blockcypher':
            return cls.get_wallets_balance_blockcypher(address_list)
        return cls.get_wallets_balance_blockbook(address_list)

    @classmethod
    def get_wallet_transactions_ltc(cls, address, network=None):
        if settings.BLOCKCYPHER_ENABLED and cls.USE_EXPLORER_TRANSACTION == 'blockcypher':
            return blockcypher_inspect(address, Currencies.ltc)
        return cls.get_wallet_transactions_blockbook(address)

    @classmethod
    def get_wallets_balance_blockbook(cls, address_list, raise_error=False):
        balances = []
        api = LitecoinBlockbookAPI.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.ltc, {}).get('amount', Decimal('0'))
                unconfirmed_balance = response.get(Currencies.ltc, {}).get('unconfirmed_amount', Decimal('0'))
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': unconfirmed_balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_electrum(cls, address_list, raise_error=False):
        try:
            electrum = get_electrum_ltc()
        except Exception as e:
            if raise_error:
                raise e
            return
        balances = []
        for addr in address_list:
            try:
                res = electrum.request('getaddressbalance', params={'address': addr})
            except Exception as e:
                if raise_error:
                    raise e
                continue
            error = res.get('error')
            result = res.get('result')
            if error or not result:
                continue
            balance = Decimal(result['confirmed'])
            balances.append({
                'address': addr,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal(result['unconfirmed']),
            })
        return balances

    @classmethod
    def parse_actions_ltc(cls, records, address):
        transactions = []
        for record in records:
            source = record.get('vin')[0].get('addresses')
            destination = record.get('vout')[0].get('addresses')[0]
            transactions.append(
                Transaction(
                    address=destination,
                    from_address=source,
                    hash=record.get('txid'),
                    block=record.get('blockHeight'),
                    timestamp=datetime.fromtimestamp(record.get('blockTime')),
                    value=Decimal(record.get('value')) / Decimal('1e8'),
                    confirmations=record.get('confirmations'),
                    is_double_spend=False,
                    details=record,
                )
            )
        return transactions

    @classmethod
    def get_wallets_balance_chainso(cls, address_list, raise_error=False):
        """
            Note: this function only returns net balances for each address and not sent/etc. details in order to make
                  fewer API call
        """
        time.sleep(0.5)
        balances = []
        for address in address_list:
            time.sleep(1)
            try:
                if settings.USE_TESTNET_BLOCKCHAINS:
                    explorer_url = 'https://chain.so/api/v2/get_address_balance/LTCTEST/{}/6'
                else:
                    explorer_url = 'https://chain.so/api/v2/get_address_balance/LTC/{}/6'
                api_response = cls.get_session().get(explorer_url.format(address), timeout=7)
                api_response.raise_for_status()
            except Exception as e:
                if raise_error:
                    raise e
                time.sleep(1)
                continue
            info = api_response.json()
            if info.get('status') != 'success':
                continue
            addr_info = info['data']
            balance = Decimal(addr_info['confirmed_balance'] or '0')
            # TODO: currently we only return balance and set other fields to zero
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_litecoinnet(cls, address_list, raise_error=False):
        """
            Note: this function only returns net balances for each address and not sent/etc. details in order to make
                  fewer API call
        """
        time.sleep(0.5)
        balances = []
        for address in address_list:
            time.sleep(1)
            try:
                explorer_url = 'http://explorer.litecoin.net/chain/Litecoin/q/addressbalance/{}'
                api_response = cls.get_session().get(explorer_url.format(address), timeout=5)
                api_response.raise_for_status()
                balance = Decimal(api_response.text)
            except Exception as e:
                if raise_error:
                    raise e
                time.sleep(1)
                continue
            # TODO: currently we only return balance and set other fields to zero
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallet_transactions_blockbook(cls, address, raise_error=False):
        api = LitecoinBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.ltc)
                value = tx_info.get('amount')
                if tx_info.get('direction') == 'outgoing':
                    # Transaction is from this address, so it is a withdraw
                    value = -value
                if tx_info.get('type') != 'normal':
                    continue
                transactions.append(Transaction(
                    address=address,
                    from_address=tx_info.get('from_address'),
                    hash=tx_info.get('hash'),
                    timestamp=tx_info.get('date'),
                    value=value,
                    confirmations=int(tx_info.get('confirmations') or 0),
                    is_double_spend=False,
                    block=tx_info.get('raw').get('blockHeight'),
                    details=tx_info,
                ))
            return transactions
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            if raise_error:
                raise error
            return []

    @classmethod
    def get_wallets_balance_blockcypher(cls, address_list, raise_error=False):
        time.sleep(0.5)
        balances = []
        use_proxy = True if not settings.IS_VIP else False
        for address in address_list:
            time.sleep(1)
            try:
                url = f'https://api.blockcypher.com/v1/ltc/main/addrs/{address}/balance'
                account_balances = cls.get_session(use_proxy=use_proxy).get(url, timeout=30).json()
            except Exception as e:
                if raise_error:
                    raise e
                time.sleep(1)
                continue

            balance = Decimal(account_balances.get('final_balance') / Decimal('100000000'))
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
        return balances

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=True):
        return cls.get_latest_block_addresses_blockbook(include_inputs=include_inputs, include_info=include_info)

    @classmethod
    def get_latest_block_addresses_blockbook(cls, include_inputs=False, include_info=True):
        """ Retrieve block from blockbook by trezor.io
        :return: Set of addresses output transactions with pay to public key hash
        in last block processed until the last block mined
        API Document: https://github.com/trezor/blockbook/blob/master/docs/api.md
        """

        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        api_name = APIS_CONF['LTC']['get_blocks_addresses']
        api_class = APIS_CLASSES[api_name].get_api()
        try:
            result = api_class.get_latest_block(
                include_inputs=include_inputs,
                include_info=include_info
            )
            transactions_addresses, transactions_info, last_processed_block = result
            return transactions_addresses, transactions_info, last_processed_block
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            traceback.print_exception(*sys.exc_info())
            return set(), None, 0

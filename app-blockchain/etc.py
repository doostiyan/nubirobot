import random
import time
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from exchange.base.connections import get_parity
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.etc.etc_blockbook import EthereumClassicBlockbookAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class ETCBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.etc
    currency_list = [Currencies.etc]

    get_balance_method = {
        CurrenciesNetworkName.ETC: 'get_wallets_balance_etc',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.ETC: 'get_wallet_transactions_etc',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.ETC: 'get_transaction_details_etc',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }

    @classmethod
    def get_transaction_details_etc(cls, tx_hash, network=None, raise_error=False):
        tx_details = None
        try:
            tx_details = EthereumClassicBlockbookAPI.get_api().get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut, Exception) as e:
            if raise_error:
                raise e
            report_exception()
        return tx_details

    @classmethod
    def get_wallets_balance_etc(cls, address_list):
        return cls.get_wallets_balance_blockbook(address_list=address_list)

    @classmethod
    def get_wallets_balance_blockbook(cls, address_list, raise_error=False):
        balances = []
        api = EthereumClassicBlockbookAPI.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.etc, {}).get('amount', 0)
            except Exception as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallets_balance_parity(cls, address_list, raise_error=False):
        """ Get ETC account balance
        """

        balances = []
        try:
            parity_client = get_parity()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get parity ETC client from get_parity_etc: {}'.format(str(e)))
            # report_event('parity ETC Connection Error')
            return
        for address in address_list:
            time.sleep(0.5)
            try:
                response = parity_client.request(
                    method="eth_getBalance",
                    params=[address, "latest"],
                )
            except Exception as e:
                if raise_error:
                    raise e
                print('Failed to get ETC balance from Parity: {}'.format(str(e)))
                continue
            if response.get('error'):
                print('Failed to get ETC balance from Parity: {}'.format(str(response.get('error'))))
                continue
            balance = response.get('result')
            if balance is None:
                continue
            balance = int(balance, 16) / Decimal(1e18)
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
        return balances

    @classmethod
    def get_wallets_balance_cryptoapis(cls, address_list, raise_error=False):
        """ Get ETC account balance

            Ratelimit: 500 request per day & 3 request per sec
        """
        time.sleep(3)
        balances = []
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            # explorer_url = 'https://api.cryptoapis.io/v1/bc/etc/mordor/address/{}'
            return None
        else:
            explorer_url = 'https://api.cryptoapis.io/v1/bc/etc/mainnet/address/{}'
        for address in address_list:
            try:
                cls.get_session().headers['X-API-Key'] = random.choice(settings.CRYPTOAPIS_API_KEYS)
                api_response = cls.get_session().get(explorer_url.format(address), timeout=30)
                api_response.raise_for_status()
                info = api_response.json().get('payload')
            except Exception as e:
                if raise_error:
                    raise e
                print('Failed to get ETC wallet balance from API: {}'.format(str(e)))
                return None
            if info.get('address') != address:
                continue
            if settings.IS_PROD and info.get('chain') != 'ETC.mainnet':
                continue
            balance = info.get('balance')
            if balance is None:
                continue
            balance = Decimal(balance)
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
        return balances

    @classmethod
    def get_wallets_balance_etccoopexplorer(cls, address_list, raise_error=False):
        """ Get ETC account balance

            Is out of sync (14h old)
        """
        time.sleep(1)
        balances = []
        use_proxy = True if not settings.IS_VIP else False
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return None
        else:
            explorer_url = 'https://classic.etccoopexplorer.com/api'
        explorer_url += '?module=account&action=balancemulti&address={}'
        try:
            api_response = cls.get_session(use_proxy=use_proxy).get(explorer_url.format(','.join(address_list)), timeout=30)
            api_response.raise_for_status()
            information = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get ETC wallet balance from API: {}'.format(str(e)))
            return None
        try:
            if information.get('status') != '1' or information.get('message') == 'ok':
                return None
            if not information.get('result'):
                return None
        except Exception as e:
            if raise_error:
                raise e
            return None
        address_index = 0
        if not address_list:
            return None
        for info in information.get('result'):
            if info.get('account').lower() != address_list[address_index].lower():
                continue
            balance = info.get('balance')
            if balance is None:
                continue
            balance = Decimal(balance) / Decimal(1e18)
            balances.append({
                'address': address_list[address_index],
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
            address_index += 1
        return balances

    @classmethod
    def get_wallet_transactions_etc(cls, address, network=None):
        return cls.get_wallet_transactions_blockbook(address=address)

    @classmethod
    def get_wallet_transactions_blockbook(cls, address, raise_error=False):
        api = EthereumClassicBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.etc)
                value = tx_info.get('amount')

                # Process transaction types
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
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            report_exception()
            return []

    @classmethod
    def get_wallet_transactions_cryptoapi(cls, address, raise_error=False):
        """ The free plan is discontinued, not used anymore """
        time.sleep(3)
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://api.cryptoapis.io/v1/bc/etc/mainnet/address/{}/transactions'.format(address)
        else:
            explorer_url = 'https://api.cryptoapis.io/v1/bc/etc/mainnet/address/{}/transactions'.format(address)
        try:
            if not address.startswith('0x'):
                address = '0x' + address
            cls.get_session().headers['X-API-Key'] = random.choice(settings.CRYPTOAPIS_API_KEYS)
            api_response = cls.get_session().get(explorer_url, timeout=60, params={"index": 0, "limit": 15})
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            print('Failed to get ETC wallet transactions from API: {}'.format(str(e)))
            return None
        records = info.get('payload')
        if not records:
            return []

        transactions = []
        for record in records:
            raw_value = Decimal(record.get('value')) / Decimal(1e18)
            if record.get('from').lower() == address.lower():
                value = -raw_value
            elif record.get('to').lower() == address.lower():
                value = raw_value
            else:
                value = Decimal('0')
            transactions.append(Transaction(
                address=address,
                from_address=[record.get('from')],
                hash=record.get('hash'),
                timestamp=parse_utc_timestamp(record.get('timestamp')),
                value=value,
                confirmations=record.get('confirmations'),
                is_double_spend=False,
                block=record.get('block'),
                details=record,
            ))
        return transactions

    @classmethod
    def parse_actions_etcblockbook(cls, records):
        transactions = []
        for record in records:
            from_address = record.get('vin')[0].get('addresses')[0]
            destination = record.get('vout')[0].get('addresses')[0]
            timestamp = datetime.fromtimestamp(record.get('blockTime'))
            confirmations = record.get('confirmations')
            height = record.get('blockHeight')
            value = Decimal(record.get('value')) / Decimal('1e18')
            transactions.append(
                Transaction(
                    address=destination,
                    from_address=from_address,
                    hash=record.get('txid'),
                    block=height,
                    timestamp=timestamp,
                    value=value,
                    confirmations=confirmations,
                    is_double_spend=False,
                )
            )
        return transactions

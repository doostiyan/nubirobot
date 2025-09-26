import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from exchange.base.connections import LndClient, get_electrum
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.btc.btc_blockbook import BitcoinBlockbookAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.blockcypher import blockcypher_inspect
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import Transaction
from exchange.blockchain.opera_ftm import OperaFTMBlockchainInspector
from exchange.blockchain.polygon_erc20 import PolygonERC20BlockchainInspector
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class BitcoinBlockchainInspector(Bep20BlockchainInspector, OperaFTMBlockchainInspector, PolygonERC20BlockchainInspector):
    USE_PROXY = True if not settings.IS_VIP else False
    TESTNET_ENABLED = False
    network = 'testnet' if TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS else 'mainnet'
    currency = Currencies.btc
    currency_list = [Currencies.btc]

    # Method to use for getting wallet balances: electrum, blockbook, cryptoid, btc_com, chainso, smartbit
    USE_EXPLORER_BALANCE = 'blockbook' if settings.DEBUG else 'electrum'
    USE_EXPLORER_BALANCE = 'chainso' if network == 'testnet' else USE_EXPLORER_BALANCE
    USE_EXPLORER_TRANSACTION = 'blockcypher' if network == 'testnet' else 'blockbook'  # Available options: blockbook, blockcypher, btc_com, smartbit
    USE_EXPLORER_TRANSACTION_DETAILS = 'blockbook'

    get_balance_method = {
        'BTC': 'get_wallets_balance_btc',
        'BSC': 'get_wallets_balance_bsc',
        'FTM': 'get_wallets_balance_ftm',
        'MATIC': 'get_wallets_balance_polygon',
    }

    get_transactions_method = {
        'BTC': 'get_wallet_transactions_btc',
        'BSC': 'get_wallet_transactions_bsc',
        'FTM': 'get_wallet_transactions_ftm',
        'MATIC': 'get_wallet_transactions_polygon',
    }

    get_transaction_details_method = {
        'BTC': 'get_transaction_details_btc',
        'BSC': 'get_transaction_details_bsc',
    }

    @classmethod
    def get_transaction_details_btc(cls, tx_hash):
        tx_details = None
        try:
            tx_details = BitcoinBlockbookAPI.get_api(network=cls.network).get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut,
                Exception) as error:
            pass
        return tx_details

    @classmethod
    def get_wallets_balance_btc(cls, address_list):
        if cls.USE_EXPLORER_BALANCE == 'electrum':
            return cls.get_wallets_balance_electrum(address_list)
        if cls.USE_EXPLORER_BALANCE == 'blockbook':
            return cls.get_wallets_balance_blockbook(address_list)
        if cls.USE_EXPLORER_BALANCE == 'cryptoid':
            return cls.get_wallets_balance_cryptoid(address_list)
        if cls.USE_EXPLORER_BALANCE == 'btc_com':
            return cls.get_wallets_balance_btc_com(address_list)
        if cls.USE_EXPLORER_BALANCE == 'chainso':
            return cls.get_wallets_balance_chainso(address_list)
        if cls.USE_EXPLORER_BALANCE == 'smartbit':
            return cls.get_wallets_balance_smartbit(address_list)

    @classmethod
    def get_wallets_balance_electrum(cls, address_list, raise_error=False):
        try:
            electrum = get_electrum()
        except Exception as e:
            if raise_error:
                raise e
            # report_event('Electrum Connection Error')
            return
        balances = []
        for addr in address_list:
            try:
                res = electrum.request('getaddressbalance', params={'address': addr})
            except Exception as e:
                metric_incr('api_errors_count', labels=['btc', 'electrum'])
                continue
            error = res.get('error')
            result = res.get('result')
            if error or not result:
                print('Failed to get BTC wallet balance from Electrum: {}'.format(str(res)))
                # report_event('Electrum Response Error')
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
    def get_wallets_balance_blockbook(cls, address_list, raise_error=False):
        if not address_list:
            return []
        balances = []
        api = BitcoinBlockbookAPI.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.btc, {}).get('amount', Decimal('0'))
                unconfirmed_balance = response.get(Currencies.btc, {}).get('unconfirmed_amount', Decimal('0'))
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                if raise_error:
                    raise error
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
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
    def get_wallets_balance_cryptoid(cls, address_list, raise_error=False):
        """
            Based on https://chainz.cryptoid.info/api.dws
            Note: this function only returns net balances for each address and not sent/etc.
                  multi address requests(bulk) -> OK -> 100 address per request
                  segwit -> OK
                  testnet -> NOK
        """
        time.sleep(1)
        balances = []
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://chainz.cryptoid.info/btc/api.dws?q=getbalances&key={}'
            else:
                explorer_url = 'https://chainz.cryptoid.info/btc/api.dws?q=getbalances&key={}'
            api_key = '98c934d7044d' if not settings.IS_VIP else '3d9a79a42637'
            api_response = cls.get_session().post(explorer_url.format(api_key), json=list(address_list), timeout=15)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['btc', 'cryptoid'])
            print('Failed to get BTC wallet balance from API: {}'.format(str(e)))
            # report_event('cryptoID API Error')
            return None
        for addr, balance in info.items():
            balance = Decimal(balance or '0')
            balances.append({
                'address': addr,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
        return balances

    @classmethod
    def get_wallets_balance_btc_com(cls, address_list, raise_error=False):
        if not address_list:
            return []

        time.sleep(0.1)
        balances = []

        # Separate Segwith addresses
        legacy_addresses = []
        segwit_addresses = []
        for address in address_list:
            if address.startswith('bc1'):
                segwit_addresses.append(address)
            else:
                legacy_addresses.append(address)

        # Use Smartbit for Segwit addresses
        if len(segwit_addresses) != 0:
            balances = cls.get_wallets_balance_smartbit(segwit_addresses)
        if balances is None:
            balances = []

        if len(legacy_addresses) == 0:
            return balances
        # Use btc.com for legacy addresses
        param = ','.join(legacy_addresses)
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://tchain.api.btc.com/v3/address/{}'
            else:
                explorer_url = 'https://chain.api.btc.com/v3/address/{}'
            api_response = cls.get_session().get(explorer_url.format(param), timeout=15, proxies=settings.DEFAULT_PROXY)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['btc', 'btc_com'])
            print('Failed to get BTC wallet balance from API: {}'.format(str(e)))
            # report_event('Btc.com API Error')
            return None
        response_info = info['data']
        if not isinstance(response_info, list):
            # if only one address is queried, a dict is returned instead of a list of dicts
            response_info = [response_info]
        for addr_info in response_info:
            if not addr_info:
                # API returns None for wallets with no transaction
                continue
            addr = addr_info['address']
            received = Decimal(addr_info['received']) / Decimal('1e8') - Decimal(
                addr_info['unconfirmed_received']) / Decimal('1e8')
            sent = Decimal(addr_info['sent']) / Decimal('1e8') - Decimal(addr_info['unconfirmed_sent']) / Decimal('1e8')
            balances.append({
                'address': addr,
                'received': received,
                'sent': sent,
                'balance': received - sent,
            })
        return balances

    @classmethod
    def parse_actions_btc_blockbook(cls, records, address):
        transactions = []
        for record in records:
            transactions.append(
                Transaction(
                    from_address=record.get('vin')[0].get('addresses'),
                    address=record.get('vout')[0].get('addresses')[0],
                    hash=record.get('txid'),
                    block=record.get('blockHeight'),
                    confirmations=record.get('confirmations'),
                    value=Decimal(record.get('value')) / Decimal('1e8'),
                    timestamp=datetime.fromtimestamp(record.get('blockTime')),
                    is_double_spend=False,
                    details=record
                )
            )
        return transactions

    @classmethod
    def parse_actions_btc_blockcypher(cls, records, address):
        transactions = []
        for record in records:
            outputs = record.get('outputs')
            inputs = record.get('inputs')
            source = inputs[0].get('addresses')
            destination = outputs[0].get('addresses')[0]
            # output_value = input_value - fee => so we considered output value in defineing transaction
            value = Decimal(str(outputs[0].get('value'))) / Decimal('100000000')
            transactions.append(Transaction(
                from_address=source,
                address=destination,
                hash=record.get('hash'),
                confirmations=record.get('confirmations'),
                block=record.get('block_height'),
                # time format is normal and do not need to parse utc
                timestamp=record.get('confirmed'),
                is_double_spend=record.get('double_spend'),
                value=value,
            ))
        return transactions

    @classmethod
    def get_wallets_balance_chainso(cls, address_list, raise_error=False):
        """
            Note: this function only returns net balances for each address and not sent/etc. details in order to make
                  fewer API call
                  Chain.so also supports SegWit Addresses
        """
        if not address_list:
            return []

        time.sleep(0.5)
        balances = []
        for address in address_list:
            time.sleep(1)
            try:
                if settings.USE_TESTNET_BLOCKCHAINS:
                    explorer_url = 'https://chain.so/api/v2/get_address_balance/BTCTEST/{}'
                else:
                    explorer_url = 'https://chain.so/api/v2/get_address_balance/BTC/{}'
                api_response = cls.get_session().get(
                    explorer_url.format(address), timeout=7)
                api_response.raise_for_status()
            except Exception as e:
                if raise_error:
                    raise e
                metric_incr('api_errors_count', labels=['btc', 'chain_so'])
                print('Failed to get BTC wallet balance from chain.so API: {}'.format(str(e)))
                # report_event('Chain.so API Error')
                time.sleep(1)
                continue
            info = api_response.json()
            if info.get('status') != 'success':
                # report_event('Chain.so API Error: {}'.format(info))
                continue
            addr_info = info['data']
            balance = Decimal(addr_info['confirmed_balance'])
            # TODO: currently we only return balance and set other fields to zero
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal(addr_info['unconfirmed_balance']),
            })
        return balances

    @classmethod
    def get_wallets_balance_smartbit(cls, address_list, raise_error=False):
        """
            Note: this function only returns net balances for each address and not sent/etc. details in order to make
                  fewer API call
                  Smartbit.com.au also supports SegWit Addresses
        """
        balances = []
        if not address_list:
            return balances

        time.sleep(0.5)
        param = ','.join(address_list)
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://testnet-api.smartbit.com.au/v1/blockchain/address/{}'
            else:
                explorer_url = 'https://api.smartbit.com.au/v1/blockchain/address/{}'
            api_response = cls.get_session().get(explorer_url.format(param), timeout=5)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['btc', 'smartbit'])
            print('Failed to get BTC wallet balance from API: {}'.format(str(e)))
            # report_event('Smartbit.com.au API Error')
            return None
        response_info = info['address'] if len(address_list) == 1 else info['addresses']
        if not isinstance(response_info, list):
            # if only one address is queried, a dict is returned instead of a list of dicts
            response_info = [response_info]
        for addr_info in response_info:
            if not addr_info:
                # API returns None for wallets with no transaction
                continue
            addr = addr_info['address']
            confirmed_info = addr_info['confirmed']
            received = Decimal(confirmed_info['received'])
            sent = Decimal(confirmed_info['spent'])
            balance = Decimal(confirmed_info['balance'])
            balances.append({
                'address': addr,
                'received': received,
                'sent': sent,
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallet_transactions_btc(cls, address):
        if cls.USE_EXPLORER_TRANSACTION == 'blockcypher':
            return blockcypher_inspect(address, Currencies.btc, network=cls.network)
        if cls.USE_EXPLORER_TRANSACTION == 'smartbit':
            return cls.get_wallet_transactions_smartbit(address)
        if cls.USE_EXPLORER_TRANSACTION == 'blockbook':
            return cls.get_wallet_transactions_blockbook(address)
        if cls.USE_EXPLORER_TRANSACTION == 'btc_com':
            return cls.get_wallet_transactions_btc_com(address)
        return cls.get_wallet_transactions_blockbook(address)

    @classmethod
    def get_wallet_transactions_blockbook(cls, address, raise_error=False):
        api = BitcoinBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.btc)
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
            if raise_error:
                raise error
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            return []

    @classmethod
    def get_wallet_transactions_btc_com(cls, address, raise_error=False):
        if address.startswith('bc1'):
            return cls.get_wallet_transactions_smartbit(address)

        time.sleep(0.1)
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                explorer_url = 'https://tchain.api.btc.com/v3/address/{}/tx?verbose=1'
            else:
                explorer_url = 'https://chain.api.btc.com/v3/address/{}/tx?verbose=1'
            api_response = cls.get_session().get(explorer_url.format(address), timeout=60,
                                                 proxies=settings.DEFAULT_PROXY)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            metric_incr('api_errors_count', labels=['btc', 'btc_com'])
            if raise_error:
                raise e
            error_message = str(e)
            error_message = error_message.replace(address, '{}')
            return None
        info = info.get('data')
        if not info:
            return []
        info = info.get('list') or []

        transactions = []
        for tx_info in info:
            from_addresses = set()
            for input in tx_info.get('inputs'):
                from_addresses.update(input.get('prev_addresses'))
            tx_timestamp = max(int(tx_info.get('created_at', 0)), int(tx_info.get('block_time', 0)))
            transactions.append(Transaction(
                address=address,
                from_address=list(from_addresses),
                hash=tx_info.get('hash'),
                timestamp=parse_utc_timestamp(tx_timestamp),
                value=Decimal(str(round(tx_info.get('balance_diff', 0)))) / Decimal('1e8'),
                confirmations=int(tx_info.get('confirmations', 0)),
                is_double_spend=bool(tx_info.get('is_double_spend')),
                details=tx_info,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_smartbit(cls, address, raise_error=False):
        time.sleep(0.2)
        try:
            if settings.USE_TESTNET_BLOCKCHAINS:
                return []
            else:
                explorer_url = 'https://api.smartbit.com.au/v1/blockchain/address/{}'
            api_response = cls.get_session().get(explorer_url.format(address), timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            metric_incr('api_errors_count', labels=['btc', 'smartbit'])
            if raise_error:
                raise e
            return None
        info = info.get('address')
        if not info:
            return []
        info = info.get('transactions') or []

        transactions = []
        for tx_info in info:
            value = Decimal('0')
            from_addresses = set()
            for txo in tx_info.get('outputs', []):
                if txo.get('addresses') != [address]:
                    continue
                value += Decimal(txo.get('value'))

            for txo in tx_info.get('inputs', []):
                from_addresses.update(txo.get('addresses'))
                if txo.get('addresses') == [address]:
                    value -= Decimal(txo.get('value'))

            if value <= Decimal('0'):
                continue
            transactions.append(Transaction(
                address=address,
                from_address=list(from_addresses),
                hash=tx_info.get('txid'),
                timestamp=parse_utc_timestamp(tx_info['time']),
                value=value,
                confirmations=int(tx_info.get('confirmations', 0)),
                is_double_spend=bool(tx_info.get('double_spend')),
                details=tx_info,
            ))
        return transactions

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=True):
        return cls.get_latest_block_addresses_blockbook(include_inputs=include_inputs, include_info=include_info)

    @classmethod
    def get_latest_block_addresses_blockbook(cls, include_inputs=False, include_info=True):
        """
            Retrieve block from blockbook by trezor.io
            :return: Set of addresses output transactions with pay to public key hash
            in last block processed until the last block mined
            API Document: https://github.com/trezor/blockbook/blob/master/docs/api.md
        """

        api = BitcoinBlockbookAPI.get_api()
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        try:
            return api.get_latest_block(include_inputs=include_inputs,
                                                                  include_info=include_info)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())

    @classmethod
    def get_invoice_status(cls, invoice_hash):
        try:
            lnd_client = LndClient.get_client()
        except Exception as e:
            report_exception()
            return
        params = [{
            'r_hash': invoice_hash,
        }]
        result = lnd_client.request('get_invoice', params=params)
        if not result:
            # report_event('[LND:GetInvoice] Empty result')
            return
        if result['status'] != 'success':
            # report_event(f'{result["code"]}-{result["message"]}')
            return
        invoice_info = result['result']
        timestamp = invoice_info.get('settleDate') or invoice_info.get('creationDate')
        if timestamp:
            timestamp = int(timestamp)
        value = invoice_info.get('amtPaidSat')
        if value is None:
            value = invoice_info.get('value', 0)
            if int(value) * Decimal('1e-8') > Decimal('0'):
                print(f'value is {value}')

        return {
            'hash': invoice_info['rHash'],
            'invoice': invoice_info['paymentRequest'],
            'state': invoice_info.get('state', 'OPEN'),
            'value': int(value) * Decimal('1e-8'),
            'timestamp': timestamp,
        }

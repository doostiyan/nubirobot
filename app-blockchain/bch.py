import re
import sys
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Union

from django.conf import settings
from django.core.cache import cache
from exchange.base.connections import get_electron_cash
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date, parse_utc_timestamp
from exchange.blockchain.api.bch.bch_blockbook import BitcoinCashBlockbookAPI
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction
from exchange.blockchain.utils import AddressNotExist, APIError, BadGateway, GatewayTimeOut, InternalServerError


class BitcoinCashBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.bch
    currency_list = [Currencies.bch]
    TESTNET_ENABLED = False
    USE_EXPLORER_BALANCE = 'node'  # Available options: node, blockbook, bitcoin_com
    USE_EXPLORER_TRANSACTION = 'blockbook'  # Available options: blockchair, blockbook, bitcoin_com
    fail_count = 0

    get_balance_method = {
        CurrenciesNetworkName.BCH: 'get_wallets_balance_bch',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.BCH: 'get_wallet_transactions_bch',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.BCH: 'get_transaction_details_bch',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }

    @classmethod
    def get_transaction_details_bch(cls, tx_hash, network=None):
        tx_details = None
        try:
            tx_details = BitcoinCashBlockbookAPI.get_api().get_tx_details(tx_hash=tx_hash)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut, Exception):
            pass
        return tx_details

    @classmethod
    def get_wallets_balance_bch(cls, address_list):
        if cls.USE_EXPLORER_BALANCE == 'node':
            return cls.get_wallets_balance_from_node(address_list)
        elif cls.USE_EXPLORER_BALANCE == 'blockbook':
            return cls.get_wallets_balance_from_blockbook(address_list)
        elif cls.USE_EXPLORER_BALANCE == 'bitcoin_com':
            return cls.get_wallets_balance_from_rest(address_list)
        return cls.get_wallets_balance_from_node(address_list)

    @classmethod
    def get_wallet_transactions_bch(cls, address, network=None):
        if cls.USE_EXPLORER_TRANSACTION == 'blockchair':
            return cls.get_wallet_transactions_from_blockchair(address)
        elif cls.USE_EXPLORER_TRANSACTION == 'blockbook':
            return cls.get_wallet_transactions_from_blockbook(address)
        elif cls.USE_EXPLORER_TRANSACTION == 'bitcoin_com':
            return cls.get_wallet_transactions_from_rest(address)
        return cls.get_wallet_transactions_from_blockbook(address)

    @classmethod
    def get_wallets_balance_from_node(cls, address_list, raise_error=False):
        """ Get BCH balance from electron cash node
            github: https://github.com/Electron-Cash/Electron-Cash
        """

        try:
            electron = get_electron_cash()
        except Exception as e:
            if raise_error:
                raise e
            print('ElectronCash Connection Error: {}'.format(str(e)))
            # report_event('ElectronCash Connection Error')
            return None
        balances = []
        for addr in address_list:
            try:
                res = electron.request('getaddressbalance', params=[addr])
            except Exception as e:
                if raise_error:
                    raise e
                print('Failed to get BCH wallet balance from ElectronCash: {}'.format(str(e)))
                # report_event('ElectronCash API Error')
                continue
            error = res.get('error')
            result = res.get('result')
            if error or not result:
                print('Failed to get BCH wallet balance from ElectronCash: {}'.format(str(res)))
                # report_event('ElectronCash Response Error')
                continue
            balance = Decimal(result['confirmed'])
            if balance is None:
                continue
            balances.append({
                'address': addr,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal(result['unconfirmed']),
            })
        return balances

    @classmethod
    def get_wallets_balance_from_blockbook(cls, address_list, raise_error=False):
        balances = []
        api = BitcoinCashBlockbookAPI.get_api()
        for address in address_list:
            try:
                response = api.get_balance(address)
                balance = response.get(Currencies.bch, {}).get('amount', Decimal('0'))
                unconfirmed_balance = response.get(Currencies.bch, {}).get('unconfirmed_amount', Decimal('0'))
            except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
                metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
                if raise_error:
                    raise error
                report_exception()
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
    def get_wallets_balance_from_rest(cls, address_list, raise_error=False):
        """ Get BCH balance from  https://rest.bitcoin.com
            API Document: https://developer.bitcoin.com/rest/docs/getting-started
        """

        time.sleep(0.1)
        use_testnet = cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS
        if use_testnet:
            fake_address = 'qp4nn5c3ve58wdc726m0wtpdx6f08hyxy53wme3lgz'
        else:
            fake_address = 'qqege9rukedym8h6knt82fpz8r0l3qruwsh3fu0mqw'

        address_list = [cls.get_signed_address(address) for address in address_list]
        if len(address_list) < 2:  # API not work for single address, adding a fake address!
            address_list += [cls.get_signed_address(fake_address)]

        try:
            if use_testnet:
                explorer_url = 'https://trest.bitcoin.com/v2/address/details'
            else:
                explorer_url = 'https://rest.bitcoin.com/v2/address/details'
            api_response = cls.get_session().post(explorer_url, data={'addresses': address_list}, timeout=5)
            api_response.raise_for_status()
            response_info = api_response.json()
        except Exception as e:
            metric_incr('api_errors_count', labels=['bch', 'rest'])
            if raise_error:
                raise e
            print('Failed to get BCH wallet balance from rest.bitcoin API: {}'.format(str(e)))
            # report_event('rest.bitcoin.com API Error')
            return None
        balances = []
        for addr_info in response_info:
            addr = addr_info['legacyAddress']
            received = Decimal(addr_info['totalReceived'])
            sent = Decimal(addr_info['totalSent'])
            balance = Decimal(addr_info['balance']) - Decimal(addr_info['unconfirmedBalance'])
            if balance is None:
                continue
            balances.append({
                'address': addr,
                'received': received,
                'sent': sent,
                'balance': balance,
            })
        return balances

    @classmethod
    def get_wallet_transactions_from_rest(cls, address, raise_error=False):
        """ Get BCH transactions from https://rest.bitcoin.com
            API Document: https://developer.bitcoin.com/rest/docs/getting-started
        """

        time.sleep(0.1)
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://trest.bitcoin.com/v2/'
        else:
            explorer_url = 'https://rest.bitcoin.com/v2/'
        try:
            explorer_url = explorer_url + f'address/transactions/{address}'
            api_response = cls.get_session().get(explorer_url, timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            metric_incr('api_errors_count', labels=['bch', 'rest'])
            if raise_error:
                raise e
            print('Failed to get BCH wallet transactions from API: {}'.format(str(e)))
            # report_event('Bitcoin.com API Error')
            return None
        if not info:
            return []

        legacy_address = info.get('legacyAddress')
        info = info.get('txs', [])
        transactions = []
        for tx_info in info:
            is_output_transaction = False
            from_address = set()
            for txin in tx_info.get('vin', []):
                from_address.add(txin.get('addr'))
                if txin.get('addr') == legacy_address:
                    is_output_transaction = True
                    break
            if is_output_transaction:
                continue

            value = Decimal('0')
            for txo in tx_info.get('vout', []):
                script = txo.get('scriptPubKey')
                if script.get('addresses') != [legacy_address]:
                    continue
                if script.get('type') != 'pubkeyhash':
                    continue
                # checking script opcodes: OP_DUP OP_HASH160 public_key_hash OP_EQUALVERIFY OP_CHECKSIG
                if not bool(re.match(r'^OP_DUP OP_HASH160[\s][\w\d]{40}[\s]OP_EQUALVERIFY OP_CHECKSIG$',
                                     script.get('asm'))):
                    continue
                # checking script opcodes hex: OP_DUP=0x76, OP_HASH160=0xa9, push=14,
                # public_key_hash=40 Hex Characters, OP_EQUALVERIFY= 0x88 OP_CHECKSIG=0xac
                if not bool(re.match(r'^76a914[\w\d]{40}88ac$', script.get('hex'))):
                    continue
                value += Decimal(txo.get('value'))
            if value <= Decimal('0'):
                continue

            tx_hash = tx_info.get('txid')
            tx_timestamp = parse_utc_timestamp(tx_info['time'])
            if tx_hash is None or tx_timestamp is None:
                continue
            transactions.append(Transaction(
                address=address,
                from_address=list(from_address),
                hash=tx_hash,
                timestamp=tx_timestamp,
                value=value,
                confirmations=tx_info.get('confirmations', 0),
                is_double_spend=False,
                details=tx_info,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_from_blockchair(cls, address, raise_error=False):
        """ Get BCH transactions from https://blockchair.com
            Support 1440 request per day and maximum 30 request per minutes
            API Document: https://blockchair.com/api/docs
        """

        try:
            if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
                return []
            explorer_url = 'https://api.blockchair.com/bitcoin-cash/'
            explorer_url = explorer_url + f'dashboards/address/{address}?transaction_details=true&limit=15'
            api_response = cls.get_session().get(explorer_url, timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
            print(info)
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['bch', 'blockchair'])
            print('Failed to get BCH wallet transactions from blockchair API: {}'.format(str(e)))
            # report_event('blockchair.com API Error')
            return None
        if not info:
            return []

        data = info.get('data').get(address)
        current_block = info.get('context').get('state')
        if data is None or current_block is None:
            return []

        address_info = data.get('address')
        if address_info.get('type') != 'pubkeyhash':
            return []

        formats_address = address_info.get('formats', {})
        if formats_address.get('legacy') != address and formats_address.get('cashaddr') != address:
            print('The address got from blockchair APi does not equal with wallet address')
            # report_event('The address got from blockchair APi does not equal with wallet address')
            return None

        transactions_info = data.get('transactions', [])
        transactions = []
        for tx_info in transactions_info:
            value = Decimal(tx_info.get('balance_change')) / Decimal(1e8)
            if value <= Decimal('0'):
                continue
            confirmations = current_block - tx_info.get('block_id') + 1
            timestamp = parse_iso_date('T'.join(tx_info['time'].split()) + 'Z')
            tx_hash = tx_info.get('hash')
            if tx_hash is None or timestamp is None:
                continue
            transactions.append(Transaction(
                address=address,
                hash=tx_hash,
                timestamp=timestamp,
                value=value,
                confirmations=confirmations,
                is_double_spend=False,
                details=tx_info,
            ))
        return transactions

    @classmethod
    def get_wallet_transactions_from_blockbook(cls, address, raise_error=False):
        api = BitcoinCashBlockbookAPI.get_api()
        try:
            txs = api.get_txs(address)
            transactions = []
            for tx_info_list in txs:
                tx_info = tx_info_list.get(Currencies.bch)
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
            report_exception()
            return []

    @classmethod
    def get_latest_block_addresses(cls, include_inputs=False, include_info=True):
        return cls.get_latest_block_addresses_blockbook(include_inputs=include_inputs, include_info=include_info)

    @classmethod
    def get_latest_block_addresses_blockbook(cls, include_inputs=False, include_info=True):
        """
            Retrieve block from blockbook by trezor.io
            :return: Set of addresses output transactions with pay to public key hash
            in last block processed until the last block mined
            API Document: https://bch.btc.com/api-doc
        """

        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set(), None, 0
        api = BitcoinCashBlockbookAPI.get_api()
        try:
            return api.get_latest_block(include_inputs=include_inputs,
                                                                      include_info=include_info)
        except (ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut) as error:
            metric_incr('api_errors_count', labels=[api.symbol, api.get_name()])
            traceback.print_exception(*sys.exc_info())

    @classmethod
    def get_latest_block_addresses_btc_com(cls) -> Union[None, set]:
        """ :return: Set of addresses output transactions with pay to public key hash
                     in last block processed until the last block mined
            API Document: https://bch.btc.com/api-doc
        """

        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return set()
        else:
            explorer_url_block_tx = 'https://bch-chain.api.btc.com/v3/block/{}/tx?page={}&verbose=3'
            explorer_url_block_info = 'https://bch-chain.api.btc.com/v3/block/{}'

        # get latest block information
        try:
            api_response = cls.get_session().get(explorer_url_block_info.format('latest'), timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            metric_incr('api_errors_count', labels=['bch', 'btc_com'])
            print('Failed to get BCH block information from API: {}'.format(str(e)))
            # report_event('bch.btc.com API Error')
            return None
        if not info:
            return set()
        if info.get('err_no') != 0:
            print('Failed to get BCH block information from API: {}'.format(info.get('err_msg')))
            # report_event('bch.btc.com API Error')
            return None

        latest_block_height_mined = info.get('data', {}).get('height')
        latest_block_height_processed = cache.get('BCH_latest_block_height_processed')
        if latest_block_height_processed and latest_block_height_processed >= latest_block_height_mined:
            cache.set('BCH_latest_block_height_processed', latest_block_height_mined)
            return set()
        if latest_block_height_processed is None:
            latest_block_height_processed = latest_block_height_mined - 5

        transactions_address = set()
        block_height = latest_block_height_mined
        while True:
            page = 1
            number_of_pages = 1
            while page <= number_of_pages:
                try:
                    url = explorer_url_block_tx.format(block_height, page)
                    api_response = cls.get_session().get(url, timeout=60)
                    api_response.raise_for_status()
                    info = api_response.json()
                    page += 1
                except Exception as e:
                    print('Failed to get BCH block transactions from API: {}'.format(str(e)))
                    # report_event('bch.btc.com API Error')
                    return None
                if not info:
                    return set()
                if info.get('err_no') != 0:
                    print('Failed to get BCH block transactions from API: {}'.format(info.get('err_msg')))
                    # report_event('bch.btc.com API Error')
                    return None

                block_data = info.get('data', {})
                total_count = block_data.get('total_count', 0)
                number_of_pages = (total_count // 50) + (total_count % 50 > 0)
                records = block_data.get('list', [])

                for tx_info in records:
                    outputs = tx_info.get('outputs') or []
                    for output in outputs:
                        if output.get('type') != 'P2PKH':
                            continue
                        if output.get('spent_by_tx') is not None:
                            continue
                        if output.get('spent_by_tx_position') != -1:
                            continue

                        # checking script opcodes: OP_DUP OP_HASH160 public_key_hash OP_EQUALVERIFY OP_CHECKSIG
                        if not bool(re.match(r'^OP_DUP OP_HASH160[\s][\w\d]{40}[\s]OP_EQUALVERIFY OP_CHECKSIG$',
                                             output.get('script_asm'))):
                            continue

                        # checking script opcodes hex: OP_DUP=0x76, OP_HASH160=0xa9, push=14,
                        # public_key_hash=40 Hex Characters, OP_EQUALVERIFY= 0x88 OP_CHECKSIG=0xac
                        if not bool(re.match(r'^76a914[\w\d]{40}88ac$', output.get('script_hex'))):
                            continue
                        value = Decimal(output.get('value')) / Decimal(1e8)
                        if value <= Decimal('0'):
                            continue

                        addresses = output.get('addresses') or []
                        if len(addresses) != 1:
                            continue
                        if addresses[0] in transactions_address:
                            continue
                        transactions_address.add(addresses[0])

            block_height -= 1
            if latest_block_height_processed >= block_height:
                cache.set('BCH_latest_block_height_processed', latest_block_height_mined)
                return set(transactions_address)

    @classmethod
    def get_signed_address(cls, address):
        if address[0] != 'q':  # Legacy address!
            return address
        addr_sign = 'bchtest' if settings.USE_TESTNET_BLOCKCHAINS else 'bitcoincash'
        return '{}:{}'.format(addr_sign, address)

    @classmethod
    def parse_actions_bchblockbook(cls, records, address):
        transactions = []
        for record in records:
            source = record.get('vin')[0].get('addresses')
            dest = record.get('vout')[0].get('addresses')[0]
            transactions.append(
                Transaction(
                    from_address=source,
                    address=dest,
                    hash=record.get('txid'),
                    block=record.get('blockHeight'),
                    confirmations=record.get('confirmations'),
                    is_double_spend=False,
                    details=record,
                    timestamp=datetime.fromtimestamp(record.get('blockTime')),
                    value=Decimal(record.get('value')) / Decimal('1e8')
                )
            )
        return transactions

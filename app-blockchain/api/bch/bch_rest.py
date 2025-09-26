from decimal import Decimal
from typing import List
from cashaddress import convert
from cashaddress.convert import InvalidAddress
import re

from django.conf import settings
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
    from blockchain.parsers import parse_utc_timestamp
else:
    from exchange.base.parsers import parse_utc_timestamp
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx, Balance


class BitcoinCashRestValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.003')

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if not balance_response:
            return False
        if not balance_response.get('balanceSat'):
            return False
        if balance_response.get('unconfirmedBalanceSat') is None:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not tx_details_response or not isinstance(tx_details_response, dict):
            return False
        if not tx_details_response.get('txid') or not isinstance(tx_details_response.get('txid'), str):
            return False
        if not tx_details_response.get('vin') or not isinstance(tx_details_response.get('vin'), list):
            return False
        if not tx_details_response.get('vout') or not isinstance(tx_details_response.get('vout'), list):
            return False
        if not tx_details_response.get('blockhash') or not isinstance(tx_details_response.get('blockhash'), str):
            return False
        if (not tx_details_response.get('confirmations') or
                not isinstance(tx_details_response.get('confirmations'), int)):
            return False
        if not tx_details_response.get('time') or not isinstance(tx_details_response.get('time'), int):
            return False
        if tx_details_response.get('fees') is None:
            return False
        if not tx_details_response.get('blockheight') or not isinstance(tx_details_response.get('blockheight'), int):
            return False
        if tx_details_response.get('blockheight') == -1:
            return False
        if tx_details_response.get('in_mempool') or not isinstance(tx_details_response.get('in_mempool'), bool):
            return False
        if tx_details_response.get('in_orphanpool') or not isinstance(tx_details_response.get('in_orphanpool'), bool):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not address_txs_response or not isinstance(address_txs_response, dict):
            return False
        if not address_txs_response.get('cashAddress') or not isinstance(address_txs_response.get('cashAddress'), str):
            return False
        if (not address_txs_response.get('legacyAddress') or
                not isinstance(address_txs_response.get('legacyAddress'), str)):
            return False
        if not address_txs_response.get('txs') or not isinstance(address_txs_response.get('txs'), list):
            return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction) -> bool:
        if not transaction.get('value'):
            return False
        value = Decimal(str(transaction.get('value')))
        if value < cls.min_valid_tx_amount:
            return False
        # If true, it means that it is an output transfer, else it is input.
        if transaction.get('scriptPubKey') and isinstance(transaction.get('scriptPubKey'), dict):
            if (not transaction.get('scriptPubKey').get('type') or
                    transaction.get('scriptPubKey').get('type') != 'pubkeyhash'):
                return False
            if (not transaction.get('scriptPubKey').get('cashAddrs') or
                    not isinstance(transaction.get('scriptPubKey').get('cashAddrs'), list)):
                return False
            if (not transaction.get('scriptPubKey').get('cashAddrs')[0] or
                    not isinstance(transaction.get('scriptPubKey').get('cashAddrs')[0], str)):
                return False
        else:
            if not transaction.get('cashAddress') or not isinstance(transaction.get('cashAddress'), str):
                return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction) -> bool:
        if not transaction or not isinstance(transaction, list):
            return False
        if not transaction[0] or not isinstance(transaction[0], dict):
            return False
        if not cls.validate_tx_details_response(transaction[0]):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer) -> bool:
        # If true, it means that it is an output transfer, else it is input.
        if transfer.get('scriptPubKey') and isinstance(transfer.get('scriptPubKey'), dict):
            if (not transfer.get('scriptPubKey').get('type') or
                    transfer.get('scriptPubKey').get('type') != 'pubkeyhash'):
                return False
            if (not transfer.get('scriptPubKey').get('addresses') or
                    not isinstance(transfer.get('scriptPubKey').get('addresses'), list)):
                return False
            if (not transfer.get('scriptPubKey').get('addresses')[0] or
                    not isinstance(transfer.get('scriptPubKey').get('addresses')[0], str)):
                return False
            if not transfer.get('value'):
                return False
            # We should check the pattern of output transfers to match the one below.
            if not bool(re.match(r'^OP_DUP OP_HASH160[\s][\w\d]{40}[\s]OP_EQUALVERIFY OP_CHECKSIG$',
                                 transfer.get('scriptPubKey').get('asm'))):
                return False
            if not bool(re.match(r'^76a914[\w\d]{40}88ac$', transfer.get('scriptPubKey').get('hex'))):
                return False
        else:
            if not transfer.get('valueSat'):
                return False
            if not transfer.get('cashAddress') or not isinstance(transfer.get('cashAddress'), str):
                return False
        return True


class BitcoinCashRestResponseParser(ResponseParser):
    validator = BitcoinCashRestValidator
    symbol = 'BCH'
    currency = Currencies.bch
    precision = 8

    @staticmethod
    def convert_address(address):
        try:
            return convert.to_legacy_address(address)
        except InvalidAddress:
            return None

    @classmethod
    def parse_balance_response(cls, balance_response):
        if not cls.validator.validate_balance_response(balance_response):
            return Balance(
                balance=Decimal('0'),
                unconfirmed_balance=Decimal('0')
            )
        return Balance(
            balance=BlockchainUtilsMixin.from_unit(
                number=balance_response.get('balanceSat', 0),
                precision=cls.precision
            ),
            unconfirmed_balance=BlockchainUtilsMixin.from_unit(
                number=balance_response.get('unconfirmedBalanceSat', 0),
                precision=cls.precision,
                negative_value=True
            ),
        )

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_height = tx_details_response.get('blockheight')
            block_hash = tx_details_response.get('blockhash')
            fee = Decimal(str(tx_details_response.get('fees')))
            tx_hash = tx_details_response.get('txid')
            confirmations = tx_details_response.get('confirmations')
            date = parse_utc_timestamp(tx_details_response.get('time'))
            for input in tx_details_response.get('vin'):
                if cls.validator.validate_tx_details_transaction(input):
                    from_address = cls.convert_address(input.get('cashAddress'))
                    value = Decimal(str(input.get('value')))
                    for tx in transfers:
                        if tx.from_address == from_address:
                            tx.value += value
                            break
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            from_address=from_address,
                            to_address='',
                            value=value,
                            block_height=block_height,
                            confirmations=confirmations,
                            block_hash=block_hash,
                            success=True,
                            symbol=cls.symbol,
                            date=date,
                            tx_fee=fee,
                        )
                        transfers.append(transfer)
            for output in tx_details_response.get('vout'):
                if cls.validator.validate_tx_details_transaction(output):
                    to_address = cls.convert_address(output.get('scriptPubKey').get('cashAddrs')[0])
                    value = Decimal(str(output.get('value')))
                    for tx in transfers:
                        if tx.from_address == to_address:
                            tx.value -= value
                            break

                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            from_address='',
                            to_address=to_address,
                            value=value,
                            block_height=block_height,
                            block_hash=block_hash,
                            confirmations=confirmations,
                            success=True,
                            symbol=cls.symbol,
                            date=date,
                            tx_fee=fee,
                        )
                        transfers.append(transfer)
        return transfers

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        address_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('txs')
            for transaction in transactions:
                if cls.validator.validate_address_tx_transaction(transaction):
                    block_height = transaction[0].get('blockheight')
                    block_hash = transaction[0].get('blockhash')
                    fee = Decimal(str(transaction[0].get('fees')))
                    tx_hash = transaction[0].get('txid')
                    confirmations = transaction[0].get('confirmations')
                    date = parse_utc_timestamp(transaction[0].get('time'))
                    for input in transaction[0].get('vin'):
                        if cls.validator.validate_transfer(input):
                            from_address = cls.convert_address(input.get('cashAddress'))
                            value = Decimal(str(input.get('valueSat')))
                            for tx in address_txs:
                                if tx.from_address == from_address and tx.tx_hash == tx_hash:
                                    tx.value += value
                                    break
                            else:
                                transfer = TransferTx(
                                    tx_hash=tx_hash,
                                    from_address=from_address,
                                    to_address='',
                                    value=value,
                                    block_height=block_height,
                                    confirmations=confirmations,
                                    block_hash=block_hash,
                                    success=True,
                                    symbol=cls.symbol,
                                    date=date,
                                    tx_fee=fee,
                                )
                                address_txs.append(transfer)
                    for output in transaction[0].get('vout'):
                        if cls.validator.validate_transfer(output):
                            to_address = cls.convert_address(output.get('scriptPubKey').get('addresses')[0])
                            value = Decimal(str(output.get('value')))
                            for tx in address_txs:
                                if tx.from_address == to_address and tx.tx_hash == tx_hash:
                                    tx.value -= value
                                    break
                            else:
                                transfer = TransferTx(
                                    tx_hash=tx_hash,
                                    from_address='',
                                    to_address=to_address,
                                    value=value,
                                    block_height=block_height,
                                    block_hash=block_hash,
                                    confirmations=confirmations,
                                    success=True,
                                    symbol=cls.symbol,
                                    date=date,
                                    tx_fee=fee,
                                )
                                address_txs.append(transfer)
        return address_txs


class BitcoinCashRestApi(GeneralApi):
    parser = BitcoinCashRestResponseParser
    _base_url = 'https://rest.bch.actorforth.org/v2'
    testnet_url = 'https://trest.bitcoin.com/v2'
    cache_key = 'bch'
    symbol = 'BCH'
    rate_limit = 0.75
    need_block_head_for_confirmation = False
    # Not good for address_txs request so removed from alternatives
    supported_requests = {
        'get_address_txs': '/address/transactions/{address}',
        'get_tx_details': '/transaction/details/{tx_hash}',
        'get_balance': '/address/details/{address}'
    }

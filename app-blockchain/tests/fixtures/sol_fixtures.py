import datetime
from decimal import Decimal
from typing import List, Dict

import pytest
import pytz

from exchange.blockchain.api.general.dtos import TransferTx


@pytest.fixture
def sol_raw_multi_transfer_address_txs() -> List[Dict]:
    raw_data = [
        {
            'result': {
                'blockTime': 1737905220,
                'meta': {
                    'err': None,
                    'fee': 5000,
                    'postBalances': [2029433761,
                                     1537679,
                                     1000000,
                                     1000000,
                                     1],
                    'postTokenBalances': [],
                    'preBalances': [2033448761,
                                    1527679,
                                    0,
                                    0,
                                    1],
                    'preTokenBalances': [],
                    'status': {'Ok': None}},
                'slot': 316514709,
                'transaction': {
                    'message': {
                        'accountKeys': [{'pubkey': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv'},
                                         {'pubkey': '9sA8AkjoegjBefJQNYWrPmX1bBKnbiSdY9bGZmpv2we9'},
                                         {'pubkey': 'AivgNohmSFG2Go7ycCcKhuiuziMs1kvSAHACPiio6taJ'},
                                         {'pubkey': 'H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ'},
                                         {'pubkey': '11111111111111111111111111111111'}],
                        'addressTableLookups': [],
                        'instructions': [
                            {
                                'parsed': {
                                    'info': {'destination': '9sA8AkjoegjBefJQNYWrPmX1bBKnbiSdY9bGZmpv2we9',
                                             'lamports': 1000000,
                                             'source': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv'},
                                    'type': 'transfer'
                                },
                                'program': 'system',
                                'programId': '11111111111111111111111111111111',
                            },
                            {
                                'parsed': {
                                    'info': {'destination': 'AivgNohmSFG2Go7ycCcKhuiuziMs1kvSAHACPiio6taJ',
                                             'lamports': 1000000,
                                             'source': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv'},
                                    'type': 'transfer'
                                },
                                'program': 'system',
                                'programId': '11111111111111111111111111111111',
                            },
                            {
                                'parsed': {
                                    'info': {'destination': 'H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ',
                                             'lamports': 1000000,
                                             'source': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv'},
                                    'type': 'transfer'
                                },
                                'program': 'system',
                                'programId': '11111111111111111111111111111111'},
                        ],
                    },
                    'signatures': [
                        '4gS19hrer6Cx6H2f6wEM594vS5qsFTHZ3Ci36rgDL9Z4HZcnYsqPLupoHcW6xQXmrkh7ZEqB9dAxZ1huUcs7uBCc']},
            }
        }
    ]
    return raw_data


@pytest.fixture
def sol_parsed_multi_transfer_address_txs() -> List[TransferTx]:
    data = [
        {
            'block_hash': None,
            'block_height': 316514709,
            'confirmations': 183732,
            'date': datetime.datetime(2025, 1, 26, 18, 57, tzinfo=pytz.UTC),
            'from_address': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv',
            'index': None,
            'memo': None,
            'success': True,
            'symbol': 'SOL',
            'to_address': '9sA8AkjoegjBefJQNYWrPmX1bBKnbiSdY9bGZmpv2we9',
            'token': None,
            'tx_fee': Decimal('0.000005000'),
            'tx_hash': '4gS19hrer6Cx6H2f6wEM594vS5qsFTHZ3Ci36rgDL9Z4HZcnYsqPLupoHcW6xQXmrkh7ZEqB9dAxZ1huUcs7uBCc',
            'value': Decimal('0.001000000'),
        },
        {
            'block_hash': None,
            'block_height': 316514709,
            'confirmations': 183732,
            'date': datetime.datetime(2025, 1, 26, 18, 57, tzinfo=pytz.UTC),
            'from_address': 'AivgNohmSFG2Go7ycCcKhuiuziMs1kvSAHACPiio6taJ',
            'index': None,
            'memo': None,
            'success': True,
            'symbol': 'SOL',
            'to_address': 'AivgNohmSFG2Go7ycCcKhuiuziMs1kvSAHACPiio6taJ',
            'token': None,
            'tx_fee': Decimal('0.000005000'),
            'tx_hash': '4gS19hrer6Cx6H2f6wEM594vS5qsFTHZ3Ci36rgDL9Z4HZcnYsqPLupoHcW6xQXmrkh7ZEqB9dAxZ1huUcs7uBCc',
            'value': Decimal('0.001000000'),
        },
        {
            'block_hash': None,
            'block_height': 316514709,
            'confirmations': 183732,
            'date': datetime.datetime(2025, 1, 26, 18, 57, tzinfo=pytz.UTC),
            'from_address': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv',
            'index': None,
            'memo': None,
            'success': True,
            'symbol': 'SOL',
            'to_address': 'H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ',
            'token': None,
            'tx_fee': Decimal('0.000005000'),
            'tx_hash': '4gS19hrer6Cx6H2f6wEM594vS5qsFTHZ3Ci36rgDL9Z4HZcnYsqPLupoHcW6xQXmrkh7ZEqB9dAxZ1huUcs7uBCc',
            'value': Decimal('0.001000000'),
        },
    ]

    transfers = [
        TransferTx(**tx_data)
        for tx_data in data
    ]

    return transfers



@pytest.fixture
def sol_multi_transfer_address():
    return 'H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ'
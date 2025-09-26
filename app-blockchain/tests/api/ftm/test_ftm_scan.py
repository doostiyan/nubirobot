from datetime import datetime
from decimal import Decimal
from typing import List, Dict
from unittest.mock import Mock

import pytest
import pytz
from django.conf import settings
from django.core.cache import cache

from exchange.blockchain.api.ftm.ftm_explorer_interface import FTMExplorerInterface
from exchange.blockchain.api.ftm.ftm_scan import FtmScanApi
from exchange.blockchain.contracts_conf import opera_ftm_contract_info
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

GET_BALANCES_MOCK_RESPONSE: List[Dict] = [{
    'status': '1',
    'message': 'OK',
    'result': [
        {
            'account': '0xc9bB715E2538A08aC7418A79E808B22f78415620',
            'balance': '5491731466303367276'
        },
        {
            'account': '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F',
            'balance': '23776584000000000000'
        }
    ]
}]

GET_TXS_MOCK_RESPONSE: List[Dict] = [
    {
        'result': '0x5393803'
    },
    {
        'message': 'OK',
        'result': [
            {
                'blockNumber': '87635177',
                'timeStamp': '1722666080',
                'hash': '0x428a6e267704eb0c8f03478348e08c9347e69986cadeb0058d5b3357d7ce85e5',
                'from': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                'to': '0xa3472370b9312f757f714972e8d1d8a75f4ad999',
                'value': '12364781633033800',
                'gas': '21000',
                'gasPrice': '18845537054',
                'input': '0x',
                'isError': '0',
                'txreceipt_status': '1',
            },
            {
                'blockNumber': '87635167',
                'timeStamp': '1722666152',
                'hash': '0x0986dcc4487aa89e164a836723d7b8a9e7082dc315c4ec3173dcec5d1cbadabd',
                'from': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                'to': '0xa3472370b9312f757f714972e8d1d8a75f4ad999',
                'value': '14767646064306940',
                'input': '0x',
                'confirmations': '92',
                'isError': '0',
                'txreceipt_status': '1',
                'gas': '21000',
                'gasPrice': '18579120385',
            }
        ]
    }
]

GET_TXS_TXRECEIPT_STATUS_ZERO_MOCK_RESPONSE: List[Dict] = [
    {
        'result': '0x5393803'
    },
    {
        'message': 'OK',
        'result': [
            {
                'isError': '0',
                'txreceipt_status': '0',
            }
        ]
    }
]

GET_TXS_IS_ERROR_ONE_MOCK_RESPONSE: List[Dict] = [
    {
        'result': '0x5393803'
    },
    {
        'message': 'OK',
        'result': [
            {
                'isError': '1',
                'txreceipt_status': '1',
            }
        ]
    }
]

GET_TX_DETAILS_MOCK_RESPONSE: List[Dict] = [
    {
        'result': '0x5393803'
    },
    {
        'result': {
            'blockNumber': '0x53101ed',
            'from': '0x2ddd6ed11400a8a1d5c4184589d9b903b1311fd8',
            'gas': '0x5208',
            'gasPrice': '0x5aa31d7af',
            'hash': '0x9c38c7e6c2dd73d605126aa011f23e52558d422ad3dc6945296feee26443f99e',
            'input': '0x',
            'to': '0xf45f0c3573c8b704bbb50fce53b4024a706d43c0',
            'value': '0x372950dd7e1ff5',
            'type': '0x2',
        }
    }
]

GET_BLOCK_ADDRESSES_MOCK_RESPONSE: List[Dict] = [
    {
        'result': '0x5395708'
    },
    {'jsonrpc': '2.0', 'id': 1,
     'result': {'baseFeePerGas': '0x400d09324', 'difficulty': '0x0', 'epoch': '0x48961', 'extraData': '0x',
                'gasLimit': '0xffffffffffff', 'gasUsed': '0x6737d',
                'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                'logsBloom': '0x00100008000000000000000000000000040000000000040004020000000000000000000000000080002000000000040000000000000000000004000000000000000000000000000000000008000040000000000000001000000000000000000010000000060400000000000000000800000000000000000010000010000000000001000000000800000000000000080000000000000000000000000000800480400000002000000000000000009000000000000000000400000000000000000000000002000000001000000000000000010000000100000000400000040020800000000000000000000040000000010000000000800040000000000000100000',
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000000', 'number': '0x5395708',
                'parentHash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
                'receiptsRoot': '0x96ec45cb0b09622a11ed00077e422887c7f7052f2599da17861a3dd620544986',
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347', 'size': '0x4c4',
                'stateRoot': '0xee9c760edc829278e90eebbe260dfcb5dcc4467ddb124390265b3eb0878200b6',
                'timestamp': '0x66ade6f7', 'timestampNano': '0x17e829dd37c76907', 'totalDifficulty': '0x0',
                'transactions': [{'blockHash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                  'blockNumber': '0x5395708', 'from': '0x055f72ab5db7c3c14233599ddec34bb3a5c88eb6',
                                  'gas': '0xf4240', 'gasPrice': '0x47cf14ddb', 'maxFeePerGas': '0x47cf14ddb',
                                  'maxPriorityFeePerGas': '0x7c20bab7',
                                  'hash': '0x4ddddfe03fd6caf25d5dd6049138a4c3c620c8a03cca21860fc9097416a3d0a2',
                                  'input': '0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000fa0000000000000000000000000dfd9b9b25cef61033ca680526722c8335281b8c00000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000cc19abe2f12c8315be0cf00114c96e10e9e44f6200000000000000000000000000000000000000000000000000000000000001470000000000000000000000000000000000000000000000000000000066ade7ab0000000000000000000000000000000000000000000000000000000000000084bc78570100000000000000000000000065be4f5e6dc20b008593437e6aa8238a79f0664600000000000000000000000000000000000000000000000000000000000078ad000000000000000000000000f5a543bba6b6655a0025fe849612951cb63caad600000000000000000000000000000000000000000000000000000000000007fb00000000000000000000000000000000000000000000000000000000',
                                  'nonce': '0x57', 'to': '0x52ceba41da235af367bfc0b0ccd3314cb901bb5f',
                                  'transactionIndex': '0x0', 'value': '0x0', 'type': '0x2', 'accessList': [],
                                  'chainId': '0xfa', 'v': '0x1',
                                  'r': '0x7e10bfa6ac01c9bf30f805e8ad3509e3fdff457dd466e912354b1ea7f5e2f644',
                                  's': '0x59bed03c2d2345875a0871e6af4d0f1c44d21944cb276d09cd2337899507075b'},
                                 {'blockHash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                  'blockNumber': '0x5395708', 'from': '0x34b0105cd7009edaa488ee31590204347ba0764f',
                                  'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'maxFeePerGas': '0x13433f9c89',
                                  'maxPriorityFeePerGas': '0xf894faca3',
                                  'hash': '0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc',
                                  'input': '0x', 'nonce': '0x13b77', 'to': '0x20c170ffcca6fc29fdb906ad22fb88abfee19b58',
                                  'transactionIndex': '0x1', 'value': '0x2c4e53da9e16f8', 'type': '0x2',
                                  'accessList': [], 'chainId': '0xfa', 'v': '0x1',
                                  'r': '0xd107e6f693de7ff0b0093318b3562987d163e4fe3d5457cb028a14763b8ec26e',
                                  's': '0x3ab79396eabbc1c5a5818677ffaa75d993753f47de9cc7ecb8a6e277c1894445'}],
                'transactionsRoot': '0x4fcc8b9b2633d5527c038ff5c19083ea851518868caca8e8ff7752aef7e0fe3d',
                'uncles': []}},
    {'jsonrpc': '2.0', 'id': 1,
     'result': {'baseFeePerGas': '0x400d09324', 'difficulty': '0x0', 'epoch': '0x48961', 'extraData': '0x',
                'gasLimit': '0xffffffffffff', 'gasUsed': '0xe8769',
                'hash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
                'logsBloom': '0x00000008000000000000000000000000040000020000020400000000000000000000000400000000000000000000000000000000000000010000000000000000000000000800000000000000000040000000000000004000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000040000000000000000000000000000000000008000000000000008100200000000000000000000000000000000000000000000000000010008000000000000000020000000000000000000000000000000000000000000000000800000080000000000000000',
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000000', 'number': '0x5395707',
                'parentHash': '0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0',
                'receiptsRoot': '0xc0bb7ad1465ca3b693dbc279fd25c5d77eeffd7cea465d2a07adead3f902a2f6',
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347', 'size': '0x615',
                'stateRoot': '0x17e09f6ce3dbff221de93831f42dca843adb95339aab920e96f94d439d9db148',
                'timestamp': '0x66ade6f6', 'timestampNano': '0x17e829dd0d29222b', 'totalDifficulty': '0x0',
                'transactions': [{'blockHash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
                                  'blockNumber': '0x5395707', 'from': '0x677ccc389a28b17043e5d21b2cb3d2ec40d4e9ee',
                                  'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'maxFeePerGas': '0x13433f9c89',
                                  'maxPriorityFeePerGas': '0xf894faca3',
                                  'hash': '0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a',
                                  'input': '0x', 'nonce': '0x1490e', 'to': '0xf87f57dcd8a97a5d40a008224855371e2cba6fe4',
                                  'transactionIndex': '0x0', 'value': '0x359bee87147b91', 'type': '0x2',
                                  'accessList': [], 'chainId': '0xfa', 'v': '0x1',
                                  'r': '0x146759c04421dec411dc02d54a880d4e3366230b4d70477f4f3fb699e1925cd',
                                  's': '0x745e148d6c268422377e23ce9b23f28383b2063fdad54723a3130d6c96eeb385'},
                                 {'blockHash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
                                  'blockNumber': '0x5395707', 'from': '0x1098db74b3cc07a78e25756765d91625773c2a04',
                                  'gas': '0x5208', 'gasPrice': '0x45d964b800',
                                  'hash': '0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274',
                                  'input': '0x', 'nonce': '0x0', 'to': '0xf89d7b9c864f589bbf53a82105107622b35eaa40',
                                  'transactionIndex': '0x1', 'value': '0xedaa05b4404f9dffa', 'type': '0x0',
                                  'v': '0x218',
                                  'r': '0x95299d15c1e4066e452f6bb3550a9926aaefd1b1e7d194dd7c6c5c7eb2782013',
                                  's': '0x4c57cfed91e74e1935126d2045559cde173ca321d46a70226aa9c61de1069520'},
                                 {'blockHash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
                                  'blockNumber': '0x5395707', 'from': '0x5f9ed9db4d8f6ba2fd2a65497097d85160ebdc40',
                                  'gas': '0x3567e0', 'gasPrice': '0x43c6b5d24', 'maxFeePerGas': '0x43c6b5d24',
                                  'maxPriorityFeePerGas': '0x3b9aca00',
                                  'hash': '0xc8518d8eafc9a4e9ef4e667f7507ba91b161ae97afc725d695cecbc2698ca144',
                                  'input': '0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000fa00000000000000000000000089e8fa64d576d84e0143af9ee9c94f759f1ef75900000000000000000000000000000000000000000000000000000000000000c00000000000000000000000008c2e12b7f08265cf1555c7cd886de84fea6a4c8100000000000000000000000000000000000000000000000000000000000000360000000000000000000000000000000000000000000000000000000066ade793000000000000000000000000000000000000000000000000000000000000016438430cce00000000000000000000000000000000000000000000000000000000000193c500000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                                  'nonce': '0x5', 'to': '0x52ceba41da235af367bfc0b0ccd3314cb901bb5f',
                                  'transactionIndex': '0x2', 'value': '0x0', 'type': '0x2', 'accessList': [],
                                  'chainId': '0xfa', 'v': '0x1',
                                  'r': '0x5cc957c4852f35c951e2f60fc0759b9306ee00f4f8d169a7a7d946e7a8d45ef4',
                                  's': '0x23b9c591650c36bba8a4a2647f4fd9cf78fe6320fbf08db2ae72a06b56383bff'}],
                'transactionsRoot': '0xcf3353b0d8a96157d24b060b5859ca185eb071c9e859809e465b54ea5d748b94',
                'uncles': []}},
    {'jsonrpc': '2.0', 'id': 1,
     'result': {'baseFeePerGas': '0x400d09324', 'difficulty': '0x0', 'epoch': '0x48961', 'extraData': '0x',
                'gasLimit': '0xffffffffffff', 'gasUsed': '0x70c92',
                'hash': '0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0',
                'logsBloom': '0x00100008200000000000000000000000040000000000040004020000000000000000800000000080002000000000040000000000000000000004000000000004000000000000000000000008000040000000000200001000010000000000000010000000060400040000000000000800000000000000000010000010000000000001000100000800000000000000080040000000000000000000000000800000000000002000000000000000009000000000000000000400000000000000000000000002000010000000000000000000000000000000000000000000040020000000000000000000000040000000010000000000800000000000000000100000',
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000000', 'number': '0x5395706',
                'parentHash': '0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39',
                'receiptsRoot': '0xeb51278b8b81ea03307b15e3f64af6330b183935cd2f6ab11e4c6c0d1368e455',
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347', 'size': '0x4c6',
                'stateRoot': '0x11db95d38ab5eb794de7cd902099be433d8c058807a44379a64018110a73a00a',
                'timestamp': '0x66ade6f6', 'timestampNano': '0x17e829dce32630b1', 'totalDifficulty': '0x0',
                'transactions': [{'blockHash': '0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0',
                                  'blockNumber': '0x5395706', 'from': '0x5275dffb00bbd7cf7ac43fee3f95a4a58871e60b',
                                  'gas': '0xf4240', 'gasPrice': '0x48b2b4634', 'maxFeePerGas': '0x48b2b4634',
                                  'maxPriorityFeePerGas': '0x8a5ab310',
                                  'hash': '0x7bb5b235e5fca2a08652825a4133cc5a63bafde98e08c58880b87e43e0198388',
                                  'input': '0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000fa0000000000000000000000000dfd9b9b25cef61033ca680526722c8335281b8c00000000000000000000000000000000000000000000000000000000000000c00000000000000000000000001b8ee43b1ef423a452d878c97b3f2018e40211e90000000000000000000000000000000000000000000000000000000000003ed10000000000000000000000000000000000000000000000000000000066ade7a90000000000000000000000000000000000000000000000000000000000000084bc785701000000000000000000000000b509d72dad8d9ebe76d660ed49fea2e46dcf96730000000000000000000000000000000000000000000000000000000000001915000000000000000000000000e44ff9dd9c8a9737d7ab4ed3e7b1e226430ad7fd000000000000000000000000000000000000000000000000000000000000037e00000000000000000000000000000000000000000000000000000000',
                                  'nonce': '0x460', 'to': '0x52ceba41da235af367bfc0b0ccd3314cb901bb5f',
                                  'transactionIndex': '0x0', 'value': '0x0', 'type': '0x2', 'accessList': [],
                                  'chainId': '0xfa', 'v': '0x0',
                                  'r': '0x7e5def16598a4e014a6ca47c8373a7d58be63683d1f0dc2dfa77af2442b659b8',
                                  's': '0x33daa7322e799ecd2be1d04dd272e4f793644749834991f2116f7463d2abc060'},
                                 {'blockHash': '0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0',
                                  'blockNumber': '0x5395706', 'from': '0x6e8a80e35c3840913b517bc4a02028831d04df96',
                                  'gas': '0x5208', 'gasPrice': '0xdf8475800', 'maxFeePerGas': '0xdf8475800',
                                  'maxPriorityFeePerGas': '0xdf8475800',
                                  'hash': '0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98',
                                  'input': '0x', 'nonce': '0x2fded', 'to': '0xc7abcd945a93bb082306fe94f67105d703c6a1d0',
                                  'transactionIndex': '0x1', 'value': '0xaa87bee538000', 'type': '0x2',
                                  'accessList': [], 'chainId': '0xfa', 'v': '0x1',
                                  'r': '0xd8297ae302706a534fdac07d511edf837017ff1cc1609a5621fc869957598a73',
                                  's': '0x660f52fbaa50b617ab425a146e5961c4d8ac3c4a014cca5f50ee66dbde642c22'}],
                'transactionsRoot': '0x1f8809edd81a3f2f6c63d8fa94fdd03bb80c95219d3a4cf5e9bac3e43e2c8678',
                'uncles': []}},
    {'jsonrpc': '2.0', 'id': 1,
     'result': {'baseFeePerGas': '0x400d09324', 'difficulty': '0x0', 'epoch': '0x48961', 'extraData': '0x',
                'gasLimit': '0xffffffffffff', 'gasUsed': '0x39e6b1',
                'hash': '0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39',
                'logsBloom': '0x0000000400000100080000002000000000000020000000000000000000000000000000000000000001000000000c000000000000000000000000800000000008000002000000000000000004000040200000000000000000000042000000000000000000020000010020000040080800000200000824000000000000080000000000000000000000000000000040100000000008000202000800000200000000000000000000000100000000400800000000000000000000000200000200000000000000000008010000000010000000000400000000000000001240000020000000000000000000000000800000000000000000000000004020020102000000',
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000000', 'number': '0x5395705',
                'parentHash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                'receiptsRoot': '0xa6bcfc5cd5cb225aafbf768e3b24825f983fbd0a9ed025b16314c9ddf5be6cdd',
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347', 'size': '0x6e6',
                'stateRoot': '0x081721a07e36f8f507d4fab5ea9cfe05344127fef3e13cd11cdcbc7dce3ed53b',
                'timestamp': '0x66ade6f5', 'timestampNano': '0x17e829dcb84d1520', 'totalDifficulty': '0x0',
                'transactions': [{'blockHash': '0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39',
                                  'blockNumber': '0x5395705', 'from': '0x1cbd230943dbb0276e337a9f2ccf05610d1c4dee',
                                  'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'maxFeePerGas': '0x13433f9c89',
                                  'maxPriorityFeePerGas': '0xf894faca3',
                                  'hash': '0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7',
                                  'input': '0x', 'nonce': '0x14e31', 'to': '0xfa4df55bbe69a76bfa17881f3a6132ffc69e43b7',
                                  'transactionIndex': '0x0', 'value': '0x2ce0775ec1ede7', 'type': '0x2',
                                  'accessList': [], 'chainId': '0xfa', 'v': '0x0',
                                  'r': '0x5eb9056c5ee8b2f8949f422bd2b45eb0703fc00a12e7f1e10481119c906c4e74',
                                  's': '0x5bd8de82a6cea5daa6fca935159c08eafcca1d59a565b4b37dd6bad3105a06c6'},
                                 {'blockHash': '0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39',
                                  'blockNumber': '0x5395705', 'from': '0x68aedee7dc9da33a1e7d32a6637361e409c40519',
                                  'gas': '0x3c46b3', 'gasPrice': '0x45a38c224', 'maxFeePerGas': '0x5c0e828d7',
                                  'maxPriorityFeePerGas': '0x59682f00',
                                  'hash': '0x07d8032650fe597f704003ecbd9590337866b6f75ef9c9716a862f03befc3c99',
                                  'input': '0xac9650d80000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000000700000000000000000000000000000000000000000000000000000000000000e0000000000000000000000000000000000000000000000000000000000000014000000000000000000000000000000000000000000000000000000000000001a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000026000000000000000000000000000000000000000000000000000000000000002c00000000000000000000000000000000000000000000000000000000000000320000000000000000000000000000000000000000000000000000000000000002485478c7f0000000000000000000000009777ce91bbcbff048b2d107dde29a58faa3bc78100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000e9e72c4eb0ac0170432f03cdf7e9aada2718143b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000082125d3afd871a3a91d8975c80efb9701fec19800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000e90ec537fab7f055f6895b73038c15644a3f511c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000aea03e59fe34f21087c89bfd9cdd1e4bc17b839100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000b5326a3f975d5f0f2305c4f4c0328478ef4de7b300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f0000000000000000000000007790a63ea9bf3281822021fcf70a7bf4d460820300000000000000000000000000000000000000000000000000000000',
                                  'nonce': '0x13af', 'to': '0xf9a66f8c569d23f1fa1a63950c3ca822cf26355e',
                                  'transactionIndex': '0x1', 'value': '0x0', 'type': '0x2', 'accessList': [],
                                  'chainId': '0xfa', 'v': '0x1',
                                  'r': '0x20dcddb47791b1e141fe9a674fcd0132011bb4b94304147ab695e9750e5ec650',
                                  's': '0x551266aa3b049c9770c11394d7705b4968fbb149adb1e1a504242a2e73cbcf65'}],
                'transactionsRoot': '0x14e7b31b6fe831b3ad43b36fc5faa49fcbec32f2240e733d37bc032005d715cb',
                'uncles': []}},
    {'jsonrpc': '2.0', 'id': 1,
     'result': {'baseFeePerGas': '0x400d09324', 'difficulty': '0x0', 'epoch': '0x48961', 'extraData': '0x',
                'gasLimit': '0xffffffffffff', 'gasUsed': '0x65d2e',
                'hash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                'logsBloom': '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                'miner': '0x0000000000000000000000000000000000000000',
                'mixHash': '0x0000000000000000000000000000000000000000000000000000000000000000',
                'nonce': '0x0000000000000000', 'number': '0x5395704',
                'parentHash': '0x0004896100000cc0c2bf713ce57d59eaf06da7fd7f70b9f85d73b72b65e17274',
                'receiptsRoot': '0xa6fa45835234e4de6b20acd26644ae3c17be4edbdc8b01a0f94ce7a6124ceeb7',
                'sha3Uncles': '0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347', 'size': '0x541',
                'stateRoot': '0x59d21743e0de76dd91840e45934fadc84d8655eb09199f9ec041117101fc8ca8',
                'timestamp': '0x66ade6f5', 'timestampNano': '0x17e829dca1316a0d', 'totalDifficulty': '0x0',
                'transactions': [{'blockHash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                                  'blockNumber': '0x5395704', 'from': '0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3',
                                  'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'maxFeePerGas': '0x13433f9c89',
                                  'maxPriorityFeePerGas': '0xf894faca3',
                                  'hash': '0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c',
                                  'input': '0x', 'nonce': '0x184f8', 'to': '0x20c170ffcca6fc29fdb906ad22fb88abfee19b58',
                                  'transactionIndex': '0x0', 'value': '0x4324fcf1e695a5', 'type': '0x2',
                                  'accessList': [], 'chainId': '0xfa', 'v': '0x0',
                                  'r': '0x1c06e04d930c798690924894626a7214ecf5be4a2dd4d18be6196ce542fe4579',
                                  's': '0x7c72fb3a4de9c4ce244015d6db776d9466395c0c11dbcfa12022c4ecea9a3713'},
                                 {'blockHash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                                  'blockNumber': '0x5395704', 'from': '0x690e8a53975e7151d1c1ee43019800cf61f79192',
                                  'gas': '0xf4240', 'gasPrice': '0x43c6b5d24', 'maxFeePerGas': '0x43c6b5d24',
                                  'maxPriorityFeePerGas': '0x3b9aca00',
                                  'hash': '0x20eb9f304162ce9443ed014cbc7503b9425cd60e8a39d49dd4577d1fa2899d5a',
                                  'input': '0xb374012b0000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000008222553246736447566b5831386c553058302b42304f484b624f516d46304a54797a6c2f4a4b77784852646b73476246694e67704e737355694f6335394b6f752f4e614e32674b463842536b4379652b7730477178616e78704c4a71794a79582f697771687271743472466d4a757056304165356a315a6a4839416f687a5374784d22000000000000000000000000000000000000000000000000000000000000',
                                  'nonce': '0x809', 'to': '0xc25283b82ba0f230604e37668e6289499057b7fd',
                                  'transactionIndex': '0x1', 'value': '0x0', 'type': '0x2', 'accessList': [],
                                  'chainId': '0xfa', 'v': '0x1',
                                  'r': '0xa7e8c8db20ae03b9ca3eead9216d14d8e0f16ef30a458a03241418c0fc3fa389',
                                  's': '0x199dbea42df738708369e44a7c709fb1ac6868bc6ca7d04e2fd143694e7bcd8d'},
                                 {'blockHash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                                  'blockNumber': '0x5395704', 'from': '0xe7798097e7171b2922bd953180ac8c3bd3421b3b',
                                  'gas': '0xa5ed9', 'gasPrice': '0x44492c1e0',
                                  'hash': '0xda8960d7e47dfee9fe8a567dd10b31d66a2ada07ff6548955ed0e902ce3710e5',
                                  'input': '0xff040000000000000000001dce753d7889a0950e936f8d53e1662f0e2c3a0b813c6bdc0dd10921be370d5312f44cb42ce377bc9b8a0cef1a4c830185e20000000193de8394e0e97e2a997186e6703a6e3636b06ed894fbe860ad699670a2293d194cf1376ef58c014a0185e2000000011f3c8421e230ff1598ae4e78b3a90fd837ab706fe992beab6659bff447893641a378fbbf031c5bd60182b8000000003d6c56f6855b7cc746fb80848755b0a9c37701223fd3a0c85b70754efc07ac9ac0cbbdce664865a60181be00000000',
                                  'nonce': '0x15298', 'to': '0xc3da629c518404860c8893a66ce3bb2e16bea6ec',
                                  'transactionIndex': '0x2', 'value': '0x0', 'type': '0x0', 'v': '0x217',
                                  'r': '0xb949eb6fb58270072dcc88e5d27ac6de7a572301761e9600d95c9c95e694d06b',
                                  's': '0xb587d1529227ba51e2bea181bb46a4a86a96b016588f73253d9d721c2aaffca'}],
                'transactionsRoot': '0x05430c96a6aabf1a3723edb5bcca96c1a4306045d30f00443a6f29a356cd594b', 'uncles': []}}

]

GET_TOKEN_BALANCE_MOCK_RESPONSE: List[Dict] = [
    {
        'status': '1',
        'message': 'OK',
        'result': '2916560'
    }
]


class TestFtmScanExplorerInterface(BaseTestCase):
    explorer = FTMExplorerInterface
    api = FtmScanApi

    def setUp(self):
        self.explorer.block_head_apis = [self.api]
        self.explorer.balance_apis = [self.api]
        self.explorer.token_balance_apis = [self.api]
        self.explorer.address_txs_apis = [self.api]
        self.explorer.block_txs_apis = [self.api]
        self.explorer.tx_details_apis = [self.api]

    def test_get_balances(self):
        self.api.request = Mock(side_effect=GET_BALANCES_MOCK_RESPONSE)

        balances = self.explorer().get_balances(
            [
                '0xc9bB715E2538A08aC7418A79E808B22f78415620',
                '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F'
            ]
        )

        expected_results = [
            {
                Currencies.ftm: {
                    'address': '0xc9bB715E2538A08aC7418A79E808B22f78415620',
                    'amount': Decimal('5.491731466303367276'),
                    'symbol': 'FTM'
                }
            },
            {
                Currencies.ftm: {
                    'address': '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F',
                    'amount': Decimal('23.776584000000000000'),
                    'symbol': 'FTM'
                }
            }
        ]
        self.assertListEqual(balances, expected_results)

    def test_get_txs_details(self):
        self.api.request = Mock(side_effect=GET_TX_DETAILS_MOCK_RESPONSE)

        tx_hash = '0x9c38c7e6c2dd73d605126aa011f23e52558d422ad3dc6945296feee26443f99e'

        tx_detail = self.explorer().get_tx_details(tx_hash)

        expected = {
            'hash': tx_hash,
            'success': True,
            'inputs': [],
            'outputs': [],
            'memo': None,
            'date': None,
            'raw': None,
            'block': 87097837,
            'fees': None,
            'confirmations': 538134,
            'transfers': [
                {
                    'type': 'MainCoin',
                    'symbol': 'FTM',
                    'currency': Currencies.ftm,
                    'from': '0x2ddd6ed11400a8a1d5c4184589d9b903b1311fd8',
                    'to': '0xf45f0c3573c8b704bbb50fce53b4024a706d43c0',
                    'value': Decimal('0.015526551009239029'),
                    'is_valid': True,
                    'token': None,
                    'memo': None
                }
            ]
        }
        self.assertDictEqual(tx_detail, expected)

    def test_get_latest_block(self):
        self.api.request = Mock(side_effect=GET_BLOCK_ADDRESSES_MOCK_RESPONSE)
        cache.delete('latest_block_height_processed_ftm')

        latest_blocks = self.explorer().get_latest_block(include_info=True, include_inputs=True)

        expected = (
            {
                'input_addresses': {
                    '0x677ccc389a28b17043e5d21b2cb3d2ec40d4e9ee',
                    '0x6e8a80e35c3840913b517bc4a02028831d04df96',
                    '0x1098db74b3cc07a78e25756765d91625773c2a04',
                    '0x1cbd230943dbb0276e337a9f2ccf05610d1c4dee',
                    '0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3',
                    '0x34b0105cd7009edaa488ee31590204347ba0764f'
                },
                'output_addresses': {
                    '0xf89d7b9c864f589bbf53a82105107622b35eaa40',
                    '0xc7abcd945a93bb082306fe94f67105d703c6a1d0',
                    '0x20c170ffcca6fc29fdb906ad22fb88abfee19b58',
                    '0xfa4df55bbe69a76bfa17881f3a6132ffc69e43b7',
                    '0xf87f57dcd8a97a5d40a008224855371e2cba6fe4'
                }
            },
            {
                'incoming_txs': {
                    "0x20c170ffcca6fc29fdb906ad22fb88abfee19b58": {
                        75: [
                            {
                                "tx_hash": "0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc",
                                "value": Decimal("0.012471021032314616"),
                                "contract_address": None,
                                "symbol": 'FTM',
                                "block_height": 87643912
                            }
                            , {
                                "tx_hash": "0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c",
                                "value": Decimal("0.018899492248393125"),
                                "contract_address": None,
                                "symbol": 'FTM',
                                "block_height": 87643908
                            }
                        ]
                    },
                    "0xfa4df55bbe69a76bfa17881f3a6132ffc69e43b7": {
                        75: [{
                            "tx_hash": "0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7",
                            "value": Decimal("0.012631702270766567"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643909
                        }]
                    },
                    "0xf87f57dcd8a97a5d40a008224855371e2cba6fe4": {
                        75: [{
                            "tx_hash": "0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a",
                            "value": Decimal("0.015089622536453009"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643911
                        }]
                    },
                    "0xf89d7b9c864f589bbf53a82105107622b35eaa40": {
                        75: [{
                            "tx_hash": "0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274",
                            "value": Decimal("274.008108876175106042"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643911
                        }]
                    },
                    "0xc7abcd945a93bb082306fe94f67105d703c6a1d0": {
                        75: [{
                            "tx_hash": "0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98",
                            "value": Decimal("0.003000000000000000"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643910
                        }]
                    },
                },
                'outgoing_txs': {
                    "0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3": {
                        75: [{
                            "tx_hash": "0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c",
                            "value": Decimal("0.018899492248393125"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643908
                        }]
                    },
                    "0x1cbd230943dbb0276e337a9f2ccf05610d1c4dee": {
                        75: [{
                            "tx_hash": "0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7",
                            "value": Decimal("0.012631702270766567"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643909
                        }]
                    },
                    "0x677ccc389a28b17043e5d21b2cb3d2ec40d4e9ee": {
                        75: [
                            {
                                "tx_hash": "0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a",
                                "value": Decimal("0.015089622536453009"),
                                "contract_address": None,
                                "symbol": 'FTM',
                                "block_height": 87643911
                            }
                        ]

                    },
                    "0x1098db74b3cc07a78e25756765d91625773c2a04": {
                        75: [{
                            "tx_hash": "0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274",
                            "value": Decimal("274.008108876175106042"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643911
                        }]
                    },
                    "0x6e8a80e35c3840913b517bc4a02028831d04df96": {
                        75: [{
                            "tx_hash": "0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98",
                            "value": Decimal("0.003000000000000000"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643910
                        }]
                    }, "0x34b0105cd7009edaa488ee31590204347ba0764f": {
                        75: [{
                            "tx_hash": "0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc",
                            "value": Decimal("0.012471021032314616"),
                            "contract_address": None,
                            "symbol": 'FTM',
                            "block_height": 87643912
                        }]
                    }
                }
            },
            87643912
        )
        self.maxDiff = None
        self.assertTupleEqual(latest_blocks, expected)

    def test_get_txs(self):
        self.api.request = Mock(side_effect=GET_TXS_MOCK_RESPONSE)

        address = '0xa3472370b9312f757f714972e8d1d8a75f4ad999'

        transactions = self.explorer().get_txs(address)

        expected_transactions = [
            {
                Currencies.ftm: {
                    'block': 87635177,
                    'date': datetime.fromtimestamp(timestamp=1722666080, tz=pytz.utc),
                    'hash': '0x428a6e267704eb0c8f03478348e08c9347e69986cadeb0058d5b3357d7ce85e5',
                    'from_address': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                    'to_address': address,
                    'address': address,
                    'amount': Decimal('0.012364781633033800'),
                    'confirmations': 0,
                    'direction': 'incoming',
                    'raw': None,
                    'memo': None
                },
            },
            {
                Currencies.ftm: {
                    'block': 87635167,
                    'date': datetime.fromtimestamp(1722666152, tz=pytz.utc),
                    'hash': '0x0986dcc4487aa89e164a836723d7b8a9e7082dc315c4ec3173dcec5d1cbadabd',
                    'from_address': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                    'to_address': '0xa3472370b9312f757f714972e8d1d8a75f4ad999',
                    'address': '0xa3472370b9312f757f714972e8d1d8a75f4ad999',
                    'amount': Decimal('0.014767646064306940'),
                    'confirmations': 92,
                    'direction': 'incoming',
                    'raw': None,
                    'memo': None
                }
            }
        ]

        self.assertListEqual(transactions, expected_transactions)

    def test_get_txs_returnsEmpty_onTxreceiptStatusNot1(self):
        self.api.request = Mock(side_effect=GET_TXS_TXRECEIPT_STATUS_ZERO_MOCK_RESPONSE)

        transactions = self.explorer().get_txs('0xa3472370b9312f757f714972e8d1d8a75f4ad999')

        self.assertListEqual(transactions, [])

    def test_get_txs_returnsEmpty_onIsErrorNot0(self):
        self.api.request = Mock(side_effect=GET_TXS_IS_ERROR_ONE_MOCK_RESPONSE)

        transactions = self.explorer().get_txs('0xa3472370b9312f757f714972e8d1d8a75f4ad999')

        self.assertListEqual(transactions, [])

    def test_get_token_balance(self):
        self.api.request = Mock(side_effect=GET_TOKEN_BALANCE_MOCK_RESPONSE)

        address = '0x000052fca55e63AaD9b0d243E5B6a9fEc9b55ff7'

        contract_info = opera_ftm_contract_info['mainnet'][Currencies.btc]

        result = self.explorer().get_token_balance(address, {
            Currencies.btc: contract_info
        })

        expected_result = {
            'address': address,
            'amount': Decimal('0.02916560'),
            'symbol': contract_info.get('symbol')
        }

        self.assertDictEqual(expected_result, result)


@pytest.mark.slow
class TestFtmScanApi(BaseTestCase):
    api = FtmScanApi

    def test_get_tx_details(self):
        tx_hashes = [
            '0xd03d77f46daf6444c3fbae969ba04fbcc89e7020b0db70d15e089382e0e21d0b',  # failed
            '0xc543de94f561676c5156d5eef5b728bc4219d91377ee290a76b0f26a0709a2bb',  # call
            '0x0efc43ddb035d01a86f31768aa2083d73fe68a2c845c40384c47999f4e68a3a5'  # transfer
        ]

        transaction_schema = {
            'from': str,
            'to': str,
            'value': str,
            'blockHash': str,
            'hash': str,
            'gas': str,
            'gasPrice': str,
            'input': str,
            'blockNumber': str
        }

        for tx_hash in tx_hashes:
            transfer = self.api.get_tx_details(tx_hash)
            self.assert_schema(transfer['result'], transaction_schema)

    def test_balance_apis(self):
        addresses = [
            '0xc9bB715E2538A08aC7418A79E808B22f78415620',
            '0x2aa07920E4ecb4ea8C801D9DFEce63875623B285',
            '0x000052fca55e63AaD9b0d243E5B6a9fEc9b55ff7',
            '0x0E8cB96CCF9EaE036920b97c5b173710D58C7603',
            '0x94d72461E0d4068f66dda040d0FdDa9b08Cbe0D6'
        ]
        for address in addresses:
            balance = self.api.get_balance(address)['result']
            self.assertIsInstance(balance, str)

    def test_address_txs_apis(self):
        addresses = [
            '0xc4b6efc7ff43ed44576ae53b3d8f1049fc827da9',
            '0x5023882f4d1ec10544fcb2066abe9c1645e95aa0',
            '0xbde27646d338950fdbc35f9f6ef9222b33417ab0',
            '0x054a86e440fe06f185cfeefc5d5dfcefc554bdfb'
        ]
        transaction_schema = {
            'value': str,
            'contractAddress': str,
            'blockNumber': str,
            'blockHash': str,
            'hash': str,
            'confirmations': str,
            'from': str,
            'to': str,
            'timeStamp': str,
            'gas': str,
            'gasPrice': str
        }

        for address in addresses:
            transactions = self.api.get_address_txs(address)['result']
            for transaction in transactions:
                self.assert_schema(transaction, transaction_schema)

    def test_block_txs_apis(self):
        blocks = [
            87304308,
            87304535,
            87304549,
            87304464
        ]
        transaction_schema = {
            'from': str,
            'to': str,
            'value': str,
            'blockHash': str,
            'hash': str,
            'gas': str,
            'gasPrice': str,
            'input': str,
            'blockNumber': str
        }
        for block in blocks:
            transactions = self.api.get_block_txs(block)
            for transaction in transactions['result']['transactions']:
                self.assert_schema(transaction, transaction_schema)

    def test_block_head(self):
        response = self.api.get_block_head()
        self.assertIsInstance(int(response['result'], 0), int)

    def test_token_balance_apis(self):
        addresses = [
            '0x27884C7647DeB61c9F2b9202D1141BB84661756b',  # only contains aave
            '0x31c798ac8159568d44c7f0c8678bf6fdc4caf57c'  # have all tokens except aave
        ]
        schema = {
            'status': str,
            'message': str,
            'result': str
        }
        for contract_info in opera_ftm_contract_info['mainnet'].values():
            for address in addresses:
                result = self.api.get_token_balance(address, contract_info)
                self.assert_schema(result, schema)

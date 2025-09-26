from decimal import Decimal
from typing import List, Dict
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from hexbytes import HexBytes

from exchange.blockchain.api.ftm.ftm_explorer_interface import FTMExplorerInterface
from exchange.blockchain.api.ftm.ftm_web3_new import FtmWeb3Api
from exchange.blockchain.contracts_conf import opera_ftm_contract_info
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

GET_BALANCES_MOCK_RESPONSE: List[int] = [
    5022473244824303012
]

GET_HEAD_MOCK_RESPONSE = [
    87974389
]

GET_TX_RECEIPT_MOCK_RESPONSE: List[Dict] = [
    {
        'blockHash': HexBytes('0x00048ba9000035aa7db1f5158502fdfecad1f38295784ab3238ebe49221c949c'),
        'blockNumber': 87974386,
        'contractAddress': None,
        'cumulativeGasUsed': 21000,
        'effectiveGasPrice': 22462310145,
        'from': '0xA0af34f0F8d8B9088A36c265b4A5c82c8274CbB3',
        'gasUsed': 21000,
        'logs': [],
        'logsBloom': HexBytes(
            '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
        'status': 1,
        'to': '0x2f2F315F8a6E9F4eb612e88381CF544C93A8565c',
        'transactionHash': HexBytes('0x6254ff971d8350d25ade62a93d0ebfffd24aee6ac57d9cdad961cc6ba8d09aef'),
        'transactionIndex': 0,
        'type': '0x2'
    }
]

GET_TX_RECEIPT_STATUS_ZERO_MOCK_RESPONSE: List[Dict] = [
    {
        'status': 0,
    }
]

GET_TX_DETAILS_MOCK_RESPONSE: List[Dict] = [
    {
        'blockHash': HexBytes('0x00048ba9000035aa7db1f5158502fdfecad1f38295784ab3238ebe49221c949c'),
        'blockNumber': 87974386,
        'from': '0xA0af34f0F8d8B9088A36c265b4A5c82c8274CbB3',
        'gas': 21000,
        'gasPrice': 22462310145,
        'maxFeePerGas': 27954376599,
        'maxPriorityFeePerGas': 494044329,
        'hash': HexBytes('0x6254ff971d8350d25ade62a93d0ebfffd24aee6ac57d9cdad961cc6ba8d09aef'),
        'input': HexBytes('0x'),
        'nonce': 108824,
        'to': '0x2f2F315F8a6E9F4eb612e88381CF544C93A8565c',
        'transactionIndex': 0,
        'value': 19313419505646418,
        'type': '0x2',
        'accessList': [],
        'chainId': '0xfa',
        'v': 0,
        'r': HexBytes('0x292138421a7f3eabfe49e0c9cadf061355586d18e0066e0bd892bcc15673ef11'),
        's': HexBytes('0x4a56904ba0516943dc61d7bd7ba27c3fcb31bc5d886dc5a5c90c7b7a9ff10b97')
    }
]

GET_TX_DETAILS_NEGATIVE_VALUE_MOCK_RESPONSE: List[Dict] = [
    {
        'input': HexBytes('0x'),
        'value': -19313419505646418,
    }
]

GET_TX_DETAILS_INVALID_INPUT_MOCK_RESPONSE: List[Dict] = [
    {
        'input': HexBytes('0x8371')
    }
]

GET_LATEST_BLOCK_MOCK_RESPONSE: List[Dict] = [
    {'baseFeePerGas': 17193538340, 'difficulty': 0, 'epoch': '0x48961', 'extraData': HexBytes('0x'),
     'gasLimit': 281474976710655, 'gasUsed': 422781,
     'hash': HexBytes('0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff'), 'logsBloom': HexBytes(
        '0x00100008000000000000000000000000040000000000040004020000000000000000000000000080002000000000040000000000000000000004000000000000000000000000000000000008000040000000000000001000000000000000000010000000060400000000000000000800000000000000000010000010000000000001000000000800000000000000080000000000000000000000000000800480400000002000000000000000009000000000000000000400000000000000000000000002000000001000000000000000010000000100000000400000040020800000000000000000000040000000010000000000800040000000000000100000'),
     'miner': '0x0000000000000000000000000000000000000000',
     'mixHash': HexBytes('0x0000000000000000000000000000000000000000000000000000000000000000'),
     'nonce': HexBytes('0x0000000000000000'), 'number': 87643912,
     'parentHash': HexBytes('0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640'),
     'receiptsRoot': HexBytes('0x96ec45cb0b09622a11ed00077e422887c7f7052f2599da17861a3dd620544986'),
     'sha3Uncles': HexBytes('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'), 'size': 1220,
     'stateRoot': HexBytes('0xee9c760edc829278e90eebbe260dfcb5dcc4467ddb124390265b3eb0878200b6'),
     'timestamp': 1722672887, 'timestampNano': '0x17e829dd37c76907', 'totalDifficulty': 0, 'transactions': [
        {'blockHash': HexBytes('0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff'),
         'blockNumber': 87643912, 'from': '0x055F72aB5Db7C3c14233599DdeC34Bb3A5C88Eb6', 'gas': 1000000,
         'gasPrice': 19276058075, 'maxFeePerGas': 19276058075, 'maxPriorityFeePerGas': 2082519735,
         'hash': HexBytes('0x4ddddfe03fd6caf25d5dd6049138a4c3c620c8a03cca21860fc9097416a3d0a2'),
         'input': HexBytes('0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000fa0000000000000000000000000dfd9b9b25cef61033ca680526722c8335281b8c00000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000cc19abe2f12c8315be0cf00114c96e10e9e44f6200000000000000000000000000000000000000000000000000000000000001470000000000000000000000000000000000000000000000000000000066ade7ab0000000000000000000000000000000000000000000000000000000000000084bc78570100000000000000000000000065be4f5e6dc20b008593437e6aa8238a79f0664600000000000000000000000000000000000000000000000000000000000078ad000000000000000000000000f5a543bba6b6655a0025fe849612951cb63caad600000000000000000000000000000000000000000000000000000000000007fb00000000000000000000000000000000000000000000000000000000'),
         'nonce': 87, 'to': '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F', 'transactionIndex': 0, 'value': 0,
         'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0x7e10bfa6ac01c9bf30f805e8ad3509e3fdff457dd466e912354b1ea7f5e2f644'),
         's': HexBytes('0x59bed03c2d2345875a0871e6af4d0f1c44d21944cb276d09cd2337899507075b')},
        {'blockHash': HexBytes('0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff'),
         'blockNumber': 87643912, 'from': '0x34b0105CD7009eDAa488Ee31590204347bA0764F', 'gas': 21000,
         'gasPrice': 82732620937, 'maxFeePerGas': 82732620937, 'maxPriorityFeePerGas': 66728209571,
         'hash': HexBytes('0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc'), 'input': HexBytes('0x'),
         'nonce': 80759, 'to': '0x20c170fFcCa6fc29fDB906Ad22fb88AbfEe19B58', 'transactionIndex': 1,
         'value': 12471021032314616, 'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0xd107e6f693de7ff0b0093318b3562987d163e4fe3d5457cb028a14763b8ec26e'),
         's': HexBytes('0x3ab79396eabbc1c5a5818677ffaa75d993753f47de9cc7ecb8a6e277c1894445')}],
     'transactionsRoot': HexBytes('0x4fcc8b9b2633d5527c038ff5c19083ea851518868caca8e8ff7752aef7e0fe3d'), 'uncles': []},
    {'baseFeePerGas': 17193538340, 'difficulty': 0, 'epoch': '0x48961', 'extraData': HexBytes('0x'),
     'gasLimit': 281474976710655, 'gasUsed': 952169,
     'hash': HexBytes('0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640'), 'logsBloom': HexBytes(
        '0x00000008000000000000000000000000040000020000020400000000000000000000000400000000000000000000000000000000000000010000000000000000000000000800000000000000000040000000000000004000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000040000000000000000000000000000000000008000000000000008100200000000000000000000000000000000000000000000000000010008000000000000000020000000000000000000000000000000000000000000000000800000080000000000000000'),
     'miner': '0x0000000000000000000000000000000000000000',
     'mixHash': HexBytes('0x0000000000000000000000000000000000000000000000000000000000000000'),
     'nonce': HexBytes('0x0000000000000000'), 'number': 87643911,
     'parentHash': HexBytes('0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0'),
     'receiptsRoot': HexBytes('0xc0bb7ad1465ca3b693dbc279fd25c5d77eeffd7cea465d2a07adead3f902a2f6'),
     'sha3Uncles': HexBytes('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'), 'size': 1557,
     'stateRoot': HexBytes('0x17e09f6ce3dbff221de93831f42dca843adb95339aab920e96f94d439d9db148'),
     'timestamp': 1722672886, 'timestampNano': '0x17e829dd0d29222b', 'totalDifficulty': 0, 'transactions': [
        {'blockHash': HexBytes('0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640'),
         'blockNumber': 87643911, 'from': '0x677Ccc389A28B17043E5D21b2cb3d2ec40D4E9EE', 'gas': 21000,
         'gasPrice': 82732620937, 'maxFeePerGas': 82732620937, 'maxPriorityFeePerGas': 66728209571,
         'hash': HexBytes('0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a'), 'input': HexBytes('0x'),
         'nonce': 84238, 'to': '0xf87f57dcd8a97A5d40a008224855371E2cbA6fe4', 'transactionIndex': 0,
         'value': 15089622536453009, 'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0x0146759c04421dec411dc02d54a880d4e3366230b4d70477f4f3fb699e1925cd'),
         's': HexBytes('0x745e148d6c268422377e23ce9b23f28383b2063fdad54723a3130d6c96eeb385')},
        {'blockHash': HexBytes('0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640'),
         'blockNumber': 87643911, 'from': '0x1098DB74b3CC07a78e25756765d91625773c2a04', 'gas': 21000,
         'gasPrice': 300000000000,
         'hash': HexBytes('0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274'), 'input': HexBytes('0x'),
         'nonce': 0, 'to': '0xf89d7b9c864f589bbF53a82105107622B35EaA40', 'transactionIndex': 1,
         'value': 274008108876175106042, 'type': '0x0', 'v': 536,
         'r': HexBytes('0x95299d15c1e4066e452f6bb3550a9926aaefd1b1e7d194dd7c6c5c7eb2782013'),
         's': HexBytes('0x4c57cfed91e74e1935126d2045559cde173ca321d46a70226aa9c61de1069520')},
        {'blockHash': HexBytes('0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640'),
         'blockNumber': 87643911, 'from': '0x5F9Ed9db4D8f6ba2FD2A65497097d85160ebDc40', 'gas': 3500000,
         'gasPrice': 18193538340, 'maxFeePerGas': 18193538340, 'maxPriorityFeePerGas': 1000000000,
         'hash': HexBytes('0xc8518d8eafc9a4e9ef4e667f7507ba91b161ae97afc725d695cecbc2698ca144'),
         'input': HexBytes('0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000fa00000000000000000000000089e8fa64d576d84e0143af9ee9c94f759f1ef75900000000000000000000000000000000000000000000000000000000000000c00000000000000000000000008c2e12b7f08265cf1555c7cd886de84fea6a4c8100000000000000000000000000000000000000000000000000000000000000360000000000000000000000000000000000000000000000000000000066ade793000000000000000000000000000000000000000000000000000000000000016438430cce00000000000000000000000000000000000000000000000000000000000193c500000000000000000000000000000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a000000000000000000000000000000000000000000000000000000000000000c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
         'nonce': 5, 'to': '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F', 'transactionIndex': 2, 'value': 0,
         'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0x5cc957c4852f35c951e2f60fc0759b9306ee00f4f8d169a7a7d946e7a8d45ef4'),
         's': HexBytes('0x23b9c591650c36bba8a4a2647f4fd9cf78fe6320fbf08db2ae72a06b56383bff')}],
     'transactionsRoot': HexBytes('0xcf3353b0d8a96157d24b060b5859ca185eb071c9e859809e465b54ea5d748b94'), 'uncles': []},
    {'baseFeePerGas': 17193538340, 'difficulty': 0, 'epoch': '0x48961', 'extraData': HexBytes('0x'),
     'gasLimit': 281474976710655, 'gasUsed': 461970,
     'hash': HexBytes('0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0'), 'logsBloom': HexBytes(
        '0x00100008200000000000000000000000040000000000040004020000000000000000800000000080002000000000040000000000000000000004000000000004000000000000000000000008000040000000000200001000010000000000000010000000060400040000000000000800000000000000000010000010000000000001000100000800000000000000080040000000000000000000000000800000000000002000000000000000009000000000000000000400000000000000000000000002000010000000000000000000000000000000000000000000040020000000000000000000000040000000010000000000800000000000000000100000'),
     'miner': '0x0000000000000000000000000000000000000000',
     'mixHash': HexBytes('0x0000000000000000000000000000000000000000000000000000000000000000'),
     'nonce': HexBytes('0x0000000000000000'), 'number': 87643910,
     'parentHash': HexBytes('0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39'),
     'receiptsRoot': HexBytes('0xeb51278b8b81ea03307b15e3f64af6330b183935cd2f6ab11e4c6c0d1368e455'),
     'sha3Uncles': HexBytes('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'), 'size': 1222,
     'stateRoot': HexBytes('0x11db95d38ab5eb794de7cd902099be433d8c058807a44379a64018110a73a00a'),
     'timestamp': 1722672886, 'timestampNano': '0x17e829dce32630b1', 'totalDifficulty': 0, 'transactions': [
        {'blockHash': HexBytes('0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0'),
         'blockNumber': 87643910, 'from': '0x5275DFfb00bBd7Cf7Ac43FeE3F95A4a58871e60b', 'gas': 1000000,
         'gasPrice': 19514738228, 'maxFeePerGas': 19514738228, 'maxPriorityFeePerGas': 2321199888,
         'hash': HexBytes('0x7bb5b235e5fca2a08652825a4133cc5a63bafde98e08c58880b87e43e0198388'),
         'input': HexBytes('0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000fa0000000000000000000000000dfd9b9b25cef61033ca680526722c8335281b8c00000000000000000000000000000000000000000000000000000000000000c00000000000000000000000001b8ee43b1ef423a452d878c97b3f2018e40211e90000000000000000000000000000000000000000000000000000000000003ed10000000000000000000000000000000000000000000000000000000066ade7a90000000000000000000000000000000000000000000000000000000000000084bc785701000000000000000000000000b509d72dad8d9ebe76d660ed49fea2e46dcf96730000000000000000000000000000000000000000000000000000000000001915000000000000000000000000e44ff9dd9c8a9737d7ab4ed3e7b1e226430ad7fd000000000000000000000000000000000000000000000000000000000000037e00000000000000000000000000000000000000000000000000000000'),
         'nonce': 1120, 'to': '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F', 'transactionIndex': 0, 'value': 0,
         'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 0,
         'r': HexBytes('0x7e5def16598a4e014a6ca47c8373a7d58be63683d1f0dc2dfa77af2442b659b8'),
         's': HexBytes('0x33daa7322e799ecd2be1d04dd272e4f793644749834991f2116f7463d2abc060')},
        {'blockHash': HexBytes('0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0'),
         'blockNumber': 87643910, 'from': '0x6E8a80e35C3840913B517Bc4a02028831d04dF96', 'gas': 21000,
         'gasPrice': 60000000000, 'maxFeePerGas': 60000000000, 'maxPriorityFeePerGas': 60000000000,
         'hash': HexBytes('0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98'), 'input': HexBytes('0x'),
         'nonce': 196077, 'to': '0xc7aBCD945a93bb082306Fe94F67105D703C6A1D0', 'transactionIndex': 1,
         'value': 3000000000000000, 'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0xd8297ae302706a534fdac07d511edf837017ff1cc1609a5621fc869957598a73'),
         's': HexBytes('0x660f52fbaa50b617ab425a146e5961c4d8ac3c4a014cca5f50ee66dbde642c22')}],
     'transactionsRoot': HexBytes('0x1f8809edd81a3f2f6c63d8fa94fdd03bb80c95219d3a4cf5e9bac3e43e2c8678'), 'uncles': []},
    {'baseFeePerGas': 17193538340, 'difficulty': 0, 'epoch': '0x48961', 'extraData': HexBytes('0x'),
     'gasLimit': 281474976710655, 'gasUsed': 3794609,
     'hash': HexBytes('0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39'), 'logsBloom': HexBytes(
        '0x0000000400000100080000002000000000000020000000000000000000000000000000000000000001000000000c000000000000000000000000800000000008000002000000000000000004000040200000000000000000000042000000000000000000020000010020000040080800000200000824000000000000080000000000000000000000000000000040100000000008000202000800000200000000000000000000000100000000400800000000000000000000000200000200000000000000000008010000000010000000000400000000000000001240000020000000000000000000000000800000000000000000000000004020020102000000'),
     'miner': '0x0000000000000000000000000000000000000000',
     'mixHash': HexBytes('0x0000000000000000000000000000000000000000000000000000000000000000'),
     'nonce': HexBytes('0x0000000000000000'), 'number': 87643909,
     'parentHash': HexBytes('0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb'),
     'receiptsRoot': HexBytes('0xa6bcfc5cd5cb225aafbf768e3b24825f983fbd0a9ed025b16314c9ddf5be6cdd'),
     'sha3Uncles': HexBytes('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'), 'size': 1766,
     'stateRoot': HexBytes('0x081721a07e36f8f507d4fab5ea9cfe05344127fef3e13cd11cdcbc7dce3ed53b'),
     'timestamp': 1722672885, 'timestampNano': '0x17e829dcb84d1520', 'totalDifficulty': 0, 'transactions': [
        {'blockHash': HexBytes('0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39'),
         'blockNumber': 87643909, 'from': '0x1cBd230943Dbb0276E337a9F2cCf05610d1C4DeE', 'gas': 21000,
         'gasPrice': 82732620937, 'maxFeePerGas': 82732620937, 'maxPriorityFeePerGas': 66728209571,
         'hash': HexBytes('0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7'), 'input': HexBytes('0x'),
         'nonce': 85553, 'to': '0xFA4DF55bBE69A76bFa17881F3a6132FFC69E43B7', 'transactionIndex': 0,
         'value': 12631702270766567, 'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 0,
         'r': HexBytes('0x5eb9056c5ee8b2f8949f422bd2b45eb0703fc00a12e7f1e10481119c906c4e74'),
         's': HexBytes('0x5bd8de82a6cea5daa6fca935159c08eafcca1d59a565b4b37dd6bad3105a06c6')},
        {'blockHash': HexBytes('0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39'),
         'blockNumber': 87643909, 'from': '0x68aeDee7DC9da33A1E7D32a6637361E409c40519', 'gas': 3950259,
         'gasPrice': 18693538340, 'maxFeePerGas': 24711276759, 'maxPriorityFeePerGas': 1500000000,
         'hash': HexBytes('0x07d8032650fe597f704003ecbd9590337866b6f75ef9c9716a862f03befc3c99'),
         'input': HexBytes('0xac9650d80000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000000700000000000000000000000000000000000000000000000000000000000000e0000000000000000000000000000000000000000000000000000000000000014000000000000000000000000000000000000000000000000000000000000001a00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000026000000000000000000000000000000000000000000000000000000000000002c00000000000000000000000000000000000000000000000000000000000000320000000000000000000000000000000000000000000000000000000000000002485478c7f0000000000000000000000009777ce91bbcbff048b2d107dde29a58faa3bc78100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000e9e72c4eb0ac0170432f03cdf7e9aada2718143b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000082125d3afd871a3a91d8975c80efb9701fec19800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000e90ec537fab7f055f6895b73038c15644a3f511c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000aea03e59fe34f21087c89bfd9cdd1e4bc17b839100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f000000000000000000000000b5326a3f975d5f0f2305c4f4c0328478ef4de7b300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002485478c7f0000000000000000000000007790a63ea9bf3281822021fcf70a7bf4d460820300000000000000000000000000000000000000000000000000000000'),
         'nonce': 5039, 'to': '0xF9A66F8C569D23f1fA1A63950c3CA822Cf26355e', 'transactionIndex': 1, 'value': 0,
         'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0x20dcddb47791b1e141fe9a674fcd0132011bb4b94304147ab695e9750e5ec650'),
         's': HexBytes('0x551266aa3b049c9770c11394d7705b4968fbb149adb1e1a504242a2e73cbcf65')}],
     'transactionsRoot': HexBytes('0x14e7b31b6fe831b3ad43b36fc5faa49fcbec32f2240e733d37bc032005d715cb'), 'uncles': []},
    {'baseFeePerGas': 17193538340, 'difficulty': 0, 'epoch': '0x48961', 'extraData': HexBytes('0x'),
     'gasLimit': 281474976710655, 'gasUsed': 417070,
     'hash': HexBytes('0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb'), 'logsBloom': HexBytes(
        '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
     'miner': '0x0000000000000000000000000000000000000000',
     'mixHash': HexBytes('0x0000000000000000000000000000000000000000000000000000000000000000'),
     'nonce': HexBytes('0x0000000000000000'), 'number': 87643908,
     'parentHash': HexBytes('0x0004896100000cc0c2bf713ce57d59eaf06da7fd7f70b9f85d73b72b65e17274'),
     'receiptsRoot': HexBytes('0xa6fa45835234e4de6b20acd26644ae3c17be4edbdc8b01a0f94ce7a6124ceeb7'),
     'sha3Uncles': HexBytes('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'), 'size': 1345,
     'stateRoot': HexBytes('0x59d21743e0de76dd91840e45934fadc84d8655eb09199f9ec041117101fc8ca8'),
     'timestamp': 1722672885, 'timestampNano': '0x17e829dca1316a0d', 'totalDifficulty': 0, 'transactions': [
        {'blockHash': HexBytes('0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb'),
         'blockNumber': 87643908, 'from': '0xA0af34f0F8d8B9088A36c265b4A5c82c8274CbB3', 'gas': 21000,
         'gasPrice': 82732620937, 'maxFeePerGas': 82732620937, 'maxPriorityFeePerGas': 66728209571,
         'hash': HexBytes('0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c'), 'input': HexBytes('0x'),
         'nonce': 99576, 'to': '0x20c170fFcCa6fc29fDB906Ad22fb88AbfEe19B58', 'transactionIndex': 0,
         'value': 18899492248393125, 'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 0,
         'r': HexBytes('0x1c06e04d930c798690924894626a7214ecf5be4a2dd4d18be6196ce542fe4579'),
         's': HexBytes('0x7c72fb3a4de9c4ce244015d6db776d9466395c0c11dbcfa12022c4ecea9a3713')},
        {'blockHash': HexBytes('0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb'),
         'blockNumber': 87643908, 'from': '0x690e8a53975e7151D1C1eE43019800CF61f79192', 'gas': 1000000,
         'gasPrice': 18193538340, 'maxFeePerGas': 18193538340, 'maxPriorityFeePerGas': 1000000000,
         'hash': HexBytes('0x20eb9f304162ce9443ed014cbc7503b9425cd60e8a39d49dd4577d1fa2899d5a'),
         'input': HexBytes('0xb374012b0000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000008222553246736447566b5831386c553058302b42304f484b624f516d46304a54797a6c2f4a4b77784852646b73476246694e67704e737355694f6335394b6f752f4e614e32674b463842536b4379652b7730477178616e78704c4a71794a79582f697771687271743472466d4a757056304165356a315a6a4839416f687a5374784d22000000000000000000000000000000000000000000000000000000000000'),
         'nonce': 2057, 'to': '0xC25283b82bA0f230604E37668E6289499057b7fd', 'transactionIndex': 1, 'value': 0,
         'type': '0x2', 'accessList': [], 'chainId': '0xfa', 'v': 1,
         'r': HexBytes('0xa7e8c8db20ae03b9ca3eead9216d14d8e0f16ef30a458a03241418c0fc3fa389'),
         's': HexBytes('0x199dbea42df738708369e44a7c709fb1ac6868bc6ca7d04e2fd143694e7bcd8d')}, {
            'blockHash': HexBytes('0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb'),
            'blockNumber': 87643908, 'from': '0xE7798097E7171b2922Bd953180Ac8C3BD3421b3B', 'gas': 679641,
            'gasPrice': 18330337760,
            'hash': HexBytes('0xda8960d7e47dfee9fe8a567dd10b31d66a2ada07ff6548955ed0e902ce3710e5'),
            'input': HexBytes('0xff040000000000000000001dce753d7889a0950e936f8d53e1662f0e2c3a0b813c6bdc0dd10921be370d5312f44cb42ce377bc9b8a0cef1a4c830185e20000000193de8394e0e97e2a997186e6703a6e3636b06ed894fbe860ad699670a2293d194cf1376ef58c014a0185e2000000011f3c8421e230ff1598ae4e78b3a90fd837ab706fe992beab6659bff447893641a378fbbf031c5bd60182b8000000003d6c56f6855b7cc746fb80848755b0a9c37701223fd3a0c85b70754efc07ac9ac0cbbdce664865a60181be00000000'),
            'nonce': 86680, 'to': '0xc3DA629c518404860c8893a66cE3Bb2e16bea6eC', 'transactionIndex': 2, 'value': 0,
            'type': '0x0', 'v': 535,
            'r': HexBytes('0xb949eb6fb58270072dcc88e5d27ac6de7a572301761e9600d95c9c95e694d06b'),
            's': HexBytes(
                '0x0b587d1529227ba51e2bea181bb46a4a86a96b016588f73253d9d721c2aaffca')}], 'transactionsRoot': HexBytes(
        '0x05430c96a6aabf1a3723edb5bcca96c1a4306045d30f00443a6f29a356cd594b'), 'uncles': []},

]

GET_TOKEN_BALANCE_MOCK_RESPONSE: List[int] = [
    2916562738420
]


class TestFTMWeb3ExplorerInterface(BaseTestCase):
    explorer = FTMExplorerInterface.get_api()
    api = FtmWeb3Api

    def setUp(self):
        self.explorer.block_head_apis = [self.api]
        self.explorer.balance_apis = [self.api]
        self.explorer.token_balance_apis = [self.api]
        self.explorer.block_txs_apis = [self.api]
        self.explorer.tx_details_apis = [self.api]
        self.maxDiff = None

    def test_get_balances(self):
        self.api.get_balance = Mock(side_effect=GET_BALANCES_MOCK_RESPONSE)

        balance = self.explorer.get_balance('0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3')

        expected_result = {
            Currencies.ftm: {
                'address': '0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3',
                'symbol': 'FTM',
                'amount': Decimal('5.022473244824303012')
            }
        }

        self.assertDictEqual(balance, expected_result)

    def test_tx_details(self):
        self.api.get_block_head = Mock(side_effect=GET_HEAD_MOCK_RESPONSE)
        self.api.get_tx_receipt = Mock(side_effect=GET_TX_RECEIPT_MOCK_RESPONSE)
        self.api.get_tx_details = Mock(side_effect=GET_TX_DETAILS_MOCK_RESPONSE)

        tx_details = self.explorer.get_tx_details('0x00048ba9000035aa7db1f5158502fdfecad1f38295784ab3238ebe49221c949c')

        expected_result = {
            'block': 87974386,
            'confirmations': 3,
            'date': None,
            'fees': None,
            'hash': '0x6254ff971d8350d25ade62a93d0ebfffd24aee6ac57d9cdad961cc6ba8d09aef',
            'inputs': [],
            'memo': None,
            'outputs': [],
            'raw': None,
            'success': True,
            'transfers': [
                {
                    'currency': Currencies.ftm,
                    'value': Decimal('0.019313419505646418'),
                    'symbol': 'FTM',
                    'is_valid': True,
                    'memo': None,
                    'from': '0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3',
                    'to': '0x2f2f315f8a6e9f4eb612e88381cf544c93a8565c',
                    'token': None,
                    'type': 'MainCoin'
                }
            ]
        }

        self.assertDictEqual(tx_details, expected_result)

    def test_tx_details_returnSuccessFalse_onReceiptStatusNot1(self):
        self.api.get_block_head = Mock(side_effect=GET_HEAD_MOCK_RESPONSE)
        self.api.get_tx_receipt = Mock(side_effect=GET_TX_RECEIPT_STATUS_ZERO_MOCK_RESPONSE)

        tx_details = self.explorer.get_tx_details('0x00048ba9000035aa7db1f5158502fdfecad1f38295784ab3238ebe49221c949c')

        expected_result = {
            'success': False
        }

        self.assertDictEqual(tx_details, expected_result)

    def test_tx_details_returnsSuccessFalse_onNegativeValue(self):
        self.api.get_block_head = Mock(side_effect=GET_HEAD_MOCK_RESPONSE)
        self.api.get_tx_receipt = Mock(side_effect=GET_TX_RECEIPT_MOCK_RESPONSE)
        self.api.get_tx_details = Mock(side_effect=GET_TX_DETAILS_NEGATIVE_VALUE_MOCK_RESPONSE)

        tx_details = self.explorer.get_tx_details('0x00048ba9000035aa7db1f5158502fdfecad1f38295784ab3238ebe49221c949c')

        expected_result = {
            'success': False
        }

        self.assertDictEqual(tx_details, expected_result)

    def test_tx_details_returnsSuccessFalse_onInvalidInput(self):
        self.api.get_block_head = Mock(side_effect=GET_HEAD_MOCK_RESPONSE)
        self.api.get_tx_receipt = Mock(side_effect=GET_TX_RECEIPT_MOCK_RESPONSE)
        self.api.get_tx_details = Mock(side_effect=GET_TX_DETAILS_INVALID_INPUT_MOCK_RESPONSE)

        tx_details = self.explorer.get_tx_details('0x00048ba9000035aa7db1f5158502fdfecad1f38295784ab3238ebe49221c949c')

        expected_result = {
            'success': False
        }

        self.assertDictEqual(tx_details, expected_result)

    def test_get_latest_block(self):
        cache.delete('latest_block_height_processed_ftm')

        self.api.get_block_head = Mock(side_effect=[87643912])
        self.api.get_block_txs = Mock(side_effect=GET_LATEST_BLOCK_MOCK_RESPONSE)

        result = self.explorer.get_latest_block(include_inputs=True, include_info=True)

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
            87643900
        )

        self.assertTupleEqual(result, expected)

    def test_get_token_balance(self):
        self.api.get_token_balance = Mock(side_effect=GET_TOKEN_BALANCE_MOCK_RESPONSE)

        contract_info = opera_ftm_contract_info['mainnet'][Currencies.btc]

        result = self.explorer.get_token_balance('0x000052fca55e63AaD9b0d243E5B6a9fEc9b55ff7', {
            Currencies.btc: contract_info
        })

        expected_result = {
            'address': '0x000052fca55e63AaD9b0d243E5B6a9fEc9b55ff7',
            'amount': Decimal('29165.62738420'),
            'symbol': contract_info.get('symbol'),
        }
        self.assertDictEqual(result, expected_result)


@pytest.mark.slow
class TestFtmWeb3Api(BaseTestCase):
    api = FtmWeb3Api.get_instance()

    def test_get_tx_details(self):
        tx_details = self.api.get_tx_details('0x3ffb9142e149de49700bca482b880d703790c59daa2cfe312a47141d8b60ba8d')
        schema = {
            'blockHash': HexBytes,
            'hash': HexBytes,
            'from': str,
            'to': str,
            'value': int,
            'gas': int,
            'gasPrice': int,
            'input': str,
        }
        self.assert_schema(tx_details, schema)

    def test_balance_apis(self):
        balance = self.api.get_balance('0x52ceba41da235af367bfc0b0ccd3314cb901bb5f')
        self.assertIsInstance(balance, int)

    def test_block_txs_apis(self):
        block_txs = self.api.get_block_txs(87976241)

        transaction_schema = {
            'from': str,
            'to': str,
            'value': int,
            'blockHash': HexBytes,
            'hash': HexBytes,
            'gas': int,
            'gasPrice': int,
            'input': str,
            'blockNumber': int
        }

        for transaction in block_txs['transactions']:
            self.assert_schema(transaction, transaction_schema)

    def test_block_head(self):
        head = self.api.get_block_head()
        self.assertIsInstance(head, int)

    def test_token_balance_apis(self):
        for contract_info in opera_ftm_contract_info['mainnet'].values():
            result = self.api.get_token_balance('0x31c798ac8159568d44c7f0c8678bf6fdc4caf57c', contract_info)
            self.assertIsInstance(result, int)

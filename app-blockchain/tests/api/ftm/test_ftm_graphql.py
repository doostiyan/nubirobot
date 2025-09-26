import datetime
import json
from decimal import Decimal
from typing import Dict
from unittest import TestCase
from unittest.mock import Mock

import pytest
import pytz
from django.conf import settings
from django.core.cache import cache

from exchange.blockchain.api.ftm.ftm_explorer_interface import FTMExplorerInterface
from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.api.ftm.ftm_graphql_new import FtmGraphqlApi
from exchange.blockchain.contracts_conf import opera_ftm_contract_info
from exchange.blockchain.staking.staking_models import CoinType, StakingInfo
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

GET_BLOCK_HEAD_MOCK_RESPONSE = {'data': {'block': {'number': '0x5395708'}}}

GET_TXS_MOCK_RESPONSE = {
    'data': {
        'account': {
            'txCount': '0xc',
            'txList': {
                'edges': [
                    {
                        'cursor': '0x25e09bb93fe82f4da832897ad9941333986a1c4e3dffd095ad9475ad99a1d338',
                        'transaction': {
                            'hash': '0x25e09bb93fe82f4da832897ad9941333986a1c4e3dffd095ad9475ad99a1d338',
                            'status': '0x1',
                            'from': '0x86d469ce0ee820f191b0e59e74666a6c3a27bd0e',
                            'to': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                            'gas': '0x5208',
                            'gasPrice': '0x31c9eaa33c',
                            'value': '0xb0d79a87dda45160',
                            'nonce': '0x7',
                            'index': '0x1',
                            'inputData': '0x',
                            'blockNumber': '0x5395707',
                            'block': {
                                'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854fd',
                                'timestamp': '0x66b77c8a'
                            }
                        }
                    },
                    {
                        'cursor': '0x3a9aa4ca05a755937415c3429870329f3cd62a2892a26b60bdb8094e8c3edabe',
                        'transaction': {
                            'hash': '0x3a9aa4ca05a755937415c3429870329f3cd62a2892a26b60bdb8094e8c3edabe',
                            'status': '0x1',
                            'from': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                            'to': '0x4b4f43cffc3ba1fccf2d918f24db19bf8fc494a7',
                            'gas': '0x5208',
                            'gasPrice': '0x78989e8e4',
                            'value': '0x105747df795c11000',
                            'nonce': '0xb',
                            'index': '0x4',
                            'inputData': '0x',
                            'blockNumber': '0x5395708',
                            'block': {
                                'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                'timestamp': '0x651b505b'
                            }
                        }
                    },
                    {
                        'cursor': '0xa2cf17d93ca04949f264296678330612e4b825538a256ce1f9c1db9cbaf86bed',
                        'transaction': {
                            'hash': '0xa2cf17d93ca04949f264296678330612e4b825538a256ce1f9c1db9cbaf86bed',
                            'status': '0x1',
                            'from': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                            'to': '0xef4b763385838fffc708000f884026b8c0434275',
                            'gas': '0xa96f',
                            'gasPrice': '0x7aef40a00',
                            'value': '0x0',
                            'nonce': '0xa',
                            'index': '0x3',
                            'inputData': '0xa9059cbb000000000000000000000000066219b11bf883b4869592cecda60098f7db5f4f000'
                                         '00000000000000000000000000000000000000005281acafe7d1109480000',
                            'blockNumber': '0x5395708',
                            'block': {
                                'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                'timestamp': '0x651b500a'
                            }
                        }
                    },
                    {
                        'cursor': '0xb6ee36ea51ddb49c3ef94b3f237ffd202b1df3800fb3fb425ed36dd4b5852f59',
                        'transaction': {
                            'hash': '0xb6ee36ea51ddb49c3ef94b3f237ffd202b1df3800fb3fb425ed36dd4b5852f59',
                            'status': '0x1',
                            'from': '0x4b4f43cffc3ba1fccf2d918f24db19bf8fc494a7',
                            'to': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                            'gas': '0x5208',
                            'gasPrice': '0x9bcf3cccb',
                            'value': '0x1057a80d89994f000',
                            'nonce': '0x2',
                            'index': '0x5',
                            'inputData': '0x',
                            'blockNumber': '0x5395708',
                            'block': {
                                'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                'timestamp': '0x651b4f85'
                            }
                        }
                    },
                    {
                        'cursor': '0xd2d24b668523a3a718370e244079d32c63532be845d541b0453bd46daeaf87e9',
                        'transaction': {
                            'hash': '0xd2d24b668523a3a718370e244079d32c63532be845d541b0453bd46daeaf87e9',
                            'status': '0x1',
                            'from': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                            'to': '0xd6778d4b10e59cd9ba1ed2b8774bab671ecc5c6d',
                            'gas': '0x5208',
                            'gasPrice': '0x21f69fcb81',
                            'value': '0x107380dc002f752cc',
                            'nonce': '0x9',
                            'index': '0x2',
                            'inputData': '0x',
                            'blockNumber': '0x5395708',
                            'block': {
                                'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                'timestamp': '0x643a6ede'
                            }
                        }
                    }
                ]
            }
        }
    }
}

GET_LATEST_BLOCK_MOCK_RESPONSE: Dict = {'data': {'blocks': {'edges': [{'block': {'txList': [
    {'hash': '0x4ddddfe03fd6caf25d5dd6049138a4c3c620c8a03cca21860fc9097416a3d0a2', 'status': '0x1',
     'from': '0x055f72ab5db7c3c14233599ddec34bb3a5c88eb6', 'to': '0x52ceba41da235af367bfc0b0ccd3314cb901bb5f',
     'gas': '0xf4240', 'gasPrice': '0x47cf14ddb', 'value': '0x0', 'nonce': '0x57', 'index': '0x0', 'inputData': '0x',
     'blockNumber': '0x5395708', 'block': {'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
                                           'timestamp': '0x66ade6f7'}},
    {'hash': '0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc', 'status': '0x1',
     'from': '0x34b0105cd7009edaa488ee31590204347ba0764f', 'to': '0x20c170ffcca6fc29fdb906ad22fb88abfee19b58',
     'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'value': '0x2c4e53da9e16f8', 'nonce': '0x13b77', 'index': '0x1',
     'inputData': '0x', 'blockNumber': '0x5395708',
     'block': {'hash': '0x0004896100000d1032aed0cf7ce18091dc68e670f2692e80693c1037a08854ff',
               'timestamp': '0x66ade6f7'}}]}}, {'block': {'txList': [
    {'hash': '0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a', 'status': '0x1',
     'from': '0x677ccc389a28b17043e5d21b2cb3d2ec40d4e9ee', 'to': '0xf87f57dcd8a97a5d40a008224855371e2cba6fe4',
     'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'value': '0x359bee87147b91', 'nonce': '0x1490e', 'index': '0x0',
     'inputData': '0x', 'blockNumber': '0x5395707',
     'block': {'hash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
               'timestamp': '0x66ade6f6'}},
    {'hash': '0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274', 'status': '0x1',
     'from': '0x1098db74b3cc07a78e25756765d91625773c2a04', 'to': '0xf89d7b9c864f589bbf53a82105107622b35eaa40',
     'gas': '0x5208', 'gasPrice': '0x45d964b800', 'value': '0xedaa05b4404f9dffa', 'nonce': '0x0', 'index': '0x1',
     'inputData': '0x', 'blockNumber': '0x5395707',
     'block': {'hash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
               'timestamp': '0x66ade6f6'}},
    {'hash': '0xc8518d8eafc9a4e9ef4e667f7507ba91b161ae97afc725d695cecbc2698ca144', 'status': '0x1',
     'from': '0x5f9ed9db4d8f6ba2fd2a65497097d85160ebdc40', 'to': '0x52ceba41da235af367bfc0b0ccd3314cb901bb5f',
     'gas': '0x3567e0', 'gasPrice': '0x43c6b5d24', 'value': '0x0', 'nonce': '0x5', 'index': '0x2', 'inputData': '0x',
     'blockNumber': '0x5395707', 'block': {'hash': '0x0004896100000cff4a69c62d354b561c1b014741fba7f77089b8569f2f074640',
                                           'timestamp': '0x66ade6f6'}}]}}, {'block': {'txList': [
    {'hash': '0x7bb5b235e5fca2a08652825a4133cc5a63bafde98e08c58880b87e43e0198388', 'status': '0x1',
     'from': '0x5275dffb00bbd7cf7ac43fee3f95a4a58871e60b', 'to': '0x52ceba41da235af367bfc0b0ccd3314cb901bb5f',
     'gas': '0xf4240', 'gasPrice': '0x48b2b4634', 'value': '0x0', 'nonce': '0x460', 'index': '0x0',
     'inputData': '0x158731ce000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000'
                  '000000000000000000000000000000000000fa0000000000000000000000000dfd9b9b25cef61033ca680526722c8335281b'
                  '8c00000000000000000000000000000000000000000000000000000000000000c00000000000000000000000001b8ee43b1e'
                  'f423a452d878c97b3f2018e40211e90000000000000000000000000000000000000000000000000000000000003ed1000000'
                  '0000000000000000000000000000000000000000000000000066ade7a9000000000000000000000000000000000000000000'
                  '0000000000000000000084bc785701000000000000000000000000b509d72dad8d9ebe76d660ed49fea2e46dcf9673000000'
                  '0000000000000000000000000000000000000000000000000000001915000000000000000000000000e44ff9dd9c8a9737d7'
                  'ab4ed3e7b1e226430ad7fd000000000000000000000000000000000000000000000000000000000000037e00000000000000'
                  '000000000000000000000000000000000000000000',
     'blockNumber': '0x5395706', 'block': {'hash': '0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0',
                                           'timestamp': '0x66ade6f6'}},
    {'hash': '0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98', 'status': '0x1',
     'from': '0x6e8a80e35c3840913b517bc4a02028831d04df96', 'to': '0xc7abcd945a93bb082306fe94f67105d703c6a1d0',
     'gas': '0x5208', 'gasPrice': '0xdf8475800', 'value': '0xaa87bee538000', 'nonce': '0x2fded', 'index': '0x1',
     'inputData': '0x', 'blockNumber': '0x5395706',
     'block': {'hash': '0x0004896100000ced4704d603bdb334e1a9d0e558ef5766f8469c29577c879ef0',
               'timestamp': '0x66ade6f6'}}]}}, {'block': {'txList': [
    {'hash': '0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7', 'status': '0x1',
     'from': '0x1cbd230943dbb0276e337a9f2ccf05610d1c4dee', 'to': '0xfa4df55bbe69a76bfa17881f3a6132ffc69e43b7',
     'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'value': '0x2ce0775ec1ede7', 'nonce': '0x14e31', 'index': '0x0',
     'inputData': '0x', 'blockNumber': '0x5395705',
     'block': {'hash': '0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39',
               'timestamp': '0x66ade6f5'}},
    {'hash': '0x07d8032650fe597f704003ecbd9590337866b6f75ef9c9716a862f03befc3c99', 'status': '0x1',
     'from': '0x68aedee7dc9da33a1e7d32a6637361e409c40519', 'to': '0xf9a66f8c569d23f1fa1a63950c3ca822cf26355e',
     'gas': '0x3c46b3', 'gasPrice': '0x45a38c224', 'value': '0x0', 'nonce': '0x13af', 'index': '0x1',
     'inputData': '0xac9650d8000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000'
                  '0000000000000000000000000000000000000700000000000000000000000000000000000000000000000000000000000000'
                  'e000000000000000000000000000000000000000000000000000000000000001400000000000000000000000000000000000'
                  '0000000000000000000000000001a00000000000000000000000000000000000000000000000000000000000000200000000'
                  '0000000000000000000000000000000000000000000000000000000260000000000000000000000000000000000000000000'
                  '00000000000000000002c0000000000000000000000000000000000000000000000000000000000000032000000000000000'
                  '0000000000000000000000000000000000000000000000002485478c7f0000000000000000000000009777ce91bbcbff048b'
                  '2d107dde29a58faa3bc781000000000000000000000000000000000000000000000000000000000000000000000000000000'
                  '00000000000000000000000000000000000000002485478c7f000000000000000000000000e9e72c4eb0ac0170432f03cdf7'
                  'e9aada2718143b00000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                  '000000000000000000000000000000002485478c7f000000000000000000000000082125d3afd871a3a91d8975c80efb9701'
                  'fec1980000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                  '0000000000000000000000002485478c7f000000000000000000000000e90ec537fab7f055f6895b73038c15644a3f511c00'
                  '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                  '00000000000000002485478c7f000000000000000000000000aea03e59fe34f21087c89bfd9cdd1e4bc17b83910000000000'
                  '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                  '000000002485478c7f000000000000000000000000b5326a3f975d5f0f2305c4f4c0328478ef4de7b3000000000000000000'
                  '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                  '2485478c7f0000000000000000000000007790a63ea9bf3281822021fcf70a7bf4d460820300000000000000000000000000'
                  '000000000000000000000000000000',
     'blockNumber': '0x5395705', 'block': {'hash': '0x0004896100000cdb16397e559dbce5a1cbb8bfcd706ea231f1c6b6e2b8405f39',
                                           'timestamp': '0x66ade6f5'}}]}}, {'block': {'txList': [
    {'hash': '0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c', 'status': '0x1',
     'from': '0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3', 'to': '0x20c170ffcca6fc29fdb906ad22fb88abfee19b58',
     'gas': '0x5208', 'gasPrice': '0x13433f9c89', 'value': '0x4324fcf1e695a5', 'nonce': '0x184f8', 'index': '0x0',
     'inputData': '0x', 'blockNumber': '0x5395704',
     'block': {'hash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
               'timestamp': '0x66ade6f5'}},
    {'hash': '0x20eb9f304162ce9443ed014cbc7503b9425cd60e8a39d49dd4577d1fa2899d5a', 'status': '0x1',
     'from': '0x690e8a53975e7151d1c1ee43019800cf61f79192', 'to': '0xc25283b82ba0f230604e37668e6289499057b7fd',
     'gas': '0xf4240', 'gasPrice': '0x43c6b5d24', 'value': '0x0', 'nonce': '0x809', 'index': '0x1',
     'inputData': '0xb374012b00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000'
                  '00000000000000000000000000000000000008222553246736447566b5831386c553058302b42304f484b624f516d46304a5'
                  '4797a6c2f4a4b77784852646b73476246694e67704e737355694f6335394b6f752f4e614e32674b463842536b4379652b773'
                  '0477178616e78704c4a71794a79582f697771687271743472466d4a757056304165356a315a6a4839416f687a5374784d220'
                  '00000000000000000000000000000000000000000000000000000000000',
     'blockNumber': '0x5395704', 'block': {'hash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                                           'timestamp': '0x66ade6f5'}},
    {'hash': '0xda8960d7e47dfee9fe8a567dd10b31d66a2ada07ff6548955ed0e902ce3710e5', 'status': '0x1',
     'from': '0xe7798097e7171b2922bd953180ac8c3bd3421b3b', 'to': '0xc3da629c518404860c8893a66ce3bb2e16bea6ec',
     'gas': '0xa5ed9', 'gasPrice': '0x44492c1e0', 'value': '0x0', 'nonce': '0x15298', 'index': '0x2',
     'inputData': '0xff040000000000000000001dce753d7889a0950e936f8d53e1662f0e2c3a0b813c6bdc0dd10921be370d5312f44cb42ce3'
                  '77bc9b8a0cef1a4c830185e20000000193de8394e0e97e2a997186e6703a6e3636b06ed894fbe860ad699670a2293d194cf'
                  '1376ef58c014a0185e2000000011f3c8421e230ff1598ae4e78b3a90fd837ab706fe992beab6659bff447893641a378fbbf0'
                  '31c5bd60182b8000000003d6c56f6855b7cc746fb80848755b0a9c37701223fd3a0c85b70754efc07ac9ac0cbbdce664865a'
                  '60181be00000000',
     'blockNumber': '0x5395704', 'block': {'hash': '0x0004896100000cd366d1e8839f8060b088e5069478d12f0c1a04933dc8988bfb',
                                           'timestamp': '0x66ade6f5'}}]}}]}}}

GET_TOKEN_BALANCE_MOCK_RESPONSE = {'data': {'ercTokenBalance': '0x9e66eb'}}

GET_BALANCE_MOCK_RESPONSE = {'data': {'account': {'balance': '0xf3db722bab2e2b211'}}}


@pytest.mark.slow
class TestFtmGraphqlApi(BaseTestCase):
    api = FtmGraphqlApi

    def test_get_address_txs(self):
        response = self.api.get_address_txs('0xa70D2B1C4C7283f0427BB090b5Bac1a9beDd510a')

        schema = {
            'data': {
                'account': {
                    'txList': {
                        'edges': {
                            'transaction': {
                                'hash': str,
                                'status': str,
                                'from': str,
                                'to': str,
                                'gas': str,
                                'gasPrice': str,
                                'value': str,
                                'nonce': str,
                                'index': str,
                                'inputData': str,
                                'blockNumber': str,
                                'block': {
                                    'hash': str,
                                    'timestamp': str
                                }
                            }
                        }
                    }
                }
            }
        }

        self.assert_schema(response, schema)

    def test_get_block_head(self):
        response = self.api.get_block_head()

        schema = {
            'data': {
                'block': {
                    'number': str
                }
            }
        }

        self.assert_schema(response, schema)

    def test_get_batch_blocks_txs(self):
        response = self.api.get_batch_block_txs(87643911, 87643914)

        blocks = list(range(87643911, 87643914 + 1))

        schema = {
            'data': {
                'blocks': {
                    'edges': {
                        'block': {
                            'number': str,
                            'txList': {
                                'hash': str,
                                'status': str,
                                'from': str,
                                'to': str,
                                'gas': str,
                                'gasPrice': str,
                                'value': str,
                                'nonce': str,
                                'index': str,
                                'inputData': str,
                                'blockNumber': str,
                                'block': {
                                    'hash': str,
                                    'timestamp': str
                                }
                            }
                        }
                    }
                }
            }
        }

        self.assert_schema(response, schema)

        for block in response.get('data').get('blocks').get('edges'):
            height = int(block.get('block').get('number'), 0)
            if height in blocks:
                blocks.pop()

        assert blocks == []

    def test_get_balance(self):
        response = self.api.get_balance('0xEB80FFa1F7493773b291fd9B41893A350F3fC331')

        schema = {
            'data': {
                'account': {
                    'balance': str
                }
            }
        }

        self.assert_schema(response, schema)

    def test_get_token_balance(self):
        schema = {
            'data': {
                'ercTokenBalance': str
            }
        }
        for key in opera_ftm_contract_info['mainnet']:
            response = self.api.get_token_balance('0xEB80FFa1F7493773b291fd9B41893A350F3fC331',
                                                  opera_ftm_contract_info['mainnet'][key])
            self.assert_schema(response, schema)

BLOCK_HEAD_MOCKED_VALUE: int = 87643912

class TestFTMGraphqlExplorerInterface(BaseTestCase):
    explorer = FTMExplorerInterface()
    api = FtmGraphqlApi

    def setUp(self):
        FTMExplorerInterface.block_head_apis = [self.api]
        FTMExplorerInterface.balance_apis = [self.api]
        FTMExplorerInterface.token_balance_apis = [self.api]
        FTMExplorerInterface.address_txs_apis = [self.api]
        FTMExplorerInterface.block_txs_apis = [self.api]
        self.maxDiff = None

    def test_get_block_head(self):
        self.api.request = Mock(side_effect=[GET_BLOCK_HEAD_MOCK_RESPONSE])
        head = self.explorer.get_block_head()
        assert head == BLOCK_HEAD_MOCKED_VALUE

    def test_get_address_txs(self):
        self.api.request = Mock(side_effect=[GET_BLOCK_HEAD_MOCK_RESPONSE, GET_TXS_MOCK_RESPONSE])

        transactions = self.explorer.get_txs('0xa70D2B1C4C7283f0427BB090b5Bac1a9beDd510a')

        expected = [
            {
                75: {
                    'amount': Decimal('12.742823578997903712'),
                    'from_address': '0x86d469ce0ee820f191b0e59e74666a6c3a27bd0e',
                    'to_address': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                    'hash': '0x25e09bb93fe82f4da832897ad9941333986a1c4e3dffd095ad9475ad99a1d338',
                    'block': 87643911,
                    'date': datetime.datetime(2024, 8, 10, 14, 43, 22, tzinfo=pytz.utc),
                    'memo': None,
                    'confirmations': 1,
                    'address': '0xa70D2B1C4C7283f0427BB090b5Bac1a9beDd510a',
                    'direction': 'incoming',
                    'raw': None
                }
            }, {
                75: {
                    'amount': Decimal('18.839821643520479232'),
                    'from_address': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                    'to_address': '0x4b4f43cffc3ba1fccf2d918f24db19bf8fc494a7',
                    'hash': '0x3a9aa4ca05a755937415c3429870329f3cd62a2892a26b60bdb8094e8c3edabe',
                    'block': 87643912,
                    'date': datetime.datetime(2023, 10, 2, 23, 20, 59, tzinfo=pytz.utc),
                    'memo': None,
                    'confirmations': 0,
                    'address': '0xa70D2B1C4C7283f0427BB090b5Bac1a9beDd510a',
                    'direction': 'outgoing',
                    'raw': None
                }
            }, {
                75: {'amount': Decimal('18.841513658835857408'),
                     'from_address': '0x4b4f43cffc3ba1fccf2d918f24db19bf8fc494a7',
                     'to_address': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                     'hash': '0xb6ee36ea51ddb49c3ef94b3f237ffd202b1df3800fb3fb425ed36dd4b5852f59',
                     'block': 87643912,
                     'date': datetime.datetime(2023, 10, 2, 23, 17, 25, tzinfo=pytz.utc),
                     'memo': None,
                     'confirmations': 0,
                     'address': '0xa70D2B1C4C7283f0427BB090b5Bac1a9beDd510a',
                     'direction': 'incoming',
                     'raw': None
                     }
            },{
                75: {
                    'amount': Decimal('18.966924949005488844'),
                    'from_address': '0xa70d2b1c4c7283f0427bb090b5bac1a9bedd510a',
                    'to_address': '0xd6778d4b10e59cd9ba1ed2b8774bab671ecc5c6d',
                    'hash': '0xd2d24b668523a3a718370e244079d32c63532be845d541b0453bd46daeaf87e9',
                    'block': 87643912,
                    'date': datetime.datetime(2023, 4, 15, 9, 31, 10, tzinfo=pytz.utc),
                    'memo': None,
                    'confirmations': 0,
                    'address': '0xa70D2B1C4C7283f0427BB090b5Bac1a9beDd510a',
                    'direction': 'outgoing',
                    'raw': None
                }
            }
        ]
        assert transactions == expected

    def test_get_block_txs(self):
        self.api.request = Mock(side_effect=[GET_BLOCK_HEAD_MOCK_RESPONSE, GET_LATEST_BLOCK_MOCK_RESPONSE])
        cache.delete('latest_block_height_processed_ftm')

        transactions = self.explorer.get_latest_block(include_info=True, include_inputs=True)

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
                    '0x20c170ffcca6fc29fdb906ad22fb88abfee19b58': {
                        75: [
                            {
                                'tx_hash': '0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc',
                                'value': Decimal('0.012471021032314616'),
                                'contract_address': None,
                                'symbol': 'FTM',
                                'block_height': 87643912
                            }
                            , {
                                'tx_hash': '0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c',
                                'value': Decimal('0.018899492248393125'),
                                'contract_address': None,
                                'symbol': 'FTM',
                                'block_height': 87643908
                            }
                        ]
                    },
                    '0xfa4df55bbe69a76bfa17881f3a6132ffc69e43b7': {
                        75: [{
                            'tx_hash': '0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7',
                            'value': Decimal('0.012631702270766567'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643909
                        }]
                    },
                    '0xf87f57dcd8a97a5d40a008224855371e2cba6fe4': {
                        75: [{
                            'tx_hash': '0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a',
                            'value': Decimal('0.015089622536453009'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643911
                        }]
                    },
                    '0xf89d7b9c864f589bbf53a82105107622b35eaa40': {
                        75: [{
                            'tx_hash': '0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274',
                            'value': Decimal('274.008108876175106042'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643911
                        }]
                    },
                    '0xc7abcd945a93bb082306fe94f67105d703c6a1d0': {
                        75: [{
                            'tx_hash': '0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98',
                            'value': Decimal('0.003000000000000000'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643910
                        }]
                    },
                },
                'outgoing_txs': {
                    '0xa0af34f0f8d8b9088a36c265b4a5c82c8274cbb3': {
                        75: [{
                            'tx_hash': '0xe8f5bb7203932d47e893606b1f3faef3ea8bf49e510c5121274f6dba08da948c',
                            'value': Decimal('0.018899492248393125'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643908
                        }]
                    },
                    '0x1cbd230943dbb0276e337a9f2ccf05610d1c4dee': {
                        75: [{
                            'tx_hash': '0x1954f4aea60af16ab6334bee48c71646bbaa2fef9a707f4d21a8d6e1109098a7',
                            'value': Decimal('0.012631702270766567'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643909
                        }]
                    },
                    '0x677ccc389a28b17043e5d21b2cb3d2ec40d4e9ee': {
                        75: [
                            {
                                'tx_hash': '0xbb817d61753a7e7931d6baf4969f2c1052bf46307339e64582cb06f65e64071a',
                                'value': Decimal('0.015089622536453009'),
                                'contract_address': None,
                                'symbol': 'FTM',
                                'block_height': 87643911
                            }
                        ]

                    },
                    '0x1098db74b3cc07a78e25756765d91625773c2a04': {
                        75: [{
                            'tx_hash': '0xa50e0893d53a55077339bf60302ce9a8a3c321a1885a7bf523e14587c429f274',
                            'value': Decimal('274.008108876175106042'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643911
                        }]
                    },
                    '0x6e8a80e35c3840913b517bc4a02028831d04df96': {
                        75: [{
                            'tx_hash': '0xa8c273b7f06a4f32ded862f175249f5e9d16d865819d7a52126a240630115f98',
                            'value': Decimal('0.003000000000000000'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643910
                        }]
                    }, '0x34b0105cd7009edaa488ee31590204347ba0764f': {
                        75: [{
                            'tx_hash': '0xb4103ee30b8ac30ab7fffdd6df486bf3e97cadbfd34e2d52157c7f175770c5bc',
                            'value': Decimal('0.012471021032314616'),
                            'contract_address': None,
                            'symbol': 'FTM',
                            'block_height': 87643912
                        }]
                    }
                }
            },
            87643912
        )
        self.assertTupleEqual(transactions, expected)  # noqa: PT009

    def test_get_token_balance(self):
        self.api.request = Mock(side_effect=[GET_TOKEN_BALANCE_MOCK_RESPONSE])

        contract = opera_ftm_contract_info['mainnet'][Currencies.btc]

        result = self.explorer.get_token_balance('0xEB80FFa1F7493773b291fd9B41893A350F3fC331',
                                                 {Currencies.btc: contract})

        expected = {
            'symbol': contract.get('symbol'),
            'amount': Decimal('0.10381035'),
            'address': '0xEB80FFa1F7493773b291fd9B41893A350F3fC331'
        }

        assert result == expected

    def test_get_balance(self):
        self.api.request = Mock(side_effect=[GET_BALANCE_MOCK_RESPONSE])

        result = self.explorer.get_balance('0xEB80FFa1F7493773b291fd9B41893A350F3fC331')

        expected = {
            Currencies.ftm: {
                'symbol': 'FTM',
                'amount': Decimal('281.148222447955390993'),
                'address': '0xEB80FFa1F7493773b291fd9B41893A350F3fC331'
            }
        }

        assert result == expected

    class TestFtmGraphql(TestCase):

        def test_get_staking_info(self):
            api = FantomGraphQlAPI()
            api.request = Mock()
            api.request.return_value = {'data': {
                'account': {'address': '0xb5a59f7f8496f179697095a20628206704c86d62',
                            'balance': '0x2b5daf7a5cbd57058',
                            'totalValue': '0x628e7214da949ea121', 'txCount': '0x3',
                            'delegations': {'totalCount': '0x1',
                                            'edges': [{
                                                'delegation': {
                                                    'createdTime': '0x62ee2d68',
                                                    'amountDelegated': '0x5ede20f01a45980000',
                                                    'lockedUntil': '0x6300a3b4',
                                                    'claimedReward': '0x0',
                                                    'pendingRewards': {
                                                        'amount': '0xfa762d1a833130c9',
                                                        '__typename': 'PendingRewards'},
                                                    '__typename': 'Delegation'},
                                                'cursor': '62ee2d6b4fd7cc0af0320353',
                                                '__typename': 'DelegationListEdge'}],
                                            '__typename': 'DelegationList'},
                            '__typename': 'Account'}}}

            result = api.get_staking_info('0xB5a59f7f8496f179697095A20628206704c86d62')
            expected_result = StakingInfo(address='0xB5a59f7f8496f179697095A20628206704c86d62',
                                          total_balance=Decimal('1799.997546504668409944'),
                                          staked_balance=Decimal('1750.000000000000000000'),
                                          rewards_balance=Decimal('18.047662148627280073'), free_balance=None,
                                          delegated_balance=None, pending_rewards=None, claimed_rewards=None,
                                          end_staking_plan=datetime.datetime(2022, 8, 20, 13, 34, 52,
                                                                             tzinfo=pytz.utc),
                                          coin_type=CoinType.NON_PERIODIC_REWARD)
            assert result == expected_result

        @pytest.mark.slow
        def test_get_staking_info_request(self):
            api = FantomGraphQlAPI()
            address = '0xB5a59f7f8496f179697095A20628206704c86d62'
            data = {
                'query': api.queries.get('get_staking_info'),
                'variables': {
                    'address': address
                }
            }
            result = api.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))

            assert list(result) == ['data']
            assert list(result.get('data')) == ['account']
            assert list(result.get('data').get('account')) == ['address', 'balance', 'totalValue',
                                                               'txCount', 'delegations']
            assert list(result.get('data').get('account').get('delegations')) == ['totalCount', 'edges']
            assert list(result.get('data').get('account').get('delegations').get('edges')[0]) == \
                   ['delegation', 'cursor']
            assert list(result.get('data').get('account').get('delegations').get('edges')[0].get('delegation')) == \
                   ['createdTime', 'amountDelegated', 'lockedUntil', 'claimedReward', 'pendingRewards']
            assert list(result.get('data').get('account').get('delegations').get('edges')[0].get('delegation')
                        .get('pendingRewards')) == ['amount']

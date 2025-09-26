import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import Mock

from django.core.cache import cache

import pytest
from django.conf import settings

from exchange.blockchain.api.doge import DogeExplorerInterface
from exchange.blockchain.api.doge.doge_block_book import DogeBlockBookApi
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


@pytest.mark.slow
class TestDogeBlockBookApi(BaseTestCase):
    api = DogeBlockBookApi

    def test_get_balance_api(self):
        response = self.api.get_balance('DKrBCSuXr9quhn9k1LyV3HGUm4g2GLjYA6')
        schema = {
            'balance': str,
            'unconfirmedBalance': str
        }
        self.assert_schema(response, schema)

    def test_get_address_txs_api(self):
        response = self.api.get_address_txs('DKrBCSuXr9quhn9k1LyV3HGUm4g2GLjYA6')
        schema = {
            'transactions': {
                'txid': str,
                'confirmations': int,
                'blockHeight': int,
                'blockHash': str,
                'blockTime': int,
                'fees': str,
                'vin': {
                    'isAddress': bool,
                    'addresses': list,
                    'value': str
                },
                'vout': {
                    'isAddress': bool,
                    'addresses': list,
                    'value': str
                }
            }
        }
        self.assert_schema(response, schema)

    def test_get_block_head_api(self):
        response = self.api.get_block_head()
        schema = {
            'blockbook': {
                'bestHeight': int
            }
        }
        self.assert_schema(response, schema)

    def test_get_tx_details_api(self):
        response = self.api.get_tx_details('d5ee61f410a3c47623d6fc512e12dd153b35805280f4d8974176d31fb47658ed')
        schema = {
            'vin': {
                'isAddress': bool,
                'value': str,
                'addresses': list
            },
            'vout': {
                'isAddress': bool,
                'value': str,
                'addresses': list
            },
            'txid': str,
            'blockHash': str,
            'blockHeight': int,
            'confirmations': int,
            'blockTime': int,
            'fees': str
        }
        self.assert_schema(response, schema)

    def test_get_block_txs_api(self):
        response = self.api.get_block_txs(5352000, 0)
        schema = {
            'txs': {
                'txid': str,
                'confirmations': int,
                'blockHeight': int,
                'blockHash': str,
                'blockTime': int,
                'fees': str,
                'vin': {
                    'isAddress': bool,
                    'addresses': Optional[list],
                    'value': str
                },
                'vout': {
                    'isAddress': bool,
                    'addresses': Optional[list],
                    'value': str
                }

            }
        }
        self.assert_schema(response, schema)


BLOCK_HEAD_MOCK_RESPONSE = {
    'blockbook': {
        'bestHeight': 5353255
    },
    'backend': {"alaki": 1}
}

GET_BALANCE_MOCK_RESPONSE = {
    'balance': "328772547281",
    'unconfirmedBalance': "361561431"
}

GET_TX_DETAILS_MOCK_RESPONSE = {'txid': 'd5ee61f410a3c47623d6fc512e12dd153b35805280f4d8974176d31fb47658ed',
                                'version': 1, 'vin': [
        {'txid': '04bd88119226a5d43810852b7828ba9bd0736655db1dafd0963fb066cf2cc416', 'vout': 17, 'sequence': 4294967295,
         'n': 0, 'addresses': ['DBgqbSoth4nPJrcu1T1fwe8oL6LJRCB68z'], 'isAddress': True, 'value': '5000000000',
         'hex': '483045022100d03c743824fed6f7924b51f9c1dd650d3259d9cbe4c26dca82f8ca11028dd10902203b2da6eeb26d0dacac0be340e693cde73f190201e47c78dd1108c6f77003d898012103a257ba17c6853e147451fc2126ff95b95bf3a65a1eb4b362bdf20833ed8fa6a4'},
        {'txid': '04bd88119226a5d43810852b7828ba9bd0736655db1dafd0963fb066cf2cc416', 'vout': 39, 'sequence': 4294967295,
         'n': 1, 'addresses': ['DRGS22tTYfRNjT9QDtiWnasmwTqxwgsV8v'], 'isAddress': True, 'value': '8000000000',
         'hex': '483045022100b5ce41fd7d6554e167e15593373b128d875f2bcd8417cf82431a69d5da97425802201d1b841e9ad9fbfe0fa909a68bbbe7eb607804cbda3c0196fa58ccfd364497e9012102f64d4f0b299840e949f5948ad95d1933251426e65e37c360f74b7eda2eb6480d'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 22, 'sequence': 4294967295,
         'n': 2, 'addresses': ['DHjVekcwvBsyd143jscqvgU1rGEKC1pRbG'], 'isAddress': True, 'value': '26438070192',
         'hex': '483045022100a110eec95e98783f2396b8595e1eab9b27cd34339acc29dc0e25dfcbeee8fefe02200fff8a9fd01ab920f0fa8bf4cd18c58d0bc20f894e284dd6ae359df9f0969f2f0121030bcf4aa82c0634fdd2ffa69d08f9bf8233766bb14b8204f545c0d77ca2203df1'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 233,
         'sequence': 4294967295, 'n': 3, 'addresses': ['DPcd27WpFMubG4UwdmgqhcZEZfvAw8ZEK6'], 'isAddress': True,
         'value': '11529677599',
         'hex': '483045022100ffbffba46d97cf7808ff5931b20df3a3f1ba2e24a34446222b5fd30e8ccb418602206232d3058e8fdeb7eec763ac02a4621115dcebbc30f4c7299ddd2d248a3bdd74012102014add3d7745591bb2f271bfb66c1705cbdc45c7d751f718f08b8ff27877548b'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 320,
         'sequence': 4294967295, 'n': 4, 'addresses': ['DKrBCSuXr9quhn9k1LyV3HGUm4g2GLjYA6'], 'isAddress': True,
         'value': '21264419348',
         'hex': '473044022017f1d99b20d7d7cf3d34cc7672a368e9128e33339402341e1c7bc0fc143505d102202d70b700e2fdbc54bd2447dbcac3aeb2af640d90be12bd9a167e712580d67bb8012103a4c722bfdcf8e3170ecc45790baf76b7ba871104c23322765070a9f4837ab4f1'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 413,
         'sequence': 4294967295, 'n': 5, 'addresses': ['D5ZBauYb36vQsHrasaEAj1cVRkzZDzXQgQ'], 'isAddress': True,
         'value': '1951090836',
         'hex': '483045022100a3024a237b0f2b44dd5e0964cbf680662d63f1d835bb066c6e3002465fce61bb02201db10a243d09a657e52b2e4df7467f3cdb97e8f0d9eefac498dc19011bdad8100121027c8de694ba64d599b27a82fb1a2d60065682bd7846fec50b3d0cc1ffe6632ff9'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 623,
         'sequence': 4294967295, 'n': 6, 'addresses': ['DMn2cEmweQzBJZnSk4xf8HA8S4EkPgQnjs'], 'isAddress': True,
         'value': '470358529',
         'hex': '4730440220786eb0097dd3f3680248dbededcd6f5c1a736e5dfcac8a8efc496d781145c19202203fd647b03d61fda5b5a9e59fdb19fd1accd765ec5142d4c40ea954de94c51a76012103a60a5b52831d4fbd313740a47019b7131fec76c05dabca05641593a7835cc102'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 641,
         'sequence': 4294967295, 'n': 7, 'addresses': ['DMuQTT7Jdt6PRgQaAEmaaMFFqkgdngREJi'], 'isAddress': True,
         'value': '584264875',
         'hex': '483045022100d05dbf271c69ef2cfc3aa651de88990705eeaed92d293638ad3ea037b5e21506022037b96e5534282bf17e0f9526fa3e4327be5749912df44701853728f666c5975901210381ff8404f891a63be4793a123935457d5530585085b9f8a714055ce8659811e0'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 701,
         'sequence': 4294967295, 'n': 8, 'addresses': ['DHprjiM1kf9SzyuQ4UF3ijDB5fFXCDysUu'], 'isAddress': True,
         'value': '23069734657',
         'hex': '47304402207fbe1bffbd5fbbb8ad9f53e7d95e1ea7c83b2e3b7082ac49cbb5b83ff20a1e760220317d84ee4e7b3e39404a3acc48c7fd2c8d4e077ee6bd296cff418e9c204a3c4801210371ada12ba5823709a41c7128788ed1b90bdbc1bd860eef97314a8d7a72e80c5b'},
        {'txid': '20bb5d6552abd8822e0cdb2e7c6aaf4ab11dadd9b352c1d96bd6af228a8a0598', 'vout': 738,
         'sequence': 4294967295, 'n': 9, 'addresses': ['DC2yjW1BFyq5AGjoJDQn6Z8jTSAM8yvNYy'], 'isAddress': True,
         'value': '22888531265',
         'hex': '483045022100fc94568fc1a3c81369c56aacb8224d374d3ccad911ffa414a46a285069c936080220461f05c4136e3235bf845a1f2f2eb84e82294904ec1272b02202d61fa6f81a3e0121035b43d7fcdaa6f03cf1c040ba56bd4e42c358e4ba47205b7e023a372f2e997085'},
        {'txid': 'c9d04d6273609933e3646563cda087bef4a93a17a38bcdeac37c62ea16e3ee9a', 'vout': 7, 'sequence': 4294967295,
         'n': 10, 'addresses': ['DM2z4T6YJgoP4ikEJVuGcWz9MmKbjswrd1'], 'isAddress': True, 'value': '656305494',
         'hex': '483045022100a2914922a396d36c846446011568732610e77932eb791cc375778f32bd26de0402202abf6056c2b9d8403507e92a8ac722244a661bf30bfff3c293d19f86e57f219201210277363324e8548a8ac4ad6b016203d93122511aed498a661e886227dbe863fda6'},
        {'txid': 'c9d04d6273609933e3646563cda087bef4a93a17a38bcdeac37c62ea16e3ee9a', 'vout': 42, 'sequence': 4294967295,
         'n': 11, 'addresses': ['DKLD984D6uWZdkfSR74P3oMo9J7wqwP6RS'], 'isAddress': True, 'value': '683808407',
         'hex': '473044022039370af42c76921cfe6df923dced8efa3fc62b0d4070b48d955422b23939333e02206d849948cb4478eba8a675727f03d2910ae8265291681d7247b4248b81d99f8a01210339032edf3c74bd3f6f5925329391de62f36b0a74e6ffe16b22530f79511f8185'},
        {'txid': 'c9d04d6273609933e3646563cda087bef4a93a17a38bcdeac37c62ea16e3ee9a', 'vout': 797,
         'sequence': 4294967295, 'n': 12, 'addresses': ['DLmYA5aNmSpxEqF55oXY1UDUDduQEUfyio'], 'isAddress': True,
         'value': '116433844336',
         'hex': '47304402207583baae753c5989a082b78bb48e83f25e9717aa3560e6e899343ba9c2bf7d49022067189934c23f59f2f7137b1319b34ffb85d2b3832feddbb223fea60cdbb902b5012102066415a8c99ccfdbe3f871121d30a1c1099c98a718fb2e86b80a026493f80cb3'},
        {'txid': 'c9d04d6273609933e3646563cda087bef4a93a17a38bcdeac37c62ea16e3ee9a', 'vout': 864,
         'sequence': 4294967295, 'n': 13, 'addresses': ['DP6mv6BG4aXC6Gn8Uyn7w6RN7BMvYS28a9'], 'isAddress': True,
         'value': '24737233791',
         'hex': '4830450221008bb31fad4f301dd949a830eebc3d1dc47c0a262960817028b790ad40629a6d85022052416f3391e47f9de3b220a80f2c9e6b8afc565bf123d1f6748f53e6a8944af60121039abddcc9a01c997ada7c825175016b17dfd215715c2edd85749a64f2bc8dc8bb'},
        {'txid': 'c9d04d6273609933e3646563cda087bef4a93a17a38bcdeac37c62ea16e3ee9a', 'vout': 912,
         'sequence': 4294967295, 'n': 14, 'addresses': ['DRCuc3E1mQvV4fngrR4J7G4NY5W8rTNQEu'], 'isAddress': True,
         'value': '6206400877',
         'hex': '483045022100d1b426c9081a3dea6b4cc21b475a6dd68c3a48323e608aeefdb4f1b510ee385902201eadda245e0c63e667b13d25834df6ed2d23a46a3810809c08d83ab812af85d6012103d30b1eaf68953aaab5bc39e7dbe996027dbb7aaefb2e00ca77b9e9e1353aa3f3'},
        {'txid': '199cba3e84d9a82204d8a060b4b439bca9c5e129a0a2e479c0c05661540e9ab3', 'vout': 18, 'sequence': 4294967295,
         'n': 15, 'addresses': ['D6Ejj8zq6vF9PseK4HsZai83qyJbxYaigQ'], 'isAddress': True, 'value': '11109531983',
         'hex': '473044022056e04a3c4ab56fd3aed480c9810d1b9ae7d8d8f9500eaa6c8e8b9e8e2b10d0a70220449be9bad1367ca389be0e2f2891b2d3644c00dbab8b4001c31708d287e09b06012103cef21721ea2dec4225277fca270e60249b2a2dca7c75bf2094d73f1cccfa048d'},
        {'txid': 'eb3d8b18f90eef5572d0ddd6c2bcb3ad6d13736db006f75f74a3ba40c7a556b6', 'sequence': 4294967295, 'n': 16,
         'addresses': ['DJdxNcfjyoyanEvQ1QXab9FXNGUqACLyGP'], 'isAddress': True, 'value': '1289097329953',
         'hex': '47304402204c41a2a3c044ecfb2d8ab1cd27486f52fb013dad13b9b345d64783c8a49c0c58022019e47e0492ba792fc3adc7ba5bcf7237da744ae91e772235599e892c8836abe901210233bec8f5fbca39b46f0a98d331118f88e770b0b711250a4cb933c1d635f97f24'}],
                                'vout': [{'value': '828495656155', 'n': 0,
                                          'hex': '76a9148a54b06de66b141b02729486d0aef3b7f4ea83d088ac',
                                          'addresses': ['DHkXF3Anv8jcXXpTAgZKcAxHiBGWXEzj5r'], 'isAddress': True},
                                         {'value': '741495195987', 'n': 1, 'spent': True,
                                          'hex': '76a914dcb7c445dbdc0ec0b55239510afdddd3511e470088ac',
                                          'addresses': ['DRG9Lo3W5f3EcThaAb4Aetrodj8gDChawR'], 'isAddress': True}],
                                'blockHash': '9188e1cce7dad42d02d2d86ee5f6eb4a4bac028f853de43dcb3fcc9ab9ad6eb5',
                                'blockHeight': 5351781, 'confirmations': 1404, 'blockTime': 1724655099,
                                'value': '1569990852142', 'valueIn': '1570120602142', 'fees': '129750000',
                                'hex': '010000001116c42ccf66b03f96d0af1ddb556673d09bba28782b851038d4a526921188bd04110000006b483045022100d03c743824fed6f7924b51f9c1dd650d3259d9cbe4c26dca82f8ca11028dd10902203b2da6eeb26d0dacac0be340e693cde73f190201e47c78dd1108c6f77003d898012103a257ba17c6853e147451fc2126ff95b95bf3a65a1eb4b362bdf20833ed8fa6a4ffffffff16c42ccf66b03f96d0af1ddb556673d09bba28782b851038d4a526921188bd04270000006b483045022100b5ce41fd7d6554e167e15593373b128d875f2bcd8417cf82431a69d5da97425802201d1b841e9ad9fbfe0fa909a68bbbe7eb607804cbda3c0196fa58ccfd364497e9012102f64d4f0b299840e949f5948ad95d1933251426e65e37c360f74b7eda2eb6480dffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb20160000006b483045022100a110eec95e98783f2396b8595e1eab9b27cd34339acc29dc0e25dfcbeee8fefe02200fff8a9fd01ab920f0fa8bf4cd18c58d0bc20f894e284dd6ae359df9f0969f2f0121030bcf4aa82c0634fdd2ffa69d08f9bf8233766bb14b8204f545c0d77ca2203df1ffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb20e90000006b483045022100ffbffba46d97cf7808ff5931b20df3a3f1ba2e24a34446222b5fd30e8ccb418602206232d3058e8fdeb7eec763ac02a4621115dcebbc30f4c7299ddd2d248a3bdd74012102014add3d7745591bb2f271bfb66c1705cbdc45c7d751f718f08b8ff27877548bffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb20400100006a473044022017f1d99b20d7d7cf3d34cc7672a368e9128e33339402341e1c7bc0fc143505d102202d70b700e2fdbc54bd2447dbcac3aeb2af640d90be12bd9a167e712580d67bb8012103a4c722bfdcf8e3170ecc45790baf76b7ba871104c23322765070a9f4837ab4f1ffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb209d0100006b483045022100a3024a237b0f2b44dd5e0964cbf680662d63f1d835bb066c6e3002465fce61bb02201db10a243d09a657e52b2e4df7467f3cdb97e8f0d9eefac498dc19011bdad8100121027c8de694ba64d599b27a82fb1a2d60065682bd7846fec50b3d0cc1ffe6632ff9ffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb206f0200006a4730440220786eb0097dd3f3680248dbededcd6f5c1a736e5dfcac8a8efc496d781145c19202203fd647b03d61fda5b5a9e59fdb19fd1accd765ec5142d4c40ea954de94c51a76012103a60a5b52831d4fbd313740a47019b7131fec76c05dabca05641593a7835cc102ffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb20810200006b483045022100d05dbf271c69ef2cfc3aa651de88990705eeaed92d293638ad3ea037b5e21506022037b96e5534282bf17e0f9526fa3e4327be5749912df44701853728f666c5975901210381ff8404f891a63be4793a123935457d5530585085b9f8a714055ce8659811e0ffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb20bd0200006a47304402207fbe1bffbd5fbbb8ad9f53e7d95e1ea7c83b2e3b7082ac49cbb5b83ff20a1e760220317d84ee4e7b3e39404a3acc48c7fd2c8d4e077ee6bd296cff418e9c204a3c4801210371ada12ba5823709a41c7128788ed1b90bdbc1bd860eef97314a8d7a72e80c5bffffffff98058a8a22afd66bd9c152b3d9ad1db14aaf6a7c2edb0c2e82d8ab52655dbb20e20200006b483045022100fc94568fc1a3c81369c56aacb8224d374d3ccad911ffa414a46a285069c936080220461f05c4136e3235bf845a1f2f2eb84e82294904ec1272b02202d61fa6f81a3e0121035b43d7fcdaa6f03cf1c040ba56bd4e42c358e4ba47205b7e023a372f2e997085ffffffff9aeee316ea627cc3eacd8ba3173aa9f4be87a0cd636564e333996073624dd0c9070000006b483045022100a2914922a396d36c846446011568732610e77932eb791cc375778f32bd26de0402202abf6056c2b9d8403507e92a8ac722244a661bf30bfff3c293d19f86e57f219201210277363324e8548a8ac4ad6b016203d93122511aed498a661e886227dbe863fda6ffffffff9aeee316ea627cc3eacd8ba3173aa9f4be87a0cd636564e333996073624dd0c92a0000006a473044022039370af42c76921cfe6df923dced8efa3fc62b0d4070b48d955422b23939333e02206d849948cb4478eba8a675727f03d2910ae8265291681d7247b4248b81d99f8a01210339032edf3c74bd3f6f5925329391de62f36b0a74e6ffe16b22530f79511f8185ffffffff9aeee316ea627cc3eacd8ba3173aa9f4be87a0cd636564e333996073624dd0c91d0300006a47304402207583baae753c5989a082b78bb48e83f25e9717aa3560e6e899343ba9c2bf7d49022067189934c23f59f2f7137b1319b34ffb85d2b3832feddbb223fea60cdbb902b5012102066415a8c99ccfdbe3f871121d30a1c1099c98a718fb2e86b80a026493f80cb3ffffffff9aeee316ea627cc3eacd8ba3173aa9f4be87a0cd636564e333996073624dd0c9600300006b4830450221008bb31fad4f301dd949a830eebc3d1dc47c0a262960817028b790ad40629a6d85022052416f3391e47f9de3b220a80f2c9e6b8afc565bf123d1f6748f53e6a8944af60121039abddcc9a01c997ada7c825175016b17dfd215715c2edd85749a64f2bc8dc8bbffffffff9aeee316ea627cc3eacd8ba3173aa9f4be87a0cd636564e333996073624dd0c9900300006b483045022100d1b426c9081a3dea6b4cc21b475a6dd68c3a48323e608aeefdb4f1b510ee385902201eadda245e0c63e667b13d25834df6ed2d23a46a3810809c08d83ab812af85d6012103d30b1eaf68953aaab5bc39e7dbe996027dbb7aaefb2e00ca77b9e9e1353aa3f3ffffffffb39a0e546156c0c079e4a2a029e1c5a9bc39b4b460a0d80422a8d9843eba9c19120000006a473044022056e04a3c4ab56fd3aed480c9810d1b9ae7d8d8f9500eaa6c8e8b9e8e2b10d0a70220449be9bad1367ca389be0e2f2891b2d3644c00dbab8b4001c31708d287e09b06012103cef21721ea2dec4225277fca270e60249b2a2dca7c75bf2094d73f1cccfa048dffffffffb656a5c740baa3745ff706b06d73136dadb3bcc2d6ddd07255ef0ef9188b3deb000000006a47304402204c41a2a3c044ecfb2d8ab1cd27486f52fb013dad13b9b345d64783c8a49c0c58022019e47e0492ba792fc3adc7ba5bcf7237da744ae91e772235599e892c8836abe901210233bec8f5fbca39b46f0a98d331118f88e770b0b711250a4cb933c1d635f97f24ffffffff02db7430e6c00000001976a9148a54b06de66b141b02729486d0aef3b7f4ea83d088ac53c98ea4ac0000001976a914dcb7c445dbdc0ec0b55239510afdddd3511e470088ac00000000'}

GET_ADDRESS_TXS_MOCK_RESPONSE = {'page': 1, 'totalPages': -1, 'itemsOnPage': 2,
                                 'address': 'DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p', 'balance': '1079124917078367',
                                 'totalReceived': '5765627872333833996', 'totalSent': '5764548747416755629',
                                 'unconfirmedBalance': '0', 'unconfirmedTxs': 0, 'txs': 740676, 'transactions': [
        {'txid': '0a7e22e0e3abeb7fbefde459baa7c7816c340a93a56b7b97e23bb67e86bbc862', 'version': 2, 'vin': [
            {'txid': '1e8b99dede92a49b42c4cb7ab08d9ae107d9a6ce5731dcfa54e43042bf4ca03b', 'vout': 1,
             'sequence': 4294967293, 'n': 0, 'addresses': ['DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p'], 'isAddress': True,
             'value': '3474945630817',
             'hex': '4730440220634bbd232ba82a1e47652e089b28cdea23f658b2e1559d7d70f688b8c53d79420220211433d2035d034caa4961d24c28adef9c1ffb2913d10b9fe96aef160a8217e40121026228360bf8b5898af555d4599d5855bccc9b4f5c1f356e180cc5369ce67e5a69'}],
         'vout': [{'value': '30120000000', 'n': 0, 'hex': '76a91495037ae11b7f0ce3c7dad90feaec966703f9c2f688ac',
                   'addresses': ['DJj1PdpWJRmLcxyKG5iMWtJeCLP6KNWTVW'], 'isAddress': True},
                  {'value': '3444701330817', 'n': 1, 'hex': '76a914a7472ddbee1d36eeeb9cd3bb42974aece491f51b88ac',
                   'addresses': ['DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p'], 'isAddress': True}],
         'blockHash': '45ed7d739e7ec895b9d529932f2ce8263552233d6668b61c825ac0ffd7e51543', 'blockHeight': 5353254,
         'confirmations': 2, 'blockTime': 1724747542, 'value': '3474821330817', 'valueIn': '3474945630817',
         'fees': '124300000',
         'hex': '02000000013ba04cbf4230e454fadc3157cea6d907e19a8db07acbc4429ba492dede998b1e010000006a4730440220634bbd232ba82a1e47652e089b28cdea23f658b2e1559d7d70f688b8c53d79420220211433d2035d034caa4961d24c28adef9c1ffb2913d10b9fe96aef160a8217e40121026228360bf8b5898af555d4599d5855bccc9b4f5c1f356e180cc5369ce67e5a69fdffffff0200ba4a03070000001976a91495037ae11b7f0ce3c7dad90feaec966703f9c2f688ac81fd3208220300001976a914a7472ddbee1d36eeeb9cd3bb42974aece491f51b88ac00000000'},
        {'txid': '1f0f8a61475efb5a6331df05909f12b712a3a04b4ba6e36d076f9e6489df6d58', 'version': 2, 'vin': [
            {'txid': 'c4d39d7ae5529832a9cee7f4c9efe73467f7ebc0a51307ad8b230977103db024', 'vout': 1,
             'sequence': 4294967293, 'n': 0, 'addresses': ['DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p'], 'isAddress': True,
             'value': '4342883150951',
             'hex': '473044022030ab898a776aec9105dc12bb5c974e8627c52d8a534f6886dc303000c5a181e90220779d9359af73ffd32b5d2727bfd6f4b72b9b3aaae7bbb3c03751b4d7d39958eb0121026228360bf8b5898af555d4599d5855bccc9b4f5c1f356e180cc5369ce67e5a69'}],
         'vout': [{'value': '9220000000', 'n': 0, 'hex': '76a914f33db7b3bb3ea757ba770ad1e9c67c40c58ae89888ac',
                   'addresses': ['DTKEg5xZuHpukffixXseWgvvyeqhk6caG5'], 'isAddress': True},
                  {'value': '4333538850951', 'n': 1, 'hex': '76a914a7472ddbee1d36eeeb9cd3bb42974aece491f51b88ac',
                   'addresses': ['DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p'], 'isAddress': True}],
         'blockHash': 'eb4f5ddaf1da8401dcdbd4429ca5dc0fba2773e3056bc3bc96b4072033bdda3d', 'blockHeight': 5353253,
         'confirmations': 3, 'blockTime': 1724747516, 'value': '4342758850951', 'valueIn': '4342883150951',
         'fees': '124300000',
         'hex': '020000000124b03d107709238bad0713a5c0ebf76734e7efc9f4e7cea9329852e57a9dd3c4010000006a473044022030ab898a776aec9105dc12bb5c974e8627c52d8a534f6886dc303000c5a181e90220779d9359af73ffd32b5d2727bfd6f4b72b9b3aaae7bbb3c03751b4d7d39958eb0121026228360bf8b5898af555d4599d5855bccc9b4f5c1f356e180cc5369ce67e5a69fdffffff0200098e25020000001976a914f33db7b3bb3ea757ba770ad1e9c67c40c58ae89888ac87380bfbf00300001976a914a7472ddbee1d36eeeb9cd3bb42974aece491f51b88ac00000000'}]}

GET_BLOCK_TXS_MOCK_RESPONSE = {'page': 1, 'totalPages': 1, 'itemsOnPage': 1000,
                               'hash': '72af6b31fb4d241760a9bff1114a7a1c087920e7b4b24b29809b324cd1203837',
                               'previousBlockHash': 'd5976f108c6acf8b0f10e7cefd07c1079b8023796a7da2c310ddbcd3de9bfbe9',
                               'nextBlockHash': 'b993f87bf19215dadacce0bdeae78bb1e35b66a9d75e390e724fd7c711c88d37',
                               'height': 5353255, 'confirmations': 9, 'size': 1055, 'time': 1724761203,
                               'version': 6422788,
                               'merkleRoot': '20953705fa886b6caaf332c1716f992371ec3042fcb4066d84c53a70e288b08b',
                               'nonce': '0', 'bits': '1a0166e2', 'difficulty': '11967421.14809413', 'txCount': 2,
                               'txs': [{'txid': 'df226336c694881ee4d43affba5b0c5d02267043ca9c6596c6fb311645c47402',
                                        'vin': [{'n': 0, 'isAddress': False, 'value': '0'}], 'vout': [
                                       {'value': '1000045200000', 'n': 0,
                                        'addresses': ['DBgHW1Shjyk91fusm9hm3HcryNBwaFwZbQ'], 'isAddress': True}],
                                        'blockHash': '72af6b31fb4d241760a9bff1114a7a1c087920e7b4b24b29809b324cd1203837',
                                        'blockHeight': 5353255, 'confirmations': 9, 'blockTime': 1724761203,
                                        'value': '1000045200000', 'valueIn': '0', 'fees': '0'},
                                       {'txid': '5e0766f759c91a7b2daffd29726fb728aeac4988d0f3de67eeddc4f562711177',
                                        'vin': [{'n': 0, 'addresses': ['DLReJq5m6oBvebCc9mDSgbjZJ9gCX9Anxy'],
                                                 'isAddress': True, 'value': '49267247496790'}], 'vout': [
                                           {'value': '6098307041', 'n': 0,
                                            'addresses': ['DHLKGsxgFzHW6qtvSQUjx7e6q1ZZFRJ9hW'], 'isAddress': True},
                                           {'value': '49261103989749', 'n': 1,
                                            'addresses': ['DLReJq5m6oBvebCc9mDSgbjZJ9gCX9Anxy'], 'isAddress': True}],
                                        'blockHash': '72af6b31fb4d241760a9bff1114a7a1c087920e7b4b24b29809b324cd1203837',
                                        'blockHeight': 5353255, 'confirmations': 9, 'blockTime': 1724761203,
                                        'value': '49267202296790', 'valueIn': '49267247496790', 'fees': '45200000'}]}


class TestDogeBlockBookExplorerInterface(BaseTestCase):
    explorer = DogeExplorerInterface()
    api = DogeBlockBookApi

    def setUp(self):
        self.explorer.balance_apis = [self.api]
        self.explorer.tx_details_apis = [self.api]
        self.explorer.address_txs_apis = [self.api]
        self.explorer.block_txs_apis = [self.api]
        self.explorer.block_head_apis = [self.api]
        self.maxDiff = None

    def test_get_balance(self):
        self.api.request = Mock(side_effect=[GET_BALANCE_MOCK_RESPONSE])

        address = 'DBgqbSoth4nPJrcu1T1fwe8oL6LJRCB68z'

        balance = self.explorer.get_balance('DBgqbSoth4nPJrcu1T1fwe8oL6LJRCB68z')

        expected_result = {
            Currencies.doge: {
                'address': address,
                'symbol': 'DOGE',
                'balance': Decimal('3287.72547281'),
                'unconfirmed_balance': Decimal('3.61561431')
            }
        }

        self.assertDictEqual(balance, expected_result)

    def test_get_tx_details(self):
        self.api.request = Mock(side_effect=[GET_TX_DETAILS_MOCK_RESPONSE])

        tx_hash = 'd5ee61f410a3c47623d6fc512e12dd153b35805280f4d8974176d31fb47658ed'

        result = self.explorer.get_tx_details(tx_hash)

        print(result)
        expected_result = {
            'hash': tx_hash,
            'success': True,
            'block': 5351781,
            'date': datetime.datetime.fromtimestamp(1724655099, tz=datetime.timezone.utc),
            'fees': Decimal('1.29750000'),
            'memo': None,
            'confirmations': 1404,
            'raw': None,
            'inputs': [],
            'outputs': [],
            'transfers': [
                {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DBgqbSoth4nPJrcu1T1fwe8oL6LJRCB68z',
                    'to': '',
                    'value': Decimal('50.00000000'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DRGS22tTYfRNjT9QDtiWnasmwTqxwgsV8v',
                    'to': '',
                    'value': Decimal('80.00000000'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DHjVekcwvBsyd143jscqvgU1rGEKC1pRbG',
                    'to': '',
                    'value': Decimal('264.38070192'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DPcd27WpFMubG4UwdmgqhcZEZfvAw8ZEK6',
                    'to': '',
                    'value': Decimal('115.29677599'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DKrBCSuXr9quhn9k1LyV3HGUm4g2GLjYA6',
                    'to': '',
                    'value': Decimal('212.64419348'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'D5ZBauYb36vQsHrasaEAj1cVRkzZDzXQgQ',
                    'to': '',
                    'value': Decimal('19.51090836'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DMn2cEmweQzBJZnSk4xf8HA8S4EkPgQnjs',
                    'to': '',
                    'value': Decimal('4.70358529'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DMuQTT7Jdt6PRgQaAEmaaMFFqkgdngREJi',
                    'to': '',
                    'value': Decimal('5.84264875'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DHprjiM1kf9SzyuQ4UF3ijDB5fFXCDysUu',
                    'to': '',
                    'value': Decimal('230.69734657'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DC2yjW1BFyq5AGjoJDQn6Z8jTSAM8yvNYy',
                    'to': '',
                    'value': Decimal('228.88531265'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DM2z4T6YJgoP4ikEJVuGcWz9MmKbjswrd1',
                    'to': '',
                    'value': Decimal('6.56305494'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DKLD984D6uWZdkfSR74P3oMo9J7wqwP6RS',
                    'to': '',
                    'value': Decimal('6.83808407'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DLmYA5aNmSpxEqF55oXY1UDUDduQEUfyio',
                    'to': '',
                    'value': Decimal('1164.33844336'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DP6mv6BG4aXC6Gn8Uyn7w6RN7BMvYS28a9',
                    'to': '',
                    'value': Decimal('247.37233791'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DRCuc3E1mQvV4fngrR4J7G4NY5W8rTNQEu',
                    'to': '',
                    'value': Decimal('62.06400877'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'D6Ejj8zq6vF9PseK4HsZai83qyJbxYaigQ',
                    'to': '',
                    'value': Decimal('111.09531983'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': 'DJdxNcfjyoyanEvQ1QXab9FXNGUqACLyGP',
                    'to': '',
                    'value': Decimal('12890.97329953'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': '',
                    'to': 'DHkXF3Anv8jcXXpTAgZKcAxHiBGWXEzj5r',
                    'value': Decimal('8284.95656155'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                }, {
                    'type': 'MainCoin',
                    'symbol': 'DOGE',
                    'currency': Currencies.doge,
                    'from': '',
                    'to': 'DRG9Lo3W5f3EcThaAb4Aetrodj8gDChawR',
                    'value': Decimal('7414.95195987'),
                    'is_valid': True,
                    'token': None,
                    'memo': None,
                },
            ]
        }

        self.assertDictEqual(result, expected_result)

    def test_get_address_txs(self):
        self.api.request = Mock(side_effect=[BLOCK_HEAD_MOCK_RESPONSE, GET_ADDRESS_TXS_MOCK_RESPONSE])

        address = 'DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p'

        result = self.explorer.get_txs(address)

        print(result)

        expected = [
            {
                Currencies.doge: {
                    'amount': Decimal('302.44300000'),
                    'from_address': 'DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p',
                    'to_address': '',
                    'hash': '0a7e22e0e3abeb7fbefde459baa7c7816c340a93a56b7b97e23bb67e86bbc862',
                    'date': datetime.datetime.fromtimestamp(1724747542, tz=datetime.timezone.utc),
                    'memo': None,
                    'block': 5353254,
                    'confirmations': 2,
                    'address': 'DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p',
                    'direction': 'outgoing',
                    'raw': None,
                }
            }, {
                Currencies.doge: {
                    'amount': Decimal('93.44300000'),
                    'from_address': 'DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p',
                    'to_address': '',
                    'hash': '1f0f8a61475efb5a6331df05909f12b712a3a04b4ba6e36d076f9e6489df6d58',
                    'date': datetime.datetime.fromtimestamp(1724747516, tz=datetime.timezone.utc),
                    'memo': None,
                    'block': 5353253,
                    'confirmations': 3,
                    'address': 'DLPaeuaJi2JLUcvYHD4ddLxadwnGaVSt4p',
                    'direction': 'outgoing',
                    'raw': None,
                }
            },
        ]

        self.assertListEqual(result, expected)

    def test_get_block_txs(self):
        cache.set('latest_block_height_processed_doge', 5353254)
        self.api.request = Mock(side_effect=[BLOCK_HEAD_MOCK_RESPONSE, GET_BLOCK_TXS_MOCK_RESPONSE])

        addresses, txs_info, _ = self.explorer.get_latest_block(include_inputs=True, include_info=True)
        expected_addresses = {
            'input_addresses': {
                'DLReJq5m6oBvebCc9mDSgbjZJ9gCX9Anxy'
            },
            'output_addresses': {
                'DBgHW1Shjyk91fusm9hm3HcryNBwaFwZbQ',
                'DHLKGsxgFzHW6qtvSQUjx7e6q1ZZFRJ9hW'
            }
        }
        expected_txs_info = {
            'outgoing_txs': {
                'DLReJq5m6oBvebCc9mDSgbjZJ9gCX9Anxy': {
                    Currencies.doge: [
                        {
                            'tx_hash': '5e0766f759c91a7b2daffd29726fb728aeac4988d0f3de67eeddc4f562711177',
                            'value': Decimal('60.98307041'),
                            'contract_address': None,
                            'block_height': 5353255,
                            'symbol': 'DOGE'
                        }
                    ]
                }
            },
            'incoming_txs': {
                'DBgHW1Shjyk91fusm9hm3HcryNBwaFwZbQ': {
                    Currencies.doge: [
                        {
                            'tx_hash': 'df226336c694881ee4d43affba5b0c5d02267043ca9c6596c6fb311645c47402',
                            'value': Decimal('10000.45200000'),
                            'contract_address': None,
                            'block_height': 5353255,
                            'symbol': 'DOGE'
                        }
                    ]
                }, 'DHLKGsxgFzHW6qtvSQUjx7e6q1ZZFRJ9hW': {
                    Currencies.doge: [
                        {
                            'tx_hash': '5e0766f759c91a7b2daffd29726fb728aeac4988d0f3de67eeddc4f562711177',
                            'value': Decimal('60.98307041'),
                            'contract_address': None,
                            'block_height': 5353255,
                            'symbol': 'DOGE'
                        }
                    ]
                },
            }
        }

        assert BlockchainUtilsMixin.compare_dicts_without_order(addresses, expected_addresses)
        assert BlockchainUtilsMixin.compare_dicts_without_order(txs_info, expected_txs_info)

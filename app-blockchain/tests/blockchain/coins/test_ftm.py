from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock, patch

from exchange.base.models import Currencies
from exchange.blockchain.api.ftm.ftm_covalent import FantomCovalenthqAPI
from exchange.blockchain.api.ftm.ftm_ftmscan import FtmScanAPI
from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.api.ftm.ftm_web3 import FtmWeb3API
from exchange.blockchain.ftm import FantomBlockchainInspector
from exchange.blockchain.utils import APIError


class TestFantomBlockchainInspector(TestCase):
    ftm = FantomBlockchainInspector()
    address_list = ['0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B']
    address = '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F'

    def test_get_api(self):
        apis = {'web3': FtmWeb3API, 'graphql': FantomGraphQlAPI,
                   'ftmscan': FtmScanAPI, 'covalent': FantomCovalenthqAPI}

        for api in apis.keys():
            res = self.ftm.get_api_ftm(api)
            assert res == apis.get(api).get_api()

    def test_get_wallets_balance_ftmscan(self):
        data = [{'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'balance': Decimal('16.688079710496600000')}, {'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B', 'balance': Decimal('45.430019392313120961')}]

        ftmscan = FtmScanAPI()
        ftmscan.get_api().get_balances = Mock()
        ftmscan.get_api().get_balances.side_effect = [data, Exception]
        balances = self.ftm.get_wallets_balance_ftmscan(self.address_list)

        expected_result = [{'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'balance': Decimal('16.688079710496600000'), 'received': Decimal('16.688079710496600000'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}, {'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B', 'balance': Decimal('45.430019392313120961'), 'received': Decimal('45.430019392313120961'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]

        assert balances == expected_result

        balances = self.ftm.get_wallets_balance_ftmscan(self.address_list)

        assert balances == []

    def test_get_wallets_balance_covalent(self):
        first_response = {Currencies.usdt: {'symbol': 'FUSDT', 'balance': Decimal('990.000000'), 'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F'}, Currencies.ftm: {'symbol': 'FTM', 'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'amount': Decimal('17.244896544969635044')}, Currencies.dai: {'symbol': 'DAI', 'balance': Decimal('0.0'), 'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F'}}
        second_response = {Currencies.ftm: {'symbol': 'FTM', 'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B', 'amount': Decimal('0.628048474731162628')}, Currencies.usdt: {'symbol': 'FUSDT', 'balance': Decimal('0.0'), 'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B'}, Currencies.eth: {'symbol': 'WETH', 'balance': Decimal('0.0'), 'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B'}, Currencies.dai: {'symbol': 'DAI', 'balance': Decimal('0.0'), 'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B'}}
        expected_result = [{'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'balance': Decimal('17.244896544969635044'), 'received': Decimal('17.244896544969635044'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}, {'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B', 'balance': Decimal('0.628048474731162628'), 'received': Decimal('0.628048474731162628'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]

        FantomCovalenthqAPI.get_api().get_balance = Mock()
        FantomCovalenthqAPI().get_api().get_balance.side_effect = [first_response, second_response, APIError]
        balances = self.ftm.get_wallets_balance_covalent(self.address_list)

        assert balances == expected_result

        balances = self.ftm.get_wallets_balance_covalent(self.address_list)

        assert balances == []

    @patch.object(FantomBlockchainInspector, 'get_api_ftm')
    def test_get_wallets_balance_api(self, mock_get_api_ftm):
        first_response = {'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'balance': Decimal('17.244896544969635044')}
        second_response = {'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B', 'balance': Decimal('3.120265329364604669')}
        expected_result = [{'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'balance': Decimal('17.244896544969635044'), 'received': Decimal('17.244896544969635044'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}, {'address': '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B', 'balance': Decimal('3.120265329364604669'), 'received': Decimal('3.120265329364604669'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]

        mock_get_api_ftm.return_value = FantomGraphQlAPI.get_api()
        FantomGraphQlAPI.get_api().get_balance = Mock()
        FantomGraphQlAPI.get_api().get_balance.side_effect = [first_response, second_response, APIError]
        balances = self.ftm.get_wallets_balance_api(self.address_list)

        assert balances == expected_result

        balances = self.ftm.get_wallets_balance_api(self.address_list)

        self.assertFalse(balances)

    @patch.object(FantomBlockchainInspector, 'get_api_ftm')
    def test_get_wallet_transactions_ftm(self, mock_get_api_ftm):
        mock_get_api_ftm.return_value = FantomCovalenthqAPI.get_api()

        response = [{Currencies.ftm: {'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', 'from_address': ['0x80865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f'], 'to_address': '0xf491e7b69e4244ad4002bc14e878a34207e38c29', 'amount': Decimal('-7130.960202844167779828'), 'block': 29316801, 'date': '2022-01-28T20:43:30Z', 'confirmations': 44953, 'direction': 'outgoing', 'raw': {'block_signed_at': '2022-01-28T20:43:30Z', 'block_height': 29316801, 'tx_hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', 'tx_offset': 16, 'successful': True, 'from_address': '0x80865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f', 'from_address_label': None, 'to_address': '0xf491e7b69e4244ad4002bc14e878a34207e38c29', 'to_address_label': None, 'value': '7130960202844167779828', 'value_quote': 15183.136623966671, 'gas_offered': 222795, 'gas_spent': 127504, 'gas_price': 389718700000, 'gas_quote': 0.10580070021320898, 'gas_quote_rate': 2.129185438156128, 'log_events': [{'block_signed_at': '2022-01-28T20:43:30Z', 'block_height': 29316801, 'tx_offset': 16, 'log_offset': 58, 'tx_hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', '_raw_log_topics_bytes': None, 'raw_log_topics': ['0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822', '0x000000000000000000000000f491e7b69e4244ad4002bc14e878a34207e38c29', '0x00000000000000000000000080865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f'], 'sender_contract_decimals': 18, 'sender_name': 'Spooky LP', 'sender_contract_ticker_symbol': 'spLP', 'sender_address': '0x2b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c', 'sender_address_label': None, 'sender_logo_url': 'https://logos.covalenthq.com/tokens/250/0x2b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c.png', 'raw_log_data': '0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000018291f3db0a5618b5f40000000000000000000000000000000000000000000000000000000382678b220000000000000000000000000000000000000000000000000000000000000000', 'decoded': {'name': 'Swap', 'signature': 'Swap(indexed address sender, uint256 amount0In, uint256 amount1In, uint256 amount0Out, uint256 amount1Out, indexed address to)', 'params': [{'name': 'sender', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0xf491e7b69e4244ad4002bc14e878a34207e38c29'}, {'name': 'amount0In', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '0'}, {'name': 'amount1In', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '7130960202844167779828'}, {'name': 'amount0Out', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '15072725794'}, {'name': 'amount1Out', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '0'}, {'name': 'to', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0x80865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f'}]}}, {'block_signed_at': '2022-01-28T20:43:30Z', 'block_height': 29316801, 'tx_offset': 16, 'log_offset': 57, 'tx_hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', '_raw_log_topics_bytes': None, 'raw_log_topics': ['0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1'], 'sender_contract_decimals': 18, 'sender_name': 'Spooky LP', 'sender_contract_ticker_symbol': 'spLP', 'sender_address': '0x2b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c', 'sender_address_label': None, 'sender_logo_url': 'https://logos.covalenthq.com/tokens/250/0x2b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c.png', 'raw_log_data': '0x000000000000000000000000000000000000000000000000000051876ace10c2000000000000000000000000000000000000000000230435d0a0c25e1be04a3e', 'decoded': {'name': 'Sync', 'signature': 'Sync(uint112 reserve0, uint112 reserve1)', 'params': [{'name': 'reserve0', 'type': 'uint112', 'indexed': False, 'decoded': True, 'value': '89642054324418'}, {'name': 'reserve1', 'type': 'uint112', 'indexed': False, 'decoded': True, 'value': '42332285863108671914920510'}]}}, {'block_signed_at': '2022-01-28T20:43:30Z', 'block_height': 29316801, 'tx_offset': 16, 'log_offset': 56, 'tx_hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', '_raw_log_topics_bytes': None, 'raw_log_topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', '0x0000000000000000000000002b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c', '0x00000000000000000000000080865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f'], 'sender_contract_decimals': 6, 'sender_name': 'USD Coin', 'sender_contract_ticker_symbol': 'USDC', 'sender_address': '0x04068da6c83afcfa0e13ba15a6696662335d5b75', 'sender_address_label': None, 'sender_logo_url': 'https://logos.covalenthq.com/tokens/1/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.png', 'raw_log_data': '0x0000000000000000000000000000000000000000000000000000000382678b22', 'decoded': {'name': 'Transfer', 'signature': 'Transfer(indexed address from, indexed address to, uint256 value)', 'params': [{'name': 'from', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0x2b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c'}, {'name': 'to', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0x80865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f'}, {'name': 'value', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '15072725794'}]}}, {'block_signed_at': '2022-01-28T20:43:30Z', 'block_height': 29316801, 'tx_offset': 16, 'log_offset': 55, 'tx_hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', '_raw_log_topics_bytes': None, 'raw_log_topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', '0x000000000000000000000000f491e7b69e4244ad4002bc14e878a34207e38c29', '0x0000000000000000000000002b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c'], 'sender_contract_decimals': 18, 'sender_name': 'Wrapped Fantom', 'sender_contract_ticker_symbol': 'WFTM', 'sender_address': '0x21be370d5312f44cb42ce377bc9b8a0cef1a4c83', 'sender_address_label': None, 'sender_logo_url': 'https://logos.covalenthq.com/tokens/1/0x4e15361fd6b4bb609fa63c81a2be19d873717870.png', 'raw_log_data': '0x00000000000000000000000000000000000000000000018291f3db0a5618b5f4', 'decoded': {'name': 'Transfer', 'signature': 'Transfer(indexed address from, indexed address to, uint256 value)', 'params': [{'name': 'from', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0xf491e7b69e4244ad4002bc14e878a34207e38c29'}, {'name': 'to', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0x2b4c76d0dc16be1c31d4c1dc53bf9b45987fc75c'}, {'name': 'value', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '7130960202844167779828'}]}}, {'block_signed_at': '2022-01-28T20:43:30Z', 'block_height': 29316801, 'tx_offset': 16, 'log_offset': 54, 'tx_hash': '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7', '_raw_log_topics_bytes': None, 'raw_log_topics': ['0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef', '0x0000000000000000000000000000000000000000000000000000000000000000', '0x000000000000000000000000f491e7b69e4244ad4002bc14e878a34207e38c29'], 'sender_contract_decimals': 18, 'sender_name': 'Wrapped Fantom', 'sender_contract_ticker_symbol': 'WFTM', 'sender_address': '0x21be370d5312f44cb42ce377bc9b8a0cef1a4c83', 'sender_address_label': None, 'sender_logo_url': 'https://logos.covalenthq.com/tokens/1/0x4e15361fd6b4bb609fa63c81a2be19d873717870.png', 'raw_log_data': '0x00000000000000000000000000000000000000000000018291f3db0a5618b5f4', 'decoded': {'name': 'Transfer', 'signature': 'Transfer(indexed address from, indexed address to, uint256 value)', 'params': [{'name': 'from', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0x0000000000000000000000000000000000000000'}, {'name': 'to', 'type': 'address', 'indexed': True, 'decoded': True, 'value': '0xf491e7b69e4244ad4002bc14e878a34207e38c29'}, {'name': 'value', 'type': 'uint256', 'indexed': False, 'decoded': True, 'value': '7130960202844167779828'}]}}]}}}, {Currencies.ftm: {'address': '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F', 'hash': '0x092a180e96a96ca38e0cc0852b35260502cf4440678e3ee413a2b6310d97781d', 'from_address': ['0xebf4fbb9c81b84dd5cf89bc75588e5d0018501b3'], 'to_address': '0x80865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f', 'amount': Decimal('7148.990000000000000000'), 'block': 29316544, 'date': '2022-01-28T20:38:09Z', 'confirmations': 45210, 'direction': 'incoming', 'raw': {'block_signed_at': '2022-01-28T20:38:09Z', 'block_height': 29316544, 'tx_hash': '0x092a180e96a96ca38e0cc0852b35260502cf4440678e3ee413a2b6310d97781d', 'tx_offset': 3, 'successful': True, 'from_address': '0xebf4fbb9c81b84dd5cf89bc75588e5d0018501b3', 'from_address_label': None, 'to_address': '0x80865b3e4de3bdd6ca05a4c64bc4c3a361d0b85f', 'to_address_label': None, 'value': '7148990000000000000000', 'value_quote': 15221.525405523776, 'gas_offered': 100000, 'gas_spent': 28900, 'gas_price': 533134050000, 'gas_quote': 0.032805582293926314, 'gas_quote_rate': 2.129185438156128, 'log_events': []}}}]

        FantomCovalenthqAPI.get_api().get_txs = Mock()
        FantomCovalenthqAPI.get_api().get_txs.side_effect = [response, APIError]
        txs = self.ftm.get_wallet_transactions_ftm(self.address)

        assert txs[0].hash == '0x6b2bf9e16cc88615650f4f2bc04200b8f47053a2e477dadc44136796cd96d2e7'
        assert txs[0].address == '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F'
        assert txs[0].value == Decimal('-7130.960202844167779828')
        assert txs[0].block == 29316801

        assert txs[1].hash == '0x092a180e96a96ca38e0cc0852b35260502cf4440678e3ee413a2b6310d97781d'
        assert txs[1].address == '0x80865B3E4dE3bDd6ca05A4C64Bc4C3A361D0B85F'
        assert txs[1].value == Decimal('7148.990000000000000000')
        assert txs[1].block == 29316544

        txs = self.ftm.get_wallet_transactions_ftm(self.address)
        self.assertFalse(txs)

    @patch.object(FantomBlockchainInspector, 'get_api_ftm')
    def test_get_latest_block(self, mock_get_api_ftm):
        mock_get_api_ftm.return_value = FtmWeb3API.get_api()
        response = ({'0x442C0eC1F0900556676135E86e01700E418d6b4c', '0x5563540fa1204fFdf68bc5a69c138AcEDF65e48E', '0xD0c4762Db1da7f471BB327660cc2c21C0851F279', '0x6803B5575B704AB202DbefAddEd66cCA404489Ff', '0x896e077c6A84f37123700b33D4a2C991Def328d8', '0xDDc4f86ABe52EDA103400169CEF0495813e15be3', '0x1b7d657C853EA0c630041153e51da9A66D9289E6', '0xEBf4FBB9C81b84dd5CF89BC75588E5d0018501b3', '0xCDb5Ff63D0c76827b0d4069073224a7a7AF4aA28'},
                    {'0x5563540fa1204fFdf68bc5a69c138AcEDF65e48E': {Currencies.ftm: [{'tx_hash': '0xbd700fa16b4024ecb3aa50005b48b580a347f6eb63174814f9bdfe5f0f99123a', 'value': Decimal('0.993996920185900000'), 'direction': 'outgoing'}], 'default_factory': []}, '0xDDc4f86ABe52EDA103400169CEF0495813e15be3': {Currencies.ftm: [{'tx_hash': '0xbd700fa16b4024ecb3aa50005b48b580a347f6eb63174814f9bdfe5f0f99123a', 'value': Decimal('0.993996920185900000'), 'direction': 'incoming'}]}, '0x6803B5575B704AB202DbefAddEd66cCA404489Ff': {Currencies.ftm: [{'tx_hash': '0xfd5e26cebb9874d938a699c819eaaf69cddfed8612cb75f16e7997334daa3c89', 'value': Decimal('0.0'), 'direction': 'outgoing'}]}, '0x896e077c6A84f37123700b33D4a2C991Def328d8': {Currencies.ftm: [{'tx_hash': '0xfd5e26cebb9874d938a699c819eaaf69cddfed8612cb75f16e7997334daa3c89', 'value': Decimal('0.0'), 'direction': 'incoming'}]}, '0xEBf4FBB9C81b84dd5CF89BC75588E5d0018501b3': {Currencies.ftm: [{'tx_hash': '0xddd65fbba09e87401e57edec1f5ba702bdce33d3ee2c7c4e7b14b6092f7f90d8', 'value': Decimal('66.255101590000000000'), 'direction': 'outgoing'}, {'tx_hash': '0x9887e6599585a31f573387962e1ce443726ec048a9eea3fc1742274137df37ad', 'value': Decimal('10.990000000000000000'), 'direction': 'outgoing'}, {'tx_hash': '0xc32db52b25ac772bbefec4562d7605ee130e9cb1afb0cf85f8e6d45f3fcbc84d', 'value': Decimal('508.481000000000000000'), 'direction': 'outgoing'}, {'tx_hash': '0x7e4de3e052a20ffb6d223429e7a0c3c75bb11798eacba0d96975597bee2deb63', 'value': Decimal('142.854150000000000000'), 'direction': 'outgoing'}]}, '0x1b7d657C853EA0c630041153e51da9A66D9289E6': {Currencies.ftm: [{'tx_hash': '0xddd65fbba09e87401e57edec1f5ba702bdce33d3ee2c7c4e7b14b6092f7f90d8', 'value': Decimal('66.255101590000000000'), 'direction': 'incoming'}]}, '0x442C0eC1F0900556676135E86e01700E418d6b4c': {Currencies.ftm: [{'tx_hash': '0x9887e6599585a31f573387962e1ce443726ec048a9eea3fc1742274137df37ad', 'value': Decimal('10.990000000000000000'), 'direction': 'incoming'}]}, '0xCDb5Ff63D0c76827b0d4069073224a7a7AF4aA28':{Currencies.ftm: [{'tx_hash': '0xc32db52b25ac772bbefec4562d7605ee130e9cb1afb0cf85f8e6d45f3fcbc84d', 'value': Decimal('508.481000000000000000'), 'direction': 'incoming'}]}, '0xD0c4762Db1da7f471BB327660cc2c21C0851F279': {Currencies.ftm: [{'tx_hash': '0x7e4de3e052a20ffb6d223429e7a0c3c75bb11798eacba0d96975597bee2deb63', 'value': Decimal('142.854150000000000000'), 'direction': 'incoming'}]}})

        FtmWeb3API.get_api().get_latest_block = Mock()
        FtmWeb3API.get_api().get_latest_block.side_effect = [response, APIError]
        addresses = self.ftm.get_latest_block_addresses()

        assert addresses == response

        addresses = self.ftm.get_latest_block_addresses()
        self.assertIsNone(addresses)





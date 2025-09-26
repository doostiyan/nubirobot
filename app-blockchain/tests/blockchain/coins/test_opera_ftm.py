import datetime
from collections import defaultdict
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock, patch

from exchange.base.models import Currencies
from exchange.blockchain.aave import AaveBlockchainInspector
from exchange.blockchain.api.ftm.ftm_covalent import FantomCovalenthqAPI
from exchange.blockchain.api.ftm.ftm_ftmscan import FtmScanAPI
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency
from exchange.blockchain.opera_ftm import OperaFTMBlockchainInspector
from exchange.blockchain.utils import APIError


class TestOperaFTMBlockchainInspector(TestCase):
    opera_ftm = OperaFTMBlockchainInspector()
    address_list = ['0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', '0x89d9bc2f2d091cfbfc31e333d6dc555ddbc2fd29']
    address = '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'

    def test_opera_ftm_contract_currency_list(self):
        network = 'mainnet'
        mainnet_contracts = self.opera_ftm.opera_ftm_contract_currency_list(network)

        assert mainnet_contracts == opera_ftm_contract_currency.get(network)

    def test_get_wallets_balance_covalent(self):
        first_response = {Currencies.aave: {'symbol': 'AAVE', 'balance': Decimal('13.928758000333637119'), 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'}, Currencies.usdt: {'symbol': 'FUSDT', 'balance': Decimal('1956.960829'), 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'}, Currencies.dai: {'symbol': 'DAI', 'balance': Decimal('1223.598419201115069984'), 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'}, Currencies.btc: {'symbol': 'WBTC', 'balance': Decimal('7.62152E-13'), 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'}, Currencies.ftm: {'symbol': 'FTM', 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'amount': Decimal('63.143595298971925704')}, Currencies.eth: {'symbol': 'WETH', 'balance': Decimal('0.012559872098282761'), 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'}, Currencies.link: {'symbol': 'ChainLink', 'balance': Decimal('0.492502748558797611'), 'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'}}
        second_response = {Currencies.link: {'symbol': 'ChainLink', 'balance': Decimal('406595.367781088790476129'), 'address': '0x89d9bc2f2d091cfbfc31e333d6dc555ddbc2fd29'}, Currencies.ftm: {'symbol': 'FTM', 'address': '0x89d9bc2f2d091cfbfc31e333d6dc555ddbc2fd29', 'amount': Decimal('0.0')}}
        expected_result = defaultdict(list, {Currencies.aave: [{'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'balance': Decimal('13.928758000333637119'), 'received': Decimal('13.928758000333637119'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]})


        FantomCovalenthqAPI.get_api().get_balance = Mock()
        FantomCovalenthqAPI.get_api().get_balance.side_effect = [first_response, second_response, APIError]

        balances = AaveBlockchainInspector().get_wallets_balance_ftm_covalent(self.address_list)

        assert balances == expected_result

        balances = AaveBlockchainInspector().get_wallets_balance_ftm_covalent(self.address_list)

        self.assertEqual(balances, defaultdict(list))

    @patch.object(AaveBlockchainInspector, 'get_fantom_api')
    def test_get_wallets_balance_api(self, mock_get_fantom_api):
        first_response = {'symbol': 'AAVE', 'amount': Decimal('15.674955625667373614'), 'address': '1'}
        second_response = {'symbol': 'AAVE', 'amount': Decimal('0.0'), 'address': '0x89d9bC2F2d091CfBFc31e333D6Dc555dDBc2fd29'}
        expected_result = defaultdict(list, {Currencies.aave: [{'address': '1', 'balance': Decimal('15.674955625667373614'), 'received': Decimal('15.674955625667373614'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}, {'address': '0x89d9bC2F2d091CfBFc31e333D6Dc555dDBc2fd29', 'balance': Decimal('0.0'), 'received': Decimal('0.0'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]})

        mock_get_fantom_api.return_value = FtmScanAPI.get_api()
        FtmScanAPI.get_api().get_token_balance = Mock()
        FtmScanAPI.get_api().get_token_balance.side_effect = [first_response, second_response, APIError]
        balances = AaveBlockchainInspector().get_wallets_balance_ftm(self.address_list)

        assert balances == expected_result

        balances = AaveBlockchainInspector().get_wallets_balance_ftm(self.address_list)
        self.assertEqual(balances, defaultdict(list))

    def test_get_wallet_transactions_ftm_covalent(self):
        response = [{Currencies.aave: {'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'hash': '0xcd0b89e7ec0a16bed753cff9d1559487bfa0b6693daca7d678264eb3e2b59521', 'from_address': ['0xebf374bb21d83cf010cc7363918776adf6ff2bf6'], 'to_address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'amount': Decimal('3.444871573594880344'), 'block': 29669933, 'date': '2022-02-01T09:46:19Z', 'confirmations': 859, 'direction': 'incoming', 'raw': {'block_signed_at': '2022-02-01T09:46:19Z', 'block_height': 29669933, 'tx_hash': '0xcd0b89e7ec0a16bed753cff9d1559487bfa0b6693daca7d678264eb3e2b59521', 'tx_offset': 5, 'successful': True, 'from_address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'from_address_label': None, 'to_address': '0xf491e7b69e4244ad4002bc14e878a34207e38c29', 'to_address_label': None, 'value': '0', 'value_quote': None, 'gas_offered': 232648, 'gas_spent': 122023, 'gas_price': 335541720000, 'gas_quote': 0.08624081484459456, 'gas_quote_rate': 2.106321334838867, 'transfers': [{'block_signed_at': '2022-02-01T09:46:19Z', 'tx_hash': '0xcd0b89e7ec0a16bed753cff9d1559487bfa0b6693daca7d678264eb3e2b59521', 'from_address': '0xebf374bb21d83cf010cc7363918776adf6ff2bf6', 'from_address_label': None, 'to_address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'to_address_label': None, 'contract_decimals': 18, 'contract_name': 'Aave', 'contract_ticker_symbol': 'AAVE', 'contract_address': '0x6a07a792ab2965c72a5b8088d3a069a7ac3a993b', 'logo_url': 'https://logos.covalenthq.com/tokens/0x6a07a792ab2965c72a5b8088d3a069a7ac3a993b.png', 'transfer_type': 'IN', 'delta': '3444871573594880344', 'balance': None, 'quote_rate': 163.43763732910156, 'delta_quote': 563.0216708905315, 'balance_quote': None, 'method_calls': None}]}}}]

        FantomCovalenthqAPI.get_api().get_token_txs = Mock()
        FantomCovalenthqAPI.get_api().get_token_txs.side_effect = [response, APIError]
        txs = AaveBlockchainInspector().get_wallet_transactions_ftm_covalent(self.address)
        tx = txs.get(Currencies.aave)[0]

        assert tx.hash == '0xcd0b89e7ec0a16bed753cff9d1559487bfa0b6693daca7d678264eb3e2b59521'
        assert tx.address == '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'
        assert tx.value == Decimal('3.444871573594880344')
        assert tx.block == 29669933

        txs = self.opera_ftm.get_wallet_transactions_ftm_covalent(self.address)
        self.assertEqual(txs, defaultdict(list))


    def test_get_wallet_transactions_ftmscan(self):
        response = [{Currencies.aave: {'address': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'from_address': ['0xebf374bb21d83cf010cc7363918776adf6ff2bf6'], 'block': 29676096, 'hash': '0xc5f133767c9f41d702e792bb413ebee7c07569127ddfe4afb4c703a4ca45b1b7', 'date': datetime.datetime(2022, 2, 1, 11, 12, 13, tzinfo=datetime.timezone.utc), 'amount': Decimal('1.741186288336256761'), 'confirmations': 1245, 'raw': {'blockNumber': '29676096', 'timeStamp': '1643713933', 'hash': '0xc5f133767c9f41d702e792bb413ebee7c07569127ddfe4afb4c703a4ca45b1b7', 'nonce': '153382', 'blockHash': '0x00012e9400000503c3f0b4f83812f53dfd602f731e2e624721e3f6cc07b11111', 'from': '0xebf374bb21d83cf010cc7363918776adf6ff2bf6', 'contractAddress': '0x6a07a792ab2965c72a5b8088d3a069a7ac3a993b', 'to': '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3', 'value': '1741186288336256761', 'tokenName': 'Aave', 'tokenSymbol': 'AAVE', 'tokenDecimal': '18', 'transactionIndex': '4', 'gas': '232672', 'gasPrice': '293073600000', 'gasUsed': '122036', 'cumulativeGasUsed': '598037', 'input': 'deprecated', 'confirmations': '1245'}}}]

        FtmScanAPI.get_api().get_token_txs = Mock()
        FtmScanAPI.get_api().get_token_txs.side_effect = [response, APIError]
        txs = AaveBlockchainInspector().get_wallet_transactions_ftmscan(self.address)
        tx = txs.get(Currencies.aave)[0]

        assert tx.hash == '0xc5f133767c9f41d702e792bb413ebee7c07569127ddfe4afb4c703a4ca45b1b7'
        assert tx.address == '0x23abcb82f468e3422a7212d4ad47cc2dd39162a3'
        assert tx.value == Decimal('1.741186288336256761')
        assert tx.block == 29676096

        txs = self.opera_ftm.get_wallet_transactions_ftmscan(self.address)
        self.assertEqual(txs, defaultdict(list))

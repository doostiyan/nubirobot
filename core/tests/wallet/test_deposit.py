import copy
import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytz
from django.test import Client, TestCase, override_settings
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, User, UserRestriction, VerificationProfile
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import ADDRESS_TYPE, NOT_COIN, Currencies, get_currency_codename
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.models import Transaction as BlockchainTransaction
from exchange.blockchain.segwit_address import eth_to_one_address
from exchange.wallet.deposit import (
    confirm_bitcoin_deposits,
    confirm_tagged_deposits,
    grab_tagcoins_deposit_address,
    save_deposit_from_blockchain_transaction,
    save_deposit_from_blockchain_transaction_tagged,
    tag_coins_addresses,
)
from exchange.wallet.models import (
    AvailableDepositAddress,
    BlacklistWalletAddress,
    ConfirmedWalletDeposit,
    Wallet,
    WalletDepositAddress,
    WalletDepositTag,
)
from tests.base.utils import create_deposit, dummy_caching


class WalletsTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)

    def test_get_deposit_address_usdt_only_eth(self):
        usdt = Currencies.usdt
        eth_address = '0xF4727615f7647f68078f5e2B5a36f385B895552B'
        wallet = Wallet.get_user_wallet(self.user, usdt)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=eth_address,
            network='ETH',
        )
        address = wallet.get_current_deposit_address(create=False, network='ETH', use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address.address == '0xF4727615f7647f68078f5e2B5a36f385B895552B'
        address = wallet.get_current_deposit_address(create=False, use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address is None
        address = wallet.get_current_deposit_address(create=False, network='TRX', use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address is None

    def test_get_deposit_address_only_trx(self):
        usdt = Currencies.usdt
        trx_address = 'TPovp4DFFFu9gGrscaDgmkJ3ZUu8Vse6za'
        wallet = Wallet.get_user_wallet(self.user, usdt)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=trx_address,
            network='TRX',
        )
        address = wallet.get_current_deposit_address(create=False, network='TRX', use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address.address == 'TPovp4DFFFu9gGrscaDgmkJ3ZUu8Vse6za'
        address = wallet.get_current_deposit_address(create=False, use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address.address == 'TPovp4DFFFu9gGrscaDgmkJ3ZUu8Vse6za'
        address = wallet.get_current_deposit_address(create=False, network='ETH', use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address is None

    def test_get_deposit_address_create(self):
        usdt = Currencies.usdt
        trx_address = 'TPovp4DFFFu9gGrscaDgmkJ3ZUu8Vse6za'
        eth_address = '0xF4727615f7647f68078f5e2B5a36f385B895552B'
        wallet = Wallet.get_user_wallet(self.user, usdt)
        addr_trx = AvailableDepositAddress.objects.create(
            address=trx_address,
            currency=Currencies.trx
        )
        addr_eth = AvailableDepositAddress.objects.create(
            address=eth_address,
            currency=Currencies.eth
        )
        address = wallet.get_current_deposit_address(create=True, network='TRX', use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address.address == 'TPovp4DFFFu9gGrscaDgmkJ3ZUu8Vse6za'
        address = wallet.get_current_deposit_address(create=True, network='ETH', use_cache=False, address_type=ADDRESS_TYPE.standard)
        assert address.address == '0xF4727615f7647f68078f5e2B5a36f385B895552B'

    def test_deposit_litecoin(self):
        ltc = Currencies.ltc
        ltc_address = 'LezhvSsYxyXo3MHen1khthBPBLwx9eD95Y'
        tx_hash = '68e4221dbb9dc4f19d0b969d70f9f8bdadf32186873d40bb1a340dd08bf362b4'
        tx_amount = Decimal('1.59')
        tx_date = datetime.datetime(2019, 2, 21, 6, 20, 31, 0, pytz.utc)
        wallet = Wallet.get_user_wallet(self.user, ltc)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=ltc_address,
        )
        tx = BlockchainTransaction(
            address=ltc_address,
            hash=tx_hash,
            timestamp=tx_date,
            value=tx_amount,
            confirmations=6,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, addr)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 1
        deposit = confirmed_deposits[0]
        assert deposit.address == addr
        assert deposit.tx_hash == tx_hash
        assert deposit.confirmed
        assert deposit.amount == tx_amount
        assert deposit.transaction
        assert deposit.transaction.amount == tx_amount
        assert deposit.transaction.wallet == wallet
        assert deposit.tag is None

    def test_deposit_litecoin_disabled(self):
        ltc = Currencies.ltc
        ltc_address = 'LezhvSsYxyXo3MHen1khthBPBLwx9eD95Y'
        tx_hash = '68e4221dbb9dc4f19d0b969d70f9f8bdadf32186873d40bb1a340dd08bf362b4'
        tx_amount = Decimal('1.59')
        tx_date = datetime.datetime(2019, 2, 21, 6, 20, 31, 0, pytz.utc)
        wallet = Wallet.get_user_wallet(self.user, ltc)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=ltc_address,
            is_disabled=True,
        )
        tx = BlockchainTransaction(
            address=ltc_address,
            hash=tx_hash,
            timestamp=tx_date,
            value=tx_amount,
            confirmations=6,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, addr)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 0

    def test_deposit_trx_dust_value(self):
        trx = Currencies.trx
        trx_address = 'TAUN6FwrnwwmaEqYcckffC7wYmbaS6cBiX'
        tx_hash = '18f52726a5edd2bd97484da97f29920607f845fe6fe5e8f9add2da49d71df1ce'
        tx_amount = Decimal('0.000001')
        tx_date = datetime.datetime(2021, 6, 5, 11, 56, 39, 0)
        wallet = Wallet.get_user_wallet(self.user, trx)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=trx_address,
        )
        tx = BlockchainTransaction(
            address=trx_address,
            hash=tx_hash,
            timestamp=tx_date,
            value=tx_amount,
            confirmations=1,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, addr)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 0

    def test_deposit_usdt_eth_fee_value(self):
        usdt = Currencies.usdt
        eth_address = '0xC51e20f3D25Dfdf6202D175406A592634870a31f'
        tx_hash = '0x649996a719b1b52d4ba9fda7f243eef227ebce2b87cdc64192bbccfe697705d6'
        tx_amount = Decimal('112')
        tx_date = datetime.datetime(2021, 6, 5, 9, 00, 11, 0, pytz.utc)
        wallet = Wallet.get_user_wallet(self.user, usdt)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=eth_address,
        )
        tx = BlockchainTransaction(
            address=eth_address,
            hash=tx_hash,
            timestamp=tx_date,
            value=tx_amount,
            confirmations=12,
            is_double_spend=False,
        )
        assert wallet.currency == 13
        save_deposit_from_blockchain_transaction(tx, addr)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 1
        deposit = confirmed_deposits[0]
        tx_amount = tx_amount - Decimal(CURRENCY_INFO[usdt]['network_list']['ETH'].get('deposit_info', {}).get('standard', {}).get('deposit_fee', '0'))
        assert deposit.address == addr
        assert deposit.tx_hash == tx_hash[2:]
        assert deposit.confirmed
        assert deposit.amount == tx_amount
        assert deposit.transaction
        assert deposit.transaction.amount == tx_amount
        assert deposit.transaction.wallet == wallet
        assert deposit.tag is None


class DepositsApiTest(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_deposits_list(self, filters=None, results=None, has_next=False):
        data = self.client.get('/users/wallets/deposits/list', filters).json()
        assert data
        assert data['status'] == 'ok'
        assert len(data['deposits']) == len(results)
        assert {item['id'] for item in data['deposits']} == {w.id for w in results}
        assert data['hasNext'] == has_next

    def _test_unsuccessful_deposits_list(self, wallet, status_code):
        response = self.client.get('/users/wallets/deposits/list', {'wallet': wallet.id})
        assert response.status_code == status_code

    def test_deposits_list_no_deposits(self):
        self._test_successful_deposits_list(results=[])

    def create_deposit(self, currency, amount, **kwargs):
        address = '0xC51e20f3D25Dfdf6202D175406A592634870a31f'
        tx_hash = '0x649996a719b1b52d4ba9fda7f243eef227ebce2b87cdc64192bbccfe697705d6'
        create_deposit(self.user, currency, Decimal(amount), address, tx_hash, **kwargs)

    def test_deposits_list_crypto_wallet_deposits(self):
        self.create_deposit(Currencies.btc, '0.03')
        self.create_deposit(Currencies.btc, '0.01')
        self.create_deposit(Currencies.eth, '0.6')
        deposits = list(ConfirmedWalletDeposit.objects.order_by('pk'))
        assert len(deposits) == 3
        self._test_successful_deposits_list({'wallet': deposits[0]._wallet_id}, results=deposits[:2])

    def test_deposits_list_crypto_wallet_deposits_currency_symbol(self):
        self.create_deposit(Currencies.btc, '0.03')
        deposits = list(ConfirmedWalletDeposit.objects.order_by('pk'))

        data = self.client.get('/users/wallets/deposits/list', {'wallet': deposits[0]._wallet_id}).json()
        assert data
        assert data['status'] == 'ok'
        assert len(data['deposits']) == 1
        assert 'currencySymbol' in data['deposits'][0]
        assert data['deposits'][0]['currencySymbol'] == get_currency_codename(Currencies.btc)

    def test_deposits_list_date_filter(self):
        self.create_deposit(Currencies.btc, '0.01')
        self.create_deposit(Currencies.usdt, '140')
        self.create_deposit(Currencies.btc, '0.02')
        deposits = list(ConfirmedWalletDeposit.objects.order_by('pk'))
        deposits[0].created_at = '2022-04-03 17:10:00.000+03:30'
        deposits[1].created_at = '2022-04-09 21:45:00.000+03:30'
        deposits[2].created_at = '2022-04-11 08:19:00.000+03:30'
        ConfirmedWalletDeposit.objects.bulk_update(deposits, ('created_at',))
        wallet = deposits[0]._wallet_id
        self._test_successful_deposits_list(
            {'wallet': wallet, 'from': '2022-04-01', 'to': '2022-04-10'}, results=[deposits[0]]
        )
        self._test_successful_deposits_list(
            {'wallet': wallet, 'from': '2022-04-05', 'to': '2022-04-15'}, results=[deposits[2]]
        )
        self._test_successful_deposits_list(
            {'wallet': wallet, 'from': '2022-04-01', 'to': '2022-04-15'}, results=[deposits[0], deposits[2]]
        )

    def test_deposits_list_pagination(self):
        for _ in range(23):
            self.create_deposit(Currencies.usdt, 100)
        for _ in range(5):
            self.create_deposit(Currencies.btc, '0.01')
        deposits = list(ConfirmedWalletDeposit.objects.order_by('pk'))
        assert len(deposits) == 28
        wallet = deposits[0]._wallet_id
        self._test_successful_deposits_list({'wallet': wallet}, results=deposits[3:23], has_next=True)
        self._test_successful_deposits_list({'wallet': wallet, 'page': 2}, results=deposits[:3], has_next=False)
        self._test_successful_deposits_list({'wallet': wallet, 'pageSize': 30}, results=deposits[:23], has_next=False)
        self._test_successful_deposits_list({'wallet': wallet, 'pageSize': 5}, results=deposits[18:23], has_next=True)
        self._test_successful_deposits_list(
            {'wallet': wallet, 'pageSize': 10, 'page': 3}, results=deposits[:3], has_next=False
        )

    def test_deposits_list_wrong_wallet(self):
        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        self._test_unsuccessful_deposits_list(margin_wallet, status.HTTP_404_NOT_FOUND)

        other_user = User.objects.get(pk=202)
        other_user_wallet = Wallet.get_user_wallet(other_user, Currencies.rls)
        self._test_unsuccessful_deposits_list(other_user_wallet, status.HTTP_400_BAD_REQUEST)

    def _test_unsuccessful_deposits_refresh(self, wallet, status_code):
        response = self.client.post('/users/wallets/deposits/refresh', {'wallet': wallet.id})
        assert response.status_code == status_code
        assert response.json() == {'error': 'NotFound', 'message': 'No Wallet matches the given query.'}

    @patch('exchange.wallet.views.refresh_wallet_deposits')
    def test_deposits_refresh_wallet_success(self, mock_refresh_wallet_deposits):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        response = self.client.post('/users/wallets/deposits/refresh', {'wallet': wallet.id})
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
        mock_refresh_wallet_deposits.assert_called_once_with(wallet, run_now=False)

    def test_deposits_refresh_wrong_wallet_id(self):
        response = self.client.post('/users/wallets/deposits/refresh', {'wallet': 'not-int'})
        assert response.status_code == 400
        assert response.json() == {
            'status': 'failed',
            'code': 'ParseError',
            'message': 'Invalid integer value: "not-int"',
        }

    def test_deposits_refresh_missing_wallet_id(self):
        response = self.client.post('/users/wallets/deposits/refresh')
        assert response.status_code == 400
        assert response.json() == {'status': 'failed', 'code': 'ParseError', 'message': 'Missing integer value'}

    def test_deposits_refresh_wrong_wallet(self):
        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        self._test_unsuccessful_deposits_refresh(margin_wallet, status.HTTP_404_NOT_FOUND)

        other_user = User.objects.get(pk=202)
        other_user_wallet = Wallet.get_user_wallet(other_user, Currencies.rls)
        self._test_unsuccessful_deposits_refresh(other_user_wallet, status.HTTP_404_NOT_FOUND)


class AvaxTest(TestCase):
    @classmethod
    def setUpClass(cls):
        # Start overriding settings at the class level
        cls.settings_override = override_settings(EOA_V1_ENABLED=False)
        cls.settings_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Revert the settings override after all tests in the class
        cls.settings_override.disable()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        avax = Currencies.avax
        cls.user = User.objects.get(pk=201)
        eth_address = '0x5b3857c22d0C65668f1A38946486F8Af6Ae3A37a'
        cls.eth_wallet = Wallet.get_user_wallet(user=cls.user, currency=Currencies.eth)
        cls.eth_deposit = WalletDepositAddress.objects.create(
            wallet=cls.eth_wallet,
            address=eth_address,
            currency=Currencies.eth,
            network=CurrenciesNetworkName.ETH,
            type=ADDRESS_TYPE.contract2
        )
        cls.avax_wallet = Wallet.get_user_wallet(cls.user, avax)
        cls.avax_deposit = cls.avax_wallet.get_current_deposit_address(create=True)

    def test_get_deposits_address_avax(self):
        assert self.avax_deposit.network == CurrenciesNetworkName.AVAX
        assert self.avax_deposit.address == self.eth_deposit.address  # to make sure avax will reuse eth address

    def test_deposit_avax(self):
        tx1 = BlockchainTransaction(
            address=self.avax_deposit.address,
            hash='0x6fd6c01a9769c8d88bf2230b8f04b128529057f47d848f81767689d8256e63ad',
            timestamp=datetime.datetime(2019, 2, 21, 6, 20, 31, 0, pytz.utc),
            value=Decimal('20'),
            confirmations=12,  # to be confirmed
            is_double_spend=False,
        )
        tx2 = BlockchainTransaction(
            address=self.avax_deposit.address,
            hash='0x6fd6c01a9769c8d88bf22308b0f4b128529057f47d848f81767689d8256e63ad',
            timestamp=datetime.datetime(2020, 2, 21, 6, 20, 31, 0, pytz.utc),
            value=Decimal('10'),
            confirmations=11,  # to not to be confirmed
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx1, self.avax_deposit)
        save_deposit_from_blockchain_transaction(tx2, self.avax_deposit)
        self.avax_wallet.refresh_from_db()
        assert self.avax_wallet.balance == Decimal('20')

    def test_deposit_avax_disabled(self):
        self.avax_deposit.is_disabled = True
        self.avax_deposit.save(update_fields=['is_disabled'])
        tx = BlockchainTransaction(
            address=self.avax_deposit.address,
            hash='0x6fd6c01a9769c8d88bf2230b8f04b128529057f47d848f81767689d8256e3ad6',
            timestamp=datetime.datetime(2021, 2, 21, 6, 20, 31, 0, pytz.utc),
            value=Decimal('20'),
            confirmations=12,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, self.avax_deposit)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 0


class HarmonyTest(TestCase):
    @classmethod
    def setUpClass(cls):
        # Start overriding settings at the class level
        cls.settings_override = override_settings(EOA_V1_ENABLED=False)
        cls.settings_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Revert the settings override after all tests in the class
        cls.settings_override.disable()
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        harmony = Currencies.one
        cls.user = User.objects.get(pk=201)
        eth_address = '0x5b3857c22d0C65668f1A38946486F8Af6Ae3A37a'
        cls.eth_wallet = Wallet.get_user_wallet(user=cls.user, currency=Currencies.eth)
        cls.eth_deposit = WalletDepositAddress.objects.create(
            wallet=cls.eth_wallet,
            address=eth_address,
            currency=Currencies.eth,
            network=CurrenciesNetworkName.ETH,
            type=ADDRESS_TYPE.contract2
        )
        cls.harmony_wallet = Wallet.get_user_wallet(cls.user, harmony)
        cls.harmony_deposit = cls.harmony_wallet.get_current_deposit_address(create=True)

    def test_get_deposits_address_harmony(self):
        assert self.harmony_deposit.address == self.eth_deposit.address  # to make sure avax will reuse eth address

    def test_deposit_harmony(self):
        tx1 = BlockchainTransaction(
            address=self.harmony_deposit.address,
            hash='0x6fd6c01a9769c8d88bf2230b8f04b128529057f47d8481f8767689d8256e63ad',
            timestamp=datetime.datetime(2019, 2, 21, 6, 20, 31, 0, pytz.utc),
            value=Decimal('20'),
            confirmations=12,  # to be confirmed
            is_double_spend=False,
        )
        tx2 = BlockchainTransaction(
            address=eth_to_one_address(self.harmony_deposit.address),  # to be okay with bech32 format
            hash='0x6fd6c01a9697c8d88bf22308b0f4b128529057f47d848f81767689d8256e63ad',
            timestamp=datetime.datetime(2020, 2, 21, 6, 20, 31, 0, pytz.utc),
            value=Decimal('10'),
            confirmations=12,
            is_double_spend=False,
        )
        tx3 = BlockchainTransaction(
            address=self.harmony_deposit.address,
            hash='0x6fd6c01a9697c8d8bf822308b0f4b128529057f47d848f81767689d8256e63ad',
            timestamp=datetime.datetime(2020, 3, 21, 6, 20, 31, 0, pytz.utc),
            value=Decimal('30'),
            confirmations=11,  # to not to be confirmed
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx1, self.harmony_deposit)
        save_deposit_from_blockchain_transaction(tx2, self.harmony_deposit)
        save_deposit_from_blockchain_transaction(tx3, self.harmony_deposit)
        self.harmony_wallet.refresh_from_db()
        assert self.harmony_wallet.balance == Decimal('30')

    def test_deposit_harmony_disabled(self):
        self.harmony_deposit.is_disabled = True
        self.harmony_deposit.save(update_fields=['is_disabled'])
        tx = BlockchainTransaction(
            address=self.harmony_deposit.address,
            hash='0x6fd6c01a9769c8d88bf3330b8f04b128529057f47d848f81767689d8256e3ad6',
            timestamp=datetime.datetime(2021, 2, 21, 7, 20, 31, 0, pytz.utc),
            value=Decimal('20'),
            confirmations=12,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, self.harmony_deposit)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 0


class DepositBlackListTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user_xrp_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.xrp)
        self.user_xrp_wallet_tag = 1
        self.xrp_address = 'rwRmyGRoJkHKtojaC8SH2wxsnB2q3yNopB'

    @patch.object(BlockchainExplorer, 'get_wallet_transactions')
    def test_source_address_detection(self, mocked_inspector):
        """
            to make sure source addresses will be stored in db
        """
        AvailableDepositAddress.objects.create(address=self.xrp_address, currency=Currencies.xrp)
        WalletDepositTag.objects.create(
            wallet=self.user_xrp_wallet,
            currency=self.user_xrp_wallet.currency,
            tag=self.user_xrp_wallet_tag,
        )
        tx = BlockchainTransaction(
            address=self.xrp_address,
            hash='2533C0A8307CA848CBC42D203FF4510D193A2F40BCBFD898F3310C12A37584C8',
            timestamp=now(),
            value=Decimal('6'),
            confirmations=219,
            is_double_spend=False,
            from_address=['rG2HAZQMec7Bbf68onwekpe4DWBRqSTcL3'],
            tag='1',
        )
        response = {Currencies.xrp: [tx]}
        mocked_inspector.return_value = response
        confirm_tagged_deposits(currency=Currencies.xrp)
        mocked_inspector.assert_called_once()
        assert ConfirmedWalletDeposit.objects.count() == 1
        deposit = ConfirmedWalletDeposit.objects.first()
        for addr in tx.from_address:
            assert addr in deposit.source_addresses.keys()

    def test_blacklist_deposit(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet_deposit_address = WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=address)
        blacklist = BlacklistWalletAddress.objects.create(address=address, is_deposit=True, is_withdraw=False)
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()
        confirmed_wallet_deposit = ConfirmedWalletDeposit(
            _wallet=wallet,
            tx_hash='wefewfewyyyG112',
            address=wallet_deposit_address,
            amount=Decimal('0.5'),
            source_addresses={address: {}, 'arfefweEEEff': {}})
        assert confirmed_wallet_deposit.get_source_address_in_blacklist()
        confirmed_wallet_deposit.save()
        assert self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()

        blacklist.is_active = False
        blacklist.save(update_fields=('is_active',))
        assert not confirmed_wallet_deposit.get_source_address_in_blacklist()

        blacklist.is_active = True
        blacklist.currency = Currencies.btc
        blacklist.save(update_fields=('is_active', 'currency'))
        assert confirmed_wallet_deposit.get_source_address_in_blacklist()

        blacklist.currency = Currencies.doge
        blacklist.save(update_fields=('currency',))
        assert not confirmed_wallet_deposit.get_source_address_in_blacklist()

        blacklist.currency = None
        blacklist.address = 'fooBar'
        blacklist.save(update_fields=('currency', 'address'))
        assert not confirmed_wallet_deposit.get_source_address_in_blacklist()

    def test_blacklist_withdraw_address_for_deposit(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet_deposit_address = WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=address)
        BlacklistWalletAddress.objects.create(address=address, is_withdraw=True, is_deposit=False)
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()
        confirmed_wallet_deposit = ConfirmedWalletDeposit(
            _wallet=wallet,
            tx_hash='wefewfewyyyG112',
            address=wallet_deposit_address,
            amount=Decimal('0.5'),
            source_addresses={address: {}, 'arfefweEEEff': {}})
        assert not confirmed_wallet_deposit.get_source_address_in_blacklist()
        confirmed_wallet_deposit.save()
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()

    def test_blacklist_withdraw_address_case_insensitive(self):
        address = '1Bm9ziyd4UmQpFiGD86ufHSniPtuq7paZh'
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet_deposit_address = WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=address)
        BlacklistWalletAddress.objects.create(address=address.lower(), is_withdraw=True, is_deposit=True)
        assert not self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()
        confirmed_wallet_deposit = ConfirmedWalletDeposit(
            _wallet=wallet,
            tx_hash='wefewfewyyyG112',
            address=wallet_deposit_address,
            amount=Decimal('0.5'),
            source_addresses={address: {}, 'arfefweEEEff': {}})
        assert confirmed_wallet_deposit.get_source_address_in_blacklist()
        confirmed_wallet_deposit.save()
        assert self.user.restrictions.filter(restriction=UserRestriction.RESTRICTION.WithdrawRequest).exists()


class DepositLimitationTests(TestCase):
    def setUp(self):
        self.user: User = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.rial_wallet: Wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.system_rial_account: BankAccount = BankAccount.get_generic_system_account()

    def test_deposit_limits_user_level0(self):
        assert self.user.user_type == User.USER_TYPES.level0
        assert UserLevelManager.get_daily_rial_deposit_limit(self.user) == 0

    def test_deposit_limits_user_level1(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        assert self.user.user_type == User.USER_TYPES.level1
        assert UserLevelManager.get_daily_rial_deposit_limit(self.user) == 25_000_000_0

    def test_deposit_limits_user_trader(self):
        self.user.user_type = User.USER_TYPES.trader
        self.user.save()
        assert self.user.user_type == User.USER_TYPES.trader
        assert UserLevelManager.get_daily_rial_deposit_limit(self.user) == 25_000_000_0

    def test_deposit_limits_user_level2(self):
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        assert self.user.user_type == User.USER_TYPES.level2
        assert UserLevelManager.get_daily_rial_deposit_limit(self.user) == 25_000_000_0

        vp = self.user.get_verification_profile()
        vp.mobile_identity_confirmed = True
        vp.save()

        assert UserLevelManager.get_daily_rial_deposit_limit(self.user) == 25_000_000_0

    def test_deposit_limits_user_level3(self):
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()
        assert self.user.user_type == User.USER_TYPES.verified
        assert UserLevelManager.get_daily_rial_deposit_limit(self.user) == 25_000_000_0


class TagCoinsTest(TestCase):

    def setUp(self):
        # setup credential for user
        self.user = User.objects.get(pk=201)
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.user.user_type = User.USER_TYPES.level1
        self.user.save(update_fields=['user_type'])

        # define tag addresses
        self.ton_address = 'EQBdWoMOSCFHkfSrU1KQDGJNO_88Xv1jAZaxgBWOt4mZD1Rc'
        self.atom_address = 'cosmos1r2z7rdlfau43zh0xp0wpx4mnf4lmwry2kjsmu6'
        self.xrp_address = 'rwRmyGRoJkHKtojaC8SH2wxsnB2q3yNopB'
        AvailableDepositAddress.objects.create(currency=NOT_COIN, address=self.ton_address)
        AvailableDepositAddress.objects.create(currency=Currencies.atom, address=self.atom_address)
        AvailableDepositAddress.objects.create(currency=Currencies.xrp, address=self.xrp_address)
        self.xrp_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.xrp)
        WalletDepositTag.objects.create(wallet=self.xrp_wallet, currency=Currencies.xrp, tag=1)  # non-common tag

    @patch.object(BlockchainExplorer, 'get_wallet_transactions')
    def test_tag_generation_wallets_list(self, mocked_inspector):
        response = self.client.get('/users/wallets/list').json()
        # Description: this api call showed the tag of wallet previously (if there was one) but now it returns
        # None to make the user create another tag (and this time based on notcoin tag) refer to docs
        assert response['status'] == 'ok'
        for info in response['wallets']:
            if info['currency'] == 'xrp':
                assert 'depositTag' in info.keys()
                assert info.get('depositTag') is None

        # but still that tag works on deposit
        tx1 = BlockchainTransaction(
            address=self.xrp_address,
            hash='EAB72E95B0A34911A266AAAA812AE6721BE556E8EF825079FE79375DE426F269',
            timestamp=now(),
            value=Decimal('169.875000'),
            confirmations=161,
            is_double_spend=False,
            tag='1',  # to correspond with non-common tag
        )
        response = {Currencies.xrp: [tx1]}
        mocked_inspector.return_value = response
        confirm_tagged_deposits(currency=Currencies.xrp)
        self.xrp_wallet.refresh_from_db()
        assert self.xrp_wallet.balance == tx1.value
        assert ConfirmedWalletDeposit.objects.filter(tag__tag=1).count() == 1

    def test_address_tag_generation_generate_address(self):
        response = self.client.post('/users/wallets/generate-address', {'currency': 'atom'}).json()
        assert Wallet.objects.filter(user=self.user, currency=NOT_COIN).exists()
        self.not_wallet = Wallet.get_user_wallet(user=self.user, currency=NOT_COIN)
        self.base_tag = self.not_wallet.deposit_tags.all().first()
        assert response['status'] == 'ok'
        assert response['address'] == self.atom_address
        assert response['tag'] == self.base_tag.tag

    @dummy_caching
    def test_tag_coins_addresses(self):
        available_deposit = AvailableDepositAddress.objects.create(currency=Currencies.ton, address=self.ton_address)
        assert [self.ton_address] == tag_coins_addresses(Currencies.ton)

    @dummy_caching
    def test_tag_coins_deposit_with_used_for(self):
        # Setup Test
        ton_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.ton)
        addr = WalletDepositAddress.objects.create(
            wallet=ton_wallet,
            address=self.ton_address,
            network='TON',
        )
        available_deposit = AvailableDepositAddress.objects.create(currency=Currencies.ton, address=self.ton_address)
        tx = BlockchainTransaction(
            address=self.ton_address,
            hash='nxVAG2kUelOL1lIw8XcqOn4Ve/xB/KZly8J30u3jkrk=',
            timestamp=now(),
            value=Decimal('0.494548182'),
            confirmations=219,
            is_double_spend=False,
            from_address=['EQCR-R9mLy263s-pzsZRnHiUyAYRHzSHr4eJ8qf-jxoemgQs'],
        )
        addresses = grab_tagcoins_deposit_address(currency=Currencies.ton)
        assert len(addresses) == 1
        save_deposit_from_blockchain_transaction_tagged(tx, addresses[0], Currencies.ton)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 0
        available_deposit.used_for = addr
        available_deposit.save()
        addresses = grab_tagcoins_deposit_address(currency=Currencies.ton)
        save_deposit_from_blockchain_transaction_tagged(tx, addresses[0], Currencies.ton)
        confirmed_deposits = ConfirmedWalletDeposit.objects.all()
        assert len(confirmed_deposits) == 1

    @dummy_caching
    @patch.object(BlockchainExplorer, 'get_wallet_transactions')
    def test_tags_coins_with_same_tag_same_user(self, mocked_inspector):
        # Setup Test
        ton_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.ton)
        unique_address = 'EQAEyk8Ky7sJC98WIb7NBPLXLKnZSj1ZjmEOkdy4CfBizDp9'
        addr = WalletDepositAddress.objects.create(
            wallet=ton_wallet,
            address=unique_address,
            network='TON',
        )
        WalletDepositTag.objects.create(wallet=ton_wallet, currency=Currencies.ton, tag=1)
        available_deposit = AvailableDepositAddress.objects.create(currency=Currencies.ton, address=self.ton_address)
        unique_available_deposit = AvailableDepositAddress.objects.create(
            currency=Currencies.ton,
            address=unique_address,
            used_for=addr,
        )

        tx1 = BlockchainTransaction(
            address=self.ton_address,
            hash='nxVAG2kUelOL1lIw8XcqOn4Ve/xB/KZly8J30u3jkrk=',
            timestamp=now(),
            value=Decimal('0.4'),
            confirmations=219,
            is_double_spend=False,
            from_address=['EQCR-R9mLy263s-pzsZRnHiUyAYRHzSHr4eJ8qf-jxoemgQs'],
            tag='1',
            huge=False,
        )
        tx2 = copy.copy(tx1)
        tx2.address = unique_address
        tx2.hash = 'vnVAG2kUelOL1lIw8XcqOn4Ve/xB/KZly8J30u3jkrk='
        tx2.value = Decimal('0.7')

        mocked_inspector.side_effect = [{Currencies.ton: [tx2]}, {Currencies.ton: [tx1]}]
        confirm_tagged_deposits(currency=Currencies.ton)
        mocked_inspector.assert_called()
        # Only one deposit create for each deposit
        assert ConfirmedWalletDeposit.objects.count() == 2
        ton_wallet.refresh_from_db()
        assert ton_wallet.balance == Decimal('1.1')

    @dummy_caching
    @patch.object(BlockchainExplorer, 'get_wallet_transactions')
    def test_tags_coins_with_same_tag_different_user(self, mocked_inspector):
        # Setup Test
        user2 = User.objects.get(pk=202)
        ton_wallet_1 = Wallet.get_user_wallet(user=self.user, currency=Currencies.ton)
        ton_wallet_2 = Wallet.get_user_wallet(user=user2, currency=Currencies.ton)

        unique_address = 'EQAEyk8Ky7sJC98WIb7NBPLXLKnZSj1ZjmEOkdy4CfBizDp9'
        addr = WalletDepositAddress.objects.create(
            wallet=ton_wallet_2,
            address=unique_address,
            network='TON',
        )
        WalletDepositTag.objects.create(wallet=ton_wallet_1, currency=Currencies.ton, tag=1)
        available_deposit = AvailableDepositAddress.objects.create(currency=Currencies.ton, address=self.ton_address)
        unique_available_deposit = AvailableDepositAddress.objects.create(
            currency=Currencies.ton,
            address=unique_address,
            used_for=addr,
        )

        tx1 = BlockchainTransaction(
            address=self.ton_address,
            hash='nxVAG2kUelOL1lIw8XcqOn4Ve/xB/KZly8J30u3jkrk=',
            timestamp=now(),
            value=Decimal('0.4'),
            confirmations=219,
            is_double_spend=False,
            from_address=['EQCR-R9mLy263s-pzsZRnHiUyAYRHzSHr4eJ8qf-jxoemgQs'],
            tag='1',
            huge=False,
        )
        tx2 = copy.copy(tx1)
        tx2.address = unique_address
        tx2.hash = 'vnVAG2kUelOL1lIw8XcqOn4Ve/xB/KZly8J30u3jkrk='
        tx2.value = Decimal('0.7')

        mocked_inspector.side_effect = [{Currencies.ton: [tx2]}, {Currencies.ton: [tx1]}]
        confirm_tagged_deposits(currency=Currencies.ton)
        mocked_inspector.assert_called()
        # Only one deposit create for each deposit
        assert ConfirmedWalletDeposit.objects.count() == 2
        ton_wallet_1.refresh_from_db()
        ton_wallet_2.refresh_from_db()
        assert ton_wallet_1.balance == Decimal('0.4')
        assert ton_wallet_2.balance == Decimal('0.7')


class DepositConfirmationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        eth_address = '0x79ad331ef266Aef44d5779DC0262D9544D607c26'
        cls.eth_wallet = Wallet.get_user_wallet(user=cls.user, currency=Currencies.eth)
        cls.eth_deposit_address = WalletDepositAddress.objects.create(
            wallet=cls.eth_wallet,
            address=eth_address,
            currency=Currencies.eth,
            network=CurrenciesNetworkName.ETH,
            type=ADDRESS_TYPE.eoa_v1,
        )

        cls.user2 = User.objects.get(pk=202)
        eth_address2 = '0x95222290dd7278aa3ddd389cc1e1d165cc4bafe5'
        cls.eth_wallet2 = Wallet.get_user_wallet(user=cls.user2, currency=Currencies.eth)
        cls.eth_deposit_address2 = WalletDepositAddress.objects.create(
            wallet=cls.eth_wallet2,
            address=eth_address2,
            currency=Currencies.eth,
            network=CurrenciesNetworkName.ETH,
            type=ADDRESS_TYPE.eoa_v1,
        )

    def __transaction_generator(self, *args, **kwargs):
        utc = pytz.UTC
        return BlockchainTransaction(
            address=kwargs.get("address", ""),
            from_address=kwargs.get("from_address", []),
            block=kwargs.get('block', 100),
            hash=kwargs.get('hash', ""),
            timestamp=kwargs.get('date', datetime.datetime.now(tz=utc)),
            value=kwargs.get('value', 100),
            confirmations=kwargs.get('confirmations', 100),
            is_double_spend=False,
            details=kwargs.get('raw', ""),
            tag=kwargs.get('memo', ''),
            contract_address=kwargs.get('contract_address', None),
        )

    @patch.object(BlockchainExplorer, 'get_wallet_transactions')
    def test_internal_deposit_should_be_filtered(self, mocked_inspector: MagicMock):
        # valid user1 tx
        valid_tx = self.__transaction_generator(
            address=self.eth_deposit_address.address,
            from_address=['0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97'],
            hash='0xe6b10eef9308618771f9a6d4027510eb826b0378677a0c483bb4edfc53b6ca71',
            block=21401151,
        )
        # invalid user1 tx because sender is user2 wallet
        invalid_tx = self.__transaction_generator(
            address=self.eth_deposit_address.address,
            from_address=[self.eth_deposit_address2.address],
            hash='0xd671445ea1801931871a3145c1564211e5a81328661167537bc19f798d94b153',
            block=21397174,
        )
        mocked_inspector.return_value = {Currencies.eth: [valid_tx, invalid_tx]}
        confirm_bitcoin_deposits(self.eth_deposit_address)
        user1_eth_deposits = ConfirmedWalletDeposit.objects.filter(_wallet=self.eth_deposit_address.wallet)
        self.assertEqual(len(user1_eth_deposits), 1)
        user1_deposit = user1_eth_deposits[0]

        self.assertEqual(user1_deposit.address, self.eth_deposit_address)
        self.assertEqual(user1_deposit.tx_hash, valid_tx.hash[2:])
        self.assertEqual(user1_deposit.source_addresses, {valid_tx.from_address[0]: {}})
        self.assertEqual(user1_deposit.amount, Decimal(str(valid_tx.value)))

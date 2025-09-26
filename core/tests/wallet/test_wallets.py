import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.base.models import ADDRESS_TYPE, Currencies
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.features.models import QueueItem
from exchange.wallet import models as wallet_models
from exchange.wallet.models import (
    AvailableDepositAddress,
    Transaction,
    Wallet,
    WalletCreditBalance,
    WalletDepositAddress,
)


class WalletsTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        Wallet.create_user_wallets(self.user)
        Wallet.create_user_wallets(self.user2)
        req = QueueItem.objects.create(
            feature=QueueItem.FEATURES.new_coins,
            user=self.user2,
        )
        req.enable_feature()
        req = QueueItem.objects.create(
            feature=QueueItem.FEATURES.miner,
            user=self.user2,
        )
        req.enable_feature()

    def test_wallet_transaction_basics(self):
        rls = Currencies.rls
        w = Wallet.get_user_wallet(self.user, rls)
        b0 = Decimal('10000000')
        zero = Decimal(0)
        assert w.current_balance == zero
        tr1 = w.create_transaction(tp='manual', amount=b0)
        assert w.current_balance == zero  # still zero because transaction is not commited
        tr1.commit()
        assert w.current_balance == b0

    def test_wallet_transaction_overspend(self):
        rls = Currencies.rls
        w = Wallet.get_user_wallet(self.user, rls)
        b0 = Decimal('10000000')
        b1 = Decimal('-10000001')
        tr1 = w.create_transaction(tp='manual', amount=b0)
        tr1.commit()
        assert w.current_balance == b0
        tr2 = w.create_transaction(tp='manual', amount=b1)
        assert tr2 is None

    def test_credit_balance(self):
        wallet_rls = Wallet.get_user_wallet(self.user, Currencies.rls)
        wallet_btc = Wallet.get_user_wallet(self.user, Currencies.btc)
        assert WalletCreditBalance.get_current_user_credit(wallet_rls, Currencies.rls) == Decimal('0')
        assert WalletCreditBalance.get_current_user_credit(self.user, Currencies.btc) == Decimal('0')
        # Give credit and check balance
        WalletCreditBalance.give_credit_to_user(self.user, Currencies.btc, Decimal('0.5'))
        assert WalletCreditBalance.get_current_user_credit(self.user, Currencies.rls) == Decimal('0')
        assert WalletCreditBalance.get_current_user_credit(self.user, Currencies.btc) == Decimal('0.5')
        assert Wallet.get_user_wallet(self.user, Currencies.btc).balance == Decimal('0.5')
        # Check transactions
        credit = WalletCreditBalance.objects.order_by('-created_at').first()
        assert credit and credit.wallet == wallet_btc
        assert credit.credit == Decimal('0.5')
        assert credit.credit_change == Decimal('0.5')
        assert credit.credit_transaction.wallet == wallet_btc
        assert credit.credit_transaction.tp == Transaction.TYPE.manual
        assert credit.credit_transaction.amount == Decimal('0.5')
        assert credit.credit_transaction.ref_module == Transaction.REF_MODULES['Credit']
        assert credit.credit_transaction.ref_id == credit.pk
        # Check credit reduction
        WalletCreditBalance.give_credit_to_user(self.user, Currencies.btc, Decimal('-0.1'))
        assert WalletCreditBalance.get_current_user_credit(self.user, Currencies.rls) == Decimal('0')
        assert WalletCreditBalance.get_current_user_credit(self.user, Currencies.btc) == Decimal('0.4')
        assert Wallet.get_user_wallet(self.user, Currencies.btc).balance == Decimal('0.4')
        # Check transactions
        credit = WalletCreditBalance.objects.order_by('-created_at').first()
        assert credit and credit.wallet == wallet_btc
        assert credit.credit == Decimal('0.4')
        assert credit.credit_change == Decimal('-0.1')
        assert credit.credit_transaction.wallet == wallet_btc
        assert credit.credit_transaction.tp == Transaction.TYPE.manual
        assert credit.credit_transaction.amount == Decimal('-0.1')
        assert credit.credit_transaction.ref_module == Transaction.REF_MODULES['Credit']
        assert credit.credit_transaction.ref_id == credit.pk

    def test_wallet_transaction_commit(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        t0 = wallet.create_transaction(tp='manual', amount=Decimal('0.01'), description='t0')
        t0.commit()
        wallet.refresh_from_db()
        balance0 = wallet.balance
        assert balance0 == Decimal('0.01')
        amount1 = Decimal('0.1')
        t1 = wallet.create_transaction(tp='manual', amount=amount1, description='t1')
        t1.commit()
        wallet.refresh_from_db()
        assert wallet.balance == balance0 + amount1
        assert t1.balance == balance0 + amount1
        # Two concurrent transactions
        t2 = wallet.create_transaction(tp='manual', amount=-t1.balance, description='t2')
        t3 = wallet.create_transaction(tp='manual', amount=-amount1, description='t3')
        t2.commit()
        expected_error = r'^Balance Error In Commiting Transaction$'
        with transaction.atomic(), pytest.raises(ValueError, match=expected_error):
            t3.commit()
        wallet.refresh_from_db()
        assert wallet.balance == Decimal('0')
        assert t2.balance == Decimal('0')
        assert not t3.pk

    def test_wallet_transaction_commit_precision(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        transaction = wallet.create_transaction(tp='manual', amount=Decimal('0.12005620445'), description='t0')
        transaction.commit()

        transaction.refresh_from_db()
        wallet.refresh_from_db()
        assert transaction.amount == Decimal('0.1200562044')
        assert wallet.balance == transaction.balance == transaction.amount

    def test_spot_wallet_creation(self):
        for currency in (Currencies.usdt, Currencies.btc):
            wallet = Wallet.get_user_wallet(self.user, currency)
            assert wallet.user == self.user
            assert wallet.currency == currency
            assert wallet.type == Wallet.WALLET_TYPE.spot
            assert Wallet.get_user_wallet(self.user, currency, tp=Wallet.WALLET_TYPE.spot) == wallet

        with pytest.raises(IntegrityError):
            Wallet.objects.create(user=self.user, currency=Currencies.usdt)

    def test_margin_wallet_creation(self):
        for currency in (Currencies.usdt, Currencies.rls):
            wallet = Wallet.get_user_wallet(self.user, currency, tp=Wallet.WALLET_TYPE.margin)
            assert wallet.user == self.user
            assert wallet.currency == currency
            assert wallet.type == Wallet.WALLET_TYPE.margin
            assert Wallet.get_user_wallet(self.user, currency, tp=Wallet.WALLET_TYPE.margin) == wallet

        assert Wallet.get_user_wallet(self.user, Currencies.btc, tp=Wallet.WALLET_TYPE.margin) is None

        with pytest.raises(IntegrityError):
            Wallet.objects.create(user=self.user, currency=Currencies.usdt, type=Wallet.WALLET_TYPE.margin)

    def test_get_user_wallets(self):
        assert Wallet.get_user_wallets(self.user).count() == 23
        assert Wallet.get_user_wallets(self.user, tp=Wallet.WALLET_TYPE.spot).count() == 21  # setUp
        assert Wallet.get_user_wallets(self.user, tp=Wallet.WALLET_TYPE.margin).count() == 2  # fixture

    def test_wallet_display(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.spot)
        assert str(wallet) == 'Tether Spot Wallet: User One'
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        assert str(wallet) == 'Tether Margin Wallet: User One'

    def test_margin_wallet_block(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        wallet.create_transaction('manual', amount='42.58').commit()
        wallet.refresh_from_db()
        assert wallet.active_balance == Decimal('42.58')
        wallet.block(Decimal('13.27'))
        assert wallet.active_balance == Decimal('29.31')
        wallet.block(Decimal('22.63'))
        assert wallet.active_balance == Decimal('6.68')
        wallet.unblock(Decimal('15.43'))
        assert wallet.active_balance == Decimal('22.11')

    def test_get_address_type_not_none(self):
        test_cases = [
            # (settings_override, currency, network, address_type_unparsed, user, expected_address_type)
            # Test case for SegWit
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': True,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': False,
                    'ADDRESS_CONTRACT_V2_ENABLED': False,
                    # 'CONTRACT_NETWORKS': {CurrenciesNetworkName.ETH, CurrenciesNetworkName.TRX},
                },
                Currencies.btc,
                CurrenciesNetworkName.BTC,
                'default',
                self.user,
                ADDRESS_TYPE.segwit,
            ),
            # Test case for EOA v1
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': True,
                    'EOA_V1_ENABLED': True,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': True,
                },
                Currencies.eth,
                CurrenciesNetworkName.ETH,
                'default',
                self.user,
                ADDRESS_TYPE.eoa_v1,
            ),
            # Test case for EOA v1 when beta
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': False,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': True,
                },
                Currencies.eth,
                CurrenciesNetworkName.ETH,
                'default',
                self.user2,
                ADDRESS_TYPE.eoa_v1,
            ),
            # Test case for Contract2
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': False,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': True,
                },
                Currencies.eth,
                CurrenciesNetworkName.ETH,
                'default',
                self.user,
                ADDRESS_TYPE.contract2,
            ),
            # Test case for USDT on ETH standard address
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': False,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': False,
                },
                Currencies.usdt,
                CurrenciesNetworkName.ETH,
                'default',
                self.user,
                ADDRESS_TYPE.standard,
            ),
            # Test case for Contract
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': False,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': False,
                },
                Currencies.eth,
                CurrenciesNetworkName.TRX,
                'default',
                self.user,
                ADDRESS_TYPE.contract,
            ),
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': False,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': True,
                },
                Currencies.trx,
                CurrenciesNetworkName.TRX,
                'default',
                self.user,
                ADDRESS_TYPE.contract,
            ),
            # Default to standard
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': False,
                    'EOA_V1_ENABLED': False,
                    'ADDRESS_CONTRACT_ENABLED': False,
                    'ADDRESS_CONTRACT_V2_ENABLED': False,
                },
                Currencies.eth,
                CurrenciesNetworkName.ETH,
                'default',
                self.user,
                ADDRESS_TYPE.standard,
            ),
            (
                {
                    'MINER_ENABLED': False,
                    'SEGWIT_ENABLED': True,
                    'EOA_V1_ENABLED': True,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': True,
                },
                Currencies.ton,
                CurrenciesNetworkName.TON,
                'default',
                self.user,
                ADDRESS_TYPE.standard,
            ),
            (
                {
                    'MINER_ENABLED': True,
                    'SEGWIT_ENABLED': True,
                    'EOA_V1_ENABLED': True,
                    'ADDRESS_CONTRACT_ENABLED': True,
                    'ADDRESS_CONTRACT_V2_ENABLED': True,
                },
                Currencies.btc,
                CurrenciesNetworkName.BTC,
                'default',
                self.user2,
                ADDRESS_TYPE.miner,
            ),
        ]

        for settings_override, currency, network, address_type_unparsed, user, expected_address_type in test_cases:
            with self.subTest(
                settings_override=settings_override,
                currency=currency,
                network=network,
                address_type_unparsed=address_type_unparsed,
            ):
                # Use override_settings as a context manager
                with override_settings(**settings_override):
                    wallet = Wallet.get_user_wallet(user, currency)

                    # Call the function
                    result = wallet.get_address_type_not_none(network, address_type_unparsed)

                    # Assert the expected result
                    assert result == expected_address_type

    @override_settings(MINER_ENABLED=True)
    def test_get_miner_wallet_address_success(self):
        btc_dummy_address = 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq'
        AvailableDepositAddress.objects.create(
            currency=Currencies.btc, address=btc_dummy_address, type=ADDRESS_TYPE.miner
        )
        w1 = Wallet.get_user_wallet(self.user2, Currencies.btc)
        address = w1.get_current_deposit_address(create=True, network=CurrenciesNetworkName.BTC)
        self.assertEqual(address.address, btc_dummy_address)
        self.assertEqual(address.type, ADDRESS_TYPE.miner)


class BalanceWatchWalletTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        user1 = User.objects.get(pk=201)
        wallet = Wallet.get_user_wallet(user1, Currencies.trx)
        cls.deposit_address = WalletDepositAddress.objects.create(
            wallet=wallet,
            address='ABCDABCD',
            last_update_check=now(),
        )

    def test_outdated_balance(self):
        assert WalletDepositAddress.get_outdated_queryset().count() == 0
        self.deposit_address.last_update_check = now() - datetime.timedelta(hours=3)
        self.deposit_address.save()
        assert WalletDepositAddress.get_outdated_queryset().count() == 1


class GetOldDepositAddressTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Patch currency_info at the class level
        cls.currency_info_patcher = patch.dict(
            wallet_models.CURRENCY_INFO,
            {
                Currencies.eth: {'default_network': 'ETH', 'network_list': {'ETH': {}}},
                Currencies.usdt: {'default_network': 'ETH', 'network_list': {'ETH': {}}},
            },
        )
        cls.address_reused_network_patcher = patch.object(wallet_models, 'ADDRESS_REUSED_NETWORK', ['ETH'])
        cls.main_address_currencies_patcher = patch.object(
            wallet_models, 'MAIN_ADDRESS_CURRENCIES', [f'{Currencies.eth}-ETH']
        )

        cls.currency_info_patcher.start()
        cls.address_reused_network_patcher.start()
        cls.main_address_currencies_patcher.start()

        # Create users
        cls.user = User.objects.get(pk=201)
        cls.other_user = User.objects.get(pk=202)

        # Create wallets
        cls.wallet = Wallet.get_user_wallet(cls.user, currency=Currencies.usdt)
        cls.other_wallet = Wallet.get_user_wallet(user=cls.other_user, currency=Currencies.usdt)
        cls.wallet_non_crypto = Wallet.get_user_wallet(user=cls.user, currency=Currencies.rls)
        cls.wallet_unknown_currency = Wallet.get_user_wallet(user=cls.user, currency=Currencies.x)

        # Create wallet deposit addresses
        cls.wallet_deposit_address = WalletDepositAddress.objects.create(
            wallet=cls.wallet, currency=Currencies.eth, address='0x1234', type=ADDRESS_TYPE.contract2, network='ETH'
        )
        cls.other_wallet_deposit_address = WalletDepositAddress.objects.create(
            wallet=cls.other_wallet,
            currency=Currencies.eth,
            address='0x4321',
            type=ADDRESS_TYPE.contract2,
            network='ETH',
        )

        # Link available deposit addresses
        cls.available_address = AvailableDepositAddress.objects.create(
            address='0x1234', currency=Currencies.eth, type=ADDRESS_TYPE.contract2, used_for=cls.wallet_deposit_address
        )
        cls.other_available_address = AvailableDepositAddress.objects.create(
            address='0x4321',
            currency=Currencies.eth,
            type=ADDRESS_TYPE.contract2,
            used_for=cls.other_wallet_deposit_address,
        )

    @classmethod
    def tearDownClass(cls):
        # Stop all patches
        cls.currency_info_patcher.stop()
        cls.address_reused_network_patcher.stop()
        cls.main_address_currencies_patcher.stop()
        super().tearDownClass()

    def test_address_belongs_to_user(self):
        """
        Test that the function returns a WalletDepositAddress when the address belongs to the user.
        """
        result = self.wallet.get_old_deposit_address(address='0x1234')
        self.assertIsNotNone(result)
        self.assertIsInstance(result, WalletDepositAddress)
        self.assertEqual(result.address, '0x1234')

    def test_address_does_not_belong_to_user(self):
        """
        Test that the function returns None when the address does not belong to the user.
        """
        result = self.wallet.get_old_deposit_address(address='0x4321')
        self.assertIsNone(result)

    def test_non_crypto_currency(self):
        """
        Test that the function returns None when the wallet is not a crypto currency.
        """
        result = self.wallet_non_crypto.get_old_deposit_address(address='0x1234')
        self.assertIsNone(result)

    def test_currency_not_in_currency_info(self):
        """
        Test that the function returns None when the currency is not in CURRENCY_INFO.
        """
        result = self.wallet_unknown_currency.get_old_deposit_address(address='0x1234')
        self.assertIsNone(result)

    def test_with_contract_address(self):
        """
        Test that the function handles contract_address correctly.
        """
        result = self.wallet.get_old_deposit_address(address='0x1234', contract_address='0x9876')
        self.assertIsNotNone(result)
        self.assertIsInstance(result, WalletDepositAddress)
        self.assertEqual(result.address, '0x1234')
        # If WalletDepositAddress has a 'contract_address' field, you can include:
        # self.assertEqual(result.contract_address, 'some_contract_address')

    def test_main_address_currencies_includes_currency_network(self):
        """
        Test that the function returns None when the currency-network pair is in MAIN_ADDRESS_CURRENCIES.
        """
        wallet = Wallet.get_user_wallet(self.user, currency=Currencies.eth)
        result = wallet.get_old_deposit_address(address='0x1234')
        self.assertIsNone(result)

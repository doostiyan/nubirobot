from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.internal.services import Services
from exchange.base.models import Currencies
from exchange.wallet.internal.exceptions import (
    DisallowedDstWalletType,
    DisallowedSrcWalletType,
    DisallowedSystemWallet,
    InactiveWallet,
    InvalidRefModule,
    InvalidTransaction,
    InvalidTransactionType,
)
from exchange.wallet.internal.permissions import (
    ALLOWED_DST_TYPES,
    ALLOWED_NEGATIVE_BALANCE_WALLETS,
    ALLOWED_SRC_TYPES,
    ALLOWED_SYSTEM_USER,
    ALLOWED_TX_TYPE,
)
from exchange.wallet.internal.service_transaction import InsufficientBalance, create_service_transaction
from exchange.wallet.models import Transaction, Wallet


class ServiceTransactionTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.spot_wallet: Wallet = Wallet.get_user_wallet(
            user=self.user, currency=Currencies.btc, tp=Wallet.WALLET_TYPE.spot
        )
        self.credit_wallet: Wallet = Wallet.get_user_wallet(
            user=self.user, currency=Currencies.btc, tp=Wallet.WALLET_TYPE.credit
        )

    def test_inactive_wallet_raises_exception(self):
        self.spot_wallet.is_active = False
        with pytest.raises(InactiveWallet):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='asset_backed_credit',
                amount=Decimal('100.00'),
                description='Test description',
            )

    def test_invalid_transaction_type_raises_exception(self):
        with pytest.raises(InvalidTransactionType):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='invalid_type',
                amount=Decimal('100.00'),
                description='Test description',
            )

    def test_disallowed_transaction_type_raises_exception(self):
        with pytest.raises(InvalidTransactionType), patch.dict(
            ALLOWED_TX_TYPE, {Services.ABC: [Transaction.TYPE.asset_backed_credit]}
        ):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='withdraw',
                amount=Decimal('100.00'),
                description='Test description',
            )

    def test_disallowed_src_wallet_type_raises_exception(self):
        with pytest.raises(DisallowedSrcWalletType), patch.dict(
            ALLOWED_SRC_TYPES,
            {Services.ABC: [Wallet.WALLET_TYPE.credit]},
        ):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )

    def test_disallowed_dst_wallet_type_raises_exception(self):
        with pytest.raises(DisallowedDstWalletType), patch.dict(
            ALLOWED_DST_TYPES,
            {Services.ABC: [Wallet.WALLET_TYPE.spot]},
        ):
            create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('100.00'),
                description='Test description',
            )

    def test_disallowed_system_wallet_raises_exception(self):
        self.credit_wallet.user.user_type = User.USER_TYPES.system
        with pytest.raises(DisallowedSystemWallet), patch.dict(ALLOWED_SYSTEM_USER, {Services.ABC: [2]}):
            create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )

        with pytest.raises(DisallowedSystemWallet), patch.dict(ALLOWED_SYSTEM_USER, {Services.ABC: [2]}):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='asset_backed_credit',
                amount=Decimal('100.00'),
                description='Test description',
            )

    def test_allowed_system_wallet_raises_exception(self):
        self.credit_wallet.user.user_type = User.USER_TYPES.system
        self.credit_wallet.balance = 100
        self.credit_wallet.save()

        self.spot_wallet.balance = 100
        self.spot_wallet.save()

        with patch.dict(ALLOWED_SYSTEM_USER, {Services.ABC: [self.credit_wallet.user.id]}):
            create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )

    def test_valid_transaction_commits_successfully(self):
        with patch.dict(ALLOWED_TX_TYPE, {Services.ABC: [Transaction.TYPE.asset_backed_credit]}), patch.dict(
            ALLOWED_SRC_TYPES,
            {Services.ABC: [self.credit_wallet.type]},
        ), patch.dict(ALLOWED_DST_TYPES, {Services.ABC: [self.credit_wallet.type]}):
            tx1 = create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('100.00'),
                description='Test description',
                ref_module='AssetBackedCreditUserSettlement',
                ref_id=123,
            )
            assert tx1 is not None
            assert tx1.balance == 100
            assert tx1.created_at is not None
            assert tx1.tp == Transaction.TYPE.asset_backed_credit
            assert tx1.wallet == self.credit_wallet
            assert tx1.ref_module == Transaction.REF_MODULES['AssetBackedCreditUserSettlement']
            assert tx1.ref_id == 123
            assert tx1.service == Services.ABC

            self.credit_wallet.refresh_from_db()
            assert self.credit_wallet.balance == 100

            tx2 = create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )
            assert tx2 is not None

            self.credit_wallet.refresh_from_db()
            assert self.credit_wallet.balance == 0

    def test_insufficient_balance(self):
        with pytest.raises(InsufficientBalance):
            create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )

    def test_invalid_ref_module(self):
        with pytest.raises(InvalidRefModule), patch.dict(
            ALLOWED_TX_TYPE,
            {Services.ABC: [Transaction.TYPE.withdraw]},
        ):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='withdraw',
                amount=Decimal('100.00'),
                description='Test description',
                ref_module='invalid-ref-module',
                ref_id=123,
            )

    def test_disallowed_ref_module(self):
        with pytest.raises(InvalidRefModule):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='withdraw',
                amount=Decimal('100.00'),
                description='Test description',
                ref_module='WithdrawRequest',
                ref_id=123,
            )

    def test_invalid_transaction_on_commit(self):
        with pytest.raises(InvalidTransaction), patch.dict(
            ALLOWED_TX_TYPE,
            {Services.ABC: [Transaction.TYPE.withdraw]},
        ):
            create_service_transaction(
                Services.ABC,
                self.spot_wallet,
                tp='withdraw',
                amount=Decimal('100.00'),
                description='Test description',
            )

    def test_allow_negative_balance_logic(self):
        with patch.dict(ALLOWED_NEGATIVE_BALANCE_WALLETS, {Services.ABC: [self.credit_wallet.pk]}):
            tx = create_service_transaction(
                Services.ABC,
                self.credit_wallet,
                tp='asset_backed_credit',
                amount=Decimal('-100.00'),
                description='Test description',
            )
            assert tx is not None

        tx = create_service_transaction(
            Services.ABC,
            self.credit_wallet,
            tp='asset_backed_credit',
            amount=Decimal('-100.00'),
            description='Test description',
            allow_negative_balance=True,
        )
        assert tx is not None

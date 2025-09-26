import functools
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.formatting import f_m
from exchange.base.models import RIAL, Currencies, get_currency_codename
from exchange.base.strings import _t
from exchange.wallet.helpers import RefMod
from exchange.wallet.models import Transaction, Wallet
from exchange.xchange import exceptions
from exchange.xchange.helpers import get_small_assets_convert_system_user
from exchange.xchange.models import MarketStatus, SmallAssetConvert
from exchange.xchange.small_asset_convertor import Notification, SmallAssetConvertor


def _patch_convert(func):
    base_patch_module = 'exchange.xchange.small_asset_convertor.'

    @patch(base_patch_module + 'Wallet.get_user_wallets')
    @patch(base_patch_module + 'SmallAssetConvertor._convert')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@patch('exchange.xchange.small_asset_convertor.XCHANGE_CURRENCIES', [Currencies.dai, Currencies.eth])
class TestConvertMethod(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create(
            username='xchange_small_asset_convertor_test',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.xchange_currency = Currencies.dai
        self.another_xchange_currency = Currencies.eth
        self.market_currency = Currencies.btc

        # Mock a wallet for the user
        self.wallet = Wallet.get_user_wallet(self.user, self.xchange_currency)

        self.market_status = MarketStatus.objects.create(
            base_currency=self.xchange_currency,
            quote_currency=RIAL,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=10,
            max_base_amount=100,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

    @_patch_convert
    def test_convert_success(
        self,
        mock_convert,
        mock_get_user_wallets,
    ):
        # Mock user wallets
        mock_get_user_wallets.return_value.filter.return_value.exclude.return_value = [self.wallet]

        # Call the method
        result = SmallAssetConvertor.convert(self.user, [self.xchange_currency], RIAL)

        # Assertions
        assert len(result) == 1
        assert self.xchange_currency in result
        assert result[self.xchange_currency] == 'success'
        mock_get_user_wallets.assert_called_once_with(user=self.user, tp=Wallet.WALLET_TYPE.spot)
        mock_convert.assert_called_once_with(self.wallet, self.market_status)

    def test_convert_invalid_dst_currency(self):
        with pytest.raises(exceptions.InvalidPair, match="dstCurrency should be 'rls' or 'usdt'"):
            SmallAssetConvertor.convert(self.user, [self.xchange_currency], Currencies.btc)

    @_patch_convert
    def test_convert_invalid_one_src_currency(
        self,
        mock_convert,
        mock_get_user_wallets,
    ):
        # Mock user wallets
        mock_get_user_wallets.return_value.filter.return_value.exclude.return_value = [self.wallet]

        # Call the method
        result = SmallAssetConvertor.convert(self.user, [self.market_currency, self.xchange_currency], RIAL)

        # Assertions
        assert len(result) == 2
        assert self.market_currency in result
        assert isinstance(result[self.market_currency], exceptions.InvalidPair)
        assert result[self.market_currency].message == 'srcCurrency should be in convert coins'
        assert self.xchange_currency in result
        assert result[self.xchange_currency] == 'success'
        mock_get_user_wallets.assert_called_once_with(user=self.user, tp=Wallet.WALLET_TYPE.spot)
        mock_convert.assert_called_once_with(self.wallet, self.market_status)

    def test_convert_invalid_all_src_currencies(self):
        with pytest.raises(exceptions.InvalidPair, match='srcCurrency should be in convert coins'):
            SmallAssetConvertor.convert(self.user, [self.market_currency], RIAL)

    def test_convert_market_unavailable_for_all_coins(self):
        self.market_status.status = MarketStatus.STATUS_CHOICES.delisted
        self.market_status.save()

        with pytest.raises(exceptions.MarketUnavailable, match='Market is not available.'):
            SmallAssetConvertor.convert(self.user, [self.market_currency, self.xchange_currency], RIAL)

    @_patch_convert
    def test_convert_market_unavailable_for_one_coin(
        self,
        mock_convert,
        mock_get_user_wallets,
    ):
        # Mock user wallets
        mock_get_user_wallets.return_value.filter.return_value.exclude.return_value = [self.wallet]

        # Call the method
        result = SmallAssetConvertor.convert(self.user, [self.xchange_currency, self.another_xchange_currency], RIAL)

        # Assertions
        assert len(result) == 2
        assert self.xchange_currency in result
        assert result[self.xchange_currency] == 'success'
        assert self.another_xchange_currency in result
        assert isinstance(result[self.another_xchange_currency], exceptions.MarketUnavailable)
        assert result[self.another_xchange_currency].message == 'Market is not available.'
        mock_get_user_wallets.assert_called_once_with(user=self.user, tp=Wallet.WALLET_TYPE.spot)
        mock_convert.assert_called_once_with(self.wallet, self.market_status)

    @_patch_convert
    def test_convert_without_wallet(
        self,
        mock_convert: MagicMock,
        mock_get_user_wallets,
    ):
        # Mock user wallets
        mock_get_user_wallets.return_value.filter.return_value.exclude.return_value = []

        # Call the method
        result = SmallAssetConvertor.convert(self.user, [self.market_currency, self.xchange_currency], RIAL)

        # Assertions
        assert len(result) == 2
        assert self.market_currency in result
        assert isinstance(result[self.market_currency], exceptions.InvalidPair)
        assert result[self.market_currency].message == 'srcCurrency should be in convert coins'
        assert self.xchange_currency in result
        assert isinstance(result[self.xchange_currency], exceptions.FailedAssetTransfer)
        assert result[self.xchange_currency].message == 'Wrong wallet or Zero balance.'
        mock_convert.assert_not_called()

    @_patch_convert
    def test_convert_inner_convert_failed(
        self,
        mock_convert: MagicMock,
        mock_get_user_wallets,
    ):
        # Mock user wallets
        mock_get_user_wallets.return_value.filter.return_value.exclude.return_value = [self.wallet]

        mock_convert.side_effect = exceptions.FailedAssetTransfer('Invalid wallet of insufficient balance.')

        # Call the method
        result = SmallAssetConvertor.convert(self.user, [self.market_currency, self.xchange_currency], RIAL)

        # Assertions
        assert len(result) == 2
        assert self.market_currency in result
        assert isinstance(result[self.market_currency], exceptions.InvalidPair)
        assert result[self.market_currency].message == 'srcCurrency should be in convert coins'
        assert self.xchange_currency in result
        assert isinstance(result[self.xchange_currency], exceptions.FailedAssetTransfer)
        assert result[self.xchange_currency].message == 'Invalid wallet of insufficient balance.'
        mock_convert.assert_called_once_with(self.wallet, self.market_status)

    @_patch_convert
    def test_convert_happened_unhandled_error(
        self,
        mock_convert: MagicMock,
        mock_get_user_wallets,
    ):
        # Mock user wallets
        mock_get_user_wallets.return_value.filter.return_value.exclude.return_value = [self.wallet]

        mock_convert.side_effect = Exception('Unknown Exception')

        with pytest.raises(Exception, match='Unknown Exception'):
            SmallAssetConvertor.convert(self.user, [self.market_currency, self.xchange_currency], RIAL)

        # Assertions
        mock_convert.assert_called_once_with(self.wallet, self.market_status)


def _patch_inner_convert(func):
    base_patch_module = 'exchange.xchange.small_asset_convertor.'

    @patch(base_patch_module + 'transaction.on_commit', lambda t: t())
    @patch(base_patch_module + 'SmallAssetConvertor._send_new_successful_convert_notification')
    @patch(base_patch_module + 'SmallAssetConvertor._create_and_commit_wallet_transactions')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


class TestInnerConvertMethod(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create(
            username='xchange_small_asset_convertor_test',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.xchange_currency = Currencies.dai
        self.market_currency = Currencies.btc

        # Mock a wallet for the user
        self.wallet = Wallet.get_user_wallet(self.user, self.xchange_currency)

        self.market_status = MarketStatus.objects.create(
            base_currency=self.xchange_currency,
            quote_currency=RIAL,
            base_to_quote_price_buy=Decimal('2.2'),
            quote_to_base_price_buy=Decimal('3.2'),
            base_to_quote_price_sell=Decimal('0.9'),
            quote_to_base_price_sell=Decimal('1.2'),
            min_base_amount=20,
            max_base_amount=100,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )

    @patch('exchange.xchange.small_asset_convertor.transaction.on_commit', lambda t: t())
    @patch('exchange.xchange.small_asset_convertor.SmallAssetConvertor._send_new_successful_convert_notification')
    def test_inner_convert_success(self, mock_send_notification: MagicMock):

        # Set wallet balance
        self.wallet.balance = Decimal('10')
        self.wallet.save()

        assert SmallAssetConvert.objects.count() == 0

        # Call the method
        SmallAssetConvertor._convert(self.wallet, self.market_status)

        # Assertions
        all_small_asset_converts = list(SmallAssetConvert.objects.all())

        assert len(all_small_asset_converts) == 1

        # Convert record assertions
        convert_record = all_small_asset_converts[0]
        assert convert_record.src_currency == self.xchange_currency
        assert convert_record.dst_currency == RIAL
        assert convert_record.src_amount == Decimal('10')
        assert convert_record.dst_amount == Decimal('9')
        assert convert_record.user_id == self.user.id
        assert convert_record.status == SmallAssetConvert.STATUS.created
        assert convert_record.related_batch_trade is None

        giving_currency = _t(get_currency_codename(self.xchange_currency))
        receiving_currency = _t(get_currency_codename(RIAL))
        expected_description = f'تبدیل {giving_currency} به {receiving_currency}'

        # User source transaction assertion
        assert convert_record.src_transaction is not None
        assert convert_record.src_transaction.wallet.user_id == self.user.id
        assert convert_record.src_transaction.amount == Decimal('-10')
        assert convert_record.src_transaction.currency == self.xchange_currency
        assert convert_record.src_transaction.tp == Transaction.TYPE.convert
        assert convert_record.src_transaction.ref_module == Transaction.REF_MODULES['ExchangeSmallAssetSrc']
        assert convert_record.src_transaction.ref_id == convert_record.id
        assert convert_record.src_transaction.description == expected_description

        # User destination transaction assertion
        assert convert_record.dst_transaction is not None
        assert convert_record.dst_transaction.wallet.user_id == self.user.id
        assert convert_record.dst_transaction.amount == Decimal('9')
        assert convert_record.dst_transaction.currency == RIAL
        assert convert_record.dst_transaction.tp == Transaction.TYPE.convert
        assert convert_record.dst_transaction.ref_module == Transaction.REF_MODULES['ExchangeSmallAssetDst']
        assert convert_record.dst_transaction.ref_id == convert_record.id
        assert convert_record.dst_transaction.description == expected_description

        # System source transaction assertion
        assert convert_record.system_src_transaction is not None
        assert convert_record.system_src_transaction.wallet.user_id == get_small_assets_convert_system_user().id
        assert convert_record.system_src_transaction.amount == Decimal('10')
        assert convert_record.system_src_transaction.currency == self.xchange_currency
        assert convert_record.system_src_transaction.tp == Transaction.TYPE.convert
        assert (
            convert_record.system_src_transaction.ref_module == Transaction.REF_MODULES['ExchangeSmallAssetSystemSrc']
        )
        assert convert_record.system_src_transaction.ref_id == convert_record.id
        assert convert_record.system_src_transaction.description == expected_description

        # System destination transaction assertion
        assert convert_record.system_dst_transaction is not None
        assert convert_record.system_dst_transaction.wallet.user_id == get_small_assets_convert_system_user().id
        assert convert_record.system_dst_transaction.amount == Decimal('-9')
        assert convert_record.system_dst_transaction.currency == RIAL
        assert convert_record.system_dst_transaction.tp == Transaction.TYPE.convert
        assert (
            convert_record.system_dst_transaction.ref_module == Transaction.REF_MODULES['ExchangeSmallAssetSystemDst']
        )
        assert convert_record.system_dst_transaction.ref_id == convert_record.id
        assert convert_record.system_dst_transaction.description == expected_description

        mock_send_notification.assert_called_once_with(convert=convert_record)

    @_patch_inner_convert
    def test_inner_convert_wallet_with_zero_amount(
        self,
        mock_create_and_commit_wallet_transactions: MagicMock,
        mock_send_notification: MagicMock,
    ):
        assert self.wallet.active_balance == Decimal('0')
        assert SmallAssetConvert.objects.count() == 0

        with pytest.raises(
            exceptions.FailedAssetTransfer,
            match='Wallet has not sufficient active balance.',
        ):
            SmallAssetConvertor._convert(self.wallet, self.market_status)

        assert SmallAssetConvert.objects.count() == 0
        mock_create_and_commit_wallet_transactions.assert_not_called()
        mock_send_notification.assert_not_called()

    @_patch_inner_convert
    def test_inner_convert_failed_asset_transfer_exception(
        self,
        mock_create_and_commit_wallet_transactions: MagicMock,
        mock_send_notification: MagicMock,
    ):
        # Set wallet balance
        self.wallet.balance = Decimal('10')
        self.wallet.save()

        mock_create_and_commit_wallet_transactions.side_effect = exceptions.FailedAssetTransfer(
            'Invalid wallet of insufficient balance.',
        )

        assert SmallAssetConvert.objects.count() == 0

        with pytest.raises(exceptions.FailedAssetTransfer, match='Invalid wallet of insufficient balance.'):
            SmallAssetConvertor._convert(self.wallet, self.market_status)

        assert SmallAssetConvert.objects.count() == 0
        mock_send_notification.assert_not_called()

    @_patch_inner_convert
    def test_inner_convert_wallet_with_more_than_min(
        self,
        mock_create_and_commit_wallet_transactions: MagicMock,
        mock_send_notification: MagicMock,
    ):
        # Set wallet balance
        self.wallet.balance = Decimal('100')
        self.wallet.save()

        assert SmallAssetConvert.objects.count() == 0

        with pytest.raises(exceptions.FailedAssetTransfer, match='Wallet balance is more than convert minimum.'):
            SmallAssetConvertor._convert(self.wallet, self.market_status)

        assert SmallAssetConvert.objects.count() == 0
        mock_create_and_commit_wallet_transactions.assert_not_called()
        mock_send_notification.assert_not_called()


def _patch_create_and_commit_wallet_transactions(func):
    base_patch_module = 'exchange.xchange.small_asset_convertor.'

    @patch(base_patch_module + 'get_small_assets_convert_system_user', lambda: User(id=14124124))
    @patch(base_patch_module + 'create_and_commit_system_user_transaction')
    @patch(base_patch_module + 'create_and_commit_transaction')
    @patch(base_patch_module + 'SmallAssetConvert.save')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


class TestWalletTransactionsMethod(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create(
            username='xchange_small_asset_convertor_test',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.xchange_currency = Currencies.dai
        self.market_currency = Currencies.btc

        # Mock a wallet for the user
        self.wallet = Wallet.get_user_wallet(self.user, self.xchange_currency)

        self.small_asset_convert, _ = SmallAssetConvert.objects.get_or_create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=Decimal('100'),
            dst_amount=Decimal('90'),
        )

    @_patch_create_and_commit_wallet_transactions
    def test_create_and_commit_wallet_transactions_success(
        self,
        small_asset_convert_save_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
        create_and_commit_system_user_transaction: MagicMock,
    ):
        transactions = [Transaction(balance=1) for _ in range(4)]
        create_and_commit_transaction_mock.side_effect = transactions[:2]
        create_and_commit_system_user_transaction.side_effect = transactions[2:]
        SmallAssetConvertor._create_and_commit_wallet_transactions(self.small_asset_convert)

        giving_currency = _t(get_currency_codename(self.xchange_currency))
        receiving_currency = _t(get_currency_codename(RIAL))
        expected_description = f'تبدیل {giving_currency} به {receiving_currency}'

        create_and_commit_transaction_mock.assert_has_calls(
            any_order=False,
            calls=[
                call(
                    user_id=self.user.id,
                    currency=self.xchange_currency,
                    amount=Decimal('-100'),
                    ref_module=RefMod.convert_sa_user_src,
                    ref_id=self.small_asset_convert.id,
                    description=expected_description,
                ),
                call(
                    user_id=self.user.id,
                    currency=RIAL,
                    amount=Decimal('90'),
                    ref_module=RefMod.convert_sa_user_dst,
                    ref_id=self.small_asset_convert.id,
                    description=expected_description,
                ),
            ],
        )

        create_and_commit_system_user_transaction.assert_has_calls(
            any_order=False,
            calls=[
                call(
                    user_id=14124124,
                    currency=self.xchange_currency,
                    amount=Decimal('100'),
                    ref_module=RefMod.convert_sa_system_src,
                    ref_id=self.small_asset_convert.id,
                    description=expected_description,
                ),
                call(
                    user_id=14124124,
                    currency=RIAL,
                    amount=Decimal('-90'),
                    ref_module=RefMod.convert_sa_system_dst,
                    ref_id=self.small_asset_convert.id,
                    description=expected_description,
                ),
            ],
        )
        small_asset_convert_save_mock.assert_called_once_with()
        assert self.small_asset_convert.src_transaction == transactions[0]
        assert self.small_asset_convert.dst_transaction == transactions[1]
        assert self.small_asset_convert.system_src_transaction == transactions[2]
        assert self.small_asset_convert.system_dst_transaction == transactions[3]

    @_patch_create_and_commit_wallet_transactions
    def test_create_and_commit_wallet_transactions_failed_user_transfer(
        self,
        small_asset_convert_save_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
        create_and_commit_system_user_transaction: MagicMock,
    ):
        create_and_commit_transaction_mock.side_effect = [Transaction(), ValueError]
        with pytest.raises(exceptions.FailedAssetTransfer):
            SmallAssetConvertor._create_and_commit_wallet_transactions(self.small_asset_convert)

        create_and_commit_system_user_transaction.assert_not_called()
        small_asset_convert_save_mock.assert_not_called()

    @_patch_create_and_commit_wallet_transactions
    def test_create_and_commit_wallet_transactions_failed_system_transfer(
        self,
        small_asset_convert_save_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
        create_and_commit_system_user_transaction: MagicMock,
    ):
        create_and_commit_transaction_mock.side_effect = [Transaction(), Transaction()]
        create_and_commit_system_user_transaction.side_effect = [ValueError]

        with pytest.raises(exceptions.PairIsClosed):
            SmallAssetConvertor._create_and_commit_wallet_transactions(self.small_asset_convert)

        create_and_commit_transaction_mock.assert_called()
        small_asset_convert_save_mock.assert_not_called()


class TestNotificationMethod(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create(
            username='xchange_small_asset_convertor_test',
            user_type=User.USER_TYPE_LEVEL1,
        )

        self.xchange_currency = Currencies.dai
        self.market_currency = Currencies.btc

        self.small_asset_convert, _ = SmallAssetConvert.objects.get_or_create(
            user=self.user,
            src_currency=self.xchange_currency,
            dst_currency=RIAL,
            src_amount=Decimal('100'),
            dst_amount=Decimal('90'),
        )

    def test_send_new_successful_convert_notification(self):
        message = 'معامله انجام شد: فروش 100.000 دای'

        assert not Notification.objects.filter(user=self.user, message=message).exists()

        SmallAssetConvertor._send_new_successful_convert_notification(self.small_asset_convert)

        assert Notification.objects.filter(user=self.user, message=message).exists()

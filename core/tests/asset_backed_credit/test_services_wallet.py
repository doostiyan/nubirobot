import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, call, patch

import fakeredis
import pytest
import responses
from django.test import TestCase
from rest_framework import status
from rest_framework.test import override_settings

from exchange import settings
from exchange.accounts.models import User
from exchange.asset_backed_credit.crons import ProcessWalletWithdrawsCron
from exchange.asset_backed_credit.exceptions import InsufficientCollateralError, PendingSettlementExists
from exchange.asset_backed_credit.externals.wallet import WalletTransferAPI, WalletType
from exchange.asset_backed_credit.models import InternalUser, Service, WalletCache, WalletTransferLog
from exchange.asset_backed_credit.models.wallet import wallet_cache_manager
from exchange.asset_backed_credit.services.wallet.transfer import process_wallet_transfer_log, process_withdraw_request
from exchange.asset_backed_credit.services.wallet.wallet import check_wallets_cache_consistency
from exchange.asset_backed_credit.tasks import process_wallet_transfer_log_task, task_process_withdraw_request
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.wallet.models import Transaction as ExchangeTransaction
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WalletBulkTransferRequest as ExchangeWalletBulkTransferRequest
from tests.asset_backed_credit.helper import ABCMixins, APIHelper
from tests.base.utils import create_order


class WithdrawCreateAPITests(ABCMixins, APIHelper):
    URL = '/asset-backed-credit/withdraws/create'

    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.internal_user = InternalUser.objects.create(uid=cls.user.uid, user_type=cls.user.user_type)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_withdraw(self, data, mock_task_withdraw_request: MagicMock = None):
        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK, response.json()
        json_response = response.json()
        assert json_response['status'] == 'ok', json_response
        assert 'result' in json_response
        result = json_response['result']
        assert result['id'] is not None
        assert result['createdAt'] is not None
        assert result['rejectionReason'] == ''
        if data.get('srcType', 'credit') in ['credit', 'collateral']:
            assert result['srcType'] == 'credit'
        else:
            assert result['srcType'] == 'debit'
        assert result['dstType'] == data['dstType']
        assert 'transfers' in result
        assert result['transfers'] == data['transfers']

        wallet_transfer_log = ExchangeWalletBulkTransferRequest.objects.filter().last()
        assert wallet_transfer_log.status == ExchangeWalletBulkTransferRequest.STATUS.new
        assert wallet_transfer_log.user == self.user
        if result['srcType'] == 'credit':
            assert wallet_transfer_log.src_wallet_type == ExchangeWallet.WALLET_TYPE.credit
        else:
            assert wallet_transfer_log.src_wallet_type == ExchangeWallet.WALLET_TYPE.debit
        assert wallet_transfer_log.dst_wallet_type == getattr(ExchangeWallet.WALLET_TYPE, data['dstType'])
        assert wallet_transfer_log.rejection_reason == ''
        assert wallet_transfer_log.currency_amounts == {
            str(self.get_currency_int(currency_amount['currency'])): currency_amount['amount']
            for currency_amount in data['transfers']
        }
        assert wallet_transfer_log.transactions.count() == 0

        if mock_task_withdraw_request:
            mock_task_withdraw_request.assert_called_once_with(result['id'])

    def get_currency_int(self, currency_codename):
        return getattr(Currencies, currency_codename)

    def _test_unsuccessful_withdraw(self, data, code, msg):
        initial_transactions = ExchangeTransaction.objects.count()
        initial_balances = list(ExchangeWallet.objects.filter(user=self.user).order_by('type'))
        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == (
            status.HTTP_400_BAD_REQUEST
            if code == 'ParseError'
            else 200
            if code == 'FeatureUnavailable'
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        ), response.json()
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert data['message'] == msg
        assert ExchangeTransaction.objects.count() == initial_transactions
        assert list(ExchangeWallet.objects.filter(user=self.user).order_by('type')) == initial_balances

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_wallets_withdraw_credit_to_spot(self, mock_task_withdraw_request: MagicMock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'))

        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)

        self._test_successful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                    {'currency': 'rls', 'amount': '10000'},
                ],
            },
            mock_task_withdraw_request,
        )

    @responses.activate
    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.process_wallet_transfer_log_task.delay')
    def test_wallets_withdraw_credit_to_spot_with_transfer_internal_api_enabled(
        self, mock_task_withdraw_request: MagicMock
    ):
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'))

        responses.post(
            url=WalletTransferAPI.url,
            json={'id': 2},
            status=status.HTTP_200_OK,
        )

        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)

        data = {
            'srcType': 'credit',
            'dstType': 'spot',
            'transfers': [
                {'currency': 'usdt', 'amount': '30.6'},
                {'currency': 'rls', 'amount': '10000'},
            ],
        }

        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK, response.json()
        json_response = response.json()
        assert json_response['status'] == 'ok', json_response
        assert 'result' in json_response
        result = json_response['result']
        assert result['id'] is not None
        assert result['createdAt'] is not None
        assert result['rejectionReason'] == ''
        assert result['srcType'] == 'credit'
        assert result['dstType'] == data['dstType']
        assert 'transfers' in result
        assert result['transfers'] == data['transfers']

        wallet_transfer_log = WalletTransferLog.objects.first()
        assert wallet_transfer_log.status == WalletTransferLog.STATUS.new
        assert wallet_transfer_log.user == self.user
        assert wallet_transfer_log.src_wallet_type == ExchangeWallet.WALLET_TYPE.credit
        assert wallet_transfer_log.dst_wallet_type == getattr(ExchangeWallet.WALLET_TYPE, data['dstType'])
        assert wallet_transfer_log.transfer_items == {
            str(self.get_currency_int(currency_amount['currency'])): currency_amount['amount']
            for currency_amount in data['transfers']
        }

        mock_task_withdraw_request.assert_called_once_with(result['id'])

    @patch('exchange.asset_backed_credit.tasks.process_wallet_transfer_log_task.delay')
    def test_when_transfer_internal_api_is_enabled_and_user_has_credit_pending_transfer_log_then_pending_error_raises(
        self, mocked_transfer_task
    ):
        ExchangeWalletBulkTransferRequest.objects.all().delete()
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'))
        WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: '30.6'},
            status=WalletTransferLog.STATUS.new,
        )

        data = {
            'srcType': 'credit',
            'dstType': 'spot',
            'transfers': [
                {'currency': get_currency_codename(Currencies.usdt), 'amount': '30.6'},
            ],
        }

        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert 'PendingTransferExists' == response.json()['code']
        assert mocked_transfer_task.call_count == 0

    @patch('exchange.asset_backed_credit.tasks.process_wallet_transfer_log_task.delay')
    def test_when_transfer_internal_api_is_enabled_and_user_has_debit_pending_transfer_log_then_pending_error_raises(
        self, mocked_transfer_task
    ):
        ExchangeWalletBulkTransferRequest.objects.all().delete()
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50'), tp=ExchangeWallet.WALLET_TYPE.debit)
        WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.debit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: '30.6'},
            status=WalletTransferLog.STATUS.new,
        )

        data = {
            'srcType': 'debit',
            'dstType': 'spot',
            'transfers': [
                {'currency': get_currency_codename(Currencies.usdt), 'amount': '30.6'},
            ],
        }

        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert 'PendingTransferExists' == response.json()['code']
        assert mocked_transfer_task.call_count == 0

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @responses.activate
    @patch('exchange.asset_backed_credit.tasks.process_wallet_transfer_log_task.delay')
    def test_wallets_withdraw_debit_to_spot_success_when_transfer_internal_api_enabled(
        self, mock_task_withdraw_request: MagicMock
    ):
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'), tp=ExchangeWallet.WALLET_TYPE.debit)
        responses.post(
            url=WalletTransferAPI.url,
            json={'id': 2},
            status=status.HTTP_200_OK,
        )
        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)

        data = {
            'srcType': 'debit',
            'dstType': 'spot',
            'transfers': [
                {'currency': 'usdt', 'amount': '30.6'},
                {'currency': 'rls', 'amount': '10000'},
            ],
        }

        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK, response.json()
        json_response = response.json()
        assert json_response['status'] == 'ok', json_response
        assert 'result' in json_response
        result = json_response['result']
        assert result['id'] is not None
        assert result['createdAt'] is not None
        assert result['rejectionReason'] == ''
        assert result['srcType'] == 'debit'
        assert result['dstType'] == data['dstType']
        assert 'transfers' in result
        assert result['transfers'] == data['transfers']

        wallet_transfer_log = WalletTransferLog.objects.first()
        assert wallet_transfer_log.status == WalletTransferLog.STATUS.new
        assert wallet_transfer_log.user == self.user
        assert wallet_transfer_log.src_wallet_type == ExchangeWallet.WALLET_TYPE.debit
        assert wallet_transfer_log.dst_wallet_type == getattr(ExchangeWallet.WALLET_TYPE, data['dstType'])
        assert wallet_transfer_log.transfer_items == {
            str(self.get_currency_int(currency_amount['currency'])): currency_amount['amount']
            for currency_amount in data['transfers']
        }

        mock_task_withdraw_request.assert_called_once_with(result['id'])

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @responses.activate
    @patch('exchange.asset_backed_credit.tasks.process_wallet_transfer_log_task.delay')
    def test_wallets_withdraw_debit_to_spot_success_when_transfer_internal_api_enabled_and_user_has_pending_credit_transfer(
        self, mock_task_withdraw_request: MagicMock
    ):
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'), tp=ExchangeWallet.WALLET_TYPE.debit)
        responses.post(
            url=WalletTransferAPI.url,
            json={'id': 2},
            status=status.HTTP_200_OK,
        )
        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)
        WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: '30000.6'},
            status=WalletTransferLog.STATUS.new,
        )

        data = {
            'srcType': 'debit',
            'dstType': 'spot',
            'transfers': [
                {'currency': 'usdt', 'amount': '30.6'},
                {'currency': 'rls', 'amount': '10000'},
            ],
        }

        response = self.client.post(self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK, response.json()
        json_response = response.json()
        assert json_response['status'] == 'ok', json_response
        assert 'result' in json_response
        result = json_response['result']
        assert result['id'] is not None
        assert result['createdAt'] is not None
        assert result['rejectionReason'] == ''
        assert result['srcType'] == 'debit'
        assert result['dstType'] == data['dstType']
        assert 'transfers' in result
        assert result['transfers'] == data['transfers']

        wallet_transfer_log = WalletTransferLog.objects.filter().last()
        assert wallet_transfer_log.status == WalletTransferLog.STATUS.new
        assert wallet_transfer_log.user == self.user
        assert wallet_transfer_log.src_wallet_type == ExchangeWallet.WALLET_TYPE.debit
        assert wallet_transfer_log.dst_wallet_type == getattr(ExchangeWallet.WALLET_TYPE, data['dstType'])
        assert wallet_transfer_log.transfer_items == {
            str(self.get_currency_int(currency_amount['currency'])): currency_amount['amount']
            for currency_amount in data['transfers']
        }

        mock_task_withdraw_request.assert_called_once_with(result['id'])

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    def test_wallets_withdraw_invalid_margin_ratio_after_transfer(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'))

        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '15.6'},
                    {'currency': 'rls', 'amount': '10000'},
                    {'currency': 'btc', 'amount': '0.01'},
                ],
            },
            'InvalidMarginRatioAfterTransfer',
            'Transfers invalidates the margin ratio to below acceptable value',
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    def test_debit_wallets_withdraw_fails_when_invalid_margin_ratio_after_transfer(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'), tp=ExchangeWallet.WALLET_TYPE.debit)

        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '15.6'},
                    {'currency': 'rls', 'amount': '10000'},
                    {'currency': 'btc', 'amount': '0.01'},
                ],
            },
            'InvalidMarginRatioAfterTransfer',
            'Transfers invalidates the margin ratio to below acceptable value',
        )

    def test_wallets_withdraw_to_credit_when_pending_settlement_exists(self):
        self.create_settlement(amount=100, user_service=self.create_user_service(user=self.user))

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'PendingSettlementExists',
            'A pending settlement exists, try again later.',
        )

    def test_wallets_withdraw_to_credit_when_pending_transfer_exists(self):
        ExchangeWalletBulkTransferRequest.objects.create(
            user=self.user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            currency_amounts={},
        )
        self._test_unsuccessful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'PendingTransferExists',
            'A pending transfer exists',
        )

    def test_wallets_withdraw_to_credit(self):
        self._test_unsuccessful_withdraw(
            {
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'InvalidDstType',
            'dstType can not be anything else that margin or spot',
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_wallets_withdraw_credit_to_margin_valid_coins(self, mock_task_withdraw_request: MagicMock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100.0'))

        self._test_successful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'margin',
                'transfers': [
                    {'currency': 'usdt', 'amount': '20.0'},
                ],
            },
            mock_task_withdraw_request,
        )

    def test_wallets_withdraw_credit_to_margin_invalid_coins(self):
        btc_credit_wallet = ExchangeWallet.get_user_wallet(
            self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        btc_credit_wallet.create_transaction('manual', amount='30.6').commit()
        usdt_credit_wallet = ExchangeWallet.get_user_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
        )
        usdt_credit_wallet.create_transaction('manual', amount='100.0').commit()

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'margin',
                'transfers': [
                    {'currency': 'btc', 'amount': '10.4'},
                    {'currency': 'usdt', 'amount': '20'},
                ],
            },
            'InvalidMarginCurrency',
            'Invalid currency selected to transfer to margin',
        )

    def test_wallets_withdraw_for_amount_above_active_balance(self):
        create_order(self.user, Currencies.btc, Currencies.usdt, '0.001', '18900', sell=False, charge_ratio=2)
        # wallet.active_balance == $18.9
        self._test_unsuccessful_withdraw(
            {
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '19'},
                ],
            },
            'InsufficientBalance',
            'Active wallet balance of usdt is less than request amount: 19',
        )

    def test_wallets_withdraw_wrong_inputs(self):
        data = {
            'dstType': 'spot',
            'transfers': [
                {'currency': 'usdt', 'amount': '10.4'},
            ],
        }
        self._test_unsuccessful_withdraw(
            {**data, 'dstType': 'invalid-type'},
            'InvalidDstType',
            'dstType can not be anything else that margin or spot',
        )
        self._test_unsuccessful_withdraw(
            {**data, 'srcType': 'spot'},
            'ParseError',
            'Source wallet should be one of collateral or debit wallets',
        )
        self._test_unsuccessful_withdraw(
            {**data, 'transfers': 'invalid-list'},
            'ParseError',
            'transfers input should be a valid list',
        )
        self._test_unsuccessful_withdraw(
            {'dstType': 'spot'},
            'ParseError',
            'transfers field required',
        )

        self._test_unsuccessful_withdraw(
            {'dstType': 'credit'},
            'InvalidDstType',
            'dstType can not be anything else that margin or spot',
        )

        self._test_unsuccessful_withdraw(
            {'transfers': []},
            'ParseError',
            'dsttype field required',
        )
        self._test_unsuccessful_withdraw(
            [1, 2, 3],
            'ParseError',
            'Input should be a dict: "[1, 2, 3]"',
        )

        self._test_unsuccessful_withdraw(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': -1}]},
            'InvalidAmount',
            'Amount can not be less than zero',
        )

        self._test_unsuccessful_withdraw(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': ''}]},
            'ParseError',
            'Missing monetary value',
        )

        self._test_unsuccessful_withdraw(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': '12,000.12'}]},
            'ParseError',
            'Invalid monetary value: "12,000.12"',
        )

        self._test_unsuccessful_withdraw(
            {**data, 'transfers': [{'currency': 'us', 'amount': '10.4'}]},
            'ParseError',
            'Invalid choices: "us"',
        )
        self._test_unsuccessful_withdraw(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': '-1E-10'}]},
            'InvalidAmount',
            'Amount can not be less than zero',
        )

        for dst in (125, 's'):
            self._test_unsuccessful_withdraw(
                {**data, 'dstType': dst}, 'InvalidDstType', f'dstType can not be anything else that margin or spot'
            )

        self._test_unsuccessful_withdraw(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': '1'} for _ in range(21)]},
            'ParseError',
            'List is too long, max len is 20',
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_debit_to_spot_success(self, mock_task_withdraw_request: MagicMock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'), tp=ExchangeWallet.WALLET_TYPE.debit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service)

        self._test_successful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                    {'currency': 'rls', 'amount': '10000'},
                ],
            },
            mock_task_withdraw_request,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_is_backward_compatible_and_default_source_is_credit(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.credit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.credit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'), tp=ExchangeWallet.WALLET_TYPE.credit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service)

        self._test_successful_withdraw(
            {
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                    {'currency': 'rls', 'amount': '10000'},
                ],
            },
            mock_task_withdraw_request,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_wallets_withdraw_debit_to_margin_success(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('20.1'), tp=ExchangeWallet.WALLET_TYPE.debit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service)

        self._test_successful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'margin',
                'transfers': [
                    {'currency': 'usdt', 'amount': '20'},
                ],
            },
            mock_task_withdraw_request,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_collateral_to_spot_success(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.credit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.credit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.01'), tp=ExchangeWallet.WALLET_TYPE.credit)

        self.create_user_service(user=self.user)

        self._test_successful_withdraw(
            {
                'srcType': 'collateral',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                    {'currency': 'rls', 'amount': '10000'},
                    {'currency': 'btc', 'amount': '0.0001'},
                ],
            },
            mock_task_withdraw_request,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_collateral_to_margin_success(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('50000'), tp=ExchangeWallet.WALLET_TYPE.credit)

        self.create_user_service(user=self.user)

        self._test_successful_withdraw(
            {
                'srcType': 'collateral',
                'dstType': 'margin',
                'transfers': [
                    {'currency': 'usdt', 'amount': '500'},
                ],
            },
            mock_task_withdraw_request,
        )

    def test_withdraw_fails_when_user_debit_wallet_has_not_enough_balance(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.5'), tp=ExchangeWallet.WALLET_TYPE.debit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service)

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                    {'currency': 'btc', 'amount': '5'},
                ],
            },
            code='InsufficientBalance',
            msg='Active wallet balance of btc is less than request amount: 5',
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_from_debit_fails_when_user_has_pending_debit_withdraw_request(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'), tp=ExchangeWallet.WALLET_TYPE.debit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_user_service(user=self.user, service=service)

        self._test_successful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '21'},
                ],
            },
            mock_task_withdraw_request,
        )
        self._test_unsuccessful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                ],
            },
            code='PendingTransferExists',
            msg='A pending transfer exists',
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_from_credit_success_when_user_has_pending_debit_withdraw_request(
        self, mock_task_withdraw_request
    ):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('300'), tp=ExchangeWallet.WALLET_TYPE.credit)

        self.create_user_service(user=self.user)

        self._test_successful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '21'},
                ],
            },
            mock_task_withdraw_request,
        )
        self._test_successful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '30.6'},
                ],
            },
        )
        assert mock_task_withdraw_request.call_count == 2

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    def test_withdraw_fails_collateral_to_spot_for_margin_ratio_error(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('10000'))

        self.create_user_service(user=self.user, initial_debt=Decimal('30.6') * 50_000_0 + 10000)

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'collateral',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '15.6'},
                    {'currency': 'rls', 'amount': '10000'},
                ],
            },
            'InvalidMarginRatioAfterTransfer',
            'Transfers invalidates the margin ratio to below acceptable value',
        )

    def test_withdraw_from_debit_fails_when_pending_settlement_transaction_exists(self):
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_settlement(
            amount=Decimal(100), user_service=self.create_user_service(user=self.user, service=service)
        )

        self._test_unsuccessful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'PendingSettlementExists',
            'A pending settlement exists, try again later.',
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_from_debit_success_when_user_has_credit_pending_settlement(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        service = self.create_service(provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit)
        self.create_settlement(Decimal(100), user_service=self.create_user_service(user=self.user, service=service))

        self._test_successful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.6'},
                ],
            },
            mock_task_withdraw_request,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_from_debit_success_when_user_has_loan_pending_settlement(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.debit)
        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        self.create_settlement(Decimal(100), user_service=self.create_user_service(user=self.user, service=service))

        self._test_successful_withdraw(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.6'},
                ],
            },
            mock_task_withdraw_request,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_withdraw_from_credit_success_when_user_has_debit_pending_settlement(self, mock_task_withdraw_request):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30.6'), tp=ExchangeWallet.WALLET_TYPE.credit)
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_settlement(
            amount=Decimal(100), user_service=self.create_user_service(user=self.user, service=service)
        )

        self._test_successful_withdraw(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.6'},
                ],
            },
            mock_task_withdraw_request,
        )


class TestProcessWithdrawsCron(ABCMixins, TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.candid_1 = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.user,
            created_at=ir_now() - timedelta(minutes=15),
        )
        self.candid_2 = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.user,
            created_at=ir_now() - timedelta(minutes=15),
        )
        self.candid_3 = self.create_wallet_bulk_transfer(
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.user,
            created_at=ir_now() - timedelta(minutes=15),
        )

        self.not_candid_1 = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.done,
            user=self.user,
        )
        self.not_candid_1 = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.rejected,
            user=self.user,
        )
        self.not_candid_1 = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.user,
            created_at=ir_now() - timedelta(minutes=14, seconds=59),
        )

    @override_settings(ABC_WITHDRAW_DELAY=datetime.timedelta(minutes=15))
    @patch('exchange.asset_backed_credit.tasks.task_process_withdraw_request.delay')
    def test_user_settlement_cron(self, withdraw_task_mock: MagicMock):
        ProcessWalletWithdrawsCron().run()
        assert withdraw_task_mock.call_count == 3
        withdraw_task_mock.assert_has_calls(
            [
                call(self.candid_1.id),
                call(self.candid_2.id),
                call(self.candid_3.id),
            ],
            any_order=True,
        )

    @override_settings(ABC_WITHDRAW_DELAY=datetime.timedelta(minutes=15))
    @patch('exchange.asset_backed_credit.tasks.process_wallet_transfer_log_task.delay')
    def test_user_settlement_when_transfer_internal_api_is_enabled(self, mock_collateral_task):
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')
        internal_user = self.create_internal_user(self.user)
        WalletTransferLog.create(
            user=self.user,
            internal_user=internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )
        WalletTransferLog.create(
            user=self.user,
            internal_user=internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
            status=WalletTransferLog.STATUS.pending_to_retry,
        )
        WalletTransferLog.create(
            user=self.user,
            internal_user=internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
            status=WalletTransferLog.STATUS.done
        )
        new_transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )
        new_transfer_log.created_at = ir_now() - (settings.ABC_WITHDRAW_DELAY * 2)
        new_transfer_log.save()

        retry_transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
            status=WalletTransferLog.STATUS.pending_to_retry,
            api_called_at=ir_now(),
        )
        retry_transfer_log.created_at = ir_now() - (settings.ABC_WITHDRAW_DELAY * 2)
        retry_transfer_log.save()

        ProcessWalletWithdrawsCron().run()

        assert mock_collateral_task.call_count == 2
        mock_collateral_task.assert_has_calls([call(new_transfer_log.id), call(retry_transfer_log.id)], any_order=True)


@patch('exchange.asset_backed_credit.tasks.process_withdraw_request')
class TestProcessWithdrawRequestTask(ABCMixins, TestCase):
    def test_process_abc_collateral_withdraw_request_task(self, process_abc_withdraw_request_mock: MagicMock):
        transfer_request = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.create_user(),
            created_at=ir_now() - timedelta(minutes=15),
        )
        task_process_withdraw_request(transfer_request.id)

        process_abc_withdraw_request_mock.assert_called_once_with(transfer_request.id)

    def test_process_withdraw_request_of_debit_to_spot(self, process_abc_withdraw_request_mock):
        transfer_request = self.create_wallet_bulk_transfer(
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.create_user(),
            created_at=ir_now() - timedelta(minutes=15),
        )
        task_process_withdraw_request(transfer_request.id)

        process_abc_withdraw_request_mock.assert_called_once_with(transfer_request.id)

    def test_process_withdraw_request_of_debit_to_margin(self, process_abc_withdraw_request_mock):
        transfer_request = self.create_wallet_bulk_transfer(
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            dst_type=ExchangeWallet.WALLET_TYPE.margin,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.create_user(),
            created_at=ir_now() - timedelta(minutes=15),
        )
        task_process_withdraw_request(transfer_request.id)

        process_abc_withdraw_request_mock.assert_called_once_with(transfer_request.id)


class TestProcessCollateralWithdrawRequestFunction(ABCMixins, TestCase):
    def setUp(self):
        self.amount = Decimal(10)
        self.withdraw_request = self.create_wallet_bulk_transfer(
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            user=self.create_user(),
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str(self.amount)},
        )
        self.user = self.withdraw_request.user
        self.internal_user = self.create_internal_user(self.user)
        self.src_wallet = ExchangeWallet.get_user_wallet(
            self.user,
            Currencies.usdt,
            ExchangeWallet.WALLET_TYPE.credit,
        )
        self.dst_wallet = ExchangeWallet.get_user_wallet(
            self.user,
            Currencies.usdt,
            tp=ExchangeWallet.WALLET_TYPE.spot,
        )

    def assert_successful(self, expected_src_wallet_balance: Decimal, expected_dst_wallet_balance: Decimal):
        self.withdraw_request.refresh_from_db()
        assert self.withdraw_request.status == ExchangeWalletBulkTransferRequest.STATUS.done
        assert self.withdraw_request.rejection_reason == ''

        self.src_wallet.refresh_from_db()
        assert self.src_wallet.balance == expected_src_wallet_balance
        assert self.src_wallet.blocked_balance == 0

        self.dst_wallet.refresh_from_db()
        assert self.dst_wallet.balance == expected_dst_wallet_balance

        assert self.withdraw_request.transactions.count() == 2

        withdraw_tx = self.withdraw_request.transactions.get(wallet=self.src_wallet)
        assert withdraw_tx.amount == -self.amount

        deposit_tx = self.withdraw_request.transactions.get(wallet=self.dst_wallet)
        assert deposit_tx.amount == self.amount

    def assert_unsuccessful(self, reason: Optional[str] = None, src_wallet_balance=0):
        self.withdraw_request.refresh_from_db()
        if reason:
            assert self.withdraw_request.status == ExchangeWalletBulkTransferRequest.STATUS.rejected
            assert self.withdraw_request.rejection_reason == reason
        else:
            assert self.withdraw_request.status == ExchangeWalletBulkTransferRequest.STATUS.new

        assert self.withdraw_request.transactions.count() == 0

        self.src_wallet.refresh_from_db()
        assert self.src_wallet.balance == src_wallet_balance
        self.dst_wallet.refresh_from_db()
        assert self.dst_wallet.balance == 0

    def test_process_abc_collateral_withdraw_request_when_insufficient_balance(self):
        process_withdraw_request(self.withdraw_request.id)
        self.assert_unsuccessful('موجودی ازاد کیف پول usdt کمتر از مقدار درخواست شده است.')

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
    def test_process_abc_collateral_withdraw_request_when_invalid_margin_ratio_after_transfer(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, 135)
        self.create_user_service(self.user, initial_debt=100 * 10_000_0)

        process_withdraw_request(self.withdraw_request.id)
        self.assert_unsuccessful('این درخواست نسبت تعهد را به زیر حد مجاز می‌رساند.', 135)

    def test_process_abc_collateral_withdraw_request_when_settlement_exists(self):
        self.create_settlement(Decimal(1), user_service=self.create_user_service(user=self.user))
        with pytest.raises(PendingSettlementExists):
            process_withdraw_request(self.withdraw_request.id)

        self.assert_unsuccessful()

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
    def test_process_abc_collateral_withdraw_request_success(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, 140)

        process_withdraw_request(self.withdraw_request.id)
        self.assert_successful(expected_src_wallet_balance=140 - self.amount, expected_dst_wallet_balance=self.amount)


class TestProcessDebitWithdrawRequestFunction(ABCMixins, TestCase):
    def setUp(self):
        self.withdraw_amount = Decimal('10.7')
        self.user = self.create_user()
        self.internal_user = self.create_internal_user(self.user)

    def assert_successful(
        self,
        withdraw_request: ExchangeWalletBulkTransferRequest,
        expected_src_wallet_balance: Decimal,
        expected_dst_wallet_balance: Decimal,
    ):
        src_wallet = ExchangeWallet.get_user_wallet(
            self.user,
            Currencies.usdt,
            withdraw_request.src_wallet_type,
        )
        dst_wallet = ExchangeWallet.get_user_wallet(
            self.user,
            Currencies.usdt,
            withdraw_request.dst_wallet_type,
        )

        withdraw_request.refresh_from_db()
        assert withdraw_request.status == ExchangeWalletBulkTransferRequest.STATUS.done
        assert withdraw_request.rejection_reason == ''

        src_wallet.refresh_from_db()
        assert src_wallet.balance == expected_src_wallet_balance
        assert src_wallet.blocked_balance == 0

        dst_wallet.refresh_from_db()
        assert dst_wallet.balance == expected_dst_wallet_balance

        assert withdraw_request.transactions.count() == 2

        withdraw_tx = withdraw_request.transactions.get(wallet=src_wallet)
        assert withdraw_tx.amount == -self.withdraw_amount

        deposit_tx = withdraw_request.transactions.get(wallet=dst_wallet)
        assert deposit_tx.amount == self.withdraw_amount

    def assert_unsuccessful(
        self,
        withdraw_request: ExchangeWalletBulkTransferRequest,
        reason: Optional[str] = None,
        src_wallet_balance: Decimal = Decimal('0.0'),
    ):
        src_wallet = ExchangeWallet.get_user_wallet(
            self.user,
            Currencies.usdt,
            withdraw_request.src_wallet_type,
        )
        dst_wallet = ExchangeWallet.get_user_wallet(
            self.user,
            Currencies.usdt,
            withdraw_request.dst_wallet_type,
        )

        withdraw_request.refresh_from_db()
        if reason:
            assert withdraw_request.status == ExchangeWalletBulkTransferRequest.STATUS.rejected
            assert withdraw_request.rejection_reason == reason
        else:
            assert withdraw_request.status == ExchangeWalletBulkTransferRequest.STATUS.new

        assert withdraw_request.transactions.count() == 0

        src_wallet.refresh_from_db()
        assert src_wallet.balance == src_wallet_balance
        dst_wallet.refresh_from_db()
        assert dst_wallet.balance == 0

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    def test_process_withdraw_request_debit_to_spot_success(self):
        withdraw_request = self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str(self.withdraw_amount)},
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('140'), tp=ExchangeWallet.WALLET_TYPE.debit)

        process_withdraw_request(withdraw_request.id)

        self.assert_successful(
            withdraw_request,
            expected_src_wallet_balance=Decimal('140') - self.withdraw_amount,
            expected_dst_wallet_balance=self.withdraw_amount,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    def test_process_withdraw_request_debit_to_margin_success(self):
        withdraw_request = self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            dst_type=ExchangeWallet.WALLET_TYPE.margin,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str(self.withdraw_amount)},
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('140'), tp=ExchangeWallet.WALLET_TYPE.debit)

        process_withdraw_request(withdraw_request.id)

        self.assert_successful(
            withdraw_request,
            expected_src_wallet_balance=Decimal('140') - self.withdraw_amount,
            expected_dst_wallet_balance=self.withdraw_amount,
        )

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price',
        lambda c, __: 50_000_0 if c == Currencies.usdt else 500_000_000_0,
    )
    def test_process_debit_withdraw_request_success_when_credit_pending_settlement_exists(self):
        service = self.create_service(provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit)
        self.create_settlement(Decimal(10), user_service=self.create_user_service(user=self.user, service=service))
        self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.credit,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str(self.withdraw_amount)},
        )
        withdraw_request = self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str(self.withdraw_amount)},
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('140'), tp=ExchangeWallet.WALLET_TYPE.debit)

        process_withdraw_request(withdraw_request.id)

        self.assert_successful(
            withdraw_request,
            expected_src_wallet_balance=Decimal('140') - self.withdraw_amount,
            expected_dst_wallet_balance=self.withdraw_amount,
        )

    def test_process_debit_withdraw_request_fails_when_pending_debit_settlement_transaction_exists(self):
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.create_settlement(Decimal(10), user_service=self.create_user_service(user=self.user, service=service))
        withdraw_request = self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str(self.withdraw_amount)},
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('140'), tp=ExchangeWallet.WALLET_TYPE.debit)

        with pytest.raises(PendingSettlementExists):
            process_withdraw_request(withdraw_request.id)

        self.assert_unsuccessful(withdraw_request, src_wallet_balance=Decimal('140'))

    def test_process_debit_withdraw_fails_request_when_balance_is_insufficient(self):
        withdraw_request = self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: str('12000.002')},
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('140'), tp=ExchangeWallet.WALLET_TYPE.debit)

        process_withdraw_request(withdraw_request.id)

        self.assert_unsuccessful(
            withdraw_request, 'موجودی ازاد کیف پول usdt کمتر از مقدار درخواست شده است.', Decimal('140')
        )

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
    def test_process_debit_withdraw_fails_request_when_invalid_margin_ratio_after_transfer(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, 115, tp=ExchangeWallet.WALLET_TYPE.debit)
        service = self.create_service(tp=Service.TYPES.debit)
        self.create_user_service(self.user, service=service, initial_debt=100 * 10_000_0)
        withdraw_request = self.create_wallet_bulk_transfer(
            user=self.user,
            status=ExchangeWalletBulkTransferRequest.STATUS.new,
            src_type=ExchangeWallet.WALLET_TYPE.debit,
            dst_type=ExchangeWallet.WALLET_TYPE.margin,
            created_at=ir_now() - timedelta(minutes=15),
            currency_amounts={Currencies.usdt: '10'},
        )

        process_withdraw_request(withdraw_request.id)
        self.assert_unsuccessful(withdraw_request, 'این درخواست نسبت تعهد را به زیر حد مجاز می‌رساند.', Decimal('115'))


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
class TestProcessWalletTransferLog(TestCase, ABCMixins):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.internal_user = self.create_internal_user(self.user)
        self.api_success_response = {'id': 2}
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @responses.activate
    def test_process_wallet_transfer_success_log_with_success(self, mock_wallet_cache_manager_invalidate: MagicMock):
        responses.post(
            url=WalletTransferAPI.url,
            json=self.api_success_response,
            status=status.HTTP_200_OK,
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('100'))

        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )

        process_wallet_transfer_log(transfer_log.id)

        transfer_log.refresh_from_db()
        assert transfer_log.api_called_at is not None
        assert transfer_log.response_code == status.HTTP_200_OK
        assert transfer_log.response_body is not None
        assert transfer_log.external_transfer_id == self.api_success_response['id']
        assert transfer_log.failed_permanently_reason is None

        mock_wallet_cache_manager_invalidate.assert_called_once_with(user_id=transfer_log.user.uid)

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @responses.activate
    def test_process_wallet_transfer_log_fails_when_invalid_margin_ratio_meets_transfer_requests(
        self, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        responses.post(
            url=WalletTransferAPI.url,
            json=self.api_success_response,
            status=status.HTTP_200_OK,
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('135'))
        self.create_user_service(self.user, initial_debt=100 * 10_000_0)

        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('135')},
        )

        process_wallet_transfer_log(transfer_log.id)

        transfer_log.refresh_from_db()
        assert transfer_log.api_called_at is None
        assert transfer_log.status == WalletTransferLog.STATUS.failed_permanently
        assert transfer_log.failed_permanently_reason == ' درخواست نسبت تعهد را به زیر حد مجاز می‌رساند.'

        mock_wallet_cache_manager_invalidate.assert_not_called()

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @responses.activate
    def test_process_wallet_transfer_log_when_internal_api_not_responding_correctly(
        self, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('100'))
        responses.post(
            url=WalletTransferAPI.url,
            json={'code': 'unknown error'},
            status=status.HTTP_400_BAD_REQUEST,
        )

        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )

        process_wallet_transfer_log(transfer_log.id)

        transfer_log.refresh_from_db()
        assert transfer_log.api_called_at is not None
        assert transfer_log.response_body is not None
        assert transfer_log.response_code == status.HTTP_400_BAD_REQUEST
        assert transfer_log.external_transfer_id is None
        assert transfer_log.failed_permanently_reason is None
        assert transfer_log.status == WalletTransferLog.STATUS.pending_to_retry

        mock_wallet_cache_manager_invalidate.assert_not_called()

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @responses.activate
    def test_process_wallet_transfer_log_when_internal_api_raises_none_retryable_error_then_log_status_changes_to_failed(
        self, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('100'))
        response = (
            {"status": "failed", "code": "InsufficientBalance", "message": "Amount cannot exceed active balance"},
        )
        responses.post(
            url=WalletTransferAPI.url,
            json=response,
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )

        process_wallet_transfer_log(transfer_log.id)

        transfer_log.refresh_from_db()

        assert transfer_log.api_called_at is not None
        assert transfer_log.response_body is not None
        assert transfer_log.response_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert transfer_log.external_transfer_id is None
        assert (
            transfer_log.failed_permanently_reason
            == WalletTransferAPI.FailedPermanentlyReasonEnum.InsufficientBalance.value
        )
        assert transfer_log.status == WalletTransferLog.STATUS.failed_permanently

        mock_wallet_cache_manager_invalidate.assert_not_called()

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @patch('exchange.asset_backed_credit.externals.wallet.WalletProvider.transfer')
    def test_process_wallet_transfer_log_when_log_id_does_not_exist_then_no_error_is_raised(
        self, mocked_provider, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        try:
            not_existing_id = WalletTransferLog.objects.latest('id').id + 1
        except WalletTransferLog.DoesNotExist:
            not_existing_id = 1

        process_wallet_transfer_log(not_existing_id)
        assert mocked_provider.call_count == 0

        mock_wallet_cache_manager_invalidate.assert_not_called()

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @patch('exchange.asset_backed_credit.externals.wallet.WalletProvider.transfer')
    def test_process_wallet_transfer_log_with_failed_log_not_call_transfer_api(
        self, mocked_provider, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
            status=WalletTransferLog.STATUS.failed_permanently,
        )

        process_wallet_transfer_log(transfer_log.id)
        assert mocked_provider.call_count == 0
        assert transfer_log.api_called_at is None

        mock_wallet_cache_manager_invalidate.assert_not_called()

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @patch('exchange.asset_backed_credit.externals.wallet.WalletProvider.transfer')
    def test_process_wallet_transfer_log_with_insufficient_balance_of_one_asset_fails(
        self, mocked_provider, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        responses.post(
            url=WalletTransferAPI.url,
            json=self.api_success_response,
            status=status.HTTP_200_OK,
        )

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10000'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0'))

        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )

        with pytest.raises(InsufficientCollateralError):
            process_wallet_transfer_log(transfer_log.id)

        transfer_log.refresh_from_db()
        assert transfer_log.api_called_at is None
        assert mocked_provider.call_count == 0

        mock_wallet_cache_manager_invalidate.assert_not_called()

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @responses.activate
    def test_process_wallet_transfer_log_from_debit_to_spot_success(
        self, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        responses.post(
            url=WalletTransferAPI.url,
            json=self.api_success_response,
            status=status.HTTP_200_OK,
        )
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'), tp=ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('100'), tp=ExchangeWallet.WALLET_TYPE.debit)

        transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.debit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={Currencies.usdt: Decimal('10'), Currencies.btc: Decimal('100')},
        )

        process_wallet_transfer_log(transfer_log.id)

        transfer_log.refresh_from_db()
        assert transfer_log.api_called_at is not None
        assert transfer_log.response_code == status.HTTP_200_OK
        assert transfer_log.response_body is not None
        assert transfer_log.external_transfer_id == self.api_success_response['id']
        assert transfer_log.failed_permanently_reason is None

        mock_wallet_cache_manager_invalidate.assert_called_once_with(user_id=transfer_log.user.uid)


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
class ProcessWalletTransferLogTaskTest(TestCase, ABCMixins):
    def setUp(self):
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')
        self.user = User.objects.get(id=201)
        self.internal_user = self.create_internal_user(self.user)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('30'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('200'))
        self.transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            dst_wallet_type=ExchangeWallet.WALLET_TYPE.spot,
            transfer_items={int(Currencies.usdt): Decimal('10'), int(Currencies.btc): Decimal('100')},
        )
        self.api_success_response = {'id': 2}

    @responses.activate
    def test_process_wallet_transfer_log_task_success(self):
        responses.post(
            url=WalletTransferAPI.url,
            json={'id': 2},
            status=status.HTTP_200_OK,
        )
        process_wallet_transfer_log_task(self.transfer_log.id)

        self.transfer_log.refresh_from_db()
        assert self.transfer_log.status == WalletTransferLog.STATUS.done
        assert self.transfer_log.external_transfer_id == self.api_success_response['id']
        assert self.transfer_log.failed_permanently_reason is None

    @responses.activate
    def test_process_wallet_transfer_log_task_when_internal_api_raises_error(self):
        responses.post(
            url=WalletTransferAPI.url,
            json={'error': 'unknown'},
            status=status.HTTP_400_BAD_REQUEST,
        )
        process_wallet_transfer_log_task(self.transfer_log.id)

        self.transfer_log.refresh_from_db()
        assert self.transfer_log.status == WalletTransferLog.STATUS.pending_to_retry
        assert self.transfer_log.external_transfer_id is None
        assert self.transfer_log.failed_permanently_reason is None
        assert self.transfer_log.api_called_at is not None
        assert self.transfer_log.response_body is not None


class TestWalletCacheConsistency(TestCase, ABCMixins):
    def setUp(self):
        self.redis = fakeredis.FakeStrictRedis()
        self.redis.flushall()
        wallet_cache_manager.client = self.redis

        self.user = self.create_user()
        self.create_internal_user(self.user)
        self.user_id = self.user.uid

        Settings.set('abc_wallets_cache_consistency_checker_enabled', 'yes')

    @patch('exchange.asset_backed_credit.services.wallet.wallet.logstash_logger.info')
    def test_consistency_no_errors(self, mock_logstash_logger):
        self.charge_exchange_wallet(self.user, Currencies.usdt, amount=130_000_000)
        wallet = WalletCache(
            id=1,
            balance=Decimal('130000000'),
            blocked_balance=Decimal('0'),
            currency=Currencies.usdt,
            type=WalletType.credit,
            updated_at=1,
        )
        wallet_cache_manager.set(self.user_id, wallet)

        errors = check_wallets_cache_consistency()
        assert errors == {}

        mock_logstash_logger.assert_called_once()

    def test_missing_from_cache(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, amount=100_000_000)

        errors = check_wallets_cache_consistency()
        assert errors == {}

    def test_some_wallets_missing_from_cache(self):
        self.charge_exchange_wallet(self.user, Currencies.btc, amount=100_000_000)
        self.charge_exchange_wallet(self.user, Currencies.usdt, amount=100_000_000)
        wallet = WalletCache(
            id=1,
            balance=Decimal('100000000'),
            blocked_balance=Decimal('0'),
            currency=Currencies.usdt,
            type=WalletType.credit,
            updated_at=1,
        )
        wallet_cache_manager.set(self.user_id, wallet)

        errors = check_wallets_cache_consistency()
        assert self.user_id in errors
        assert any('Missing from cache' in e for e in errors[self.user_id])

    def test_missing_from_db(self):
        wallet = WalletCache(
            id=1,
            balance=Decimal('100000000'),
            blocked_balance=Decimal('0'),
            currency=Currencies.usdt,
            type=WalletType.credit,
            updated_at=1,
        )
        wallet_cache_manager.set(self.user_id, wallet)

        errors = check_wallets_cache_consistency()
        assert self.user_id in errors
        assert any('Missing from DB' in e for e in errors[self.user_id])

    def test_field_mismatch(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, amount=123_000_000)
        bad_wallet = WalletCache(
            id=1,
            balance=Decimal('99999999'),
            blocked_balance=Decimal('0'),
            currency=Currencies.usdt,
            type=WalletType.credit,
            updated_at=1,
        )
        wallet_cache_manager.set(self.user_id, bad_wallet)

        errors = check_wallets_cache_consistency()
        assert self.user_id in errors
        assert any('Mismatch for balance' in e for e in errors[self.user_id])

    def test_batch_processing_all_good(self):
        users = [self.user]
        for _ in range(6):
            u = self.create_user()
            self.create_internal_user(u)
            users.append(u)

        for u in users:
            self.charge_exchange_wallet(u, Currencies.eth, amount=50_000_000)
            matching_wallet = WalletCache(
                id=1,
                balance=Decimal('50000000'),
                blocked_balance=Decimal('0'),
                currency=Currencies.eth,
                type=WalletType.credit,
                updated_at=1,
            )
            wallet_cache_manager.set(u.uid, matching_wallet)

        errors = check_wallets_cache_consistency(batch_size=2)
        assert errors == {}

    def test_batch_processing_some_errors(self):
        users = [self.user]
        for _ in range(3):
            u = self.create_user()
            self.create_internal_user(u)
            users.append(u)

        for idx, u in enumerate(users):
            if idx in (0, 1):
                self.charge_exchange_wallet(u, Currencies.usdt, amount=20_000_000)
                w = WalletCache(
                    id=1,
                    balance=Decimal('20000000'),
                    blocked_balance=Decimal('0'),
                    currency=Currencies.usdt,
                    type=WalletType.credit,
                    updated_at=1,
                )
                wallet_cache_manager.set(u.uid, w)
            elif idx == 2:
                self.charge_exchange_wallet(u, Currencies.usdt, amount=30_000_000)
                w = WalletCache(
                    id=1,
                    balance=Decimal('30_000_000'),
                    blocked_balance=Decimal('0'),
                    currency=Currencies.usdt,
                    type=WalletType.credit,
                    updated_at=1,
                )
                wallet_cache_manager.set(u.uid, w)
                self.charge_exchange_wallet(u, Currencies.btc, amount=30_000_000)
            else:
                orphan_wallet = WalletCache(
                    id=1,
                    balance=Decimal('40000000'),
                    blocked_balance=Decimal('0'),
                    currency=Currencies.eth,
                    type=WalletType.credit,
                    updated_at=1,
                )
                wallet_cache_manager.set(u.uid, orphan_wallet)

        errors = check_wallets_cache_consistency(batch_size=2)

        assert users[0].uid not in errors
        assert users[1].uid not in errors

        assert users[2].uid in errors
        assert any('Missing from cache' in msg for msg in errors[users[2].uid])

        assert users[3].uid in errors
        assert any('Missing from DB' in msg for msg in errors[users[3].uid])

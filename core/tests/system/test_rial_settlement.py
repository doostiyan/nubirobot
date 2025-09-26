from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
import pytz
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.models import Currencies
from exchange.system.scripts.rial_settlement import do_settlement
from exchange.wallet.models import Wallet, WithdrawRequest
from tests.base.utils import create_withdraw_request


class RialSettlementTest(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.withdraw = create_withdraw_request(self.user, Currencies.rls, 510_000_000_0,
                                                'None: 546546546546546546546546', WithdrawRequest.STATUS.verified)

    def test_do_settlement_unknown_gateway(self):
        with pytest.raises(ValueError, match='Unknown gateway: "bad_gateway"'):
            do_settlement(withdraw=self.withdraw, gateway='bad_gateway')

    def test_do_settlement_just_work_in_production(self):
        with pytest.raises(ValueError, match='NotAllowedInTestnet'):
            do_settlement(withdraw=self.withdraw, gateway='jibit_v2')

    def test_do_settlement_already_settled(self):
        self.withdraw.updates = 'something'
        self.withdraw.save()
        with pytest.raises(ValueError, match='AlreadySettled'):
            do_settlement(withdraw=self.withdraw, gateway='jibit_v2')

    @override_settings(IS_PROD=True)
    def test_do_settlement_internal_withdraw(self):
        self.withdraw.tp = WithdrawRequest.TYPE.internal
        self.withdraw.save()
        with pytest.raises(ValueError, match='InternalTransfer'):
            do_settlement(withdraw=self.withdraw, gateway='jibit_v2')

    @override_settings(IS_PROD=True)
    def test_do_settlement_not_accepted_withdraw(self):
        cache.set('jibit_trf_access_token', 'nothing')
        self.withdraw.status = WithdrawRequest.STATUS.new
        self.withdraw.save()
        with pytest.raises(ValueError, match='Only accepted requests can be settled'):
            do_settlement(withdraw=self.withdraw, gateway='jibit_v2')

    @override_settings(IS_PROD=True)
    def test_do_settlement_just_rial(self):
        cache.set('jibit_trf_access_token', 'nothing')
        btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        withdraw = create_withdraw_request(user=self.user,
                                           currency=Currencies.rls,
                                           amount=110_000_000_0,
                                           address='None: 546546546546546546546546',
                                           status=WithdrawRequest.STATUS.accepted)
        withdraw.status = WithdrawRequest.STATUS.manual_accepted
        withdraw.wallet = btc_wallet
        withdraw.save()
        with pytest.raises(ValueError, match='Settlement is only available for Rial withdrawals'):
            do_settlement(withdraw=withdraw, gateway='jibit_v2')

    def test_is_over_shaba_limit(self):
        bank_account = BankAccount.objects.create(user=self.user, shaba_number='shaba_number', confirmed=True)
        self.assertTrue(
            WithdrawRequest.is_over_shaba_limit(
                wallet=self.withdraw.wallet, amount=self.withdraw.amount, target_account=bank_account
            )
        )

    def test_do_settlement_invalid_gateway_for_vandar_withdraw(self):
        self.withdraw.target_account = BankAccount.objects.create(
            bank_id=BankAccount.BANK_ID.vandar, account_number='123', shaba_number='123', user=self.user
        )
        self.withdraw.save()
        with pytest.raises(ValueError, match='Vandar withdraw cannot be processed with another gateway!'):
            do_settlement(withdraw=self.withdraw, gateway='jibit')


class WithdrawOver100MTagTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def update_withdraw_status(self, withdraw, bank_account):
        withdraw.status = WithdrawRequest.STATUS.verified
        withdraw.target_account = bank_account
        withdraw.rial_value = 0
        withdraw.save(update_fields=['rial_value', 'status', 'target_account', ])

    @patch('exchange.wallet.models.ir_now')
    def test_is_over_amount_limit_per_date_check(self, dt_mock):
        dt = datetime.strptime('2020-01-10T01:30:00Z', '%Y-%m-%dT%H:%M:%SZ').astimezone(pytz.timezone('Asia/Tehran'))
        bank_account = BankAccount.objects.create(
            user=self.user, shaba_number='546546546546546546546546', confirmed=True, created_at=dt
        )
        dt_mock.return_value = dt

        yesterday = dt - timedelta(hours=1, minutes=31)  # 2020-01-09 23:59
        withdraw = create_withdraw_request(self.user, Currencies.rls,
                                           Decimal(370_000_000_0),
                                           '546546546546546546546546',
                                           created_at=yesterday.astimezone(timezone.utc))
        self.update_withdraw_status(withdraw, bank_account)
        self.assertFalse(
            WithdrawRequest.is_over_shaba_limit(
                wallet=withdraw.wallet, amount=Decimal(40_000_000_0), target_account=bank_account
            )
        )

        today = dt - timedelta(hours=1, minutes=29)  # 2020-01-10 00:01
        withdraw = create_withdraw_request(self.user, Currencies.rls,
                                           Decimal(370_000_000_0),
                                           '546546546546546546546546',
                                           created_at=today.astimezone(timezone.utc))
        self.update_withdraw_status(withdraw, bank_account)
        self.assertTrue(
            WithdrawRequest.is_over_shaba_limit(
                wallet=withdraw.wallet, amount=Decimal(140_000_000_0), target_account=bank_account
            )
        )

    @patch('exchange.wallet.models.ir_now')
    def test_is_over_amount_limit_per_date_check_with_now(self, dt_mock):
        dt = datetime.strptime('2020-01-10T01:30:00Z', '%Y-%m-%dT%H:%M:%SZ').astimezone(pytz.timezone('Asia/Tehran'))
        bank_account = BankAccount.objects.create(
            user=self.user, shaba_number='546546546546546546546546', confirmed=True, created_at=dt
        )
        # like django.utils.timezone.now()
        dt_mock.return_value = dt.astimezone(pytz.utc)

        yesterday = dt - timedelta(hours=1, minutes=31)  # 2020-01-09 23:59
        withdraw = create_withdraw_request(self.user, Currencies.rls,
                                           Decimal(370_000_000_0),
                                           '546546546546546546546546',
                                           created_at=yesterday.astimezone(timezone.utc))
        self.update_withdraw_status(withdraw, bank_account)
        self.assertTrue(
            WithdrawRequest.is_over_shaba_limit(
                wallet=withdraw.wallet, amount=Decimal(140_000_000_0), target_account=bank_account
            )
        )

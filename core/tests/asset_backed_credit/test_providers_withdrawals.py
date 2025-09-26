from decimal import Decimal
from unittest import mock
from unittest.mock import patch

import responses
from django.test import TestCase

from exchange.accounts.models import BankAccount, User
from exchange.asset_backed_credit.crons import ABCProvidersWithdrawalsCron
from exchange.asset_backed_credit.externals.withdraw import RialWithdrawRequestAPI
from exchange.asset_backed_credit.models import ProviderWithdrawRequestLog, Service
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.asset_backed_credit.services.providers.provider_manager import ProviderManager
from exchange.asset_backed_credit.services.withdraw import (
    _get_explanation,
    create_provider_withdraw_requests,
    settle_provider_withdraw_request_logs,
)
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Transaction as ExchangeTransaction
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WithdrawRequest as ExchangeWithdrawRequest
from tests.asset_backed_credit.helper import ABCMixins


class TestProvidersWithdrawals(TestCase, ABCMixins):
    fixtures = ('test_data', 'system')

    @classmethod
    def setUpTestData(cls):
        cls.provider1 = SignSupportProvider('tara', ['127.0.0.1'], 1, 910, 'public_key')
        wallet = ExchangeWallet.get_user_wallet(cls.provider1.account, Currencies.rls, ExchangeWallet.WALLET_TYPE.spot)
        wallet.create_transaction(tp='manual', amount=2_000_000_000_0).commit()
        cls.provider_bank_account1 = BankAccount.objects.create(
            confirmed=1,
            user=cls.provider1.account,
            account_number='0217225661033',
            shaba_number='0217225661033',
        )

        cls.provider2 = SignSupportProvider('baloan', ['127.0.0.1'], 2, 911, 'public_key')
        wallet = ExchangeWallet.get_user_wallet(cls.provider2.account, Currencies.rls, ExchangeWallet.WALLET_TYPE.spot)
        wallet.create_transaction(tp='manual', amount=999_000_000_0).commit()
        cls.provider_bank_account2 = BankAccount.objects.create(
            confirmed=1,
            user=cls.provider2.account,
            account_number='0217225661034',
            shaba_number='0217225661034',
        )
        cls.provider3 = SignSupportProvider('digipay', ['127.0.0.1'], 3, -1, 'public_key')

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.service1 = self.create_service(contract_id=12345, provider=self.provider1.id)
        self.permission1 = self.create_user_service_permission(user=self.user, service=self.service1)
        self.user_service1 = self.create_user_service(
            user=self.user,
            service=self.service1,
            permission=self.permission1,
        )

        self.service2 = self.create_service(contract_id=67890, provider=self.provider2.id)
        self.permission2 = self.create_user_service_permission(user=self.user, service=self.service2)
        self.user_service2 = self.create_user_service(
            user=self.user,
            service=self.service2,
            permission=self.permission2,
        )
        self.system_rial_account = BankAccount.get_generic_system_account()
        self.user_rial_wallet = ExchangeWallet.get_user_wallet(user=self.user, currency=Currencies.rls)
        self.service3 = self.create_service(contract_id=53891, provider=self.provider3.id)
        self.permission3 = self.create_user_service_permission(user=self.user, service=self.service3)
        self.user_service3 = self.create_user_service(
            user=self.user,
            service=self.service3,
            permission=self.permission3,
        )

    @staticmethod
    def _create_transaction(
        amount: Decimal, wallet: ExchangeWallet, tp: ExchangeTransaction.TYPE, ref: ExchangeTransaction.REF_MODULES
    ):
        return ExchangeTransaction.objects.create(
            tp=tp,
            ref_module=ref,
            amount=amount,
            wallet=wallet,
            created_at=ir_now(),
        )

    def test_providers_withdrawals_no_candidate(self):
        assert not ExchangeWithdrawRequest.objects.all().first()

        ABCProvidersWithdrawalsCron().run()

        assert not ExchangeWithdrawRequest.objects.all().first()

    def test_providers_withdrawals_single_transaction(self):
        with patch.object(ProviderManager, 'providers', (self.provider1, self.provider2)):
            amount = Decimal('100_000_0')
            settlement = self.create_settlement(
                amount=amount,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )

            ABCProvidersWithdrawalsCron().run()

            withdraw = ExchangeWithdrawRequest.objects.all()
            assert withdraw.count() == 1

            withdraw = withdraw.first()
            assert withdraw
            assert withdraw.amount == amount
            assert withdraw.transaction
            assert withdraw.status == ExchangeWithdrawRequest.STATUS.verified
            assert withdraw.target_account == self.provider1.bank_account

            settlement.refresh_from_db()
            assert settlement.provider_withdraw_requests.get(pk=withdraw.pk) == withdraw

    def test_providers_withdrawals_multiple_transaction(self):
        with patch.object(ProviderManager, 'providers', (self.provider1, self.provider2)):
            amount1 = Decimal('100_000_0')
            amount2 = Decimal('50_000_0')
            settlement1 = self.create_settlement(
                amount=amount1,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount1,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount1,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )
            settlement2 = self.create_settlement(
                amount=amount2,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount2,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount2,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )

            ABCProvidersWithdrawalsCron().run()

            withdraw = ExchangeWithdrawRequest.objects.all()
            assert withdraw.count() == 1

            withdraw = withdraw.first()
            assert withdraw.amount == amount1 + amount2
            assert withdraw.target_account == self.provider1.bank_account
            assert withdraw.transaction
            assert withdraw.status == ExchangeWithdrawRequest.STATUS.verified

            settlement1.refresh_from_db()
            settlement2.refresh_from_db()
            assert settlement1.provider_withdraw_requests.get(pk=withdraw.pk) == withdraw
            assert settlement2.provider_withdraw_requests.get(pk=withdraw.pk) == withdraw

    @patch.object(Service, 'PROVIDERS', [(1, 'tara', 'تارا'), (2, 'baloan', 'بالون')])
    def test_providers_withdrawals_multiple_provider_transaction(self):
        with patch.object(ProviderManager, 'providers', (self.provider1, self.provider2)):
            amount1 = Decimal('100_000_0')
            amount2 = Decimal('50_000_0')
            amount3 = Decimal('150_000_0')
            amount4 = Decimal('70_000_0')
            settlement1 = self.create_settlement(
                amount=amount1,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount1,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount1,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )
            settlement2 = self.create_settlement(
                amount=amount2,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount2,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount2,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )
            settlement3 = self.create_settlement(
                amount=amount3,
                user_service=self.user_service2,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount3,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount3,
                    wallet=self.provider2.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )
            settlement4 = self.create_settlement(
                amount=amount4,
                user_service=self.user_service2,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount4,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount4,
                    wallet=self.provider2.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )

            ABCProvidersWithdrawalsCron().run()

            withdraws = ExchangeWithdrawRequest.objects.all()
            assert withdraws.count() == 2

            withdraw_provider_1 = withdraws.filter(target_account=self.provider1.bank_account).first()
            withdraw_provider_2 = withdraws.filter(target_account=self.provider2.bank_account).first()

            assert withdraw_provider_1
            assert withdraw_provider_2

            assert withdraw_provider_1.amount == amount1 + amount2
            assert withdraw_provider_2.amount == amount3 + amount4

            assert withdraw_provider_1.status == ExchangeWithdrawRequest.STATUS.verified
            assert withdraw_provider_2.status == ExchangeWithdrawRequest.STATUS.verified

            assert withdraw_provider_1.transaction
            assert withdraw_provider_2.transaction

            settlement1.refresh_from_db()
            settlement2.refresh_from_db()
            settlement3.refresh_from_db()
            settlement4.refresh_from_db()

            assert settlement1.provider_withdraw_requests.get(pk=withdraw_provider_1.pk) == withdraw_provider_1
            assert settlement2.provider_withdraw_requests.get(pk=withdraw_provider_1.pk) == withdraw_provider_1
            assert settlement3.provider_withdraw_requests.get(pk=withdraw_provider_2.pk) == withdraw_provider_2
            assert settlement4.provider_withdraw_requests.get(pk=withdraw_provider_2.pk) == withdraw_provider_2

    def test_providers_withdrawals_split_requests(self):
        with patch.object(ProviderManager, 'providers', (self.provider1, self.provider2)):
            amount = Decimal('190_000_000_0')
            settlement = self.create_settlement(
                amount=amount,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )

            ABCProvidersWithdrawalsCron().run()

            withdraws = ExchangeWithdrawRequest.objects.all()
            assert withdraws.count() == 4

            for withdraw in withdraws:
                assert withdraw.status == ExchangeWithdrawRequest.STATUS.verified
                assert withdraw.transaction
                assert withdraw.transaction.description == 'تسویه نهایی با سرویس دهنده در سرویس اعتبار‌ریالی'

                settlement.refresh_from_db()
                assert settlement.provider_withdraw_requests.get(pk=withdraw.pk) == withdraw

    def test_providers_withdrawals_over_1b(self):
        with patch.object(ProviderManager, 'providers', (self.provider1, self.provider2)):
            amount = Decimal('1_050_000_000_0')
            settlement = self.create_settlement(
                amount=amount,
                user_service=self.user_service1,
                user_withdraw_transaction=self._create_transaction(
                    amount=amount,
                    wallet=self.user_rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
                ),
                provider_deposit_transaction=self._create_transaction(
                    amount=amount,
                    wallet=self.provider1.rial_wallet,
                    tp=ExchangeTransaction.TYPE.asset_backed_credit,
                    ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
                ),
            )

            ABCProvidersWithdrawalsCron().run()

            withdraws = ExchangeWithdrawRequest.objects.all()
            assert withdraws.count() == 21

            for withdraw in withdraws:
                assert withdraw.status == ExchangeWithdrawRequest.STATUS.verified
                assert withdraw.transaction
                assert withdraw.transaction.description == 'تسویه نهایی با سرویس دهنده در سرویس اعتبار‌ریالی'

                settlement.refresh_from_db()
                assert settlement.provider_withdraw_requests.get(pk=withdraw.pk) == withdraw

    @mock.patch('exchange.asset_backed_credit.services.withdraw._create_withdraw_request_by_internal_api')
    @mock.patch('exchange.asset_backed_credit.services.withdraw._create_and_verify_withdraw_request')
    def test_withdraw_with_internal_api_flag_not_set(self, withdraw, withdraw_by_internal_api):
        amount = Decimal(10_000_000)
        self.create_settlement(
            amount=amount,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        create_provider_withdraw_requests()
        withdraw.assert_called_once()
        withdraw_by_internal_api.assert_not_called()

    def test_withdraw_with_internal_api(self):
        amount1 = Decimal(10_000_000)
        amount2 = Decimal(20_000_000)
        settlement_1 = self.create_settlement(
            amount=amount1,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        settlement_2 = self.create_settlement(
            amount=amount2,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        assert not ProviderWithdrawRequestLog.objects.exists()

        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        create_provider_withdraw_requests()

        withdraw_log = ProviderWithdrawRequestLog.objects.last()
        assert withdraw_log
        assert withdraw_log.amount == amount1 + amount2

        settlement_1.refresh_from_db()
        settlement_2.refresh_from_db()

        assert settlement_1.provider_withdraw_request_log == withdraw_log
        assert settlement_2.provider_withdraw_request_log == withdraw_log

    def test_withdraw_request_with_internal_api_invalid_provider_do_nothing(self):
        amount1 = Decimal(10_000_000)
        amount2 = Decimal(20_000_000)
        self.create_settlement(
            amount=amount1,
            user_service=self.user_service3,
            user_withdraw_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        self.create_settlement(
            amount=amount2,
            user_service=self.user_service3,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        assert not ProviderWithdrawRequestLog.objects.exists()

        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        create_provider_withdraw_requests()

        assert not ProviderWithdrawRequestLog.objects.exists()

    def test_withdraw_request_not_select_duplicate_settlement(self):
        amount1 = Decimal(10_000_000)
        amount2 = Decimal(20_000_000)
        settlement_1 = self.create_settlement(
            amount=amount1,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        settlement_2 = self.create_settlement(
            amount=amount2,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        create_provider_withdraw_requests()

        settlement_3 = self.create_settlement(
            amount=amount2,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        create_provider_withdraw_requests()

        settlement_1.refresh_from_db()
        settlement_2.refresh_from_db()
        settlement_3.refresh_from_db()

        withdraw_logs = ProviderWithdrawRequestLog.objects.order_by('pk').all()
        assert len(withdraw_logs) == 2

        assert settlement_1.provider_withdraw_request_log == withdraw_logs[0]
        assert settlement_2.provider_withdraw_request_log == withdraw_logs[0]
        assert settlement_3.provider_withdraw_request_log == withdraw_logs[1]

    def test_withdraw_request_not_select_duplicate_settlement_flag_off_first(self):
        amount1 = Decimal(10_000_000)
        amount2 = Decimal(20_000_000)
        amount3 = Decimal(30_000_000)

        settlement_1 = self.create_settlement(
            amount=amount1,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        create_provider_withdraw_requests()

        settlement_2 = self.create_settlement(
            amount=amount2,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        settlement_3 = self.create_settlement(
            amount=amount3,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        create_provider_withdraw_requests()

        settlement_1.refresh_from_db()
        settlement_2.refresh_from_db()
        settlement_3.refresh_from_db()

        withdraw_logs = ProviderWithdrawRequestLog.objects.order_by('pk').all()
        assert len(withdraw_logs) == 1
        assert withdraw_logs[0].amount == amount2 + amount3

        assert settlement_1.provider_withdraw_request_log is None
        assert settlement_2.provider_withdraw_request_log == withdraw_logs[0]
        assert settlement_3.provider_withdraw_request_log == withdraw_logs[0]

    @responses.activate
    def test_settle_provider_withdraw_request_logs(self):
        amount1 = Decimal(10_000_000)
        amount2 = Decimal(20_000_000)
        amount3 = Decimal(30_000_000)

        self.create_settlement(
            amount=amount1,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        self.create_settlement(
            amount=amount2,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        self.create_settlement(
            amount=amount3,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        create_provider_withdraw_requests()

        assert ProviderWithdrawRequestLog.objects.count() == 1
        log = ProviderWithdrawRequestLog.objects.last()
        assert log.status == ProviderWithdrawRequestLog.STATUS_CREATED
        assert log.amount == amount1 + amount2 + amount3

        responses.post(
            url=RialWithdrawRequestAPI.url,
            json={'id': 100},
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'userId': str(self.provider1.account.uid),
                        'amount': log.amount,
                        'shabaNumber': self.provider1.bank_account.shaba_number,
                        'explanation': _get_explanation(self.provider1),
                    },
                ),
            ],
        )

        settle_provider_withdraw_request_logs()
        log.refresh_from_db()
        assert log.status == ProviderWithdrawRequestLog.STATUS_DONE
        assert log.external_id == 100

    @responses.activate
    def test_settle_provider_withdraw_request_logs_fail(self):
        amount1 = Decimal(10_000_000)
        amount2 = Decimal(20_000_000)
        amount3 = Decimal(30_000_000)

        self.create_settlement(
            amount=amount1,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount1,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        self.create_settlement(
            amount=amount2,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )
        self.create_settlement(
            amount=amount3,
            user_service=self.user_service1,
            user_withdraw_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.user_rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement'],
            ),
            provider_deposit_transaction=self._create_transaction(
                amount=amount2,
                wallet=self.provider1.rial_wallet,
                tp=ExchangeTransaction.TYPE.asset_backed_credit,
                ref=ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement'],
            ),
        )

        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        create_provider_withdraw_requests()

        assert ProviderWithdrawRequestLog.objects.count() == 1
        log = ProviderWithdrawRequestLog.objects.last()
        assert log.status == ProviderWithdrawRequestLog.STATUS_CREATED

        responses.post(
            url=RialWithdrawRequestAPI.url,
            json={},
            status=400,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'userId': str(self.provider1.account.uid),
                        'amount': log.amount,
                        'shabaNumber': self.provider1.bank_account.shaba_number,
                        'explanation': _get_explanation(self.provider1),
                    },
                ),
            ],
        )

        settle_provider_withdraw_request_logs()
        log.refresh_from_db()
        assert log.status == ProviderWithdrawRequestLog.STATUS_CREATED
        assert log.external_id is None

    @responses.activate
    def test_settle_provider_withdraw_request_logs_invalid_provider_do_nothing(self):
        Settings.set('abc_use_rial_withdraw_request_internal_api', 'yes')
        responses.post(url=RialWithdrawRequestAPI.url, json={'id': 100}, status=200)
        log = ProviderWithdrawRequestLog.objects.create(amount=60000, provider=self.provider3.id)

        settle_provider_withdraw_request_logs()

        log.refresh_from_db()
        assert log.status == ProviderWithdrawRequestLog.STATUS_CREATED
        assert log.external_id is None

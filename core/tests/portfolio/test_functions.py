import datetime
import random
from decimal import Decimal

import jdatetime
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import BankAccount, User
from exchange.base.models import ADDRESS_TYPE, Currencies
from exchange.blockchain.models import Transaction as BlockchainTransaction
from exchange.portfolio.functions import (
    get_earliest_time,
    get_total_deposits,
    get_total_saved_deposits,
    get_total_saved_withdraw,
    get_total_withdraw,
)
from exchange.portfolio.models import UserTotalDailyProfit, UserTotalMonthlyProfit
from exchange.wallet.deposit import save_deposit_from_blockchain_transaction
from exchange.wallet.models import ConfirmedWalletDeposit, Wallet, WalletDepositAddress, WithdrawRequest


class PortfolioFunctionsTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.system_rial_account = BankAccount.get_generic_system_account()

        report_date_threshold = datetime.datetime(2021, 6, 25, 12, 0, tzinfo=datetime.timezone.utc)
        j_report_date = jdatetime.datetime.fromgregorian(date=report_date_threshold)
        j_report_date_first_day = j_report_date.replace(day=1)
        self.report_date_month_1 = j_report_date_first_day.togregorian()

        j_report_date = j_report_date_first_day - jdatetime.timedelta(days=1)
        j_report_date_first_day = j_report_date.replace(day=1)
        self.report_date_month_2 = j_report_date_first_day.togregorian()

        j_report_date = j_report_date_first_day - jdatetime.timedelta(days=1)
        j_report_date_first_day = j_report_date.replace(day=1)
        self.report_date_month_3 = j_report_date_first_day.togregorian()

    def change_initial_balance(self, value):
        rand_num = random.randint(-5, 10)
        profit = (rand_num / 100) * value
        return value + profit

    def create_withdraw_request(self, user, amount, report_date) -> WithdrawRequest:

        wallet = Wallet.get_user_wallet(user, Currencies.rls)
        wallet.balance = 1000000000
        wallet.save()

        wr = WithdrawRequest.objects.create(
            wallet=wallet,
            status=WithdrawRequest.STATUS.new,
            target_account=self.system_rial_account,
            amount=amount,
            fee=0,
        )
        wr.created_at = get_earliest_time(report_date)
        wr.status = WithdrawRequest.STATUS.done
        wr.save()
        tr = wr.transaction
        tr.created_at = get_earliest_time(report_date)
        tr.save()
        return wr

    def create_deposit_request(self, user, amount, report_date) -> ConfirmedWalletDeposit:
        address = '0xC51e20f3D25Dfdf6202D175406A592634870a31f'
        tx_hash = '0x649996a719b1b52d4ba9fda7f243eef227ebce2b87cdc64192bbccfe697705d6'
        wallet = Wallet.get_user_wallet(user, Currencies.btc)
        addr = WalletDepositAddress.objects.create(
            wallet=wallet,
            address=address,
            type=ADDRESS_TYPE.standard,
        )
        tx = BlockchainTransaction(
            address=address,
            hash=tx_hash,
            timestamp=timezone.now(),
            value=amount,
            confirmations=1000,
            is_double_spend=False,
        )
        save_deposit_from_blockchain_transaction(tx, addr)
        deposit = ConfirmedWalletDeposit.objects.get(tx_hash=tx_hash, address=addr)

        deposit.confirmed = True
        deposit.rial_value = amount
        deposit.created_at = get_earliest_time(report_date)
        deposit.save()
        tr = deposit.transaction
        tr.created_at = get_earliest_time(report_date)
        tr.save()
        return deposit

    def create_daily_profits(self, user):
        balance = 10_000_000_0
        init_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        for i in range(90, 0, -1):
            report_date = init_date - datetime.timedelta(days=i)
            balance = self.change_initial_balance(balance)
            user_profit = UserTotalDailyProfit.objects.create(
                report_date=report_date,
                user=user,
                total_balance=balance,
                profit=0,
                profit_percentage=0,
                total_withdraw=0,
                total_deposit=0
            )
            # 2021/07/05
            if i == 90:
                user_profit.total_deposit = 200_000_0
                user_profit.total_withdraw = 250_000_0
                user_profit.save()
                self.create_withdraw_request(user, 250_000_0, report_date)

            # 2021/07/15
            if i == 80:
                user_profit.total_deposit = 250_000_0
                user_profit.total_withdraw = 10_000_0
                user_profit.save()
                self.create_withdraw_request(user, 10_000_0, report_date)

            # 2021/07/25
            if i == 70:
                user_profit.total_deposit = 10_000_0
                user_profit.total_withdraw = 50_000_0
                user_profit.save()
                self.create_withdraw_request(user, 50_000_0, report_date)

            # 2021/08/04
            if i == 60:
                user_profit.total_deposit = 50_000_0
                user_profit.total_withdraw = 500_000_0
                user_profit.save()
                self.create_withdraw_request(user, 500_000_0, report_date)

            # 2021/08/14
            if i == 50:
                user_profit.total_deposit = 500_000_0
                user_profit.total_withdraw = 110_000_0
                user_profit.save()
                self.create_withdraw_request(user, 110_000_0, report_date)

            # 2021/08/19
            if i == 45:
                user_profit.total_deposit = 110_000_0
                user_profit.total_withdraw = 80_000_0
                user_profit.save()
                self.create_withdraw_request(user, 80_000_0, report_date)

            # 2021/08/24
            if i == 40:
                user_profit.total_deposit = 80_000_0
                user_profit.total_withdraw = 70_000_0
                user_profit.save()
                self.create_withdraw_request(user, 70_000_0, report_date)

            # 2021/09/3
            if i == 30:
                user_profit.total_deposit = 70_000_0
                user_profit.total_withdraw = 170_000_0
                user_profit.save()
                self.create_withdraw_request(user, 170_000_0, report_date)

            # 2021/09/13
            if i == 20:
                user_profit.total_deposit = 170_000_0
                user_profit.total_withdraw = 30_000_0
                user_profit.save()
                self.create_withdraw_request(user, 30_000_0, report_date)

            # 2021/09/23
            if i == 10:
                user_profit.total_deposit = 30_000_0
                user_profit.total_withdraw = 200_000_0
                user_profit.save()
                self.create_withdraw_request(user, 200_000_0, report_date)

            # 2021/09/28
            if i == 5:
                user_profit.total_deposit = 200_000_0
                user_profit.total_withdraw = 55_000_0
                user_profit.save()
                self.create_withdraw_request(user, 55_000_0, report_date)

            # 2021/10/1
            if i == 2:
                user_profit.total_deposit = 55_000_0
                user_profit.total_withdraw = 470_000_0
                user_profit.save()
                self.create_withdraw_request(user, 470_000_0, report_date)

            # 2021/10/2
            if i == 1:
                user_profit.total_deposit = 470_000_0
                user_profit.total_withdraw = 200_000_0
                user_profit.save()
                self.create_withdraw_request(user, 200_000_0, report_date)

    def create_monthly_profits(self, user):

        UserTotalMonthlyProfit.objects.create(
            report_date=self.report_date_month_1,
            user=user,
            total_balance=9_500_000_0,
            first_day_total_balance=8_500_000_0,
            total_profit=0,
            total_profit_percentage=0,
            total_withdraw=1_000_000_0,
            total_deposit=0
        )

        UserTotalMonthlyProfit.objects.create(
            report_date=self.report_date_month_2,
            user=user,
            total_balance=8_500_000_0,
            first_day_total_balance=9_000_000_0,
            total_profit=0,
            total_profit_percentage=0,
            total_withdraw=0,
            total_deposit=1_200_000_0
        )

        UserTotalMonthlyProfit.objects.create(
            report_date=self.report_date_month_3,
            user=user,
            total_balance=9_000_000_0,
            first_day_total_balance=10_000_000_0,
            total_profit=0,
            total_profit_percentage=0,
            total_withdraw=2_200_000_0,
            total_deposit=1_500_000_0
        )

    def test_get_total_saved_withdraw(self):
        self.create_daily_profits(self.user)
        self.create_monthly_profits(self.user)

        from_date = datetime.datetime(2021, 8, 29, 12, 0, tzinfo=datetime.timezone.utc)
        to_date = datetime.datetime(2021, 9, 26, 12, 0, tzinfo=datetime.timezone.utc)
        total_withdraw = get_total_saved_withdraw(self.user, to_date, from_date)
        assert total_withdraw == 4000000
        total_withdraw_old = get_total_withdraw(self.user, to_date, from_date)
        assert total_withdraw_old == total_withdraw
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 2700000

        report_date = datetime.datetime(2021, 9, 23, 12, 0, tzinfo=datetime.timezone.utc)
        total_withdraw = get_total_saved_withdraw(self.user, report_date)
        assert total_withdraw == 2000000
        total_withdraw_old = get_total_withdraw(self.user, report_date)
        assert total_withdraw_old == total_withdraw
        total_deposit = get_total_saved_deposits(self.user, report_date)
        assert total_deposit == 300000

        from_date = datetime.datetime(2021, 9, 21, 12, 0, tzinfo=datetime.timezone.utc)
        to_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        total_withdraw = get_total_saved_withdraw(self.user, to_date, from_date)
        assert total_withdraw == 9250000
        total_withdraw_old = get_total_withdraw(self.user, to_date, from_date)
        assert total_withdraw_old == total_withdraw
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 7550000

        from_date = datetime.datetime(2021, 7, 3, 12, 0, tzinfo=datetime.timezone.utc)
        to_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        total_withdraw = get_total_saved_withdraw(self.user, to_date, from_date)
        assert total_withdraw == 21950000
        total_withdraw_old = get_total_withdraw(self.user, to_date, from_date)
        assert total_withdraw_old == total_withdraw
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 21950000

        from_date = self.report_date_month_1 + datetime.timedelta(days=1)
        to_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        total_withdraw = get_total_saved_withdraw(self.user, to_date, from_date)
        assert total_withdraw == 21950000
        total_withdraw_old = get_total_withdraw(self.user, to_date, from_date)
        assert total_withdraw_old == total_withdraw
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 21950000

        # test with monthly profits
        from_date = self.report_date_month_1 - datetime.timedelta(days=1)
        to_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        total_withdraw = get_total_saved_withdraw(self.user, to_date, from_date)
        assert total_withdraw == 29350000
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 17450000

        from_date = self.report_date_month_2 - datetime.timedelta(days=1)
        to_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 29450000

        from_date = self.report_date_month_3 - datetime.timedelta(days=1)
        to_date = datetime.datetime(2021, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)
        total_deposit = get_total_saved_deposits(self.user, to_date, from_date)
        assert total_deposit == 44450000

    def test_get_total_withdraw(self):
        from_date = datetime.datetime(2021, 10, 3, 0, 0, tzinfo=datetime.timezone.utc)
        to_date = datetime.datetime(2021, 10, 3, 23, 59, tzinfo=datetime.timezone.utc)
        amount = Decimal(10)

        # This should be counted as a valid withdraw
        edge_case_wr1 = self.create_withdraw_request(self.user, amount, to_date)
        edge_case_wr1.created_at = datetime.datetime(2021, 10, 2, 23, 0, tzinfo=datetime.timezone.utc)
        edge_case_wr1.transaction.created_at = datetime.datetime(2021, 10, 3, 0, 1, tzinfo=datetime.timezone.utc)
        edge_case_wr1.save()

        self.create_withdraw_request(
            self.user, amount, datetime.datetime(2021, 10, 1, 23, 45, tzinfo=datetime.timezone.utc)
        )
        self.create_withdraw_request(
            self.user, amount, datetime.datetime(2021, 10, 4, 23, 45, tzinfo=datetime.timezone.utc)
        )
        total_withdraw = get_total_withdraw(self.user, to_date, from_date)
        assert total_withdraw == Decimal(10)

    def test_get_total_deposit(self):
        from_date = datetime.datetime(2021, 10, 3, 0, 0, tzinfo=datetime.timezone.utc)
        to_date = datetime.datetime(2021, 10, 3, 23, 59, tzinfo=datetime.timezone.utc)
        amount = Decimal(10)

        # This should be counted as a valid deposit
        edge_case_deposit = self.create_deposit_request(self.user, amount, to_date)
        edge_case_deposit.created_at = datetime.datetime(2021, 10, 2, 23, 0, tzinfo=datetime.timezone.utc)
        edge_case_deposit.transaction.created_at = datetime.datetime(2021, 10, 3, 0, 1, tzinfo=datetime.timezone.utc)
        edge_case_deposit.save()

        self.create_deposit_request(
            self.user, amount, datetime.datetime(2021, 10, 1, 23, 45, tzinfo=datetime.timezone.utc)
        )
        self.create_deposit_request(
            self.user, amount, datetime.datetime(2021, 10, 4, 23, 45, tzinfo=datetime.timezone.utc)
        )
        total_deposit = get_total_deposits(self.user, to_date, from_date)
        assert total_deposit == Decimal(10)

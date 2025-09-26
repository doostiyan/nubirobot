import decimal
from typing import Dict, Union, List

from django.db import models, transaction

from exchange.base.formatting import f_m
from exchange.base.strings import _t
from exchange.base.calendar import ir_now
from exchange.base.models import Choices, Currencies, get_currency_codename
from exchange.accounts.models import User
from exchange.wallet.models import Transaction, Wallet
from exchange.wallet.helpers import create_and_commit_transaction, RefMod

from exchange.credit import helpers
from exchange.credit import errors


class CreditPlan(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    maximum_withdrawal_percentage = models.DecimalField(max_digits=2, decimal_places=2, default=2.0)
    credit_limit_percentage = models.DecimalField(max_digits=2, decimal_places=2)
    credit_limit_in_usdt = models.DecimalField(max_digits=20, decimal_places=0)

    @classmethod
    def get_active_plan(cls, user_id: int,) -> 'CreditPlan':
        return cls.objects.select_for_update().get(
            user_id=user_id, starts_at__lt=ir_now(), expires_at__gt=ir_now(),
        )

    @classmethod
    @transaction.atomic
    def lend(cls, user_id: int, currency: int, amount: decimal.Decimal,) -> 'CreditTransaction':
        if amount <= decimal.Decimal('0'):
            raise errors.InvalidAmount('Cant Lend non positive amount.')
        plan = CreditPlan.get_active_plan(user_id,)
        current_debt = helpers.get_user_debt_worth(user_id,)
        requested_debt = helpers.ToUsdtConvertor(currency).get_price() * amount
        if plan.credit_limit_in_usdt < current_debt + requested_debt:
            raise errors.CreditLimit('Violating lending limit.')

        net_worth = helpers.get_user_net_worth(user_id,) - current_debt
        if net_worth * plan.credit_limit_percentage < current_debt + requested_debt:
            raise errors.NotEnoughCollateral('You dont have enough collateral assets.')

        credit_transaction = CreditTransaction.objects.create(
            plan=plan, currency=currency, tp=CreditTransaction.TYPES.lend, amount=amount,
        )
        try:
            system_wallet_transaction = create_and_commit_transaction(
                user_id=helpers.get_system_user_id(),
                currency=currency,
                amount=-amount,
                ref_module=RefMod.credit_system_lend,
                ref_id=credit_transaction.id,
                description=f'اعطای اعتبار به کاربر #{user_id}',
            )
        except ValueError as e:
            raise errors.CreditLimit('Exceed nobitex lending quota. Call support.') from e

        try:
            user_wallet_transaction = create_and_commit_transaction(
                user_id=user_id,
                currency=currency,
                amount=amount,
                ref_module=RefMod.credit_lend,
                ref_id=credit_transaction.id,
                description=f'اعطای {f_m(amount, currency)} {_t(get_currency_codename(currency))} اعتبار.',
            )
        except ValueError as e:
            raise errors.CantTransferAsset('your wallet has been deactivated.') from e

        CreditTransaction.add_wallet_transactions(
            credit_transaction.id, system_wallet_transaction.id, user_wallet_transaction.id,
        )
        return credit_transaction

    @classmethod
    @transaction.atomic
    def repay(cls, user_id: int, currency: int, amount: decimal.Decimal,) -> 'CreditTransaction':
        if amount <= decimal.Decimal('0'):
            raise errors.InvalidAmount('Cant Repay non positive amount.')
        if amount > cls._get_debt_amount(user_id, currency,):
            raise errors.InvalidAmount('Cant Repay more than your debt.')

        credit_transaction = CreditTransaction.objects.create(
            plan=cls.get_last_plan(user_id), currency=currency, tp=CreditTransaction.TYPES.repay, amount=amount,
        )
        try:
            user_wallet_transaction = create_and_commit_transaction(
                user_id=user_id,
                currency=currency,
                amount=-amount,
                ref_module=RefMod.credit_repay,
                ref_id=credit_transaction.id,
                description=f'تسویه‌ی {f_m(amount, currency)} {_t(get_currency_codename(currency))}.',
            )
        except ValueError as e:
            raise errors.CantTransferAsset('Low Balance or Deactivated Wallet.') from e

        system_wallet_transaction = create_and_commit_transaction(
            user_id=helpers.get_system_user_id(),
            currency=currency,
            amount=amount,
            ref_module=RefMod.credit_system_repay,
            ref_id=credit_transaction.id,
            description=f'تسویه‌ی اعتبار کاربر #{user_id}',
        )

        CreditTransaction.add_wallet_transactions(
            credit_transaction.id, system_wallet_transaction.id, user_wallet_transaction.id,
        )
        return credit_transaction

    @classmethod
    def _get_debt_amount(cls, user_id: int, currency: int,) -> decimal.Decimal:
        transactions_sum = CreditTransaction.objects.filter(plan__user_id=user_id, currency=currency,).aggregate(
            total_lend=models.Sum('amount', filter=models.Q(tp=CreditTransaction.TYPES.lend),),
            total_repay=models.Sum('amount', filter=models.Q(tp=CreditTransaction.TYPES.repay),),
        ) or {}
        return (
            transactions_sum.get('total_lend') or decimal.Decimal('0')
        ) - (
            transactions_sum.get('total_repay') or decimal.Decimal('0')
        )

    @classmethod
    def get_user_debts(cls, user_id: int,) -> Dict[int, decimal.Decimal]:
        '''returning `currency` to user `debt value` map'''
        transactions_sum = CreditTransaction.objects.filter(plan__user_id=user_id).values('currency').annotate(
            total_lend=models.Sum('amount', filter=models.Q(tp=CreditTransaction.TYPES.lend),),
            total_repay=models.Sum('amount', filter=models.Q(tp=CreditTransaction.TYPES.repay),),
        ).values_list('currency', 'total_lend', 'total_repay',)
        return {
            currency: total_lend - (total_repay or decimal.Decimal('0'))
            for currency, total_lend, total_repay in transactions_sum
        }

    @classmethod
    def get_user_debts_and_usdt_values(cls, user_id: int,) -> Dict[int, Dict[str, decimal.Decimal]]:
        '''returning `currency` to user debt `{amount: 11, value: 22}` map'''
        debt_details = {}
        for currency, amount in cls.get_user_debts(user_id).items():
            if not amount:
                continue
            debt_details[currency] = {
                'amount': amount,
                'value': helpers.ToUsdtConvertor(currency).get_price() * amount,
            }
        return debt_details

    @classmethod
    def get_user_transactions(cls, user_id: int,) -> Union[models.QuerySet, List['CreditTransaction']]:
        return CreditTransaction.objects.filter(
            plan_id__in=cls.objects.filter(user_id=user_id).values_list('id', flat=True,),
        ).order_by('-created_at')

    @classmethod
    def get_last_plan(cls, user_id: int,) -> 'CreditPlan':
        plan = cls.objects.filter(user_id=user_id,).order_by('-expires_at').first()
        if plan is None:
            raise cls.DoesNotExist('No plan exists.')
        return plan

    @classmethod
    def get_user_max_possible_lendings(cls, user_id: int,) -> Dict[int, decimal.Decimal]:
        plan = CreditPlan.get_last_plan(user_id)

        user_debt = helpers.get_user_debt_worth(user_id,)
        credit_value_quota = plan.credit_limit_in_usdt - user_debt
        if credit_value_quota <= decimal.Decimal('0'):
            return {}
        user_assets_worth = helpers.get_user_net_worth(user_id,) - user_debt
        perceptual_credit_value_quota = user_assets_worth * plan.credit_limit_percentage - user_debt
        if perceptual_credit_value_quota <= decimal.Decimal('0'):
            return {}

        max_possible_lendings = {}
        for currency, system_balance in Wallet.objects.filter(
            user_id=helpers.get_system_user_id(), balance__gt=decimal.Decimal('0'),  type=Wallet.WALLET_TYPE.spot,
        ).values_list('currency', 'balance',):
            usdt_price = helpers.ToUsdtConvertor(currency).get_price()
            usdt_price *= decimal.Decimal('1.0025')  # The price might (and probably will) change
            # between calling calculator api, and lend api, so we use slightly higher price to prevent
            # failure when user is requesting, the calculated amount.
            max_possible_lendings[currency] = min(system_balance, min(
                perceptual_credit_value_quota, credit_value_quota,
            ) / usdt_price,)

        return max_possible_lendings

    @classmethod
    def get_user_max_possible_withdraws(cls, user_id: int,) -> Dict[int, decimal.Decimal]:
        plan = CreditPlan.get_last_plan(user_id)

        user_controlled_assets = helpers.get_user_net_worth(user_id,)
        user_debt_value = helpers.get_user_debt_worth(user_id,)
        user_assets_value = user_controlled_assets - user_debt_value
        min_possible_net_worth = user_debt_value / plan.maximum_withdrawal_percentage
        withdraw_max_usdt_value = user_assets_value - min_possible_net_worth

        possible_withdraws = {}
        for currency, balance in Wallet.objects.filter(
            user_id=user_id, balance__gt=decimal.Decimal('0'), type=Wallet.WALLET_TYPE.spot,
        ).values_list('currency', 'balance',):
            usdt_price = helpers.ToUsdtConvertor(currency).get_price()
            usdt_price *= decimal.Decimal('1.0025')  # The price might (and probably will) change
            # between calling calculator api, and withdraw api, so we use slightly higher price to
            # prevent failure when user is requesting, the calculated amount.
            possible_withdraws[currency] = min(balance, withdraw_max_usdt_value / usdt_price,)
        return possible_withdraws


class CreditTransaction(models.Model):
    """Nobitex will **lend** money to users, and (same as any other loan)
        **interest** would periodically be added to users' debt. Finally,
        users should **repay** their loans.
    """
    TYPES = Choices(
        (10, 'lend', 'lend',),
        (20, 'repay', 'repay',),
    )
    plan = models.ForeignKey(CreditPlan, on_delete=models.CASCADE)
    currency = models.SmallIntegerField(choices=Currencies)
    created_at = models.DateTimeField(default=ir_now)
    tp = models.SmallIntegerField(choices=TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=10)
    user_wallet_transaction = models.ForeignKey(Transaction, related_name='+', null=True, on_delete=models.SET_NULL)
    system_wallet_transaction = models.ForeignKey(Transaction, related_name='+', null=True, on_delete=models.SET_NULL)

    @classmethod
    def add_wallet_transactions(
        cls, credit_transaction_id: int, system_wallet_transaction_id: int, user_wallet_transaction_id: int,
    ) -> None:
        cls.objects.filter(id=credit_transaction_id).update(
            system_wallet_transaction_id=system_wallet_transaction_id,
            user_wallet_transaction_id=user_wallet_transaction_id,
        )

import datetime
from copy import copy
from decimal import Decimal
from typing import Dict, Optional, Tuple

from django.conf import settings
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import now

from exchange.accounts.models import User, UserPlan, VerificationRequest
from exchange.base.calendar import get_earliest_time, ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import ZERO
from exchange.base.logging import report_exception
from exchange.base.models import CURRENCIES_WITHOUT_MARKET, RIAL, Currencies, Settings
from exchange.features.utils import is_feature_enabled
from exchange.market.models import OrderMatching
from exchange.settings import NOBITEX_OPTIONS
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import WithdrawRequest, WithdrawRequestRestriction


class UserLevelManager:
    """Verification & KYC Utilities"""

    @classmethod
    def is_eligible_to_add_bank_info(cls, user):
        """Return whether the user can add a bank account/card or not."""
        return user.first_name and user.last_name and user.national_code and user.mobile

    @classmethod
    def is_eligible_to_start_verification_process(cls, user):
        """Return whether the user can start a verification process(Liveness or Selfie) or not."""
        return user.first_name and user.last_name and user.national_code and user.mobile and user.is_address_confirmed()

    @classmethod
    def get_user_withdraw_limitations(cls, user: User):
        has_identified_mobile = bool(user.get_verification_profile().mobile_identity_confirmed)
        limits_key = 'withdrawLimitsWithIdentifiedMobile' if has_identified_mobile else 'withdrawLimits'
        options = settings.NOBITEX_OPTIONS[limits_key]
        steps = sorted(options.keys(), reverse=True)
        user_step_limit = options[0]
        for step in steps:
            if user.user_type >= step:
                user_step_limit = options[step]
                break
        return copy(user_step_limit)

    @classmethod
    def get_user_withdraw_summations(cls, user) -> Dict:
        dt_day = ir_now() - datetime.timedelta(days=1)
        dt_month = ir_now() - datetime.timedelta(days=30)
        daily_coin_withdrawal = WithdrawRequest.get_rial_value_summation(user, dt_day)
        monthly_coin_withdrawal = WithdrawRequest.get_rial_value_summation(user, dt_month)
        daily_rial_withdrawal = WithdrawRequest.get_rial_value_summation(user, dt_day, just_rial=True)
        monthly_rial_withdrawal = WithdrawRequest.get_rial_value_summation(user, dt_month, just_rial=True)
        withdraw_limits = UserLevelManager.get_user_withdraw_limitations(user)
        return {
                'withdrawRialDaily': {'used': daily_rial_withdrawal, 'limit': withdraw_limits['dailyRial']},
                'withdrawCoinDaily': {'used': daily_coin_withdrawal, 'limit': withdraw_limits['dailyCoin']},
                'withdrawTotalDaily': {'used': daily_coin_withdrawal+daily_rial_withdrawal, 'limit': withdraw_limits['dailySummation']},
                'withdrawTotalMonthly': {'used': monthly_rial_withdrawal+monthly_coin_withdrawal, 'limit': withdraw_limits['monthlySummation']},
            }

    @classmethod
    def get_daily_rial_deposit(cls, user: User) -> Decimal:
        """
        Calculate the amount of rial deposits for a certain user from start of the day till now.

        Args:
            user: the user that the client wants to know her daily rial depsoit.

        Returns:
            Decimal: the amount of rial deposits for the give user from start of the day till now.
        """
        start_of_day = get_earliest_time(ir_now())
        user_day_shetab_deposits = (
            user.shetab_deposits.filter(
                created_at__gte=start_of_day,
                status_code__in=[ShetabDeposit.STATUS.pay_success, ShetabDeposit.STATUS.invalid_card],
            ).aggregate(sum=Sum('amount'))['sum']
            or 0
        )
        # Calculate recent pending deposits
        recent_deposits = user.shetab_deposits.filter(
            created_at__gte=ir_now() - datetime.timedelta(minutes=15),
            status_code=ShetabDeposit.STATUS.pay_new,
        ).aggregate(sum=Sum('amount'))['sum'] or 0
        return user_day_shetab_deposits + recent_deposits

    @classmethod
    def get_daily_rial_deposit_limit(cls, user: User) -> Optional[int]:
        """
        Calculate the user limitation for daily rial deposits of user.

        Args:
            user: the user that the client wants to know her limit.

        Returns:
            dict: the limit for daily rial deposit. if ``None`` it means no limit is set.
        """
        rial_deposit_limit = None
        deposit_limits = settings.NOBITEX_OPTIONS.get('depositLimits', {})
        deposit_limits_identified_mobile = settings.NOBITEX_OPTIONS.get('depositLimitsWithIdentifiedMobile', {})
        if user.user_type in deposit_limits.keys():
            if user.get_verification_profile().mobile_identity_confirmed:
                rial_deposit_limit = deposit_limits_identified_mobile.get(user.user_type)
            else:
                rial_deposit_limit = deposit_limits.get(user.user_type)
        return rial_deposit_limit

    @classmethod
    def get_user_deposit_summations(cls, user: User) -> Dict:
        """
        Calculate the user limitations for deposits and the used amount from each limitation.

        Each limitation is captured in a dictionary paired with its used amount.

        Args:
            user: the user that the client wants to know her limits.

        Returns:
            dict: a dictionary with limit name as its key and limit-used pair as its value.
        """

        daily_rial = cls.get_daily_rial_deposit(user)
        rial_deposit_limit = (
            cls.get_daily_rial_deposit_limit(user) or settings.NOBITEX_OPTIONS['rialDepositGatewayLimit']
        )
        return {
            'depositRialDaily': {'used': daily_rial, 'limit': rial_deposit_limit},
        }

    @classmethod
    def is_eligible_to_rial_deposit(cls, user, amount, is_shetab=True):
        """ Check if the user is allowed to deposit Rial, based on
            the user level deposit limits
        """
        # No Rial deposit is allowed for low-level users
        if user.user_type < User.USER_TYPES.level1:
            return False, 'User Low Level'

        # Bank Deposit
        if not is_shetab:
            if user.user_type < User.USER_TYPES.verified:
                return False, 'User Not Verified'
            return amount <= 1_000_000_000_0, None

        # Shetab Deposit
        level_max_daily_amount = cls.get_daily_rial_deposit_limit(user)
        if settings.IS_TESTNET and not Settings.is_feature_active("kyc2"):
            level_max_daily_amount = 500_000_0

        if level_max_daily_amount is not None:
            if amount > level_max_daily_amount:
                return False, 'Amount Level Limitation'
            # Check limit
            if cls.get_daily_rial_deposit(user) + amount > level_max_daily_amount:
                return False, 'Amount Daily Limitation'
        return amount <= 50_000_000_0, None

    @classmethod
    def is_eligible_to_bank_id_deposit(cls, user: User):
        """ Check if user is allowed to do bank deposit with Jibit payment ID
        """
        return not user.tags.filter(name='استعلام').exists()

    @classmethod
    def is_eligible_to_rial_deposit_from_foreign_ip(cls, user):
        if settings.DEBUG:
            return True
        return user.user_type >= User.USER_TYPES.level2

    @classmethod
    def is_eligible_to_withdraw(cls, user, currency, amount, network=None):
        """ Check if user can withdraw the given amount of currency
        """
        # Disallow all withdraws for unknown users
        if user.user_type < User.USER_TYPES.level1:
            return False

        # Trader users cannot withdraw coin
        is_trader_user = user.user_type == User.USER_TYPES.trader
        if is_trader_user and currency != RIAL and currency not in CURRENCIES_WITHOUT_MARKET:
            return False

        if not network:
            network = CURRENCY_INFO[currency]['default_network']

        # Daily withdraw values
        dt_day = ir_now() - datetime.timedelta(days=1)
        dt_month = ir_now() - datetime.timedelta(days=30)
        (
            daily_coin_withdrawals_value,
            daily_rial_withdrawals_value,
        ) = WithdrawRequest.get_rial_value_summation_for_rial_and_coin(user, dt_day)

        # Check withdraw amount with user type limits
        # TODO: Fix zero amount for coins with no market
        coin_amount = amount
        amount = PriceEstimator.get_rial_value_by_best_price(amount, currency, 'buy')
        withdraw_limits = cls.get_user_withdraw_limitations(user)

        # TODO: It seems that the structure of the WithdrawRequestLimit is wrong and needs to be reviewed in the future
        #  and the correct structure implemented. For example, in the WithdrawRequestLimit model we save the currency and
        #  network, but these two values are only used for dailyCurrency and monthlyCurrency.This means that the
        #  currency and network are useless for dailyRial, dailyCoin, dailySummation, monthlySummation
        # Apply additional user-specific limitations
        user_withdraw_limits = user.user_withdraw_limits.filter(
            Q(currency__isnull=True) | Q(currency=currency),
        ).filter(Q(network__isnull=True) | Q(network=network))
        # Checking global restriction
        restriction = WithdrawRequestRestriction.objects.filter(
            currency=currency,
            network__iexact=network
        ).last()
        global_restriction = None
        if restriction:
            try:
                unlimited_withdraw_users = Settings.get_list('unlimited_withdraw_users')
                if user.email not in unlimited_withdraw_users:
                    global_restriction = restriction
            except:
                report_exception()

        user_limitations = {}
        for user_withdraw_limit in user_withdraw_limits:
            limit_type = user_withdraw_limit.get_tp_display()
            if not limit_type in user_limitations or user_withdraw_limit.network:
                user_limitations[limit_type] = user_withdraw_limit
        if global_restriction:
            limit_type = global_restriction.get_tp_display()
            if (
                limit_type not in user_limitations or
                (
                    limit_type in user_limitations and
                    user_limitations[limit_type].limitation > global_restriction.limitation
                )
            ):
                user_limitations[limit_type] = global_restriction
        for limit_type, user_limitation in user_limitations.items():
            # It is assumed dailyCurrency and monthlyCurrency are only in WithdrawRequestLimit
            if limit_type in ['dailyCurrency', 'monthlyCurrency']:  # Because these require a network to check.
                withdraw_limits[limit_type] = user_limitation
            else:
                withdraw_limits[limit_type] = user_limitation.limitation
        # Check limitations
        if currency == RIAL:
            if daily_rial_withdrawals_value + amount > withdraw_limits['dailyRial']:
                return False
        elif currency in CURRENCIES_WITHOUT_MARKET and is_trader_user:
            if daily_rial_withdrawals_value + daily_coin_withdrawals_value + amount > withdraw_limits['dailyRial']:
                return False
        else:
            if daily_coin_withdrawals_value + amount > withdraw_limits['dailyCoin']:
                return False
        if daily_coin_withdrawals_value + daily_rial_withdrawals_value + amount > withdraw_limits['dailySummation']:
            return False
        if withdraw_limits['monthlySummation']:
            (
                monthly_coin_withdrawals_value,
                monthly_rial_withdrawals_value,
            ) = WithdrawRequest.get_rial_value_summation_for_rial_and_coin(user, dt_month)
            monthly_total_value = monthly_coin_withdrawals_value + monthly_rial_withdrawals_value
            if monthly_total_value + amount > withdraw_limits['monthlySummation']:
                return False

        # Check per-coin limitations
        if user_withdraw_limit := withdraw_limits.get('dailyCurrency'):
            currency_daily_value = WithdrawRequest.get_total_amount(
                user, currency, dt_from=dt_day, network=user_withdraw_limit.network
            )
            if currency_daily_value + coin_amount > user_withdraw_limit.limitation:
                return False
        if user_withdraw_limit := withdraw_limits.get('monthlyCurrency'):
            currency_monthly_value = WithdrawRequest.get_total_amount(
                user, currency, dt_from=dt_month, network=user_withdraw_limit.network
            )
            if currency_monthly_value + coin_amount > user_withdraw_limit.limitation:
                return False

        # Allow withdraw if all limits are checked
        return True

    @classmethod
    def is_eligible_to_trade(cls, user: User):
        return user.user_type >= User.USER_TYPES.level1

    @classmethod
    def is_eligible_to_deposit_coin(cls, user: User):
        if user.user_type < User.USER_TYPES.level1:
            return False
        if settings.IS_TESTNET:
            if user.user_type < User.USER_TYPES.nobitex:
                return False
        return True

    @classmethod
    def is_eligible_to_change_mobile(cls, user):
        """Check if the user can change mobile number."""
        return user.user_type <= User.USER_TYPES.verified

    @classmethod
    def is_user_type_eligible_to_delegate_to_liquidity_pool(cls, user_type: int):
        return user_type >= User.USER_TYPES.level1

    @classmethod
    def is_eligible_to_delegate_to_liquidity_pool(cls, user: User):
        return cls.is_user_type_eligible_to_delegate_to_liquidity_pool(
            user.user_type,
        )

    @classmethod
    def is_user_eligible_for_vandar_deposit(cls, user: User) -> bool:
        return is_feature_enabled(user=user, feature='vandar_deposit')

    @classmethod
    def is_eligible_to_vandar_withdraw(cls, user: User):
        return is_feature_enabled(user, 'vandar_withdraw')

    @classmethod
    def is_eligible_to_get_rejection_reason(cls, user: User):
        if user.user_type not in [User.USER_TYPES.level0, User.USER_TYPES.level1, User.USER_TYPES.level2]:
            return False
        return True

    @classmethod
    def is_eligible_to_stake(cls, user: User):
        return user.user_type >= User.USER_TYPES.level1

    @classmethod
    def is_eligible_to_have_tfa(cls, user: User):
        verification = user.get_verification_profile()
        return bool(user.mobile and verification.mobile_confirmed)

    @classmethod
    def is_eligible_for_social_trading_leadership(cls, user: User) -> bool:
        if not user.is_email_verified:
            return False
        return user.user_type >= User.USER_TYPES.level2 and user.is_customer_user

    @classmethod
    def is_eligible_for_email_required_services(cls, user: User):
        return user.is_email_verified

    @classmethod
    def is_eligible_for_nobitex_id_deposit(cls, user: User) -> bool:
        return user.user_type >= User.USER_TYPE_LEVEL1

    @classmethod
    def is_eligible_to_upgrade_level3(cls, user: User) -> Tuple[bool, str]:
        if not Settings.is_feature_active('kyc2'):
            return False, 'KYC2Disabled'

        vp = user.get_verification_profile()
        if user.user_type < User.USER_TYPES.level2 or not vp.is_verified_level2:
            return False, 'NotVerifiedLevel2'

        if not vp.mobile_identity_confirmed:
            return False, 'NotMobileIdentityConfirmed'

        has_specified_days_passed = VerificationRequest.objects.filter(
            tp__in=[VerificationRequest.TYPES.auto_kyc, VerificationRequest.TYPES.selfie],
            status=VerificationRequest.STATUS.confirmed,
            user=user,
            created_at__lte=ir_now() - datetime.timedelta(days=60),
        ).exists()
        if not has_specified_days_passed:
            return False, 'DaysLimitationViolated'

        trades_last_month = OrderMatching.get_trades(
            user=user, date_from=ir_now() - datetime.timedelta(days=30), date_to=ir_now()
        ).aggregate(total=Coalesce(Sum('rial_value'), ZERO))

        if trades_last_month['total'] < Decimal('1_000_000_000_0'):
            return False, 'InsufficientTrades'

        return True, ''

    @classmethod
    def is_user_verified_as_level_1(cls, user: User) -> bool:
        return user.get_verification_profile().is_verified_level1

    @classmethod
    def is_user_mobile_identity_confirmed(cls, user: User) -> bool:
        return user.get_verification_profile().mobile_identity_confirmed


class UserPlanManager:

    @classmethod
    def is_eligible_to_activate(cls, user, plan_tp):
        if plan_tp == UserPlan.TYPE.trader:
            month_trader_plans = UserPlan.objects.filter(
                date_from__gte=now() - datetime.timedelta(days=30),
                user=user,
                type=plan_tp,
            )
            if month_trader_plans.count() >= settings.TRADER_PLAN_MONTHLY_LIMIT:
                return False
            return user.user_type in UserPlan.ALLOWED_TRADER_INITIAL_LEVELS
        return True

    @classmethod
    def is_eligible_to_deactivate(cls, user_plan):
        from exchange.pool.models import UserDelegation
        from exchange.staking.exportables import (
            get_balances_blocked_in_staking,
            get_balances_blocked_in_yield_aggregator,
        )

        user = user_plan.user
        if user_plan.type == UserPlan.TYPE.trader:
            # Check if user has coin balance
            wallets = user.wallets.exclude(currency=RIAL)
            for w in wallets:
                min_balance = NOBITEX_OPTIONS['minWithdraws'].get(w.currency, 0)
                if w.currency == Currencies.pmn:
                    min_balance = 200
                if w.balance > min_balance:
                    return False

            # Check if user has active delegations in liquidity-pools
            if UserDelegation.objects.filter(user=user, closed_at=None).exists():
                return False

            # Check if user has asset in staking
            if any(get_balances_blocked_in_staking(user.id).values()):
                return False

            # Check if user has asset in yield farming
            if any(get_balances_blocked_in_yield_aggregator(user.id).values()):
                return False

            # Level1 users can only exit to Level2
            initial_user_type = user_plan.get_kv('initial_user_type')
            has_level2_verification = user.get_verification_profile().is_verified_level2
            if initial_user_type < User.USER_TYPES.trader and not has_level2_verification:
                return False
        return True

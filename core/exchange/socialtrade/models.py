from datetime import timedelta
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.db import connection, models, transaction
from django.db.models import JSONField, Q, Sum
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.calendar import ir_now, to_shamsi_date
from exchange.base.constants import ZERO
from exchange.base.decorators import measure_time
from exchange.base.helpers import get_symbol_from_currency_code
from exchange.base.locker import Locker
from exchange.base.logging import report_event
from exchange.base.models import ALL_CURRENCIES, AMOUNT_PRECISIONS, RIAL, Currencies, Settings
from exchange.base.money import quantize_number
from exchange.base.storages import get_public_s3_storage
from exchange.base.templatetags.nobitex import currencyformat
from exchange.portfolio.models import UserTotalDailyProfit
from exchange.portfolio.services import Portfolio
from exchange.socialtrade.constants import LEADER_WINRATE_CACHE_KEY
from exchange.socialtrade.enums import WinratePeriods
from exchange.socialtrade.exceptions import (
    AcceptNotNewLeaderRequest,
    AlreadySubscribedException,
    InsufficientBalance,
    LeaderAlreadyExist,
    LeaderNotFound,
    PendingLeadershipRequestExist,
    ReachedSubscriptionLimit,
    RejectNotNewLeaderRequest,
    SelfSubscriptionImpossible,
    SubscriptionNotRenewable,
)
from exchange.socialtrade.managers import LeaderManager
from exchange.socialtrade.notifs import SocialTradeNotifs
from exchange.subscription.exceptions import SubscriptionExpired
from exchange.subscription.models import Subscription
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import Transaction, Wallet


class SocialTradeAvatar(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='social_trade_avatars', storage=get_public_s3_storage())
    is_active = models.BooleanField(default=True)


class LeadershipRequest(models.Model):
    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'accepted', 'Accepted'),
        (3, 'rejected', 'Rejected'),
    )
    REASONS = Choices(
        (1, 'low_experience', 'نداشتن عملکرد مناسب ترید برای لیدر شدن'),
        (2, 'low_trade_volume', 'نداشتن حجم معاملاتی مناسب برای لیدر شدن'),
        (3, 'no_new_registration', 'عدم ثبت نام لیدر جدید در بازه زمانی فعلی'),
        (4, 'invalid_nickname', 'مشخصات ثبت شده برای پروفایل در قسمت یوزر نیم مورد تایید نمی باشد'),
        (5, 'invalid_avatar', 'مشخصات ثبت شده برای پروفایل در قسمت عکس مورد تایید نمی‌باشد'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=24)
    avatar = models.ForeignKey(SocialTradeAvatar, related_name='+', on_delete=models.PROTECT, null=True)
    subscription_fee = models.DecimalField(max_digits=30, decimal_places=10)
    subscription_currency = models.IntegerField(choices=Currencies)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)
    reason = models.SmallIntegerField(choices=REASONS, null=True)
    leader = models.ForeignKey(to='Leader', null=True, on_delete=models.CASCADE, related_name='requests')

    class Meta:
        verbose_name = 'درخواست لیدر شدن'
        verbose_name_plural = 'درخواست های لیدر شدن'
        constraints = (
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user_on_new_request',
                condition=models.Q(status=1),
            ),
        )

    def accept(self, system_fee_percentage):
        if self.status != self.STATUS.new:
            raise AcceptNotNewLeaderRequest(f'{self.status} request cannot be accepted.')

        leader, _ = Leader.objects.update_or_create(
            user=self.user,
            defaults=dict(
                deleted_at=None,
                delete_reason=None,
                nickname=self.nickname,
                avatar=self.avatar,
                subscription_fee=self.subscription_fee,
                subscription_currency=self.subscription_currency,
                system_fee_percentage=system_fee_percentage,
            ),
        )

        self.status = self.STATUS.accepted
        self.leader = leader
        self.save(update_fields=('status', 'leader'))
        self._notify_request_assessment_result()

    def reject(self, reason: int):
        if self.status != self.STATUS.new:
            raise RejectNotNewLeaderRequest(f'{self.status} request cannot be rejected.')

        self.status = self.STATUS.rejected
        self.reason = reason
        self.save(update_fields=('status', 'reason'))
        self._notify_request_assessment_result()

    def _notify_request_assessment_result(self):
        if self.status == LeadershipRequest.STATUS.new:
            return
        if self.status == LeadershipRequest.STATUS.accepted:
            subscription_acceptance_date = to_shamsi_date(self.leader.activates_at.date())
            SocialTradeNotifs.leadership_acceptance.send(
                self.user,
                data=dict(
                    sms_text=subscription_acceptance_date,
                    subscription_acceptance_date=subscription_acceptance_date,
                ),
            )
        else:
            SocialTradeNotifs.leadership_rejection.send(
                self.user,
                data=dict(
                    sms_text=self.get_reason_display(),
                    rejection_reason=self.get_reason_display(),
                ),
            )

    @classmethod
    def can_request_to_become_leader(cls, user):
        leader = Leader.objects.filter(user=user).order_by('-created_at').first()
        if leader:
            if not leader.deleted_at:
                # active leaders cannot make a request
                raise LeaderAlreadyExist()
            if LeadershipRequest.objects.filter(user=user, created_at__gte=leader.deleted_at).exclude(
                status=LeadershipRequest.STATUS.rejected,
            ):
                # deleted leaders who have a new or accepted request after deletion, cannot make a request
                raise PendingLeadershipRequestExist()
        elif LeadershipRequest.objects.filter(user=user).exclude(status=cls.STATUS.rejected):
            # non-leaders who have a new or accepted request cannot make a request
            raise PendingLeadershipRequestExist()
        return True


    @classmethod
    def is_nickname_unique(cls, user: User, nickname: str) -> bool:
        not_rejected_status = [LeadershipRequest.STATUS.new, LeadershipRequest.STATUS.accepted]
        return (
            not LeadershipRequest.objects.filter(
                nickname__iexact=nickname.lower(),
                status__in=not_rejected_status,
            )
            .exclude(user=user)
            .exists()
        )


class LeadershipBlacklist(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.CharField(max_length=256)
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        verbose_name = 'لیست سیاه لیدر شدن'
        verbose_name_plural = verbose_name
        constraints = (
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user_on_blacklist',
                condition=models.Q(deleted_at__isnull=True),
            ),
        )

    def delete(self, *args, **kwargs):
        self.deleted_at = ir_now()
        self.save(update_fields=['deleted_at'])

    @classmethod
    def is_user_blacklisted(cls, user):
        return LeadershipBlacklist.objects.filter(user=user, deleted_at__isnull=True).exists()


class Leader(models.Model):
    DELETE_REASONS = Choices(
        (1, 'leader_request', 'حذف به دلیل درخواست شما از طریق تیکت'),
        (2, 'low_trade', 'حذف به دلیل عدم فعالیت و ترید'),
        (3, 'ineligibility', 'حذف به دلیل عدم انطباق با شرایط تریدر سوشال ترید'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activates_at = models.DateTimeField(null=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nickname = models.CharField(unique=True, max_length=24)
    avatar = models.ForeignKey(SocialTradeAvatar, related_name='+', on_delete=models.PROTECT, null=True)
    subscription_fee = models.DecimalField(max_digits=30, decimal_places=10)
    subscription_currency = models.IntegerField(choices=Currencies)
    deleted_at = models.DateTimeField(null=True, blank=True)
    delete_reason = models.SmallIntegerField(choices=DELETE_REASONS, null=True, blank=True)
    gained_subscription_fees = models.DecimalField(max_digits=36, decimal_places=10, default=Decimal('0.0'))
    system_fee_percentage = models.DecimalField(max_digits=4, decimal_places=2)
    last_month_profit_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.0'))
    daily_profits = JSONField(default=list)

    objects = LeaderManager()

    class Meta:
        verbose_name = 'لیدر'
        verbose_name_plural = 'لیدرها'
        constraints = (
            models.UniqueConstraint(
                fields=['user'],
                name='unique_user',
                condition=models.Q(deleted_at__isnull=False),
            ),
        )

    def __str__(self):
        return f'leader-{self.id}-{self.nickname}'

    @property
    def is_active(self):
        return not self.deleted_at and self.activates_at <= ir_now()

    @property
    def system_fee_rate(self) -> Decimal:
        return quantize_number(self.system_fee_percentage / 100, precision=Decimal('0.0001'), rounding=ROUND_DOWN)

    @classmethod
    def get_actives(cls):
        return cls.objects.filter(deleted_at__isnull=True, activates_at__lte=ir_now())

    @classmethod
    def get_actives_for_user(cls, user: User):
        return (
            cls.objects.filter(
                activates_at__lte=ir_now(),
            )
            .annotate_is_subscribed(user)
            .filter(Q(deleted_at__isnull=True) | Q(is_subscribed=True))
        )

    @classmethod
    def get_subscribed_to(cls, user):
        return cls.objects.all().annotate_is_subscribed(user).filter(Q(is_subscribed=True))

    def delete_leader(self, reason: int):
        with transaction.atomic():
            self.deleted_at = ir_now()
            self.delete_reason = reason
            self.save(update_fields=('deleted_at', 'delete_reason'))

            self._notify_leader_deletion()
            SocialTradeSubscription.end_subscriptions_of_a_leader(self)

    def get_winrate(self, period: WinratePeriods) -> Decimal:
        winrate_cache_key = LEADER_WINRATE_CACHE_KEY % (self.pk, period.value)
        winrate = cache.get(winrate_cache_key)
        if not winrate:
            from exchange.socialtrade.functions import update_winrates

            winrates = update_winrates(self).get(self.pk)
            if winrates is None:
                report_event(f'winrate is null for leader: {self.pk}')
                return ZERO

            winrate = winrates.get(period.value)
            if winrate is None:
                report_event(f'winrate is null for leader: {self.pk}, period: {period.value}, winrates: {winrates}')
                return ZERO

        return winrate

    @measure_time(metric='socialtrade_update_leader_profits_milliseconds', verbose=False)
    def update_profits(self):
        from exchange.base.serializers import serialize
        from exchange.socialtrade.serializers import serialize_decimal_with_precision

        # set last_month_profit_percentage and daily_profits
        leader_daily_profits = []

        daily_profits = list(
            reversed(UserTotalDailyProfit.objects.filter(user_id=self.user_id).order_by('-report_date')[:30])
        )
        if len(daily_profits) == 0:
            return

        first_report_date = daily_profits[0].report_date
        previous_daily_profits = UserTotalDailyProfit.objects.filter(
            user_id=self.user_id, report_date__lt=first_report_date
        )
        if previous_daily_profits:
            initial_balance = previous_daily_profits.order_by('report_date').first().total_balance
            previous_withdraws = previous_daily_profits.aggregate(total_withdraws=Sum('total_withdraw'))[
                'total_withdraws'
            ]
            previous_deposits = previous_daily_profits.aggregate(total_deposits=Sum('total_deposit'))['total_deposits']
        else:
            initial_balance = daily_profits[0].total_balance
            previous_withdraws = previous_deposits = 0

        report_day_deposits = report_day_withdraws = 0
        for daily_profit in daily_profits:
            report_day_deposits += daily_profit.total_deposit
            report_day_withdraws += daily_profit.total_withdraw

            portfolio = Portfolio(
                user_id=self.user_id,
                initial_balance=initial_balance,
                final_balance=daily_profit.total_balance,
                total_deposit=report_day_deposits + previous_deposits,
                total_withdraw=report_day_withdraws + previous_withdraws,
            )

            leader_daily_profits.append(
                dict(
                    report_date=serialize(daily_profit.report_date),
                    profit_percentage=serialize_decimal_with_precision(daily_profit.profit_percentage, Decimal('1E-2')),
                    cumulative_profit_percentage=serialize_decimal_with_precision(
                        portfolio.profit_percent, Decimal('1E-2')
                    ),
                ),
            )

        self.daily_profits = leader_daily_profits

        last_month_portfo = Portfolio(
            user_id=self.user_id,
            initial_balance=daily_profits[0].total_balance or 0,
            final_balance=daily_profits[-1].total_balance or 0,
            total_deposit=Decimal(report_day_deposits),
            total_withdraw=Decimal(report_day_withdraws),
        )
        self.last_month_profit_percentage = serialize_decimal_with_precision(
            Decimal(last_month_portfo.profit_percent), Decimal('1E-2')
        )
        self.save(update_fields=('daily_profits', 'last_month_profit_percentage'))

    def _notify_leader_deletion(self):
        self._notify_leader_deletion_to_leader()
        self._notify_leader_deletion_to_subscribers()
        self._notify_leader_deletion_to_trials()

    def _notify_leader_deletion_to_leader(self):
        reason = self.get_delete_reason_display()
        data = dict(sms_text=reason, reason=reason)
        SocialTradeNotifs.leader_deletion_leader.send(self.user, data=data)

    def _notify_leader_deletion_to_subscribers(self):

        user_ids = list(
            SocialTradeSubscription.get_actives()
            .filter(leader=self, is_trial=False)
            .values_list('subscriber_id', flat=True),
        )
        nickname = self.nickname
        data = dict(sms_text=nickname, nickname=nickname)
        SocialTradeNotifs.leader_deletion_subscribers.send_many(user_ids, data=data)

    def _notify_leader_deletion_to_trials(self):
        user_ids = list(
            SocialTradeSubscription.get_actives()
            .filter(leader=self, is_trial=True)
            .values_list('subscriber_id', flat=True),
        )
        nickname = self.nickname
        data = dict(sms_text=nickname, nickname=nickname)
        SocialTradeNotifs.leader_deletion_trials.send_many(user_ids, data=data)

    @property
    def asset_ratios(self):
        wallets = Wallet.objects.filter(
            user=self.user, currency__in=ALL_CURRENCIES, type=Wallet.WALLET_TYPE.spot
        ).values('currency', 'balance')
        total_assets_value = Decimal(0)
        assets_values = dict()
        for wallet in wallets:
            asset_value = PriceEstimator.get_rial_value_by_best_price(
                wallet['balance'], wallet['currency'], order_type='buy'
            )
            total_assets_value += Decimal(asset_value)
            assets_values[wallet['currency']] = Decimal(asset_value)
        return {
            currency: quantize_number(assets_values[currency] / total_assets_value, precision=Decimal('1e-6'))
            if total_assets_value
            else Decimal('0.0')
            for currency in assets_values
        }


class SocialTradeSubscription(Subscription):
    leader = models.ForeignKey(Leader, on_delete=models.CASCADE)
    leader_transaction = models.ForeignKey(Transaction, related_name='+', null=True, on_delete=models.DO_NOTHING)
    system_transaction = models.ForeignKey(Transaction, related_name='+', null=True, on_delete=models.DO_NOTHING)
    is_notif_enabled = models.BooleanField(verbose_name='ارسال نوتیف؟', default=True)

    class Meta:
        verbose_name = 'اشتراک سوشال ترید'
        verbose_name_plural = 'اشتراک های سوشال ترید'
        unique_together = (('subscriber', 'leader', 'starts_at'),)
        constraints = (
            models.UniqueConstraint(
                fields=['subscriber', 'leader'],
                name='unique_subscriber_leader_trial',
                condition=models.Q(is_trial=True),
            ),
        )

    @property
    def leader_amount(self):
        if self.leader_transaction:
            return self.leader_transaction.amount
        return self.fee_amount - self.system_amount

    @property
    def system_amount(self):
        if self.system_transaction:
            return self.system_transaction.amount

        symbol = get_symbol_from_currency_code(self.fee_currency).upper()
        precision = AMOUNT_PRECISIONS[f'{symbol}IRT'] if self.fee_currency != RIAL else 1
        return (self.fee_amount * self.system_fee_rate).quantize(precision, ROUND_HALF_EVEN)

    @property
    def system_fee_user(self):
        if self.system_transaction:
            return self.system_transaction.user_id
        return settings.SOCIAL_TRADE['fee_user']

    @property
    def system_fee_rate(self):
        if self.system_transaction:
            return self.system_transaction.amount / self.fee_amount
        return self.leader.system_fee_rate

    @property
    def translated_renewal_currency(self):
        return currencyformat(self.leader.subscription_currency, translate=True)

    @property
    def normalized_renewal_fee(self):
        return f'{self.leader.subscription_fee.normalize():f}'

    @property
    def translated_currency(self):
        return currencyformat(self.fee_currency, translate=True)

    @property
    def normalized_fee(self):
        return f'{self.fee_amount.normalize():f}'

    @property
    def is_renewable(self):
        return not self.is_renewed and self.leader.is_active and not self.canceled_at

    @classmethod
    def is_trial_available(cls, user: User, leader: Leader) -> bool:
        """Check if user can use trial for this leader:
            1. Every user can use trial once per leader
            2. Max active trial count should be lower than social_trade_max_trial_count setting

        Args:
            user (User): user
            leader (Leader): leader

        Returns:
            bool: is user able to use trial for this leader
        """
        trial_count = cls.get_actives().filter(subscriber=user, is_trial=True).count()
        if trial_count >= int(Settings.get('social_trade_max_trial_count', 5)):
            return False

        is_trial_used = cls.objects.filter(subscriber=user, leader=leader, is_trial=True).exists()
        if is_trial_used:
            return False

        return True

    @classmethod
    def has_reached_subscribe_limit(cls, user: User) -> bool:
        """
        Check if user reached subscription limit.
        Active subscription count should be lower than social_trade_max_subscription_count setting

        Args:
            user (User): user

        Returns:
            bool: is user reached the limit
        """
        subscription_count = cls.get_actives().filter(subscriber=user).count()
        if subscription_count >= int(Settings.get('social_trade_max_subscription_count', 5)):
            return True
        return False

    def create_transactions(self) -> None:
        assert connection.in_atomic_block

        if self.fee_amount < 0:
            raise ValueError('Invalid Fee amount')

        if self.is_expired:
            raise SubscriptionExpired('Cannot create tx for expired subscription')

        if self.withdraw_transaction or self.is_trial or self.fee_amount == 0:
            return

        subscriber_wallet = Wallet.get_user_wallet(self.subscriber, self.fee_currency)
        if not subscriber_wallet or subscriber_wallet.active_balance < self.fee_amount:
            raise InsufficientBalance()

        withdraw_transaction = subscriber_wallet.create_transaction(
            tp='social_trade',
            amount=-self.fee_amount,
            description=f'کسر هزینه اشتراک لیدر {self.leader.nickname}',
        )

        if withdraw_transaction is None:
            raise InsufficientBalance()

        withdraw_transaction.commit(ref=Transaction.Ref('SocialTradeUserTransaction', self.pk))
        self.withdraw_transaction = withdraw_transaction

        leader_transaction = Wallet.get_user_wallet(self.leader.user, self.fee_currency).create_transaction(
            tp='social_trade',
            amount=self.leader_amount,
            description='واریز درامد اشتراک',
        )
        leader_transaction.commit(ref=Transaction.Ref('SocialTradeLeaderTransaction', self.pk))
        self.leader_transaction = leader_transaction
        self.leader.gained_subscription_fees += self.leader_transaction.amount
        self.leader.save(update_fields=['gained_subscription_fees'])

        if self.system_amount:
            system_transaction = Wallet.get_user_wallet(self.system_fee_user, self.fee_currency).create_transaction(
                tp='social_trade',
                amount=self.system_amount,
                description='واریز کارمزد اشتراک',
            )
            system_transaction.commit(ref=Transaction.Ref('SocialTradeSystemTransaction', self.pk))
            self.system_transaction = system_transaction

    def save(self, *args, update_fields=None, **kwargs) -> None:
        _update_fields = []
        if not self.pk:
            if not self.starts_at:
                self.starts_at = ir_now()
                _update_fields.append('starts_at')
            if not self.expires_at:
                self.expires_at = self.starts_at + timedelta(
                    days=settings.SOCIAL_TRADE['subscriptionTrialPeriod' if self.is_trial else 'subscriptionPeriod']
                )
                _update_fields.append('expires_at')

            if not self.fee_amount:
                self.fee_amount = self.leader.subscription_fee
                _update_fields.append('fee_amount')

            if not self.fee_currency:
                self.fee_currency = self.leader.subscription_currency
                _update_fields.append('fee_currency')

            if not self.withdraw_transaction and not self.is_trial:
                self.create_transactions()
                _update_fields.extend(('leader_transaction', 'withdraw_transaction', 'system_transaction'))

        if update_fields is not None:
            update_fields = (*update_fields, *_update_fields)

        super().save(*args, update_fields=update_fields, **kwargs)

    @classmethod
    def is_user_subscriber_of_leader(cls, user: User, leader: Leader):
        return cls.get_actives().filter(subscriber=user, leader=leader).exists()

    @classmethod
    def subscribe(
        cls, leader: Optional[Leader], user: User, *, is_auto_renewal_enabled: bool
    ) -> 'SocialTradeSubscription':
        """This method subscribes a user to a leader

        Args:
            leader (Optional[Leader]): leader
            user (User): user
            is_auto_renewal_enabled (bool): enable auto renewal

        Raises:
            LeaderNotFoundException: Leader not exists or not active yet
            AlreadySubscribedException: there is an active subscription
            InsufficientBalance: user wallet balance is not enough
        Returns:
            SocialTradeSubscription: subscription instance
        """

        if not leader or not leader.is_active:
            raise LeaderNotFound()

        if leader.user_id == user.id:
            raise SelfSubscriptionImpossible()

        Locker.require_lock('socialtrade', user.pk)

        is_subscription_exists = cls.get_actives().filter(leader=leader, subscriber=user).exists()
        if is_subscription_exists:
            raise AlreadySubscribedException()

        if cls.has_reached_subscribe_limit(user):
            raise ReachedSubscriptionLimit()

        is_trial = cls.is_trial_available(user, leader)

        subscription = cls.objects.create(
            subscriber=user,
            leader=leader,
            is_trial=is_trial,
            is_auto_renewal_enabled=is_auto_renewal_enabled,
        )
        return subscription

    def unsubscribe(self):
        self.canceled_at = ir_now()
        self.save(update_fields=['canceled_at'])

    def renew(self) -> 'SocialTradeSubscription':
        if not self.is_renewable:
            self.set_not_renewed()
            raise SubscriptionNotRenewable()

        if self.has_reached_subscribe_limit(self.subscriber):
            self.set_not_renewed()
            raise ReachedSubscriptionLimit()

        try:
            with transaction.atomic():
                renewed_subscription = self.__class__.objects.create(
                    subscriber=self.subscriber,
                    leader=self.leader,
                    starts_at=self.expires_at,
                    is_trial=False,
                    is_auto_renewal_enabled=self.is_auto_renewal_enabled,
                    is_notif_enabled=self.is_notif_enabled,
                )
                self.is_renewed = True
                self.save(update_fields=(('is_renewed',)))

            return renewed_subscription

        except:
            self.set_not_renewed()
            raise

    def set_not_renewed(self):
        self.is_renewed = False
        self.save(update_fields=(('is_renewed',)))

    @classmethod
    def end_subscriptions_of_a_leader(cls, leader: Leader):
        """
        This method ends all active subscriptions of a deleted lead.
        Waiting subscriptions practically don't exist in Social Trade Subscriptions, but if they do exist one day,
        we should cancel them here as well.
        Trials end immediately but subscriptions last until the end of their cycles.

        :param leader: The deleted leader
        :return: None
        """
        trials = cls.get_actives().filter(leader=leader, is_trial=True)
        trials.update(canceled_at=ir_now(), is_auto_renewal_enabled=False)

        subscriptions = cls.get_actives().filter(leader=leader, is_trial=False)
        subscriptions.update(is_auto_renewal_enabled=False)

    def change_auto_renewal(self, new_status: bool):
        self.is_auto_renewal_enabled = new_status
        self.save(update_fields=['is_auto_renewal_enabled'])

    def change_is_notif_enabled(self, new_status: bool):
        self.is_notif_enabled = new_status
        self.save(update_fields=['is_notif_enabled'])

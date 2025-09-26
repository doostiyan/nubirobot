from decimal import Decimal

from django.db import models
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.models import RIAL
from exchange.features.managers import QueueItemManager


class QueueItem(models.Model):
    '''New Features Request Queue'''
    objects = QueueItemManager()

    FEATURES = Choices(
        (0, 'portfolio', 'Portfolio'),
        (1, 'price_alert', 'PriceAlert'),
        (2, 'xchange', 'Xchange'),
        (3, 'stop_loss', 'StopLoss'),
        (4, 'new_coins', 'NewCoins'),
        (5, 'gift_card', 'GiftCard'),
        (6, 'oco', 'OCO'),
        (7, 'short_sell', 'ShortSell'),
        (8, 'ticketing', 'Ticketing'),
        (9, 'convert', 'Convert'),
        (10, 'liquidity_pool', 'LiquidityPool'),
        (11, 'staking', 'Staking'),
        (12, 'vandar_deposit', 'VandarDeposit'),
        (13, 'vandar_withdraw', 'VandarWithdraw'),
        (14, 'vip_credit', 'VipCredit'),
        (15, 'leverage', 'Leverage'),
        (16, 'bot_transactions', 'BotTransactions'),
        (17, 'long_buy', 'LongBuy'),
        (18, 'social_trading_leadership', 'SocialTradingLeadership'),
        (19, 'social_trading_subscriber', 'SocialTradingSubscriber'),
        (20, 'jibit_pip', 'JibitPIP'),
        (21, 'convert2', 'Convert2'),
        (22, 'asset_backed_credit', 'AssetBackedCredit'),
        (23, 'convert3', 'Convert3'),
        (24, 'direct_debit', 'DirectDebit'),
        (25, 'abc_loan', 'AssetBackedCreditLoan'),
        (26, 'nobitex_jibit_ideposit', 'NobitexJibitIDeposit'),
        (27, 'miner', 'Miner'),
        (28, 'abc_debit', 'ABC_Debit'),
        (29, 'cobank', 'CorporateBanking'),
        (30, 'cobank_cards', 'CobankCards'),
        (31, 'bank_manual_deposit', 'BankManualDeposit'),
    )
    STATUS = Choices(
        (0, 'waiting', 'Waiting'),
        (1, 'done', 'Done'),
        (2, 'failed', 'Failed'),
    )

    # Bit Flags (for User.track field)
    BIT_FLAG_PORTFOLIO = 1

    # Feature Lifecycle
    ALPHA_USERS_TAG = 'تست آلفا'
    ALPHA_FEATURES = []
    BETA_FEATURES = []
    ENABLED_FEATURES = [FEATURES.price_alert, FEATURES.stop_loss, FEATURES.gift_card, FEATURES.oco]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    feature = models.IntegerField(default=FEATURES.portfolio, choices=FEATURES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+', null=False)
    status = models.IntegerField(choices=STATUS, default=STATUS.waiting)
    description = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ('created_at',)
        unique_together = ['user', 'feature']

    def get_position_in_queue(self):
        '''Return user position in this feature's waiting list. Zero means already active.'''
        if self.status == self.STATUS.done:
            return 0
        return QueueItem.objects.filter(
            feature=self.feature,
            status=self.STATUS.waiting,
            created_at__lte=self.created_at,
        ).count()

    def enable_feature(self):
        '''Enable this requested feature, and set any related flags/options/etc.'''
        if self.status == self.STATUS.done:
            return False
        # Handle special features
        if self.feature == self.FEATURES.portfolio:
            track = self.user.track or 0
            if not track & self.BIT_FLAG_PORTFOLIO:
                self.user.track = track + self.BIT_FLAG_PORTFOLIO
                self.user.save(update_fields=['track'])
        # Update queue item
        self.status = self.STATUS.done
        self.save(update_fields=['status'])
        return True

    def is_eligible_to_enable(self) -> bool:
        """Simple checks for limiting users that can participate in beta testing.

        Note: This should not be used for limiting final users of the feature, as
        feature flags are only intended for the duration of alpha/beta testing and
        is not checked after a feature is finalized.
        """
        if self.feature == self.FEATURES.short_sell:
            if self.user.user_type <= User.USER_TYPES.level1:
                return False
            total_trades = self.user.order_set.filter(dst_currency=RIAL).aggregate(
                total=models.Sum('matched_total_price'),
            )['total'] or Decimal('0')
            return total_trades >= Decimal('50_000_000_0')
        return True

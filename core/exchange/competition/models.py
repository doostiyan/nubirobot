import datetime
import json
from decimal import Decimal

from django.db import models

from exchange.accounts.models import User
from exchange.base.calendar import ir_today, ir_dst
from exchange.market.models import Order
from exchange.wallet.models import Wallet


class Competition(models.Model):
    name = models.CharField(max_length=100)
    date_from = models.DateField()
    date_to = models.DateField()
    is_active = models.BooleanField(default=False)
    initial_balance = models.DecimalField(max_digits=20, decimal_places=10)
    initial_balance_plan = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'مسابقه'
        verbose_name_plural = verbose_name

    def __str__(self):
        return 'Competition#{}: {}'.format(self.pk, self.name)

    @property
    def is_finished(self):
        return ir_today() > self.date_to

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=['is_active'])
        for registration in self.registrations.all():
            registration.is_active = False
            registration.save(update_fields=['is_active'])

    def get_user_registration(self, user):
        registrations = CompetitionRegistration.objects.filter(competition=self, user=user, is_active=True)
        if len(registrations) < 1:
            return None
        return registrations[0]

    def is_user_registered(self, user):
        return self.get_user_registration(user) is not None

    def register_user(self, user, force_reset=False):
        # Check if user is already registered in this competition
        current_registration = CompetitionRegistration.objects.filter(competition=self, user=user)
        if current_registration:
            current_registration = current_registration[0]
            if current_registration.is_active and not force_reset:
                return
        # Cancel all user orders
        for order in Order.objects.filter(user=user, status=Order.STATUS.active):
            order.do_cancel()
        # Initial balance plan
        initial_balance_plan = json.loads(self.initial_balance_plan or '{}')
        # Reset all wallet balances
        # Not revised for margin wallets
        wallets = Wallet.get_user_wallets(user)
        for wallet in wallets:
            if wallet.balance > Decimal('0'):
                tr = wallet.create_transaction(
                    tp='manual',
                    amount=-wallet.balance,
                    description='ریست موجودی برای شرکت در مسابقه‌ی {}'.format(self.name),
                )
                tr.commit()
            wallet_currency = str(wallet.currency)
            if wallet_currency in initial_balance_plan:
                initial_amount = Decimal(initial_balance_plan[wallet_currency])
                tr = wallet.create_transaction(
                    tp='manual',
                    amount=initial_amount,
                    description='موجودی اولیه شرکت در مسابقه‌ی {}'.format(self.name),
                )
                tr.commit()
        # Register user
        if current_registration:
            current_registration.is_active = True
            current_registration.save(update_fields=['is_active'])
        else:
            current_registration = CompetitionRegistration.objects.create(competition=self, user=user, is_active=True)
        current_registration.update_current_balance()

    def get_date_range(self):
        start = datetime.datetime(self.date_from.year, self.date_from.month, self.date_from.day)
        start = ir_dst.localize(start)
        end = datetime.datetime(self.date_to.year, self.date_to.month, self.date_to.day)
        end = ir_dst.localize(end) + datetime.timedelta(days=1)
        return start, end

    def get_leaderboard(self):
        return self.registrations.filter(is_active=True).select_related('user').order_by('-current_balance')

    @classmethod
    def get_active_competition(cls):
        return cls.objects.filter(is_active=True).order_by('-date_from').first()


class CompetitionRegistration(models.Model):
    competition = models.ForeignKey(Competition, related_name='registrations', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='competition_registrations', on_delete=models.CASCADE)
    current_balance = models.DecimalField(max_digits=30, decimal_places=10, db_index=True, default=Decimal('0'))
    gift_balance = models.DecimalField(max_digits=20, decimal_places=10, db_index=True, default=Decimal('0'))
    is_active = models.BooleanField(default=False)
    resets_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ['competition', 'user']
        verbose_name = 'شرکت در مسابقه'
        verbose_name_plural = verbose_name

    @property
    def user_display_name(self):
        return self.user.nickname or self.user.referral_code or self.user.pk

    def update_current_balance(self):
        balance = 0
        # Not revised for margin wallets
        for wallet in Wallet.get_user_wallets(self.user):
            balance += wallet.get_estimated_rls_balance(order_type='sell')
        self.current_balance = Decimal(balance)
        self.current_balance -= self.gift_balance
        self.save(update_fields=['current_balance'])

    def reset_funds(self):
        if self.resets_count >= 1:
            return False
        if not self.competition.is_active:
            return False
        self.competition.register_user(self.user, force_reset=True)
        self.resets_count += 1
        self.save(update_fields=['resets_count'])
        return True

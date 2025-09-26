import datetime
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional

from django.db import models
from model_utils import Choices

from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_dst, ir_now
from exchange.base.formatting import f_m
from exchange.base.models import Currencies
from exchange.base.money import money_is_close, money_is_zero
from exchange.wallet.models import Transaction, Wallet


class Diff(models.Model):
    """ Stores diff for all aspects of Nobitex system

        There are many system calculations that can be done in two ways. Usually one way
        is calculating based on internal DB and the other way is based on external systems'
        APIs. Diff is any mismatch between these calculated values.
    """
    TYPE = Choices(
        (0, 'unknown', 'نامعین'),
        (11, 'InternalDeposit', 'داخلی - واریز'),
        (12, 'InternalWithdraw', 'داخلی - برداشت'),
        (13, 'InternalTrade', 'داخلی - معامله'),
        (21, 'WithdrawHot', 'برداشت هات'),
    )
    date = models.DateField(verbose_name='روز')
    currency = models.IntegerField(choices=Currencies, verbose_name='رمزارز')
    tp = models.IntegerField(choices=TYPE)
    expected_value = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'),
                                         verbose_name='مقدار مورد انتظار')
    real_value = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'),
                                     verbose_name='مقدار واقعی')
    diff = models.DecimalField(max_digits=30, decimal_places=10, default=Decimal('0'), verbose_name='دیف')

    class Meta:
        verbose_name = 'دیف'
        verbose_name_plural = verbose_name
        unique_together = ['date', 'currency', 'tp']

    @property
    def date_from(self):
        """ Start of the time interval for this diff """
        return ir_dst.localize(datetime.datetime(self.date.year, self.date.month, self.date.day))

    @property
    def date_to(self):
        """ End of the time interval for this diff """
        return self.date_from + datetime.timedelta(days=1)

    def set_values(self, expected, real):
        """ Set expected and real values and send notif if there is a diff """
        self.expected_value = expected
        self.real_value = real
        initial_diff = self.diff if self.pk else Decimal('0')
        self.diff = self.expected_value - self.real_value
        if money_is_zero(self.diff):
            self.diff = Decimal('0')
        if self.pk:
            self.save(update_fields=['expected_value', 'real_value', 'diff'])
        else:
            self.save()
        if not money_is_close(initial_diff, self.diff):
            if self.diff == Decimal('0'):
                action = '🟢'
            else:
                action = '🔴' if self.diff > initial_diff else '🔵'
            Notification.notify_admins('```Expected:  {}\nReal:      {}\nDiff:      {}```'.format(
                self.expected_value,
                self.real_value,
                f_m(self.diff, c=self.currency, show_c=True),
            ), title='{} حسابرسی {}'.format(
                action,
                self.get_tp_display(),
            ))

    @classmethod
    def get(cls, date, currency, tp):
        """ Get or create a Diff object based on its keys """
        return cls.objects.get_or_create(currency=currency, date=date, tp=tp)[0]


class BotTransaction(models.Model):
    transactions = models.ManyToManyField(Transaction)
    wallet = models.ForeignKey(Wallet, related_name='bot_wallets', on_delete=models.CASCADE, verbose_name='کیف پول')
    amount = models.DecimalField(max_digits=25, decimal_places=10, verbose_name='مبلغ تراکنش')
    balance = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='موجودی')
    created_at = models.DateTimeField(db_index=True, auto_now_add=True)
    description = models.TextField(verbose_name='توضیحات')

    def __str__(self):
        return 'T#{}: {} {}'.format(self.pk, self.amount, self.wallet.get_currency_display())

    @classmethod
    def get_transactions(cls, ir_time: datetime.datetime, transaction_id: Optional[int], user: User) -> List[Transaction]:
        filter_params = {'bottransaction__wallet__user': user}
        transaction_id_q = None

        if transaction_id:
            if transaction_id > 0:
                transaction_id_q = models.Q(transaction_id__gte=transaction_id) | models.Q(transaction_id__lte=0)
            else:
                transaction_id_q = models.Q(transaction_id__gte=transaction_id) & models.Q(transaction_id__lte=0)

        if ir_time:
            filter_params['transaction__created_at__gte'] = ir_time
        if not ir_time and not transaction_id:
            filter_params['transaction__created_at__gte'] = ir_now() - timedelta(days=2)
        bot_transactions = cls.transactions.through.objects.filter(**filter_params)
        if transaction_id_q:
            bot_transactions = bot_transactions.filter(transaction_id_q)

        bot_transactions.select_related('transaction')
        transactions = [bot_transaction.transaction for bot_transaction in bot_transactions]
        return transactions

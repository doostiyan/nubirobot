from django.conf import settings
from django.db import models, transaction

from exchange.accounts.models import BankAccount, User
from exchange.base.calendar import ir_now
from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.base.models import RIAL, Settings
from exchange.base.tasks import run_admin_task
from exchange.wallet.constants import DEPOSIT_MAX_DIGITS
from exchange.wallet.helpers import RefMod, create_and_commit_transaction
from exchange.wallet.models import Transaction


class CoBankUserDeposit(models.Model):
    cobank_statement = models.OneToOneField('CoBankStatement', on_delete=models.DO_NOTHING, related_name='deposit')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=DEPOSIT_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    fee = models.DecimalField(max_digits=DEPOSIT_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    created_at = models.DateTimeField(default=ir_now, verbose_name='زمان')

    class Meta:
        verbose_name = 'واریزهای کاربری کوبنک'
        verbose_name_plural = verbose_name

    @property
    def effective_date(self):
        return self.created_at

    def calculate_fee(self):
        return int(self.amount * settings.NOBITEX_OPTIONS['coBankFee']['rate'])

    def save(self, *args, update_fields=None, **kwargs):
        if self.amount <= 0:
            raise ValueError('Deposit amount should be positive')

        tx_created = False
        if not self.pk:
            self.fee = self.calculate_fee()
            tx = create_and_commit_transaction(
                user_id=self.user.id,
                currency=RIAL,
                amount=self.amount - self.fee,
                ref_module=RefMod.cobank_deposit,
                description=f'واریز حساب به حساب - شماره شبا: {self.user_bank_account.shaba_number} - شماره رهگیری: {self.cobank_statement.tracing_number}',
                ref_id=self.cobank_statement.id,
                allow_negative_balance=True,
            )
            self.transaction = tx
            if update_fields:
                update_fields = (*update_fields, *('fee', 'transaction'))
            tx_created = bool(tx)

        super().save(*args, update_fields=update_fields, **kwargs)
        if tx_created and not Settings.is_disabled('detect_deposit_for_fraud'):
            transaction.on_commit(
                lambda: run_admin_task('detectify.check_cobank_deposit_fraud', cobank_deposit_id=self.pk)
            )

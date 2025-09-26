from django.db import models

from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.corporate_banking.models.constants import ACCOUNT_TP, COBANK_PROVIDER, NOBITEX_BANK_CHOICES, TRANSFER_MODE
from exchange.wallet.constants import BALANCE_MAX_DIGITS


class CoBankAccount(models.Model):
    # general fields
    provider_is_active = models.BooleanField(default=True)
    provider_bank_id = models.CharField(max_length=64, help_text='Our bank account database ID belonging to provider')
    bank = models.SmallIntegerField(choices=NOBITEX_BANK_CHOICES)
    iban = models.CharField(max_length=26)
    account_number = models.CharField(max_length=25)
    account_owner = models.CharField(max_length=200, blank=True, null=True)
    opening_date = models.DateTimeField(blank=True, null=True)

    # Nobitex fields
    provider = models.SmallIntegerField(choices=COBANK_PROVIDER, default=COBANK_PROVIDER.toman)
    is_active = models.BooleanField(default=False)
    transfer_mode = models.SmallIntegerField(choices=TRANSFER_MODE, default=TRANSFER_MODE.intra_bank)
    # To handle the difference between an operational account and a storage account:
    # withdraws should be handles from a storage account, while deposits can only be made to an operational account
    account_tp = models.SmallIntegerField(choices=ACCOUNT_TP)
    is_deleted = models.BooleanField(default=False)  # For soft delete

    deails = models.JSONField(default=dict)
    balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS + 6, decimal_places=MONETARY_DECIMAL_PLACES, blank=True, null=True
    )

    class Meta:
        verbose_name = 'حساب‌های نزد کوبنک'
        verbose_name_plural = verbose_name

        constraints = [
            models.UniqueConstraint(fields=['bank', 'iban', 'account_number', 'provider'], name='unique_bank_account'),
        ]

    def soft_delete(self):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=['is_deleted', 'is_active'])


class CoBankCard(models.Model):
    bank_account = models.ForeignKey(CoBankAccount, on_delete=models.CASCADE)
    card_number = models.CharField(max_length=16, unique=True)
    provider_is_active = models.BooleanField(default=True)
    provider_card_id = models.CharField(max_length=64, help_text='Our bank card database ID belonging to provider')
    name = models.CharField(max_length=64, default='')
    is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # For soft delete

    class Meta:
        verbose_name = 'کارت‌های بانکی کوبنک'
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        if self.is_active and not self.name:
            raise ValueError('Cannot activate card without a name.')
        super().save(*args, **kwargs)

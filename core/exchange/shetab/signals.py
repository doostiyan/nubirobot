from django.db.models.signals import pre_save, post_save
from django.db.utils import IntegrityError
from django.dispatch import receiver

from exchange.accounting.models import DepositSystemBankAccount
from exchange.accounts.models import Notification
from exchange.base.formatting import f_m
from exchange.base.logging import report_exception
from exchange.base.models import Currencies
from exchange.shetab.models import ShetabDeposit, JibitAccount


@receiver(pre_save, sender=ShetabDeposit, dispatch_uid='shetab_deposit_before_save')
def shetab_deposit_before_save(sender, instance, **kwargs):
    old = ShetabDeposit.objects.filter(id=instance.id).first()
    if not old or old.status_code == instance.status_code:
        return
    if instance.is_status_done:
        if not instance.check_card_number():
            return

    # Invalid case => tx created and status is -2
    if instance.status_code == ShetabDeposit.STATUS.confirmation_failed and instance.transaction:
        Notification.notify_admins('*Deposit #{}*\n*Amount:* {}\n*User:* {}'.format(
            instance.pk,
            f_m(instance.amount, c=Currencies.rls, show_c=True),
            str(instance.user),
        ), title='⛔️ *واریز شتابی نامعتبر*', channel='critical')


@receiver(post_save, sender=ShetabDeposit, dispatch_uid='shetab_deposit_post_save')
def shetab_deposit_post_save(sender, instance, **kwargs):
    if not instance.transaction:
        return
    if instance.status_code == ShetabDeposit.STATUS.invalid_card and getattr(instance, '_invalid_card_flag', False):
        instance.block_balance()


@receiver(post_save, sender=JibitAccount, dispatch_uid='jibit_account_post_save')
def jibit_account_post_save(sender, instance, **kwargs):
    bank_id = DepositSystemBankAccount.BANK_ID
    jibit_bank_mapper = {
        JibitAccount.BANK_CHOICES.BMJIIR: bank_id.centralbank,
        JibitAccount.BANK_CHOICES.BOIMIR: bank_id.sanatomadan,
        JibitAccount.BANK_CHOICES.BKMTIR: bank_id.mellat,
        JibitAccount.BANK_CHOICES.REFAIR: bank_id.refah,
        JibitAccount.BANK_CHOICES.BKMNIR: bank_id.maskan,
        JibitAccount.BANK_CHOICES.SEPBIR: bank_id.sepah,
        JibitAccount.BANK_CHOICES.KESHIR: bank_id.keshavarzi,
        JibitAccount.BANK_CHOICES.MELIIR: bank_id.melli,
        JibitAccount.BANK_CHOICES.BTEJIR: bank_id.tejarat,
        JibitAccount.BANK_CHOICES.BSIRIR: bank_id.saderat,
        JibitAccount.BANK_CHOICES.EDBIIR: bank_id.toseesaderat,
        JibitAccount.BANK_CHOICES.PBIRIR: bank_id.postbank,
        JibitAccount.BANK_CHOICES.TTBIIR: bank_id.toseetaavon,
        JibitAccount.BANK_CHOICES.BTOSIR: bank_id.tosee,
        14: bank_id.ghavamin,
        15: bank_id.karafarin,
        JibitAccount.BANK_CHOICES.BKPAIR: bank_id.parsian,
        JibitAccount.BANK_CHOICES.BEGNIR: bank_id.eghtesadenovin,
        JibitAccount.BANK_CHOICES.SABCIR: bank_id.saman,
        JibitAccount.BANK_CHOICES.BKBPIR: bank_id.pasargad,
        JibitAccount.BANK_CHOICES.SRMBIR: bank_id.sarmayeh,
        JibitAccount.BANK_CHOICES.SINAIR: bank_id.sina,
        JibitAccount.BANK_CHOICES.MEHRIR: bank_id.mehreiran,
        JibitAccount.BANK_CHOICES.CIYBIR: bank_id.shahr,
        JibitAccount.BANK_CHOICES.AYBKIR: bank_id.ayandeh,
        JibitAccount.BANK_CHOICES.TOSMIR: bank_id.gardeshgari,
        JibitAccount.BANK_CHOICES.HEKMIR: bank_id.hekmateiraninan,
        JibitAccount.BANK_CHOICES.ANSBIR: bank_id.resalat,
        JibitAccount.BANK_CHOICES.DAYBIR: bank_id.dey,
        JibitAccount.BANK_CHOICES.IRZAIR: bank_id.iranzamin,
        JibitAccount.BANK_CHOICES.MELLIR: bank_id.melal,
        JibitAccount.BANK_CHOICES.KHMIIR: bank_id.khavarmiane,
        JibitAccount.BANK_CHOICES.IVBBIR: bank_id.iranvenezoela,
        JibitAccount.BANK_CHOICES.NOORIR: bank_id.noor,
        JibitAccount.BANK_CHOICES.MEGHIR: bank_id.mehreghtesad}
    # Checking deposit system bank account
    bank_name = jibit_bank_mapper.get(instance.bank)
    if bank_name:
        try:
            DepositSystemBankAccount.objects.get_or_create(
                iban_number=instance.iban,
                account_number=instance.account_number,
                defaults={'is_private': True,
                          'type_of_account': DepositSystemBankAccount.ACCOUNT_TYPE.jibit,
                          'bank_id': bank_name}
            )
        except IntegrityError:
            report_exception()

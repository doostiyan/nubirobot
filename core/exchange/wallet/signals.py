from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from exchange.accounts.models import Notification
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.emailmanager import EmailManager
from exchange.base.formatting import f_m, get_status_translation
from exchange.base.models import TAG_NEEDED_CURRENCIES, Settings, get_currency_codename
from exchange.security.models import AddressBook
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import (
    AutomaticWithdraw,
    AvailableDepositAddress,
    AvailableHotWalletAddress,
    BankDeposit,
    ConfirmedWalletDeposit,
    Transaction,
    TransactionHistoryFile,
    Wallet,
    WithdrawRequest,
)
from exchange.web_engage.events import DepositWebEngageEvent, MarginTransactionEngageEvent, WithdrawWebEngageEvent


@receiver(post_save, sender=ConfirmedWalletDeposit, dispatch_uid='new_confirmed_wallet_deposit_created')
def new_confirmed_wallet_deposit_created(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.rial_value and instance.rial_value < Decimal('100_000_000_0'):
        return
    Notification.notify_admins(
        '*Deposit:* {} #{}\n*Username:* {}\n*User:* {}\n*Amount:* {}\n*URL:* {}'.format(  # noqa: UP032
            instance.currency_display,
            instance.pk,
            instance.wallet.user.username,
            instance.wallet.user.get_full_name(),
            f_m(instance.amount, c=instance.currency, show_c=True),
            str(instance.get_external_url()),
        ),
        title='💰 واریز مهم',
    )


@receiver(pre_save, sender=ConfirmedWalletDeposit, dispatch_uid='confirmed_wallet_deposit_before_save')
def confirmed_wallet_deposit_before_save(sender, instance: ConfirmedWalletDeposit, update_fields=None, **kwargs):
    old = ConfirmedWalletDeposit.objects.filter(id=instance.id).select_related('transaction').first()
    if old:
        if not old.confirmed and instance.confirmed:
            if not instance.transaction:
                return  # Special case when transaction is not confirmed
            wallet = instance._wallet or instance.transaction.wallet
            if not wallet.user.is_email_verified:
                return
            # Send notification email
            if Settings.get_flag('email_send_deposit_notification'):
                EmailManager.send_email(
                    wallet.user.email,
                    'deposit',
                    data={
                        'amount': instance.transaction.amount,
                        'currency': wallet.get_currency_display(),
                    },
                    priority='high',
                )


@receiver(post_save, sender=WithdrawRequest, dispatch_uid='new_withdraw_request_created')
def new_withdraw_request_created(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.is_internal_service and instance.is_rial:
        return
    if instance.status == WithdrawRequest.STATUS.new:
        are_2fa_and_otp_required = AddressBook.are_2fa_and_otp_required(
            user=instance.wallet.user,
            address=instance.target_address,
            network=instance.network,
            tag=instance.tag,
            is_crypto_currency=instance.wallet.is_crypto_currency,
        )
        if are_2fa_and_otp_required:
            if instance.is_otp_required:
                EmailManager.send_withdraw_request_confirmation_code(instance)
        else:
            AddressBook.send_addressbook_withdraw_request_affirmation(instance.wallet.user)


@receiver(pre_save, sender=WithdrawRequest, dispatch_uid='withdraw_status_user_notif')
def withdraw_status_user_notif(sender, instance, update_fields=None, **kwargs):
    if instance.is_internal_service and instance.is_rial:
        return
    if update_fields and 'rial_value' in update_fields:
        return
    old = WithdrawRequest.objects.filter(id=instance.id).first()
    if old:
        if old.status != instance.status:
            message = 'وضعیت درخواست برداشت شما به شناسه *{}* و مقدار *{}* به *{}* تغییر کرد.'.format(
                instance.pk,
                f_m(instance.amount, c=instance.wallet.currency, show_c=True),
                get_status_translation(instance.get_status_display())
            )
            Notification.objects.create(
                user=instance.wallet.user,
                message=message,
            )

            # Create reverse transaction for rejected withdraws
            if instance.status == WithdrawRequest.STATUS.rejected:
                t = instance.create_reverse_transaction()
                Notification.notify_admins('*Withdraw:* #{}\n*Transaction:* #{}\n*Reverse:* #{}'.format(
                    instance.pk,
                    instance.transaction.pk if instance.transaction else '-',
                    t.pk if t else '-',
                ), title='❌️ درخواست برداشت رد شد', channel='critical')

            # Set rial value
            if instance.status in [WithdrawRequest.STATUS.accepted, WithdrawRequest.STATUS.manual_accepted]:
                instance.rial_value = PriceEstimator.get_rial_value_by_best_price(
                    instance.amount, instance.wallet.currency, 'buy')
                instance.save(update_fields=['rial_value'])
    else:
        instance.rial_value = PriceEstimator.get_rial_value_by_best_price(
                    instance.amount, instance.wallet.currency, 'buy')
        if update_fields:
            update_fields = (*update_fields, 'rial_value')


@receiver(post_save, sender=AutomaticWithdraw, dispatch_uid='automatic_withdraw_created')
def new_automatic_withdraw_created(sender, instance, created, **kwargs):
    if instance.status in [
        AutomaticWithdraw.STATUS.new,
        AutomaticWithdraw.STATUS.sending,
        AutomaticWithdraw.STATUS.accepted,
    ]:
        return
    withdraw = instance.withdraw
    if instance.status == AutomaticWithdraw.STATUS.done:
        is_important_withdraw = not withdraw.rial_value or withdraw.rial_value >= Decimal('100_000_000_0')
        if is_important_withdraw:
            Notification.notify_admins(
                '*Type:* {}\n*Amount:* {}\n*Username:* {}\n*User:* {}\n*Withdraw:* {}\n*URL:* {}'.format(  # noqa: UP032
                    instance.get_tp_display(),
                    f_m(withdraw.amount, c=withdraw.currency, show_c=True),
                    withdraw.wallet.user.username,
                    withdraw.wallet.user.get_full_name(),
                    withdraw.pk,
                    withdraw.blockchain_url or instance.transaction_id or instance.binance_id,
                ),
                title='💸 برداشت مهم',
            )
    else:
        Notification.notify_admins(
            f'Current status of automatic withdraw for withdraw #{withdraw.pk} is: {instance.get_status_display()}',
            title='🔵 Automatic Withdraw Notification',
        )


@receiver(post_save, sender=BankDeposit, dispatch_uid='bank_deposit_post_save')
def bank_deposit_post_save(sender, instance, created, **kwargs):
    if created:
        Notification.notify_admins(
            'واریز بانکی جدید:\n*User:* {}'.format(str(instance.user)),
            channel='critical',
        )
        return
    if instance.confirmed:
        instance.commit_deposit()


@receiver(post_save, sender=AvailableHotWalletAddress, dispatch_uid='hot_wallet_post_save')
def hot_wallet_post_save(sender, instance, created, **kwargs):
    if created:
        hot_wallet_post_save_update_cache(instance)
        return
    address = instance.address
    balance = instance.total_received - instance.total_sent
    min_balance = settings.ADMIN_OPTIONS['minBalanceHotWallets'].get(instance.currency)
    if not min_balance:
        return  # No threshold defined
    if instance.active and balance < min_balance:
        Notification.notify_admins(
            '*Currency:* {}\n*Address:* {}\n*Balance:* {}'.format(
                instance.get_currency_display(),
                address,
                balance,
            ),
            title='⚠ *کمبود موجودی هات ولت*',
            channel='critical',
        )


def hot_wallet_post_save_update_cache(instance):
    network = instance.network or CURRENCY_INFO.get(instance.currency).get('default_network')
    cache.delete(f'hot_address_on_{network.upper()}')


@receiver(post_save, sender=AvailableDepositAddress, dispatch_uid='tagcoins_cold_address_post_save')
def tagcoins_cold_address_post_save(sender, instance, **kwargs):
    if instance.currency in TAG_NEEDED_CURRENCIES:
        cache.set(f'tag_deposit_address_on_{get_currency_codename(instance.currency).upper()}', None)


@receiver(pre_delete, sender=AvailableDepositAddress, dispatch_uid="tagcoins_cold_address_pre_delete")
def tagcoins_cold_address_pre_delete(sender, instance, **kwargs):
    if instance.currency in TAG_NEEDED_CURRENCIES:
        cache.set(f'tag_deposit_address_on_{get_currency_codename(instance.currency).upper()}', None)


@receiver(pre_save, sender=TransactionHistoryFile, dispatch_uid='set_transaction_history_filename')
def set_transaction_history_filename(sender, instance: TransactionHistoryFile, update_fields=None, **kwargs):
    if not instance.file_name:
        instance.set_file_name()
        if update_fields:
            update_fields = (*update_fields, 'file_name')


@receiver(post_save, sender=Transaction, dispatch_uid='send_web_engage_withdraw_and_deposit_events')
def send_web_engage_withdraw_and_deposit_events(sender, instance: Transaction, created, **_):
    if not created:
        return

    if instance.tp == Transaction.TYPE.deposit:
        DepositWebEngageEvent(
            user=instance.wallet.user,
            currency=instance.currency,
            amount=instance.amount,
            tp=instance.RIAL_DEPOSIT_REF_MODULES.get(instance.ref_module, 'Other'),
        ).send()
    elif instance.tp == Transaction.TYPE.withdraw:
        WithdrawWebEngageEvent(user=instance.wallet.user, currency=instance.currency, amount=instance.amount).send()
    # TODO some transactions are committed in admin.


@receiver(post_save, sender=Transaction, dispatch_uid='send_web_engage_on_transfer_event')
def send_web_engage_on_transfer_to_margin_event(sender, instance: Transaction, created, **kwargs):
    if not created:
        return

    if instance.tp == Transaction.TYPE.transfer and instance.wallet.type == Wallet.WALLET_TYPE.margin:
        MarginTransactionEngageEvent(
            user=instance.wallet.user,
            currency=instance.wallet.currency,
            amount=instance.amount,
            event_time=instance.created_at,
        ).send()

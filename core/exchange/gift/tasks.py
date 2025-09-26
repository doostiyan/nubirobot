from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction

from exchange.accounts.models import BankAccount, Notification, User, UserSms
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.crypto import random_string
from exchange.base.emailmanager import EmailManager
from exchange.base.formatting import f_m
from exchange.base.helpers import get_max_withdraw_amount
from exchange.base.logging import report_event
from exchange.base.models import RIAL, TAG_NEEDED_CURRENCIES
from exchange.gift.models import GiftBatchRequest, GiftCard
from exchange.wallet.models import Wallet, WithdrawRequest, WithdrawRequestPermit


@shared_task(name='cancel_gift_card', max_retries=1)
@transaction.atomic
def cancel_gift_card(pk):
    gift = GiftCard.objects.get(pk=pk)
    gift.initial_withdraw.system_reject_request()
    if gift.is_physical:
        gift.revert_physical_cost()
    gift.gift_status = GiftCard.GIFT_STATUS.canceled
    gift.save(update_fields=['gift_status'])
    if (
        gift.gift_batch
        and gift.gift_batch.batch_gifts.filter(gift_status=GiftCard.GIFT_STATUS.canceled).count()
        == gift.gift_batch.number
    ):
        gift.gift_batch.status = GiftBatchRequest.BATCH_STATUS.canceled
        gift.gift_batch.save(update_fields=['status'])
    Notification.notify_admins(
        f'Gift card with amount of {f_m(gift.amount)} and currency {gift.get_currency_display()}'
        f'for user {gift.sender.email} has been canceled.',
        title='کنسل کردن هدیه'
    )


@shared_task(name='cancel_gift_without_cost_reduction', max_retries=1)
@transaction.atomic
def cancel_gift_without_cost_reduction(pk):
    gift = GiftCard.objects.get(pk=pk)
    gift.gift_status = GiftCard.GIFT_STATUS.canceled
    gift.initial_withdraw.system_reject_request()
    gift.save(update_fields=['gift_status'])
    Notification.notify_admins(
        f'Physical gift card with amount of {f_m(gift.amount)} and currency {gift.get_currency_display()}'
        f'for user {gift.sender.email} has been canceled without physical fee reduction.',
        title='کنسل کردن هدیه بدون کارمزد'
    )


@shared_task(name='cancel_batch_request_gifts', max_retries=1)
def cancel_batch_request_gifts(batch_id):
    batch = GiftBatchRequest.objects.get(pk=batch_id)
    if batch.status == GiftBatchRequest.BATCH_STATUS.canceled:
        report_event('InvalidGiftBatchStatusForCancelling', extras={'batch_id': batch_id})
        return

    if batch.batch_gifts.filter(gift_status=GiftCard.GIFT_STATUS.verified).count() != batch.number:
        report_event('NotAllGiftsVerified', extras={'batch_id': batch_id})
        return

    gifts = batch.batch_gifts.all().select_for_update()
    with transaction.atomic():
        # system reject all initial withdraws
        for gift in gifts:
            gift.initial_withdraw.system_reject_request()
        gifts.update(gift_status=GiftCard.GIFT_STATUS.canceled)
        if batch.gift_type == GiftBatchRequest.GIFT_TYPES.physical:
            gift_user = User.get_gift_system_user()
            gift_cards_cost = (settings.GIFT_CARD_PHYSICAL_PRINT_FEE * batch.number) + \
                              settings.GIFT_CARD_PHYSICAL_POSTAL_FEE
            cancel_physical_gifts_cost_tr = Wallet.get_user_wallet(gift_user, RIAL).create_transaction(
                amount=-gift_cards_cost,
                description=f'User-{batch.user.id}, cancel transaction for physical gift cost.',
                tp='manual',
            )
            cancel_physical_gifts_cost_tr.commit()
            return_physical_costs_tr = Wallet.get_user_wallet(batch.user, RIAL).create_transaction(
                amount=gift_cards_cost,
                description=f'User-{batch.user.id} return physical cost.',
                tp='manual',
            )
            return_physical_costs_tr.commit()
        batch.status = GiftBatchRequest.BATCH_STATUS.canceled
        batch.save(update_fields=['status'])


@shared_task(name='resend_redeem_code_email', max_retries=1)
def resend_redeem_code_email(pk):
    gift = GiftCard.objects.get(pk=pk)
    if gift.receiver_email:
        EmailManager.send_email(
            gift.receiver_email,
            'giftcard',
            data={
                'redeem_code': gift.redeem_code,
                'user_text': gift.gift_sentence,
                'amount_display': f_m(gift.amount, c=gift.currency, show_c=True),
            },
            priority='high',
        )


@shared_task(name='gift_reset_password', max_retries=1)
def gift_reset_password(pk):
    gift = GiftCard.objects.get(pk=pk)
    new_gift_password = random_string(6).lower()
    gift.password = make_password(new_gift_password)
    UserSms.objects.create(
        user=gift.sender,
        tp=UserSms.TYPES.gift_password,
        to=gift.sender.mobile,
        text=f'پین جدید هدیه‌ی نوبیتکس شما: {new_gift_password}',
    )
    gift.save(update_fields=['password'])


@shared_task(name='revert_physical_cost', max_retries=1)
def revert_physical_cost(pk):
    """task for reverting physical gift cost"""
    gift = GiftCard.objects.get(pk=pk)
    if gift.is_physical and not gift.is_redeemed:
        gift.revert_physical_cost()


@shared_task(name='create_gift_batch', max_retries=1)
def create_gift_batch(user_id, batch_id):
    user = User.objects.get(pk=user_id)
    gift_batch = GiftBatchRequest.objects.get(id=batch_id)
    if gift_batch.status == GiftBatchRequest.BATCH_STATUS.confirmed:
        report_event('InvalidGiftBatchStatus', extras={'batch_id': batch_id, 'user_id': user_id})
        return
    currency = gift_batch.currency
    amount = gift_batch.amount
    password = gift_batch.password
    gift_sentence = gift_batch.gift_sentence
    sender_wallet = Wallet.get_user_wallet(user, currency)
    gift_user = User.get_gift_system_user()
    gift_wallet = Wallet.get_user_wallet(gift_user, currency)
    address_params = {}
    bank_account = None
    network = CURRENCY_INFO[currency]['default_network']
    is_restricted = False
    if user.is_restricted('WithdrawRequest'):
        is_restricted = True
    if sender_wallet.is_rial and user.is_restricted('WithdrawRequestRial'):
        is_restricted = True
    if sender_wallet.is_crypto_currency and user.is_restricted('WithdrawRequestCoin'):
        is_restricted = True
    if is_restricted:
        withdraw_permit = WithdrawRequestPermit.get(user, sender_wallet.currency, gift_batch.number * amount)
        if not withdraw_permit:
            report_event('GiftBatchWithdrawUnavailable', extras={'batch_id': batch_id, 'user_id': user_id})
            return

    max_withdraw_amount = Decimal(get_max_withdraw_amount(currency))
    if gift_batch.number * amount > max_withdraw_amount:
        report_event('GiftBatchWithdrawAmountLimitation', extras={'batch_id': batch_id, 'user_id': user_id})
        return
    amount_to_check = amount * gift_batch.number
    if gift_batch.gift_type == GiftCard.GIFT_TYPES.physical:
        if currency == RIAL:
            amount_to_check += settings.GIFT_CARD_PHYSICAL_FEE * gift_batch.number
        else:
            # check if user rial wallet has the balance needed for physical fee.
            user_rial_wallet = Wallet.get_user_wallet(user, RIAL)
            if user_rial_wallet.active_balance < settings.GIFT_CARD_PHYSICAL_FEE * gift_batch.number:
                report_event('GiftBatchInsufficientRialBalance', extras={'batch_id': batch_id, 'user_id': user_id})
                return
    if amount_to_check > sender_wallet.active_balance:
        report_event('GiftBatchInsufficientBalance', extras={'batch_id': batch_id, 'user_id': user_id})
        return
    if currency == RIAL:
        bank_account = BankAccount.objects.get(
            user=gift_user,
            confirmed=True, is_deleted=False, is_temporary=False)
        address_params['target_address'] = bank_account.display_name
    elif currency in TAG_NEEDED_CURRENCIES:
        with transaction.atomic():
            gift_wallet_tag = gift_wallet.get_current_deposit_tag(create=True)
            if isinstance(gift_wallet_tag, int):
                address_params['tag'] = gift_wallet_tag
            else:
                address_params['tag'] = gift_wallet_tag.tag
            gift_wallet_address = gift_wallet.get_current_deposit_address(create=True)
            if isinstance(gift_wallet_address, str):
                address_params['target_address'] = gift_wallet_address
            else:
                address_params['target_address'] = gift_wallet_address.address
    else:
        with transaction.atomic():
            gift_wallet_address = gift_wallet.get_current_deposit_address(create=True)
        if isinstance(gift_wallet_address, str):
            address_params['target_address'] = gift_wallet_address
        else:
            address_params['target_address'] = gift_wallet_address.address
    if not password:
        # generates a random password for batch gifts and message it to user.
        password = random_string(6).lower()
        UserSms.objects.create(
            user=user,
            tp=UserSms.TYPES.gift_password,
            to=user.mobile,
            text=f'پین هدایای نوبیتکس شما: {password}',
        )

    if gift_batch.gift_type == GiftCard.GIFT_TYPES.physical:
        # reduce physical cost for number of requested cards
        gift_cards_cost = (settings.GIFT_CARD_PHYSICAL_PRINT_FEE * gift_batch.number) +\
                          settings.GIFT_CARD_PHYSICAL_POSTAL_FEE
        # cost removal transaction for batch physical cards
        physical_cost_removal_transaction = Wallet.get_user_wallet(user, RIAL).create_transaction(
            amount=-gift_cards_cost,
            description=f'User-{user.id}, physical gift cost transaction.',
            tp='manual',
        )
        if physical_cost_removal_transaction is None:
            report_event('GiftBatchInsufficientRialBalance', extras={'batch_id': batch_id, 'user_id': user_id})
            return
        physical_cost_removal_transaction.commit()
        # cost transaction for system gift user for batch physical cards.
        physical_cost_addition_for_system_gift_transaction = Wallet.get_user_wallet(gift_user, RIAL).create_transaction(
            amount=gift_cards_cost,
            description=f'Gift account transaction for user-{user.id} physical gift cost.',
            tp='manual',
        )
        physical_cost_addition_for_system_gift_transaction.commit()
    mobile = email = None
    for count in range(gift_batch.number):
        initial_user_withdraw = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=sender_wallet,
            amount=amount,
            explanations='بابت صدور کارت هدیه',
            target_account=bank_account,
            network=network,
            **address_params,
        )
        initial_user_withdraw.do_verify()
        if gift_batch.gift_type == GiftBatchRequest.GIFT_TYPES.digital:
            receiver_info = gift_batch.digital_info[f'receiver_{count}']
            mobile = receiver_info['mobile']
            email = receiver_info['email']
        GiftCard.objects.create(
            gift_type=gift_batch.gift_type,
            amount=amount,
            sender=user,
            currency=currency,
            address=gift_batch.address,
            postal_code=gift_batch.postal_code,
            package_type=gift_batch.package_type,
            password=make_password(password),
            gift_batch_id=batch_id,
            redeem_type=gift_batch.redeem_type,
            card_design=gift_batch.card_design,
            redeem_code=random_string(32).upper(),
            redeem_date=gift_batch.redeem_date,
            otp_enabled=gift_batch.otp_enabled,
            receiver_email=email,
            mobile=mobile,
            initial_withdraw=initial_user_withdraw,
            gift_status=GiftCard.GIFT_STATUS.verified,
            gift_sentence=gift_sentence,
        )

    gift_batch.status = GiftBatchRequest.BATCH_STATUS.confirmed
    gift_batch.save(update_fields=['status'])
    Notification.notify_admins(
        f'{gift_batch.number} Gift cards for batch request with id: {gift_batch.id}'
        f' with amount of {f_m(gift_batch.amount)} for each card'
        f' and currency {gift_batch.get_currency_display()} and gift type {gift_batch.get_gift_type_display()}'
        f' for user {gift_batch.user.email} have been created.',
        title='ایجاد هدایای مربوط به درخواست دسته‌ای'
    )

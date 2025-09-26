import datetime

from django.db import transaction
from django.db.models import Q
from django_cron import Schedule
from post_office.models import Email

from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob
from exchange.base.emailmanager import EmailManager
from exchange.base.formatting import f_m
from exchange.gift.models import GiftCard
from exchange.wallet.models import WithdrawRequest


class SendGiftRedeemCodes(CronJob):
    """
    Sends redeem codes for digital gifts which created last thirty minutes, scheduled by gift's redeem date.
    """
    schedule = Schedule(run_every_mins=30)
    code = 'send_gift_redeem_codes'

    def run(self):
        print('[CRON] sending digital gifts redeem codes.')
        datetime_filter = Q(
            created_at__gte=ir_now() - datetime.timedelta(minutes=30),
            created_at__lte=ir_now(),
        )
        last_half_hour_gifts = GiftCard.objects.filter(
            datetime_filter,
            gift_status__in=GiftCard.REDEEMABLE_STATUSES,
            gift_type=GiftCard.GIFT_TYPES.digital,
        )
        for gift in last_half_hour_gifts:
            if gift.receiver_email:
                EmailManager.send_email(
                    gift.receiver_email,
                    'giftcard',
                    data={
                        'redeem_code': gift.redeem_code,
                        'user_text': gift.gift_sentence,
                        'amount_display': f_m(gift.amount, c=gift.currency, show_c=True),
                    },
                    scheduled_time=gift.redeem_date,
                    priority='medium',
                )

        # making sure if every redeem email is set to be sent to digital gift receivers.
        last_three_hours = ir_now() - datetime.timedelta(hours=3)
        last_thirty_minutes = ir_now() - datetime.timedelta(minutes=30)
        last_three_hours_gifts = GiftCard.objects.filter(
            created_at__gte=last_three_hours,
            created_at__lte=last_thirty_minutes,
            gift_status__in=GiftCard.REDEEMABLE_STATUSES,
            gift_type=GiftCard.GIFT_TYPES.digital,
        )
        for gift in last_three_hours_gifts:
            if not (
                Email.objects.filter(
                    to=gift.receiver_email,
                    template__name='giftcard',
                    created__gte=last_three_hours,
                    created__lte=last_thirty_minutes,
                ).exists()
            ):
                EmailManager.send_email(
                    gift.receiver_email,
                    'giftcard',
                    data={
                        'redeem_code': gift.redeem_code,
                        'user_text': gift.gift_sentence,
                        'amount_display': f_m(gift.amount, c=gift.currency, show_c=True),
                    },
                    scheduled_time=gift.redeem_date,
                    priority='medium',
                )


class VerifyGifts(CronJob):
    """
    Verifies gifts which their initial withdraw have been verified and cancels ones which their initial withdraw is not
    verified.
    """
    schedule = Schedule(run_every_mins=1)
    code = 'cancel_unverified_gifts'

    def run(self):
        print('[CRON] Verifying newly created gifts.')
        to_verify_gifts = GiftCard.objects.filter(
            created_at__gte=ir_now() - datetime.timedelta(days=1),
            created_at__lte=ir_now() - datetime.timedelta(minutes=3),
            gift_status=GiftCard.GIFT_STATUS.new,
            initial_withdraw__status__in=[WithdrawRequest.STATUS.verified, WithdrawRequest.STATUS.done]
        )
        to_verify_gifts.update(gift_status=GiftCard.GIFT_STATUS.verified)

        print(f'[CRON] {to_verify_gifts.count()} gift cards are verified')

        cancelable_gifts = GiftCard.objects.filter(
            created_at__gte=ir_now() - datetime.timedelta(days=1),
            created_at__lte=ir_now() - datetime.timedelta(minutes=3),
            gift_status=GiftCard.GIFT_STATUS.new,
            initial_withdraw__status__in=[WithdrawRequest.STATUS.new, WithdrawRequest.STATUS.rejected]
        )

        print(f'[CRON] {len(cancelable_gifts)} gift cards are going to be canceled')
        for gift in cancelable_gifts:
            with transaction.atomic():
                if gift.is_physical:
                    gift.revert_physical_cost()
                gift.gift_status = GiftCard.GIFT_STATUS.closed
                gift.save(update_fields=['gift_status'])

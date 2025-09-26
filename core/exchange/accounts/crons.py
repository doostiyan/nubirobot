import datetime

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.utils.timezone import now
from rest_framework.authtoken.models import Token

from exchange.accounts.constants import RESTRICTION_REMOVAL_INTERVAL_MINUTES
from exchange.accounts.models import (
    BankAccount,
    BankCard,
    User,
    UserMergeRequest,
    UserRestrictionRemoval,
    VerificationRequest,
)
from exchange.base.calendar import ir_now
from exchange.base.crons import CronJob, Schedule


class UpdateCacheCron(CronJob):
    schedule = Schedule(run_every_mins=10)
    code = 'update_cache'

    def run(self):
        from exchange.accounts.views.profile import get_options_v1, get_options_v2
        options = get_options_v1()
        cache.set('options_v1', options)
        options_v2 = get_options_v2(new_version=True)
        cache.set('options_v2', options_v2)


class TokenExpiryCron(CronJob):
    schedule = Schedule(run_every_mins=30)
    code = 'token_expiry'

    def run(self):
        if settings.DEBUG:
            return
        print('Revoking old tokens...')
        nw = now()
        Token.objects.filter(user__logout_threshold__isnull=True, apptoken__isnull=True, created__lt=nw - datetime.timedelta(hours=4)).delete()
        Token.objects.filter(user__logout_threshold__isnull=True, apptoken__isnull=False, created__lt=nw - datetime.timedelta(days=30)).delete()
        for token in Token.objects.filter(user__logout_threshold__isnull=False, apptoken__isnull=True).select_related('user'):
            if token.created < nw - datetime.timedelta(minutes=token.user.logout_threshold):
                token.delete()


class AutoVerificationCron(CronJob):
    schedule = Schedule(run_every_mins=60)
    code = 'auto_verification'

    def run(self):
        print('Verifying user requests...')
        nw = ir_now()
        recently = nw - datetime.timedelta(days=1)
        # Identity
        recent_identity_requests = VerificationRequest.objects.filter(
            created_at__gt=recently,
            status=VerificationRequest.STATUS.new,
        )
        for request in recent_identity_requests:
            request.updating_from_cron = True
            request.update_api_verification()
        # Mobile Identity
        mobile_identity_requests = User.objects.filter(date_joined__gt=recently)
        mobile_identity_requests = mobile_identity_requests.filter(verification_profile__mobile_identity_confirmed__isnull=True)
        for user in mobile_identity_requests:
            user.update_mobile_identity_status()
        # Bank Account Verification
        recent_bank_accounts = BankAccount.objects.filter(created_at__gt=recently, status=BankAccount.STATUS.new)
        for bank_account in recent_bank_accounts:
            bank_account.updating_from_cron = True
            bank_account.update_api_verification()
        # Bank Card Verification
        recent_bank_cards = BankCard.objects.filter(created_at__gt=recently, status=BankCard.STATUS.new)
        for bank_card in recent_bank_cards:
            bank_card.updating_from_cron = True
            bank_card.update_api_verification()


class DelayedRestrictionRemoval(CronJob):
    schedule = Schedule(run_every_mins=RESTRICTION_REMOVAL_INTERVAL_MINUTES)
    code = 'delayed_restriction_removal'

    def run(self):
        restrictions = UserRestrictionRemoval.objects.filter(
            is_active=True,
            ends_at__lte=now(),
        ).select_related('restriction')
        for item in restrictions:
            item.is_active = False
            item.save()
            user_restriction = item.restriction
            if user_restriction:
                user_restriction.delete()


class DeleteUncompletedMergeRequest(CronJob):
    schedule = Schedule(run_every_mins=5)
    code = 'delete_uncompleted_merge_request'

    def run(self):
        half_hour_ago = ir_now() - datetime.timedelta(minutes=30)
        UserMergeRequest.objects.filter(
            created_at__lte=half_hour_ago,
            status__in=UserMergeRequest.ACTIVE_STATUS,
        ).update(status=UserMergeRequest.STATUS.failed, description='کدیکبار مصرف منقضی شده است.')


class PopulateCaptchaPool(CronJob):
    schedule = Schedule(run_every_mins=1)
    code = 'populate_captcha_pool'

    def run(self):
        call_command('captcha_create_pool', loop=False, pool_size=3000 if settings.IS_PROD else 100)

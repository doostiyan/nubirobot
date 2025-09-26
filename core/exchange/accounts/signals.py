""" Accounts: Signals """
import uuid
from functools import partial
from json import JSONDecodeError

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver
from post_office.models import Log as EmailSendingLog

from exchange.accounts.constants import ACCOUNT_NUMBER_PATTERN_RE, new_tags
from exchange.accounts.custom_signals import (
    ACCOUNT_USER_TYPE_CHANGED,
    BANK_ITEM_CONFIRMED,
    BANK_ITEM_REJECTED,
    MERGE_REQUEST_STATUS_CHANGED,
    VERIFICATION_REQUEST_STATUS_CHANGED,
    VPROFILE_CONFIRMATIVE_FIELD_CHANGED,
)
from exchange.accounts.functions import get_bank_info_cache_key
from exchange.accounts.merge import MergeRequestStatusChangedContext
from exchange.accounts.models import (
    BankAccount,
    BankCard,
    BaseBankAccount,
    Notification,
    Tag,
    User,
    UserMergeRequest,
    UserSms,
    UserVoiceMessage,
    VerificationProfile,
    VerificationRequest,
)
from exchange.accounts.producer import notification_producer
from exchange.accounts.tasks import task_send_user_sms
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies, Settings, has_changed_field
from exchange.broker.broker.schema import SMSSchema
from exchange.broker.broker.topics import Topics
from exchange.notification.switches import NotificationConfig


@receiver(pre_save, sender=User, dispatch_uid='new_user_create_webengage_id')
def create_webengage_id_for_new_user(sender, instance, update_fields, **kwargs):
    # In order to avoid /users/profile API from writing in database
    if not instance.webengage_cuid:
        instance.webengage_cuid = uuid.uuid4()
        if update_fields:
            update_fields = (*update_fields, 'webengage_cuid')


@receiver(post_save, sender=User, dispatch_uid='new_user_created')
def new_user_created(sender, instance, created, **kwargs):
    from exchange.wallet.models import Wallet

    if not created:
        return
    user = instance
    Wallet.get_user_wallet(user, Currencies.rls)
    Notification.objects.create(
        user=user,
        message='به نوبیتکس خوش آمدید!',
    )
    # In order to avoid /users/profile API from writing in database
    VerificationProfile.objects.get_or_create(user=user)


@receiver(pre_save, sender=Notification, dispatch_uid='new_notification_presave')
def new_notification_presave(sender, instance, **kwargs):
    if instance.pk is None:
        Notification.send_to_broker([instance])
    if instance.sent_to_telegram:
        return
    try:
        instance.send_to_telegram_conversation(save=False)
    except:
        report_exception()


@receiver(post_save, sender=BankCard, dispatch_uid='bank_card_save')
def bank_card_save(sender, instance, created, **kwargs):
    if not Settings.is_feature_active('kyc2'):
        instance.user.update_verification_status()
    transaction.on_commit(lambda: cache.set(get_bank_info_cache_key(instance.user_id), None, 1))


@receiver(pre_save, sender=BankCard, dispatch_uid='new_bank_card_confirmed')
def new_bank_card_confirmed(sender, instance, **kwargs):
    from exchange.shetab.tasks import task_update_user_invalid_deposits
    instance.update_status(save=False)
    # Check if confirmed state is changed
    old = BankCard.objects.filter(id=instance.id).first()
    if old and not old.confirmed and instance.confirmed:
        transaction.on_commit(lambda: task_update_user_invalid_deposits.delay(instance.user_id))


@receiver(pre_save, sender=BankAccount, dispatch_uid='bank_account_presave')
def bank_account_presave(sender, instance: BankAccount, **kwargs):
    if instance.confirmed and instance.account_number in ['0', '', None]:
        try:
            verification_api = instance.get_api_verification_as_dict()
        except JSONDecodeError:
            verification_api = None

        has_valid_account_number = False

        if (
            verification_api
            and verification_api.get('result')
            and verification_api['result'].get('deposit')
            and ACCOUNT_NUMBER_PATTERN_RE.match(verification_api['result']['deposit'].strip())
        ):
            # Finnotech
            instance.account_number = verification_api['result']['deposit'].strip()
            has_valid_account_number = True

        elif (
            verification_api
            and verification_api.get('ibanInfo')
            and verification_api['ibanInfo'].get('depositNumber')
            and ACCOUNT_NUMBER_PATTERN_RE.match(
                verification_api['ibanInfo']['depositNumber'].strip(),
            )
        ):
            # Jibit
            instance.account_number = verification_api['ibanInfo']['depositNumber'].strip()
            has_valid_account_number = True

        if (
            has_valid_account_number
            and kwargs['update_fields'] is not None
            and 'account_number' not in kwargs['update_fields']
        ):
            kwargs['update_fields'] = ['account_number', *kwargs['update_fields']]


@receiver(post_save, sender=BankAccount, dispatch_uid='bank_account_save')
def bank_account_save(sender, instance: BankAccount, created, **kwargs):
    if not Settings.is_feature_active('kyc2'):
        instance.user.update_verification_status()
    instance.update_bank_id()
    transaction.on_commit(lambda: cache.set(get_bank_info_cache_key(instance.user_id), None, 1))

    # Check for blu account numbers with dash
    if instance.is_blu and '-' in instance.account_number:
        log_event(
            'Blu Account With Dash',
            details={
                'iban': instance.shaba_number,
                'account_number': instance.account_number,
                'api_response': instance.api_verification_json(),
            },
        )


@receiver(pre_save, sender=BankAccount, dispatch_uid='new_bank_account_confirmed')
def new_bank_account_confirmed(sender, instance, **kwargs):
    instance.update_status(save=False)


@receiver(post_save, sender=EmailSendingLog, dispatch_uid='new_failed_email')
def new_failed_email(sender, instance, created, **kwargs):
    if not created or instance.status != 1:
        return
    Notification.notify_admins(
        f'*Status:* {str(instance.email)[1:-1]}\n*Email:* {instance.get_status_display()}\n*Exception:* {instance.exception_type}',
        title='Warning: Email Sending Failed',
    )


@receiver(post_save, sender=VerificationProfile, dispatch_uid='verification_profile_updated')
def verification_profile_updated(sender, instance, created, **kwargs):
    if created:
        return
    instance.user.update_verification_status()


def produce_sms_event(sms_data: UserSms):
    sms = SMSSchema(
        user_id=str(sms_data.user.uid) if sms_data.user else None,
        text=sms_data.text,
        tp=sms_data.tp,
        to=sms_data.to,
        template=sms_data.template,
    )
    topic = Topics.FAST_SMS.value if sms.tp in sms_data.SMS_OTP_TYPES else Topics.SMS.value
    notification_producer.write_event(topic, sms.serialize())


def schedule_send_sms_task_and_save_task_id(instance):
    expires = 120 if instance.template in UserSms.SMS_OTP_TEMPLATE else 600
    task_async_result = task_send_user_sms.apply_async((instance.id,), expires=expires)
    if settings.CACHE_TASK_IDS_FOR_SENDING_SMS:
        cache.set(
            UserSms.TASK_ID_CACHE_KEY.format(sms_id=instance.id),
            str(task_async_result.id),
            timeout=1200,  # 20 minutes TTL
        )


@receiver(post_save, sender=UserSms, dispatch_uid='send_user_sms')
def send_user_sms(sender, instance, created, **kwargs):
    """Send SMS to user via sms.ir for newly created UserSms objects"""
    if not created:
        return

    if NotificationConfig.is_sms_logging_enabled():
        produce_sms_event(instance)

    if NotificationConfig.is_sms_broker_enabled():
        return

    transaction.on_commit(lambda: schedule_send_sms_task_and_save_task_id(instance))


@receiver(post_save, sender=UserVoiceMessage, dispatch_uid='send_voice_message')
def send_voice_message(sender, instance, created, **kwargs):
    if not created:
        return
    # Emulate Call sending in test environments
    if not settings.IS_PROD:
        Notification.objects.create(
            user=instance.user,
            message=f'شبیه‌سازی تماس تلفنی: {instance.text}',
        )
    # Check flag to send calls
    if not Settings.get_flag('send_call'):
        return
    # Skip sending call in Debug mode
    if not settings.IS_PROD:
        instance.delivery_status = 'sent: faked'
        instance.save(update_fields=['delivery_status'])
        return
    # Send the call
    instance.send()


@receiver(post_save, sender=VerificationRequest, dispatch_uid='verification_request_updated')
def verification_request_updated(sender, instance, created, **kwargs):

    if instance.tp == VerificationRequest.TYPES.auto_kyc and instance.status == VerificationRequest.STATUS.rejected:
        if Settings.is_feature_active('kyc2'):
            return
        try:
            api_verification = instance.get_api_verification_as_dict()
        except:
            liveness = None
        else:
            liveness = api_verification.get('liveness')

        messages = []
        if liveness:
            vr_result = liveness.get('verification_result')
            if isinstance(vr_result, dict):
                # new format of auto-kyc response - Jibit v2
                vr_data = vr_result.get('data', dict())
                verification_result = vr_data.get('result', False)

                lr_result = liveness.get('liveness_result', dict())
                lr_data = lr_result.get('data', dict())
                liveness_result = lr_data.get('State', False)
            else:
                verification_result = liveness.get('verification_result')
                liveness_result = liveness.get('liveness_result')

            if verification_result not in ('true', True, 'True', '1', 1):
                messages.append('هویت شما با توجه به مشخصات ارسالی مانند سریال کارت ملی تایید نشد.')
            if liveness_result not in ('true', True, 'True', '1', 1):
                messages.append('زنده بودن تصویر ارسالی مورد تایید نمی باشد.')
        if not len(messages):
            messages.append('مدارک و مشخصات ارسالی مورد تایید نمی باشد.')

        m = 'با سلام'
        m += '\n\n'
        m += 'کاربر گرامی، احراز هویت شما به دلایل مشروحه ذیل رد شد.'
        m += '\n\n'
        for message in messages:
            m += message
            m += '\n'
        m += '\n'
        m += 'لطفا مدارک و مشخصات ارسالی را با دقت بررسی و مجددا درخواست نمایید.'
        m += '\n\n'
        m += 'با تشکر'
        m += '\n'
        m += 'تیم پشتیبانی نوبیتکس'

        Notification.objects.create(user=instance.user, message=m)

    if instance.tp == VerificationRequest.TYPES.identity and instance.status == VerificationRequest.STATUS.confirmed:
        verification: VerificationProfile = instance.user.get_verification_profile()
        if not verification.mobile_identity_confirmed:
            instance.user.update_mobile_identity_status()


@receiver(post_save, sender=VerificationRequest)
def remove_incomplete_documents_tag(sender, instance, created, **kwargs):
    """
        Signal handler to remove the 'incomplete_documents' tag from a user's tags
        when a VerificationRequest object is created.
    """
    if created:
        incomplete_documents_tag_name = new_tags.get('incomplete_documents')

        if instance.user.tags.filter(name=incomplete_documents_tag_name).exists():
            instance.user.tags.remove(Tag.objects.filter(name=incomplete_documents_tag_name).first())


def bank_item_survey_and_trigger(sender, instance: BaseBankAccount, is_create, update_fields):
    def survey_and_trigger(change_dict):
        must_be_notified = all([
            not instance.is_deleted,
            has_changed_field(change_dict, 'confirmed', update_fields),
            has_changed_field(change_dict, 'status', update_fields),
            (not is_create) or getattr(instance, 'is_from_bank_card', False),
        ])
        if must_be_notified:
            if instance.has_confirmed_status:
                signal: Signal = BANK_ITEM_CONFIRMED
            elif instance.has_rejected_status:
                signal: Signal = BANK_ITEM_REJECTED
            else:
                return
            signal.send(sender=sender, item=instance)

    transaction.on_commit(partial(survey_and_trigger, instance.tracker.changed()))


@receiver(post_save, sender=BankCard, dispatch_uid='bank_card_survey_and_trigger')
def bank_card_survey_and_trigger(sender, instance: BankCard, created, **kwargs):
    bank_item_survey_and_trigger(sender, instance, created, kwargs['update_fields'])


@receiver(post_save, sender=BankAccount, dispatch_uid='bank_account_survey_and_trigger')
def bank_account_survey_and_trigger(sender, instance: BankAccount, created, **kwargs):
    bank_item_survey_and_trigger(sender, instance, created, kwargs['update_fields'])


@receiver(post_save, sender=VerificationProfile, dispatch_uid='verification_profile_survey_and_trigger')
def verification_profile_survey_and_trigger(sender, instance: VerificationProfile, created, **kwargs):
    update_fields = kwargs['update_fields']

    def survey_and_trigger(change_dict):
        if created:
            return
        for confirmative_field in instance.confirmative_fields:
            if has_changed_field(change_dict, confirmative_field, update_fields):
                VPROFILE_CONFIRMATIVE_FIELD_CHANGED.send(
                    sender=sender,
                    vprofile=instance, confirmative_field=confirmative_field,
                )

    transaction.on_commit(partial(survey_and_trigger, instance.tracker.changed()))


@receiver(post_save, sender=VerificationRequest, dispatch_uid='verification_request_survey_and_trigger')
def verification_request_survey_and_trigger(sender, instance: VerificationRequest, created, **kwargs):
    update_fields = kwargs['update_fields']

    def survey_and_trigger(change_dict):
        if has_changed_field(change_dict, 'status', update_fields):
            VERIFICATION_REQUEST_STATUS_CHANGED.send(
                sender=sender,
                verification_request=instance,
            )
    transaction.on_commit(partial(survey_and_trigger, instance.tracker.changed()))


@receiver(post_save, sender=User, dispatch_uid='user_survey_and_trigger')
def user_survey_and_trigger(sender, instance: User, created, **kwargs):
    update_fields = kwargs['update_fields']

    def survey_and_trigger(change_dict):
        # send email on user_type change
        if not created and has_changed_field(
            change_dict, 'user_type', update_fields,
        ):
            ACCOUNT_USER_TYPE_CHANGED.send(
                sender=sender,
                user=instance,
                previous_type=change_dict.get('user_type'),
                current_type=instance.user_type,
            )
    transaction.on_commit(partial(survey_and_trigger, instance.tracker.changed()))


@receiver(post_save, sender=UserMergeRequest, dispatch_uid='user_merge_request_survey_and_trigger')
def user_merge_request_survey_and_trigger(sender, instance: UserMergeRequest, created, **kwargs):
    update_fields = kwargs['update_fields']

    if has_changed_field(instance.tracker.changed(), 'status', update_fields):
        merge_data = MergeRequestStatusChangedContext.from_users(
            main_user=instance.main_user, second_user=instance.second_user
        )
        # add User event on status changed
        def survey_and_trigger():
            MERGE_REQUEST_STATUS_CHANGED.send(
                sender=sender,
                item=instance,
                merge_data=merge_data,
            )

        transaction.on_commit(survey_and_trigger)

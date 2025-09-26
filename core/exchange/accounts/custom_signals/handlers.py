import contextlib
from typing import TYPE_CHECKING, Union

from django.conf import settings
from django.dispatch import receiver

from exchange.accounts.custom_signals import (
    ACCOUNT_USER_TYPE_CHANGED,
    BANK_ITEM_CONFIRMED,
    BANK_ITEM_REJECTED,
    MERGE_REQUEST_STATUS_CHANGED,
    VERIFICATION_REQUEST_STATUS_CHANGED,
    VPROFILE_CONFIRMATIVE_FIELD_CHANGED,
)
from exchange.accounts.functions import get_text_level_features
from exchange.accounts.kyc_param_notifier import KYCParam, try_notifying_kyc_param
from exchange.accounts.merge import MergeNotifier, MergeRequestStatusChangedContext
from exchange.accounts.models import (
    BankAccount,
    BankCard,
    BaseBankAccount,
    User,
    UserEvent,
    UserLevelChangeHistory,
    UserMergeRequest,
    UserReferral,
    UserSms,
    VerificationProfile,
    VerificationRequest,
)
from exchange.accounts.tasks import task_convert_card_number_to_iban
from exchange.base.logging import metric_incr, report_event
from exchange.base.models import Settings
from exchange.base.tasks import send_email
from exchange.web_engage.events import user_attribute_verified_events as user_events

if TYPE_CHECKING:
    from exchange.web_engage.events.base import WebEngageKnownUserEvent


@receiver(ACCOUNT_USER_TYPE_CHANGED)
def send_email_on_user_type_change(user, previous_type, current_type, **kwargs):
    if not Settings.is_feature_active('kyc2'):
        return

    if current_type not in [
        User.USER_TYPES.level1,
        User.USER_TYPES.level2,
        User.USER_TYPES.verified,
    ]:
        return

    # for sudden changes in user_type
    if current_type != user.user_type:
        return

    if not user.user_type_label:
        report_event('LevelLabelNotFound', extras={'user_type': current_type})
        return

    level_features = get_text_level_features(current_type, user.get_verification_profile().mobile_identity_confirmed)
    send_email(
        email=user.email,
        template='new_user_type_notif',
        data=dict(
            has_more_level=current_type < 90,
            level_label=user.user_type_label,
            user_full_name=user.get_full_name(),
            features=level_features,
        ),
        priority='medium',
    )


@receiver(BANK_ITEM_CONFIRMED)
def send_web_engage_event_on_bank_item_confirmed(item: BaseBankAccount, **kwargs):
    item.web_engage_class_for_confirmation(user=item.user).send()


@receiver(ACCOUNT_USER_TYPE_CHANGED)
def send_web_engage_event_on_user_type_change(user: User, previous_type: int, current_type: int, **kwargs):
    if previous_type == User.USER_TYPES.trader:
        return
    if current_type == User.USER_TYPES.level1:
        user_events.Level1VerifiedWebEngageEvent(user=user).send()
        user_referral = UserReferral.objects.filter(child=user).first()
        if user_referral is not None:
            user_events.ReferredUserUpgradedToLevel1WebEngageEvent(user=user_referral.parent).send()
        return
    with contextlib.suppress(KeyError):
        {
            User.USER_TYPES.level2: user_events.Level2VerifiedWebEngageEvent,
            User.USER_TYPES.verified: user_events.Level3VerifiedWebEngageEvent,
        }[current_type](user=user).send()


@receiver(BANK_ITEM_CONFIRMED)
def call_iban_api_on_bank_card_confirmed(item: BaseBankAccount, **kwargs):
    if isinstance(item, BankCard) and (settings.IS_PROD or item.user.is_user_considered_in_production_test):
        task_convert_card_number_to_iban.delay(item.id)


@receiver(VPROFILE_CONFIRMATIVE_FIELD_CHANGED)
def notify_on_verification_profile_fields_confiremd(vprofile: VerificationProfile, confirmative_field: str, **kwargs):
    if not getattr(vprofile, confirmative_field):
        # Handle confirmation only (not rejection)
        return

    vprofile_field2kyc_param = {
        'email_confirmed': KYCParam.EMAIL,
        'mobile_confirmed': KYCParam.MOBILE,
        'identity_confirmed': KYCParam.IDENTITY,
        'address_confirmed': KYCParam.ADDRESS,
        'selfie_confirmed': KYCParam.SELFIE,
        'mobile_identity_confirmed': KYCParam.MOBILE_IDENTITY,
        'identity_liveness_confirmed': KYCParam.AUTO_KYC,
    }

    try:
        param = vprofile_field2kyc_param[confirmative_field]
    except KeyError:
        return
    try_notifying_kyc_param(param, vprofile.user, True, vprofile)


@receiver(VPROFILE_CONFIRMATIVE_FIELD_CHANGED)
def notify_sms_on_email_confirmed(vprofile: VerificationProfile, confirmative_field: str, **kwargs):
    if confirmative_field != 'email_confirmed' or not vprofile.email_confirmed:
        return
    if not vprofile.user.has_verified_mobile_number:
        return

    UserSms.objects.create(
        user=vprofile.user,
        tp=UserSms.TYPES.kyc_parameter,
        to=vprofile.user.mobile,
        text='ایمیل',
        template=UserSms.TEMPLATES.set_user_parameter,
    )


def _notify_on_bank_item_got_rejected_or_confirmed(item: Union[BankCard, BankAccount], confirmed: bool, **kwargs):
    param = {
        BankCard: KYCParam.BANK_CARD,
        BankAccount: KYCParam.BANK_ACCOUNT,
    }[type(item)]
    try_notifying_kyc_param(param, item.user, confirmed, item)


@receiver(BANK_ITEM_CONFIRMED)
def notify_on_bank_card_or_account_get_confirmed(item: BaseBankAccount, **kwargs):
    _notify_on_bank_item_got_rejected_or_confirmed(item, True)


@receiver(BANK_ITEM_REJECTED)
def notify_on_bank_card_or_account_get_rejected(item: BaseBankAccount, **kwargs):
    _notify_on_bank_item_got_rejected_or_confirmed(item, False)


@receiver(VERIFICATION_REQUEST_STATUS_CHANGED)
def notify_on_verification_request_rejected(verification_request: VerificationRequest, **kwargs):
    if verification_request.status != VerificationRequest.STATUS.rejected:
        return
    param = {
        VerificationRequest.TYPES.identity: KYCParam.IDENTITY,
        VerificationRequest.TYPES.address: KYCParam.ADDRESS,
        VerificationRequest.TYPES.selfie: KYCParam.SELFIE,
        VerificationRequest.TYPES.auto_kyc: KYCParam.AUTO_KYC,
    }[verification_request.tp]
    try_notifying_kyc_param(param, verification_request.user, False, verification_request)


@receiver(MERGE_REQUEST_STATUS_CHANGED)
def add_user_event_on_merge_request_status_changed(item: UserMergeRequest, **kwargs):
    try:
        action_type = {
            UserMergeRequest.STATUS.requested: UserEvent.USER_MERGE_ACTION_TYPES.requested,
            UserMergeRequest.STATUS.accepted: UserEvent.USER_MERGE_ACTION_TYPES.accepted,
            UserMergeRequest.STATUS.rejected: UserEvent.USER_MERGE_ACTION_TYPES.rejected,
            UserMergeRequest.STATUS.need_approval: UserEvent.USER_MERGE_ACTION_TYPES.need_approval,
        }[item.status]
        UserEvent.objects.create(
            user=item.main_user,
            action=UserEvent.ACTION_CHOICES.user_merge,
            action_type=action_type,
            description=item.description,
        )
        if item.status in [UserMergeRequest.STATUS.accepted, UserMergeRequest.STATUS.need_approval]:
            UserEvent.objects.create(
                user=item.second_user,
                action=UserEvent.ACTION_CHOICES.user_merge,
                action_type=action_type,
                description=item.description,
            )
    except KeyError:
        return


@receiver(MERGE_REQUEST_STATUS_CHANGED)
def notify_on_merge_request_status_accepted(
    item: UserMergeRequest,
    merge_data: MergeRequestStatusChangedContext,
    **kwargs,
):
    if item.status == UserMergeRequest.STATUS.accepted:
        MergeNotifier(merge_request=item, merge_data=merge_data).send()


@receiver(VERIFICATION_REQUEST_STATUS_CHANGED)
def send_web_engage_event_on_verification_request_confirmed(verification_request: VerificationRequest, **kwargs):
    try:
        web_engage: WebEngageKnownUserEvent = {
            VerificationRequest.TYPES.identity: user_events.IdentityConfirmedWebEngageEvent,
            VerificationRequest.TYPES.selfie: user_events.SelfieConfirmedWebEngageEvent,
            VerificationRequest.TYPES.auto_kyc: user_events.AutoKycConfirmedWebEngageEvent,
        }[verification_request.tp](user=verification_request.user)
    except KeyError:
        return

    if verification_request.status == VerificationRequest.STATUS.confirmed:
        web_engage.send()


@receiver(VERIFICATION_REQUEST_STATUS_CHANGED)
def send_web_engage_event_on_verification_request_rejected(verification_request: VerificationRequest, **kwargs):
    try:
        web_engage: WebEngageKnownUserEvent = {
            VerificationRequest.TYPES.selfie: user_events.SelfieRejectedWebEngageEvent,
            VerificationRequest.TYPES.auto_kyc: user_events.AutoKycRejectedWebEngageEvent,
        }[verification_request.tp](user=verification_request.user, reject_reason='')
    except KeyError:
        return

    if verification_request.status == VerificationRequest.STATUS.rejected:
        # todo: use show_to_user field that amin will put it in AdminConsideration model to extract reject reason
        # web_engage.reject_reason = 'something'
        web_engage.send()


@receiver(VERIFICATION_REQUEST_STATUS_CHANGED)
def send_web_engage_event_on_verification_request_created(verification_request: VerificationRequest, **kwargs):
    try:
        web_engage: WebEngageKnownUserEvent = {
            VerificationRequest.TYPES.selfie: user_events.SelfieStartedWebEngageEvent,
            VerificationRequest.TYPES.auto_kyc: user_events.AutoKycStartedWebEngageEvent,
        }[verification_request.tp](user=verification_request.user, device_kind=verification_request.device)
    except KeyError:
        return

    if verification_request.status == VerificationRequest.STATUS.new:
        web_engage.send()


@receiver(ACCOUNT_USER_TYPE_CHANGED)
def send_sms_on_user_type_change(user, previous_type, current_type, **kwargs):
    must_be_notified = (
        user.has_verified_mobile_number
        and previous_type < user.USER_TYPES.level1
        and current_type == user.USER_TYPES.level1
    )
    if not must_be_notified:
        return
    level_to_sms_message = {
        user.USER_TYPES.level1: 'کاربر گرامی، احراز شما در نوبیتکس در سطح یک کامل شد.',
    }
    message = level_to_sms_message[current_type]
    UserSms.objects.create(
        user=user,
        tp=UserSms.TYPES.kyc,
        to=user.mobile,
        text=message,
    )


@receiver(ACCOUNT_USER_TYPE_CHANGED)
def add_log_on_user_type_change(user, previous_type, current_type, **kwargs):
    if previous_type == current_type:
        return
    UserLevelChangeHistory.objects.create(changed_by=user, user=user, from_level=previous_type, to_level=current_type)
    metric_incr(f'metric_change_user_type__{current_type}')

import json

from celery import shared_task
from django.db import transaction

from exchange.accounts.functions import create_bank_account, revoke_sms_tasks_by_template
from exchange.accounts.kyc_param_notifier import KYCParam, try_notifying_kyc_param
from exchange.accounts.merge.merge_manager import MergeByEmail, MergeByMobile
from exchange.accounts.models import BankAccount, BankCard, User, UserMergeRequest, UserSms, VerificationRequest
from exchange.base.logging import report_event
from exchange.fcm.models import FCMDevice
from exchange.integrations.errors import APICallProviderError
from exchange.integrations.exceptions import JibitAPIError, VerificationAPIError, VerificationError
from exchange.integrations.jibit import JibitVerificationClient
from exchange.integrations.verification import VerificationClient


@shared_task(name='send_user_sms', max_retries=2)
def task_send_user_sms(sms_id):
    UserSms.objects.get(id=sms_id).send()


@shared_task(name='deactivate_user_tokens')
def task_deactivate_user_tokens(user_id):
    """This administration task revokes all tokens of the user, including
    login token and FCM tokens. This task should ensure that the user cannot
    access any of its accounts data or perform any action with any of the old
    tokens/cookies/etc.
    """
    user = User.objects.filter(id=user_id).select_related('auth_token').first()
    if not user:
        return
    with transaction.atomic():
        FCMDevice.objects.filter(user=user, is_active=True).update(is_active=False)
        if hasattr(user, 'auth_token'):
            user.auth_token.delete()


def notify_on_no_bank_account_created(bank_card, error_mesasge):
    # Debt: Highly Inconsistent with the overall structure of KYC Param notifications
    bank_account = BankAccount(
        user=bank_card.user,
        status=BankAccount.STATUS.rejected,
        confirmed=False,
        is_from_bank_card=True,
    )
    bank_account._from_bank_card = bank_card
    bank_account.api_verification_verbose_message = error_mesasge
    try_notifying_kyc_param(KYCParam.BANK_ACCOUNT, bank_account.user, bank_account.confirmed, bank_account)
    return


@shared_task(name='convert_card_number_to_iban')
def task_convert_card_number_to_iban(bank_card_id: int):
    bank_card = BankCard.objects.filter(id=bank_card_id, is_deleted=False).select_related('user').first()
    if not bank_card:
        return

    try:
        result = VerificationClient().convert_card_number_to_iban(bank_card)
    except (APICallProviderError, VerificationAPIError, VerificationError) as ex:
        notify_on_no_bank_account_created(bank_card, getattr(ex, 'msg', 'عدم برفراری ارتباط با سرویس‌دهنده'))
        return

    if result.successful and BankAccount.objects.filter(
        shaba_number=result.iban, user=bank_card.user, is_deleted=False, confirmed=True,
    ).exists():
        return

    result.api_response.update({'verification': result.successful})
    bank_account = create_bank_account(
        user=bank_card.user,
        shaba_number=result.iban,
        deposit=result.deposit or '0',
        owner_name=bank_card.user.get_full_name(),
        status=BankAccount.STATUS.confirmed if result.successful else BankAccount.STATUS.rejected,
        confirmed=result.successful,
        api_verification=json.dumps(result.api_response),
        is_from_bank_card=True,
        save=False,
    )
    if bank_account:
        bank_account._from_bank_card = bank_card
        bank_account.api_verification_verbose_message = result.error_message
        bank_account.save()


@shared_task(name='retry_calling_auto_kyc_api')
def task_retry_calling_auto_kyc_api(verification_request_id: int, retry: int):
    verification_request = VerificationRequest.objects.get(id=verification_request_id)
    if verification_request.status == verification_request.STATUS.new:
        verification_request.update_api_verification(force_update=True, retry=retry)


@shared_task(name='user_merge')
def task_user_merge(merge_request_id: int) -> None:
    request = UserMergeRequest.objects.filter(pk=merge_request_id, status=UserMergeRequest.STATUS.need_approval).first()
    if not request:
        report_event(
            'UserMergeRequestDoesNotExist',
            extra={
                'src': 'TaskUserMerge',
                'id': merge_request_id,
            },
        )
        return

    try:
        if request.merge_by == UserMergeRequest.MERGE_BY.mobile:
            MergeByMobile(request.main_user, request.second_user).merge(request)
        else:
            MergeByEmail(request.main_user, request.second_user).merge(request)
    except Exception as e:
        report_event(
            'MergeTaskError',
            extra={
                'src': 'Merge.merge',
                'exception': str(e),
            },
        )


@shared_task(name='reject_merge_request')
def task_reject_merge_request(merge_request_id: int, description: str) -> None:
    request = (
        UserMergeRequest.objects.filter(pk=merge_request_id).exclude(status=UserMergeRequest.STATUS.rejected).first()
    )
    if not request:
        report_event(
            'UserMergeRequestDoesNotExist',
            extra={
                'src': 'TaskUserMerge',
                'id': merge_request_id,
            },
        )
        return

    request.change_to_rejected_status(description)


@shared_task(name='revoke_tasks_sending_sms_by_template')
def task_revoke_tasks_sending_sms_by_template(templates: str):
    revoke_sms_tasks_by_template(templates)


@shared_task(
    bind=True,
    name='convert_iban_to_account_number',
    default_retry_delay=30,
    autoretry_for=(JibitAPIError,),
    retry_kwargs={'max_retries': 5, 'countdown': 10},
)
def task_convert_iban_to_account_number(self, bank_account_id: int):
    bank_account = BankAccount.objects.filter(pk=bank_account_id).first()
    if not bank_account or not bank_account.confirmed or not bank_account.shaba_number:
        return

    result = JibitVerificationClient().iban_inquery(bank_account.shaba_number)
    bank_account.account_number = result.deposit_number
    bank_account.save(update_fields=('account_number',))

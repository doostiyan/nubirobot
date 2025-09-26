from decimal import Decimal
from typing import List, Union

from celery import shared_task

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.api import ParseError
from exchange.base.constants import ZERO
from exchange.base.decorators import measure_time_cm
from exchange.base.emailmanager import EmailManager
from exchange.base.logging import report_exception
from exchange.base.models import AMOUNT_PRECISIONS, get_currency_codename
from exchange.base.parsers import parse_strict_decimal
from exchange.base.tasks import task_run_cron
from exchange.celery import app
from exchange.socialtrade.exceptions import InsufficientBalance, ReachedSubscriptionLimit, SubscriptionNotRenewable
from exchange.socialtrade.utils import format_amount
from exchange.socialtrade.validators import validate_subscription_fee


@shared_task(name='socialtrade.admin.approve_leadership_request')
def task_approve_leadership_request(request_id: int, system_fee_percentage: str):
    from exchange.socialtrade.models import LeadershipRequest

    system_fee_percentage: Decimal = parse_strict_decimal(system_fee_percentage, Decimal('0.01'), required=True)
    if system_fee_percentage >= 100 or system_fee_percentage < 0:
        raise ValueError('Invalid system_fee_percentage, should be between 0 and 100')

    leadership_request: LeadershipRequest = LeadershipRequest.objects.get(pk=request_id)
    leadership_request.accept(system_fee_percentage)


@shared_task(name='socialtrade.admin.reject_leadership_request')
def task_reject_leadership_request(request_id: int, reason: int):
    from exchange.socialtrade.models import LeadershipRequest

    leadership_request: LeadershipRequest = LeadershipRequest.objects.get(pk=request_id)
    if not reason or reason not in LeadershipRequest.REASONS:
        raise ParseError('Reason for rejection is either empty or not acceptable.')
    leadership_request.reject(reason)


@shared_task(name='socialtrade.admin.delete_leader')
def task_delete_leader(leader_id: int, reason: int):
    """
    Admin task to delete a leader
    :param leader_id: the id of the leader to be deleted
    :param reason: the reason to deletion which should be one of the choices in the Leader model.
    :return: None
    """
    from exchange.socialtrade.models import Leader

    leader: Leader = Leader.objects.get(pk=leader_id)
    leader.delete_leader(reason)


@shared_task(name='socialtrade.core.notif.mass_sms')
def task_send_mass_sms(
    users_ids: List[int],
    sms_tps: Union[List[int], int],
    sms_texts: Union[List[str], str],
    sms_templates: Union[List[int], int, None] = None,
):
    """
    Sending mass sms texts to many users.
    :param users_ids: the list of ids of the users we wish to send sms text to.
    :param sms_tps: the types of sms texts to be sent. If we wish to send the same sms text to all the users,
     sms_tps can be a single integer from the type choices of UserSms model. If we intend to send different sms texts
     to the users, each user should have their own sms_tp.
    :param sms_texts: the texts of sms texts to be sent. If we wish to send the same sms text to all the users,
     sms_texts can be a single string. If we intend to send different sms texts
     to the users, each user should have their own sms_text.
    :param sms_templates: the templates of sms texts to be sent. If we wish to send the same sms text to all the users,
     sms_templates can be a single integer from the template choices of UserSms model. If we intend to send different
     sms texts to the users, each user should have their own sms_templates.
    :return: None
    """
    users = User.objects.filter(pk__in=users_ids)
    bulk_sms = [
        UserSms(
            user=user,
            tp=sms_tps[i] if isinstance(sms_tps, list) else sms_tps,
            to=user.mobile,
            template=sms_templates[i] if isinstance(sms_templates, list) else sms_templates,
            text=sms_texts[i] if isinstance(sms_texts, list) else sms_texts,
        )
        for i, user in enumerate(users)
        if user.has_verified_mobile_number
    ]
    with measure_time_cm(metric=f'custom_bulk_create_accounts.usersms'):
        UserSms.objects.bulk_create(bulk_sms)


@shared_task(name='socialtrade.core.notif.mass_notification')
def task_send_mass_notifications(
    users_ids: List[int],
    notification_messages: Union[List[str], str],
):
    """
    Sending mass notifications to many users.
    :param users_ids: the list of ids of the users we wish to send notifications to.
    :param notification_messages: the messages to be sent as notification. If we wish to send the same message to all
     the users, we should use a single string for this param. Otherwise, we should include one message per user in a
     list of strings.
    :return: None
    """
    users = User.objects.filter(pk__in=users_ids)
    bulk_notifications = [
        Notification(
            user=user,
            message=notification_messages[i] if isinstance(notification_messages, list) else notification_messages,
        )
        for i, user in enumerate(users)
    ]
    with measure_time_cm(metric='custom_bulk_create_accounts.notification'):
        Notification.objects.bulk_create(bulk_notifications, batch_size=100)


@shared_task(name='socialtrade.core.notif.mass_email')
def task_send_mass_emails(
    users_ids: List[int],
    email_templates: Union[List[str], str],
    email_data: Union[List[dict], dict, None] = None,
):
    """
    Sending mass emails to many users.
    :param users_ids: the list of ids of the users we wish to send emails to.
    :param email_templates: the templates of emails to be sent. If we wish to send the same email to all the users,
     email_templates can be a single string from the templates in exchange/base/templates/emails/.
     If we intend to send different emails to the users, each user should have their own email template.
    :param email_data: the data of emails to be sent. If we wish to send the same email to all the users,
     email_data can be a single string dictionary containing data fields to be put in the email.
     If we intend to send different emails to the users, each user should have their own email data.
    :return:
    """
    users = User.objects.filter(pk__in=users_ids)
    for i, user in enumerate(users):
        if not user.is_email_verified:
            continue

        task_send_email.delay(
            email=user.email,
            template=email_templates[i] if isinstance(email_templates, list) else email_templates,
            data=email_data[i] if isinstance(email_data, list) else email_data,
        )


@shared_task(name='socialtrade.core.notif.send_email')
def task_send_email(
    email: str,
    template: str,
    data: Union[dict, None] = None,
    priority='low',
):
    EmailManager.send_email(
        email=email,
        template=template,
        data=data,
        priority=priority,
    )


@shared_task(name='socialtrade.core.logic.renew_subscription', max_retries=2)
def task_renew_subscription(subscription_id: int):
    from exchange.socialtrade.models import SocialTradeSubscription
    from exchange.socialtrade.notifs import SocialTradeNotifs

    subscription = SocialTradeSubscription.objects.filter(pk=subscription_id).select_related('leader').first()
    if not subscription:
        return

    try:
        renewed_subscription = subscription.renew()
        if renewed_subscription.fee_amount == ZERO:
            return

        if subscription.is_trial:
            SocialTradeNotifs.successful_trial_renewal.send(
                renewed_subscription.subscriber,
                data=dict(
                    nickname=renewed_subscription.leader.nickname,
                    expires_at=renewed_subscription.shamsi_expire_date,
                    subscription_fee=format_amount(
                        renewed_subscription.fee_amount,
                        renewed_subscription.fee_currency,
                    ),
                ),
            )
        else:
            SocialTradeNotifs.successful_subscription_renewal.send(
                renewed_subscription.subscriber,
                data=dict(
                    nickname=renewed_subscription.leader.nickname,
                    expires_at=renewed_subscription.shamsi_expire_date,
                    subscription_fee=format_amount(
                        renewed_subscription.fee_amount,
                        renewed_subscription.fee_currency,
                    ),
                ),
            )

    except SubscriptionNotRenewable:
        report_exception()
    except ReachedSubscriptionLimit:
        pass
    except InsufficientBalance:
        if subscription.is_trial:
            SocialTradeNotifs.failed_trial_renewal.send(
                subscription.subscriber,
                data=dict(
                    nickname=subscription.leader.nickname,
                    subscription_fee=format_amount(
                        subscription.leader.subscription_fee,
                        subscription.leader.subscription_currency,
                    ),
                ),
            )
        else:
            SocialTradeNotifs.failed_subscription_renewal.send(
                subscription.subscriber,
                data=dict(
                    nickname=subscription.leader.nickname,
                    subscription_fee=format_amount(
                        subscription.leader.subscription_fee,
                        subscription.leader.subscription_currency,
                    ),
                ),
            )


@shared_task(name='socialtrade.admin.change_subscription_fee')
def change_subscription_fee(leader_id: int, new_fee: str):
    from exchange.socialtrade.models import Leader, SocialTradeSubscription
    from exchange.socialtrade.notifs import SocialTradeNotifs

    leader = Leader.objects.get(id=leader_id)
    new_fee: Decimal = parse_strict_decimal(
        new_fee,
        AMOUNT_PRECISIONS.get(get_currency_codename(leader.subscription_currency).upper() + 'IRT', 1),
        required=True,
    )
    validate_subscription_fee(leader.subscription_currency, new_fee)
    leader.subscription_fee = new_fee
    leader.save(update_fields=['subscription_fee'])

    subscribers = SocialTradeSubscription.get_actives().filter(leader=leader).values_list('subscriber__id', flat=True)
    SocialTradeNotifs.change_subscription_fee.send_many(
        user_ids=list(subscribers),
        data={
            'nickname': leader.nickname,
            'subscription_fee': format_amount(
                leader.subscription_fee,
                leader.subscription_currency,
            ),
        },
    )


@shared_task(name='socialtrade.core.notif.send_pre_renewal_alert')
def send_pre_renewal_alert(subscription_id: int):
    from exchange.socialtrade.models import SocialTradeSubscription
    from exchange.socialtrade.notifs import SocialTradeNotifs

    subscription = (
        SocialTradeSubscription.get_actives()
        .filter(
            pk=subscription_id,
        )
        .select_related('subscriber', 'leader')
    ).first()

    if not subscription:
        return

    if subscription.leader.subscription_fee == ZERO:
        return

    data = dict(
        nickname=subscription.leader.nickname,
        expires_at=subscription.shamsi_expire_date,
        fee=format_amount(subscription.leader.subscription_fee, subscription.leader.subscription_currency),
    )
    if subscription.is_trial:
        SocialTradeNotifs.pre_trial_renewal_alert.send(subscription.subscriber, data=data)
    elif subscription.is_auto_renewal_enabled:
        SocialTradeNotifs.pre_subscription_auto_renewal_alert.send(subscription.subscriber, data=data)
    else:
        SocialTradeNotifs.pre_subscription_non_auto_renewal_alert.send(subscription.subscriber, data=data)

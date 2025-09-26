import random
from collections import defaultdict
from typing import List, Literal, Optional, Union

from django.conf import settings
from post_office import mail

from exchange.base.calendar import to_shamsi_date
from exchange.base.formatting import f_m
from exchange.base.helpers import batcher, get_base_api_url
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Settings
from exchange.notification.email.email_utils import filter_no_send_emails
from exchange.security.functions import get_emergency_cancel_url


class EmailManager:
    # Email Templates Categories
    NORMAL_TEMPLATES = ['login_notif']
    IMPORTANT_TEMPLATES = [
        'withdraw_request_confirmation_code',
        'new_device_notif',
        'tfa_enable_notif',
    ]
    CRITICAL_TEMPLATES = [
        'welcome',
        'template',
        'otp',
        'reset_password',
        'tfa_otp',
        'tfa_removal',
        'giftcard',
        'change_password_notif',
        'change_mobile_notif',
        'change_email_notif',
    ]

    @classmethod
    def send_email(
        cls,
        email: Union[str, List[str]],
        template,
        data=None,
        backend=None,
        scheduled_time=None,
        priority: Literal['low', 'medium', 'high', 'now'] = 'high',
    ):
        email_kwargs = cls.create_email(
            email=email,
            template=template,
            data=data,
            backend=backend,
            scheduled_time=scheduled_time,
            priority=priority,
        )
        cls.send_mail_many(email_kwargs)

    @classmethod
    def create_email(
        cls,
        email: Union[str, List[str]],
        template,
        data=None,
        backend=None,
        scheduled_time=None,
        priority: Literal['low', 'medium', 'high', 'now'] = 'high',
    ) -> List[dict]:
        """
        This function prepares email kwargs suitable for `mail.send_many()`.
        It returns only a list of mail kwargs (dict).
        """
        if not email:
            return []

        if isinstance(email, str):
            email = [email]

        priority = priority or settings.EMAIL_DEFAULT_PRIORITY
        emails = filter_no_send_emails(email, template)
        if len(emails) == 0:
            return []

        backend = backend or cls.get_email_backend(template)
        if backend is None:
            return []

        emails_with_phishing_code = {}
        emails_without_phishing_code = []
        data_without_phishing_code = None

        for e in emails:
            _data = cls.prepare_email_data(data, e)
            if _data.get('anti_phishing_code'):
                emails_with_phishing_code[e] = _data
            else:
                if not data_without_phishing_code:
                    data_without_phishing_code = _data
                emails_without_phishing_code.append(e)

        shared_args = dict(
            sender=settings.EMAIL_FROM,
            template=template,
            priority=priority,
            backend=backend,
            scheduled_time=scheduled_time,
            headers={'Reply-To': 'Do not reply! <noreply@nobitex.ir>'},
        )

        emails_kwargs = []

        # Batch for emails without phishing code
        if len(emails_without_phishing_code) > 1:
            for chunk in batcher(emails_without_phishing_code, batch_size=100):
                emails_kwargs.append(
                    {
                        'recipients': settings.EMAIL_BATCH_TO,
                        'bcc': chunk,
                        'context': data_without_phishing_code,
                        **shared_args,
                    }
                )
        elif len(emails_without_phishing_code) == 1:
            emails_kwargs.append(
                {
                    'recipients': emails_without_phishing_code[0],
                    'context': data_without_phishing_code,
                    **shared_args,
                }
            )

        # One by one for emails with phishing code
        for e, _data in emails_with_phishing_code.items():
            emails_kwargs.append(
                {
                    'recipients': e,
                    'context': _data,
                    **shared_args,
                }
            )

        return emails_kwargs

    @classmethod
    def send_mail_many(cls, mail_kwargs: List[dict]):
        """Sends (and logs) the emails based on config. If email logging or
        broker is enabled, produce schemas to Kafka. If broker is not enabled,
        actually send the emails via `mail.send_many()`.

        Args:
            mail_kwargs: the exact kwargs as `mail.send_many`; also the
                result of `EmailManager.create_email()` can be used.

        Returns:
            None
        """

        if not mail_kwargs:
            return

        mail.send_many(mail_kwargs)
        grouped_metrics = defaultdict(int)
        for kw in mail_kwargs:
            backend = kw.get('backend')
            priority = kw.get('priority')
            template = kw.get('template')
            if backend and priority and template:
                grouped_metrics[(backend, priority, template)] += 1

        for (backend, priority, template), amount in grouped_metrics.items():
            metric_incr(
                f'metric_send_email_counter__{backend}_{priority}_{cls.to_pascal_case(template)}',
                amount=amount,
            )

    @staticmethod
    def get_email_backend(template):
        if settings.IS_TEST_RUNNER:
            return 'default'

        email_backends = Settings.get_cached_json(
            'email_backends',
            {
                'tfa_removal': 'postfix',
                'withdraw_request_confirmation_code': 'postfix',
                'transaction_history': 'postfix',
                'margin_call': 'postfix2',
                'otp': 'postfix2',
            },
        )
        email_backend = email_backends.get(template, 'random')
        if email_backend == 'random':
            default_backends = email_backends.get('default', ['postfix', 'postfix2'])
            if isinstance(default_backends, str):
                default_backends = [default_backends]

            email_backend = random.choice(default_backends)  # noqa: S311

        if isinstance(email_backend, list):
            email_backend = random.choice(email_backend)  # noqa: S311

        return email_backend

    @classmethod
    def prepare_email_data(cls, data: dict, email: str) -> dict:
        data = data or {}
        anti_phishing_code = cls._find_anti_phishing_code_by_email(email)
        if anti_phishing_code:
            data = {**data, 'anti_phishing_code': anti_phishing_code}
        data.setdefault('is_prod', settings.IS_PROD)
        data.setdefault('isTestnet', settings.IS_TESTNET)
        return data

    @classmethod
    def _find_anti_phishing_code_by_email(cls, email: str) -> Optional[str]:
        from exchange.accounts.models import AntiPhishing

        return AntiPhishing.get_anti_phishing_code_by_email(email)

    @classmethod
    def send_withdraw_request_confirmation_code(cls, withdraw_request):
        from exchange.accounts.models import Notification, UserSms

        user = withdraw_request.wallet.user
        base_url = get_base_api_url()
        verify_url = base_url + f'direct/confirm-withdraw/{withdraw_request.pk}/{withdraw_request.token.hex}'
        amount_str = f_m(withdraw_request.amount, c=withdraw_request.currency, show_c=True)
        target = withdraw_request.get_target_display()
        emergency_cancel_url = get_emergency_cancel_url(user)
        # Create a short summary of withdraw request
        short_message = f'کد تایید برداشت شما: {withdraw_request.otp}\nWithdraw {amount_str} to {target}'
        if emergency_cancel_url:
            short_message += '\n\nلغو اضطراری: ' + emergency_cancel_url

        # Send code as email
        if user.is_email_verified:
            from exchange.wallet.tasks import send_withdraw_email_otp

            send_withdraw_email_otp.apply_async(
                (
                    user.email,
                    withdraw_request.id,
                    amount_str,
                    target,
                    withdraw_request.tag,
                    verify_url,
                    emergency_cancel_url,
                    withdraw_request.otp,
                    short_message,
                ),
                countdown=(
                    int(Settings.get_value('withdraw_otp_email_task_countdown', default=30))
                    if user.has_verified_mobile_number
                    else 0
                ),  # Send immediately if mobile is not verified
                expires=10 * 60,
            )

        # Send code as telegram message
        telegram_message = 'درخواست برداشت جدیدی در حساب نوبیتکس شما ثبت شد.\n\n*مبلغ:* {}\n*مقصد:* {}'
        if emergency_cancel_url:
            telegram_message += '\n\n*لغو اضطراری:* ' + emergency_cancel_url
        Notification(
            user=user,
            message=telegram_message.format(
                amount_str,
                target,
            ),
        ).send_to_telegram_conversation(title='📤 درخواست برداشت جدید', save=False)

        # Send code as SMS
        if user.has_verified_mobile_number:
            try:
                UserSms.objects.create(
                    user=user,
                    tp=UserSms.TYPES.verify_withdraw,
                    to=user.mobile,
                    text=withdraw_request.otp,
                    template=UserSms.TEMPLATES.withdraw,
                )
            except:
                report_exception()

    @classmethod
    def send_withdraw_request_status_update(cls, withdraw_request):
        if not withdraw_request.wallet.user.is_email_verified:
            return
        if not Settings.get_flag('email_send_withdraw_request_status_update'):
            return

        track_code = track_link = None

        if withdraw_request.is_rial and withdraw_request.blockchain_url:
            track_code = withdraw_request.blockchain_url.replace('nobitex://app/wallet/rls/transaction/', '')
        else:
            track_link = withdraw_request.blockchain_url

        cls.send_email(
            withdraw_request.wallet.user.email,
            'withdraw_done',
            data={
                'title': 'برداشت ثبت شد' if withdraw_request.is_rial else 'برداشت انجام شد',
                'destination': withdraw_request.get_target_display(),
                'trackLink': track_link,
                'trackCode': track_code,
                'amount': withdraw_request.amount,
                'currency': withdraw_request.wallet.get_currency_display(),
                'amountDisplay': f_m(withdraw_request.amount, c=withdraw_request.currency, show_c=True),
                'tag': withdraw_request.tag,
                'coinTypeDisplay': 'وجه' if withdraw_request.wallet.is_rial else 'رمزارز',
                'is_withdrawal_rial': withdraw_request.is_rial,
            },
            priority='medium',
        )

    @classmethod
    def send_change_password_notif(cls, user, ip, device_id):
        from exchange.base.calendar import ir_now

        known_device = user.login_attempts.filter(ip=ip, device__device_id=device_id).order_by('-created_at').first()
        device = known_device.get_device_name() if known_device else 'unknown'
        cls.send_email(
            user.email,
            'change_password_notif',
            data={
                'ip': ip,
                'date': to_shamsi_date(ir_now()),
                'device': device,
                'emergency_cancel_url': get_emergency_cancel_url(user),
            },
            priority='high',
        )

    @classmethod
    def send_enable_tfa_notif(cls, user):
        cls.send_email(
            user.email,
            'tfa_enable_notif',
            data={'emergency_cancel_url': get_emergency_cancel_url(user)},
            priority='high',
        )

    @classmethod
    def to_pascal_case(cls, template_name: str) -> str:
        # If there are any '/' in the template's name, replace it with '_' and then turn from snake_case to PascalCase
        slash_free_template = template_name.replace('/', '_')
        return ''.join(x.capitalize() for x in slash_free_template.lower().split('_'))

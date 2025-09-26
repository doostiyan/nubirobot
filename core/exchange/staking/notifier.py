from decimal import Decimal
from enum import Enum
from typing import Optional, TypedDict

from exchange.accounts.models import Notification, User
from exchange.base.decorators import measure_time_cm
from exchange.base.emailmanager import EmailManager
from exchange.base.formatting import f_m
from exchange.base.models import Settings, get_currency_codename
from exchange.base.money import format_small_money
from exchange.base.strings import _t
from exchange.staking.metrics import Metrics


class StakingNotifTopic(Enum):
    CREATE_REQUEST = 'create_request'
    STAKED = 'staked'
    END_REQUEST = 'end_request'
    REWARD_DEPOSIT_AND_EXTEND = 'reward_deposit_and_extend'
    REWARD_DEPOSIT_NO_EXTEND = 'reward_deposit_no_extend'
    RELEASE = 'release'
    PLAN_CAPACITY_INCREASE = 'plan_capacity_increase'
    INSTANT_END_REQUEST = 'instant_end_request'


class ContextInfo(TypedDict):
    currency: Optional[int]
    amount: Optional[Decimal]
    platform: str  # 'fa' description
    platform_code: str
    release_day: Optional[str] # either 'امروز' or 'فردا'


class Notifier:

    @classmethod
    @measure_time_cm(metric=str(Metrics.NOTIFICATION_SEND_USER_NOTIFICATION_TIME))
    def notify(cls, topic: StakingNotifTopic, user_id: int, context: ContextInfo):
        format_func = format_small_money if topic in (
            StakingNotifTopic.REWARD_DEPOSIT_AND_EXTEND,
            StakingNotifTopic.REWARD_DEPOSIT_NO_EXTEND,
        ) else f_m
        if context.get('currency'):
            currency = context['currency']
            context['currency'] = _t(get_currency_codename(context['currency']))
        if context.get('currency') and context.get('amount'):
            context['amount'] = format_func(context['amount'], c=currency, exact=True,)

        if 'realized_apr' in context and (
            topic == StakingNotifTopic.REWARD_DEPOSIT_AND_EXTEND or topic == StakingNotifTopic.REWARD_DEPOSIT_NO_EXTEND):
            context['realized_apr'] = round(context['realized_apr'], 2)

        Notification.objects.create(
            user_id=user_id,
            message=cls._get_notification_template(topic).format(**context),
        )
        if Settings.get_flag('send_staking_email_notification'):
            EmailManager.send_email(
                email=User.objects.get(pk=user_id).email,
                template=context['platform_code'] + '/' + topic.value,
                data=context,
                priority='low',
            )

    @classmethod
    def _get_notification_template(cls, topic: StakingNotifTopic,) -> str:

        if topic == StakingNotifTopic.CREATE_REQUEST:
            return 'درخواست {platform} شما به میزان {amount} {currency} با موفقیت ثبت شد و در انتظار شروع طرح قرار گرفت.'

        if topic == StakingNotifTopic.STAKED:
            return '{platform} شما به میزان {amount} {currency} شروع شد. ' \
                + 'جهت پیگیری وضعیت به صفحه‌ی طرح‌های من در پنل {platform} مراجعه کنید.'

        if topic == StakingNotifTopic.REWARD_DEPOSIT_AND_EXTEND:
            return 'مدت زمان {platform} شما به پایان رسید' \
                + ' و پاداش طرح با درصد بازده سالانه (APR) برابر {realized_apr} درصد به میزان {amount} {currency} ' \
                + 'به کیف پول شما واریز شد. ' \
                + 'با توجه به فعال بودن تمدید خودکار {platform} شما این طرح ' \
                + 'برای یک دوره‌ی دیگر فعال شد. جهت پیگیری وضعیت به پنل {platform} خود مراجعه نمایید.'

        if topic == StakingNotifTopic.REWARD_DEPOSIT_NO_EXTEND:
            return 'مدت زمان {platform} شما به پایان رسید' \
                + ' و پاداش طرح با درصد بازده سالانه (APR) برابر {realized_apr} درصد به میزان {amount} {currency} ' \
                + 'به کیف پول شما واریز شد. '\
                + 'جهت پیگیری وضعیت به پنل {platform} خود مراجعه کنید.'

        if topic == StakingNotifTopic.END_REQUEST:
            return 'درخواست لغو {platform} شما با موفقیت ثبت شد. پس از اتمام دوره‌ی طرح فعلی، ' \
                + '{platform} وارد فرآیند لغو خواهد شد.'

        if topic == StakingNotifTopic.RELEASE:
            return 'دوره‌ی لغو {platform} شما پایان یافت و میزان {amount} {currency} به کیف پول معاملات شما منتقل شد.'

        if topic == StakingNotifTopic.PLAN_CAPACITY_INCREASE:
            return 'ظرفیت {platform} انتخابی شما روی رمز ارز {currency} افزایش ' \
                + 'یافت. جهت ثبت {platform} به پنل {platform} نوبیتکس مراجعه کنید.'

        if topic == StakingNotifTopic.INSTANT_END_REQUEST:
            return 'درخواست لغو {platform} با موفقیت ثبت شد. ' \
                + 'دارایی از ساعت ۱۵ {release_day} در جریان آزادسازی قرار خواهد گرفت ' \
                + 'و پس از اتمام دوره آزادسازی به کیف پول شما واریز خواهد شد. ' \
                + 'شما می‌توانید از بخش طرح‌های من، سربرگ در انتظار، از آخرین وضعیت و زمان آزادسازی دارایی خود آگاهی کسب کنید.'

        raise ValueError

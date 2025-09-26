from dataclasses import dataclass
from typing import List, Optional, Union

from exchange.accounts.models import User, UserSms
from exchange.socialtrade.notify import notify_mass_users, notify_user


@dataclass
class SocialTradeNotif:
    message_template: Optional[str] = None
    email_template: Optional[str] = None
    email_title: Optional[str] = None
    sms_tp: Optional[int] = None
    sms_template: Optional[int] = None

    def __post_init__(self):
        if not self.message_template and not self.email_template and not self.sms_template:
            raise ValueError('At least one of message_template or email_template or sms_template should be passed')

    def get_message(self, data: Union[dict, None]) -> Optional[str]:
        if not data:
            return self.message_template
        return self.message_template.format(**data) if self.message_template else None

    def send(self, user: User, data: Union[dict, None] = None):
        if not data:
            data = {}

        if self.sms_tp and not data.get('sms_text'):
            raise ValueError('sms_text should be passed with the sms_tp')

        data.update(email_title=self.email_title)
        notify_user(
            user=user,
            email_template=self.email_template,
            notification_message=self.get_message(data),
            email_data=data,
            sms_tp=self.sms_tp,
            sms_template=self.sms_template,
            sms_text=data.get('sms_text'),
        )

    def send_many(self, user_ids: List[int], data: Union[dict, None] = None):
        if not data:
            data = {}

        if self.sms_tp and not data.get('sms_text'):
            raise ValueError('sms_text should be passed with the sms_tp')

        data.update(email_title=self.email_title)
        notify_mass_users(
            users_ids=user_ids,
            email_templates=self.email_template,
            notification_messages=self.get_message(data),
            email_data=data,
            sms_tps=self.sms_tp,
            sms_templates=self.sms_template,
            sms_texts=data.get('sms_text'),
        )


class SocialTradeNotifs:
    successful_trial_renewal = SocialTradeNotif(
        email_template='socialtrade/successful_trial_renewal',
        email_title='اطلاع رسانی سوشال ترید: شروع اشتراک سوشال ترید',
        message_template=(
            'کاربر گرامی، اشتراک سوشال ترید شما به مدت یک ماه فعال شده '
            'و هزینه اشتراک از کیف پول شما کسر شده است.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {subscription_fee}\n'
            'تاریخ پایان اشتراک: {expires_at}'
        ),
    )

    successful_subscription_renewal = SocialTradeNotif(
        email_template='socialtrade/successful_subscription_renewal',
        email_title='اطلاع رسانی سوشال ترید: تمدید اشتراک سوشال ترید',
        message_template=(
            'کاربر گرامی، اشتراک سوشال ترید شما به مدت یک ماه تمدید شده '
            'و هزینه اشتراک از کیف پول شما کسر شده است.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {subscription_fee}\n'
            'تاریخ پایان اشتراک: {expires_at}'
        ),
    )

    failed_trial_renewal = SocialTradeNotif(
        email_template='socialtrade/failed_trial_renewal',
        email_title='اطلاع رسانی سوشال ترید: عدم امکان فعالسازی اشتراک',
        message_template=(
            'کاربر گرامی، موجودی شما برای فعالسازی اشتراک سوشال ترید، کافی نمی‌باشد. '
            'برای افزایش موجودی و فعال‌سازی اشتراک به پنل کاربری مراجعه نمایید.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {subscription_fee}'
        ),
    )

    failed_subscription_renewal = SocialTradeNotif(
        email_template='socialtrade/failed_subscription_renewal',
        email_title='اطلاع رسانی سوشال ترید: عدم امکان تمدید اشتراک',
        message_template=(
            'کاربر گرامی، موجودی شما برای تمدید اشتراک سوشال ترید، کافی نمی‌باشد. '
            'لطفا با مراجعه به پنل کاربری موجودی کیف پول خود را افزایش داده و سپس اقدام به فعالسازی اشتراک نمایید.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {subscription_fee}'
        ),
    )

    change_subscription_fee = SocialTradeNotif(
        email_template='socialtrade/change_fee_notify_subscribers',
        email_title='اطلاع رسانی سوشال ترید: تغییر هزینه اشتراک',
        message_template=(
            'سوشال ترید: تغییر هزینه اشتراک \n '
            'کاربر گرامی، هزینه اشتراک سوشال ترید برای تریدر انتخابی شما در دوره بعدی با تغییر قیمت مواجه شده است. در صورت تمایل برای تغییر در اشتراک دوره بعدی به پنل کاربری مراجعه نمایید.\n '
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {subscription_fee}'
        ),
    )

    pre_trial_renewal_alert = SocialTradeNotif(
        email_template='socialtrade/pre_trial_renewal_alert',
        email_title='اطلاع رسانی سوشال ترید: پایان اشتراک آزمایشی',
        message_template=(
            'اشتراک آزمایشی شما در حال اتمام است. '
            'درصورت داشتن موجودی، اشتراک شما به صورت خودکار فعال خواهد شد.\n'
            'تریدر: {nickname}\n'
            'زمان پایان اشتراک آزمایشی : {expires_at}\n'
            'هزینه اشتراک: {fee}'
        ),
    )

    pre_subscription_auto_renewal_alert = SocialTradeNotif(
        email_template='socialtrade/pre_subscription_auto_renewal_alert',
        email_title='اطلاع رسانی سوشال ترید: پایان اشتراک',
        message_template=(
            'اشتراک تریدر انتخابی شما در تاریخ {expires_at} به پایان میرسد '
            'و به صورت خودکار برای دوره بعد تمدید خواهد شد. '
            'درصورت تمایل به تغییر در عملیات تمدید به پنل کاربری خود مراجعه نمایید.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {fee}'
        ),
    )

    pre_subscription_non_auto_renewal_alert = SocialTradeNotif(
        email_template='socialtrade/pre_subscription_non_auto_renewal_alert',
        email_title='اطلاع رسانی سوشال ترید: پایان اشتراک',
        message_template=(
            'اشتراک تریدر انتخابی شما در تاریخ {expires_at} به پایان میرسد، '
            'درصورت تمایل برای تمدید اشتراک به پنل کاربری خود مراجعه نمایید.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {fee}'
        ),
    )

    upcoming_renewal = SocialTradeNotif(
        email_template='socialtrade/upcoming_renewal',
        email_title='اطلاع رسانی سوشال ترید: تمدید اشتراک',
        message_template=(
            'کاربر گرامی، اشتراک سوشال ترید شما در تاریخ {expires_at} تمدید خواهد شد.\n'
            'تریدر: {nickname}\n'
            'هزینه اشتراک: {subscription_fee}'
        ),
    )

    leadership_acceptance = SocialTradeNotif(
        email_template='socialtrade/leadership_acceptance',
        email_title='اطلاع رسانی سوشال ترید: قبول درخواست عضویت به عنوان تریدر',
        message_template=(
            'کاربر عزیز، درخواست شما برای تریدر راهبر بودن تایید شد و از تاریخ {subscription_acceptance_date} '
            'می‌توانید دنبال‌کننده داشته باشید.'
        ),
        sms_tp=UserSms.TYPES.social_trade_leadership_acceptance,
        sms_template=UserSms.TEMPLATES.social_trade_leadership_acceptance,
    )

    leadership_rejection = SocialTradeNotif(
        email_template='socialtrade/leadership_rejection',
        email_title='اطلاع رسانی سوشال ترید: رد درخواست عضویت به عنوان تریدر',
        message_template='کاربر گرامی، درخواست شما برای انتخاب به عنوان تریدر مرجع رد شد. دلیل رد {rejection_reason}',
        sms_tp=UserSms.TYPES.social_trade_leadership_rejection,
        sms_template=UserSms.TEMPLATES.social_trade_leadership_rejection,
    )

    leader_deletion_leader = SocialTradeNotif(
        email_template='socialtrade/leader_deletion_leader',
        email_title='اطلاع رسانی سوشال ترید: عدم امکان فعالیت به عنوان تریدر',
        message_template=(
            'کاربر گرامی،‌ از این تاریخ شما امکان دریافت اشتراک جدید را نداشته و '
            'پس از پایان دوره اشتراک کاربران، امکان فعالیت به عنوان تریدر سوشال ترید'
            ' را نخواهید داشت. دلیل: {reason}'
        ),
        sms_tp=UserSms.TYPES.social_trade_notify_leader_of_deletion,
        sms_template=UserSms.TEMPLATES.social_trade_notify_leader_of_deletion,
    )

    leader_deletion_subscribers = SocialTradeNotif(
        email_template='socialtrade/leader_deletion_subscribers',
        email_title='اطلاع رسانی سوشال ترید: عدم فعالیت تریدر انتخابی',
        message_template=(
            'کاربر گرامی، تریدر انتخابی شما تا پایان دوره فعلی اشتراک فعالیت خواهد داشت'
            ' و پس از آن امکان تمدید اشتراک وجود نخواهد داشت.\n'
            'تریدر: {nickname}'
        ),
        sms_tp=UserSms.TYPES.social_trade_notify_subscribers_of_leader_deletion,
        sms_template=UserSms.TEMPLATES.social_trade_notify_subscribers_of_leader_deletion,
    )

    leader_deletion_trials = SocialTradeNotif(
        email_template='socialtrade/leader_deletion_trials',
        email_title='اطلاع رسانی سوشال ترید: عدم فعالیت تریدر انتخابی',
        message_template=(
            'کاربر گرامی، به دلیل عدم فعالیت تریدر انتخابی شما، امکان فعال‌سازی اشتراک سوشال ترید'
            ' برای تریدر انتخابی وجود نداشته و دوره آزمایشی اشتراک شما به پایان رسیده است.\n'
            'تریدر: {nickname}'
        ),
        sms_tp=UserSms.TYPES.social_trade_notify_trials_of_leader_deletion,
        sms_template=UserSms.TEMPLATES.social_trade_notify_trials_of_leader_deletion,
    )

    order_limit_market_notif = SocialTradeNotif(
        message_template=(
            'تریدر انتخابی شما {nickname} سفارش جدیدی برای {open_close} موقعیت {side} '
            'تعهدی در بازار {market} ثبت کرده است.'
            '\nزمان ثبت سفارش: {timestamp}'
        ),
    )

    position_opened_notif = SocialTradeNotif(
        message_template=(
            'موقعیت {sell_buy} تعهدی تریدر انتخابی شما {nickname} در بازار {market} باز شد.'
            '\nزمان باز شدن موقعیت: {timestamp}'
        ),
    )

    position_closed_notif = SocialTradeNotif(
        message_template=(
            'موقعیت {sell_buy} تعهدی تریدر انتخابی شما {nickname} در بازار {market} بسته شد.'
            '\nزمان بسته شدن موقعیت: {timestamp}'
        ),
    )

    position_liquidated_notif = SocialTradeNotif(
        message_template=(
            'هشدار! یک موقعیت {sell_buy} تعهدی تریدر انتخابی شما {nickname} در بازار {market} لیکویید شده است.'
            '\nزمان لیکویید شدن موقعیت: {timestamp}'
        ),
    )

    xchange_notif = SocialTradeNotif(
        message_template=(
            'تریدر انتخابی شما سفارش ثبت کرده است:\n'
            'تریدر: {nickname}\n'
            'نوع بازار: صرافی\n'
            'بازار: {market}\n'
            '{sell_buy} به قیمت: {price}'
        ),
    )

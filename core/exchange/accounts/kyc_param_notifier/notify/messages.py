from typing import Any, Dict

from django.conf import settings

from exchange.accounts.kyc_param_notifier.enums import KYCParamForNotify
from exchange.accounts.kyc_param_notifier.notify import Notifier
from exchange.accounts.models import User


class MessageBuilder(Notifier.MessageBuilderInterface):
    """
    A base class that forms a hierarchy for building the messages needed in the "email" and "notification".

    This class realizes the ``KYCParamNotifier.MessageBuilderInterface`` and thus
    serves the objects of ``KYCParamNotifier``.
    """

    def __new__(cls, kyc_param: KYCParamForNotify, kyc_obj: Any, *args, **kwargs):
        if (kyc_param == KYCParamForNotify.BANK_CARD) or (
            kyc_param == KYCParamForNotify.BANK_ACCOUNT and hasattr(kyc_obj, '_from_bank_card')
        ):
            return super().__new__(BankCardRelatedMessageBuilder)
        if kyc_param == KYCParamForNotify.BANK_ACCOUNT and not hasattr(kyc_obj, '_from_bank_card'):
            return super().__new__(BankAccountMessageBuilder)
        return super().__new__(GeneralMessageBuilder)

    def __init__(
        self, kyc_param: KYCParamForNotify, kyc_obj: Any, /,
        user: User, confirmed: bool,
    ):
        self.kyc_param = kyc_param
        self.kyc_obj = kyc_obj
        self.user = user
        self.confirmed = confirmed

    def get_confirmed_message(self):
        raise NotImplementedError

    def get_rejected_message(self):
        raise NotImplementedError

    def get_message(self) -> str:
        """
        Generate the message based on the fact that the kyc parameter is confirmed or rejected.
        """
        return self.get_confirmed_message() if self.confirmed else self.get_rejected_message()


class GeneralMessageBuilder(MessageBuilder):
    @property
    def user_full_name(self) -> str:
        if self.user.get_full_name():
            return '{} عزیز'.format(self.user.get_full_name())
        return 'کاربر گرامی'

    def get_confirmed_message(self):
        return '\n'.join(
            [
                self.user_full_name,
                '',
                '{} شما با موفقیت تایید شد.'.format(self.kyc_param.value),
                'شما می‌توانید برای افزایش امکانات و دسترسی‌های حساب خود '
                'به احراز هویت و ارتقای سطح کاربری خود بپردازید.',
            ]
        )

    def get_target_user_type_verbose(self):
        types = [
            User.USER_TYPES.level0,
            User.USER_TYPES.level1,
            User.USER_TYPES.level2,
        ]
        target_type = None
        for i, tp in enumerate(types[:-1]):
            if self.user.user_type == tp:
                target_type = types[i + 1]
        return settings.NOBITEX_OPTIONS['userTypes'].get(target_type, None)

    def get_rejected_message(self):
        verbose_target_user_type = self.get_target_user_type_verbose()
        lines = [
            self.user_full_name,
        ]
        if verbose_target_user_type:
            lines.append(
                'در بررسی {} شما برای ارتقا به سطح کاربری {} خطایی پیش آمده است.'.format(
                    self.kyc_param.value,
                    verbose_target_user_type
                )
            )
        else:
            lines.append(
                'در بررسی {} شما خطایی پیش آمده است.'.format(
                    self.kyc_param.value,
                )
            )
        lines.append(
            'برای مشاهده دلیل خطا و تلاش دوباره به صفحه سطوح کاربری در پنل خود مراجعه کنید.'
        )
        return '\n'.join(lines)


class BankCardRelatedMessageBuilder(MessageBuilder):

    @property
    def bank_card(self):
        return self.kyc_obj if self.kyc_param == KYCParamForNotify.BANK_CARD else self.kyc_obj._from_bank_card

    @property
    def confirmation_template(self):
        return {
            KYCParamForNotify.BANK_CARD: (
                'شماره کارت {card_number} با موفقیت تایید شد، '
                'از اینک می‌توانید برای واریز در درگاه، از این شماره کارت استفاده کنید.'
            ),
            KYCParamForNotify.BANK_ACCOUNT: (
                'شماره شبای مربوط به کارت {card_number} با موفقیت تایید شد، '
                'از اینک می‌توانید به این حساب برداشت وجه انجام دهید.'
            )
        }[self.kyc_param].format

    @property
    def rejection_template(self):
        parts = []
        if self.kyc_param == KYCParamForNotify.BANK_CARD:
            parts.append('شماره کارت {card_number} رد شد، ')
        else:
            parts.append('شماره شبای مربوط به کارت {card_number} رد شد، ')
        parts.extend([
            'لطفا از فعال بودن حساب، تطابق کارت ثبت شده با نام خود و تاریخ انقضای کارت خود اطمینان حاصل کنید.',
            'دلیل رد طبق بررسی سرویس دهنده: {rejection_reason}',
            '',
        ])
        if self.kyc_param == KYCParamForNotify.BANK_CARD:
            parts.append(
                'در صورت عدم حل مشکل می‌توانید از طریق تیکتینگ با بخش احراز هویت پشتیبانی در ارتباط باشید.'
            )
        else:
            parts.append(
                'همچنین شما می‌توانید از طریق صفحه اطلاعات بانکی در پروفایل من '
                'به طور مستقیم شماره شبا مدنظر خود را وارد کنید.'
            )
        return '\n'.join(parts).format

    def get_confirmed_message(self):
        return self.confirmation_template(card_number=self.bank_card.card_number)

    def get_rejected_message(self):
        api_verbose_message = getattr(self.kyc_obj, 'api_verification_verbose_message', None) or 'نامعین'
        return self.rejection_template(
            card_number=self.bank_card.card_number, rejection_reason=api_verbose_message
        )


class BankAccountMessageBuilder(MessageBuilder):
    def get_confirmed_message(self):
        return 'شماره شبای شما با موفقیت تایید شد، از اینک می‌توانید به این حساب برداشت وجه انجام دهید.'

    def get_rejected_message(self):
        return '\n'.join(
            [
                'شماره شبای شما رد شد، '
                'لطفا از فعال بودن حساب و تطابق اطلاعات حساب وارد شده با نام خود اطمینان حاصل کنید.',
                'در صورت عدم حل مساله می‌توانید از طریق تیکتینگ با بخش احراز هویت پشتیبانی در ارتباط باشید.'
            ]
        )


class SMSMessageBuilder(Notifier.MessageBuilderInterface):
    """
    Builds the messages needed for a sms notifying.

    This class realizes the ``KYCParamNotifier.MessageBuilderInterface`` and thus
    serves the objects of ``KYCParamNotifier``.
    """

    CONFIRMATION_MESSAGES: Dict[KYCParamForNotify, str] = {
        KYCParamForNotify.SELFIE: 'مدرک احرازهویت سطح دو شما تایید شد، جزییات بیشتر در پنل کاربری',
        KYCParamForNotify.AUTO_KYC: 'مدرک احرازهویت سطح دو شما تایید شد، جزییات بیشتر در پنل کاربری',
    }
    REJECTION_MESSAGES: Dict[KYCParamForNotify, str] = {
        KYCParamForNotify.IDENTITY: 'کاربر نوبیتکس، احراز هویت شما ناموفق بود. جزییات بیشتر در پنل کاربری',
        KYCParamForNotify.SELFIE: 'احراز هویت سطح دو نوبیتکس شما ناموفق بود. جزییات بیشتر در پنل کاربری',
        KYCParamForNotify.AUTO_KYC: 'احراز هویت سطح دو نوبیتکس شما ناموفق بود. جزییات بیشتر در پنل کاربری',
    }

    def __init__(self, kyc_param: KYCParamForNotify, user, confirmed: bool):
        self.kyc_param = kyc_param
        self.user = user
        self.confirmed = confirmed

    def get_message(self) -> str:
        message_dict = self.CONFIRMATION_MESSAGES if self.confirmed else self.REJECTION_MESSAGES
        return message_dict[self.kyc_param]

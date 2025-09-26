from enum import Enum


class KYCParamForNotify(Enum):
    """
    Enum for different kyc parameters.

    Different parameters of a user that are related to KYC and this module tend to
    notify its status to the user.
    """
    EMAIL = 'ایمیل'
    MOBILE = 'موبایل'
    IDENTITY = 'اطلاعات هویتی'
    MOBILE_IDENTITY = ' شماره همراه به نام'
    BANK_ACCOUNT = 'شماره شبا'
    BANK_CARD = 'شماره کارت'
    ADDRESS = 'آدرس'
    SELFIE = 'تصویر احراز هویت'
    AUTO_KYC = 'احراز هویت هوشمند'


class KYCParamNotifyType(Enum):
    """
    Enum for types of kyc notifying.

    ``EMAIL`` results in using ``EmailManager``, ``NOTIFICATION`` results in
    creation of ``Notification``, and ``SMS`` results in creation of ``UserSms``.
    """
    EMAIL = 'email'
    NOTIFICATION = 'notification'
    SMS = 'sms'

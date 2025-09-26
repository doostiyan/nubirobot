import functools
from typing import ClassVar, Iterable, List, Optional

from exchange.base.decorators import measure_success_time_cm
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Settings
from exchange.base.normalizers import compare_full_names
from exchange.integrations.base import VerificationClientBase
from exchange.integrations.exceptions import (
    CardToIbanError,
    DeadLivingStatus,
    InactiveCard,
    InactiveIBAN,
    InvalidBirthDate,
    InvalidCard,
    InvalidIBAN,
    InvalidMobile,
    InvalidNationalCode,
    MismatchedCard,
    MismatchedIBAN,
    NotFound,
    UnknownCardQueryError,
    UnknownLivingStatus,
    VerificationAPIError,
    VerificationError,
)
from exchange.integrations.finnotech import FinnotechVerificationClient
from exchange.integrations.jibit import JibitVerificationClient
from exchange.integrations.types import (
    BankCardOwnerVerificationResult,
    CardToIbanResult,
    IBANOwnerVerificationResult,
    IdentityVerificationResult,
    MobileOwnerVerificationResult,
    VerificationAPIProviders,
)


def _send_notif(channel, title, message):
    from exchange.accounts.models import Notification  # To avoid circular import
    Notification.notify_admins(
        channel=channel,
        title=title,
        message=message,
    )


class VerificationProviders:
    PROVIDERS: ClassVar = {
        VerificationAPIProviders.FINNOTECH.value: FinnotechVerificationClient,
        VerificationAPIProviders.JIBIT.value: JibitVerificationClient,
    }

    @classmethod
    def get_active_providers(cls) -> List[VerificationClientBase]:
        keys = Settings.get_value('verification_providers', VerificationAPIProviders.FINNOTECH.value).split(',')
        return [provider for provider in [cls.get_provider_by_key(key) for key in keys] if provider is not None]

    @classmethod
    def is_primary_provider(cls, provider: VerificationClientBase) -> bool:
        return provider is cls.get_active_providers()[0]

    @classmethod
    @functools.lru_cache(maxsize=8)
    def get_provider_by_key(cls, key: str):
        provider_class = cls.PROVIDERS.get(key.strip().lower())
        if not provider_class:
            return None

        return provider_class()


def multi_provider_inquiry(service_metric_key: str, *, reraise_verification_error=False, send_notif=False):
    """
    Decorator to manage inquiries across multiple service providers and log metrics.

    This decorator is designed to wrap a function that performs a service inquiry
    using various service providers. It handles success and failure cases for each
    provider, logs relevant metrics, and sends notifications in case of errors.

    Args:
        service_metric_key (str): The key used to identify the service for metric logging.
        reraise_verification_error (bool): This flag used to determine should the verification_error reraise.
        send_notif (bool): This flag used to determine should the notification be sent.
    Returns:
        function: A wrapped function that performs the inquiry with additional
                  functionality for handling multiple providers.

    The wrapped function should accept `provider` as a keyword argument to specify
    the service provider being used.

    Functionality:
    - Iterates through all active service providers retrieved via `get_active_providers()`.
    - Tries to execute the wrapped function for each provider.
    - Logs success or specific error codes using `metric_incr`.
    - Sends notifications to a specified channel in case of exceptions.
    - Reports unknown exceptions.
    - If all providers fail, logs a special metric and raises a `VerificationAPIError`.

    Example usage:

    @multi_provider_inquiry("UserIdentity")
    def check_user_identity(user, provider=None):
        # Function implementation using the specified provider
    """

    def _metric_incr(provider, status):
        priority = 'primary' if VerificationProviders.is_primary_provider(provider) else 'secondary'
        metric_incr(f'metric_verification__{service_metric_key}_{provider.name}_{status}_{priority}')

    def _metric_incr_all_providers_failed():
        active_providers_types = [type(p) for p in VerificationProviders.get_active_providers()]
        is_jibit_active = JibitVerificationClient in active_providers_types
        is_finnotech_active = FinnotechVerificationClient in active_providers_types
        metric_incr(f'metric_verification_no_provider__{service_metric_key}_{is_jibit_active}_{is_finnotech_active}')

    @functools.wraps(multi_provider_inquiry)
    def outer_wrapper(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            verification_client: VerificationClient = args[0]  # self

            exceptions_messages = {}
            for provider in verification_client.providers or VerificationProviders.get_active_providers():
                try:
                    with measure_success_time_cm(
                        f'verification_success_request_v2__{provider.name}_{service_metric_key}',
                    ):
                        result = f(*args, provider=provider, **kwargs)
                    is_success = result.get('result') or result.get('err_code') == ''
                    _metric_incr(
                        provider,
                        'Success' if is_success else result.get('err_code'),
                    )
                except VerificationError as exception:
                    _metric_incr(provider, exception.__class__.__name__)
                    if reraise_verification_error:
                        raise
                except Exception as exception:
                    if isinstance(exception, VerificationAPIError):
                        metric_status = f'{exception.code}{exception.status}' if exception.status else exception.code
                        exceptions_messages[provider.name] = f'{exception.__class__.__name__}: {metric_status}'
                    else:
                        # Unknown error
                        metric_status = exception.__class__.__name__
                        args_str = (str(arg) for arg in exception.args)
                        exceptions_messages[provider.name] = f'{exception.__class__.__name__}: {"-".join(args_str)}'
                        report_exception()
                        if send_notif:
                            _send_notif(
                                channel='identity_inquiries',
                                title=f'🔵 اختلال در سرویس {service_metric_key} {provider.name}',
                                message=f'{exception}__' + '-'.join(args_str),
                            )

                    _metric_incr(provider, metric_status)

                else:
                    return result

            # If all providers raised exceptions
            if send_notif:
                _send_notif(
                    channel='identity_inquiries',
                    title='🔵 هیج کدام از پروایدر ها پاسخگوی سرویس بررسی هویت کاربر نبودند.',
                    message=exceptions_messages,
                )
            _metric_incr_all_providers_failed()
            raise VerificationAPIError(f'All clients failed for the service {service_metric_key}')

        return wrapper

    return outer_wrapper


class VerificationClient:
    def __init__(self, providers: Optional[Iterable[VerificationClientBase]] = None) -> None:
        self.providers = providers

    @multi_provider_inquiry('UserIdentity')
    def check_user_identity(self, user, *, provider: VerificationClientBase) -> IdentityVerificationResult:
        try:
            result = provider.get_user_identity(user)
        except UnknownLivingStatus as ex:
            return IdentityVerificationResult(
                result=False,
                confidence=10,
                apiresponse=ex.api_response,
                message='وضعیت حیات کاربر مشخص نیست',
                err_code='UnknownLivingStatus',
            )
        except DeadLivingStatus as ex:
            return IdentityVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='کاربر زنده نیست.',
                err_code='DeadLivingStatus',
            )
        except InvalidBirthDate as ex:
            return IdentityVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='تاریخ تولد کاربر نامعتبر است',
                err_code='InvalidBirthDate',
            )
        except (InvalidNationalCode, NotFound) as ex:
            return IdentityVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='کد ملی کاربر اشتباه است',
                err_code='InvalidNationalCode',
            )

        if result.first_name_similarity is not None and result.first_name_similarity < 80:
            return IdentityVerificationResult(
                result=False,
                confidence=70,
                apiresponse=result.api_response,
                message='نام اشتباه است.',
                err_code='BadFirstName',
            )

        if result.last_name_similarity is not None and result.last_name_similarity < 50:
            return IdentityVerificationResult(
                result=False,
                confidence=70,
                apiresponse=result.api_response,
                message='نام خانوادگی اشتباه است.',
                err_code='BadLastName',
            )

        if result.full_name_similarity is not None and result.full_name_similarity < 66:
            return IdentityVerificationResult(
                result=False,
                confidence=70,
                apiresponse=result.api_response,
                message='نام کامل اشتباه است.',
                err_code='BadFullName',
            )

        if result.father_name_similarity is not None and result.father_name_similarity < 80:
            return IdentityVerificationResult(
                result=False,
                confidence=70,
                apiresponse=result.api_response,
                message='نام پدر اشتباه است.',
                err_code='BadFatherName',
            )

        return IdentityVerificationResult(
            result=True,
            confidence=100,
            apiresponse=result.api_response,
            message='ok',
            err_code='',
        )

    @multi_provider_inquiry('UserOwnsMobile')
    def is_user_owner_of_mobile_number(
        self,
        national_code: str,
        mobile: str,
        *,
        provider: VerificationClientBase,
    ) -> MobileOwnerVerificationResult:
        try:
            is_valid, json_result = provider.is_national_code_owner_of_mobile_number(national_code, mobile)
        except InvalidNationalCode as ex:
            return {
                'result': False,
                'message': 'کد ملی کاربر اشتباه است.',
                'apiresponse': ex.api_response,
                'err_code': 'InvalidNationalCode',
            }
        except InvalidMobile as ex:
            return {
                'result': False,
                'message': 'شماره موبایل کاربر اشتباه است.',
                'apiresponse': ex.api_response,
                'err_code': 'InvalidMobile',
            }

        if not is_valid:
            return {
                'result': False,
                'message': 'مشخصات صاحب تلفن با مشخصات ارائه شده مغایرت دارد.',
                'apiresponse': json_result,
                'err_code': 'NameWontMatchPhoneHolder',
            }

        return {
            'result': True,
            'message': 'ok',
            'apiresponse': json_result,
            'err_code': '',
        }

    @multi_provider_inquiry('UserOwnsBankAccount')
    def is_user_owner_of_bank_account(
        self,
        bank_account,
        *,
        provider: VerificationClientBase,
    ) -> IBANOwnerVerificationResult:
        user = bank_account.user
        try:
            is_valid, json_result = provider.is_user_owner_of_iban(
                user.first_name,
                user.last_name,
                bank_account.shaba_number,
            )
        except InactiveIBAN as ex:
            return IBANOwnerVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='حساب فعال نیست',
                err_code='InactiveIBAN',
            )
        except MismatchedIBAN as ex:
            return IBANOwnerVerificationResult(
                result=False,
                confidence=70,
                apiresponse=ex.api_response,
                message='نام کاربر با صاحب حساب مطابقت ندارد',
                err_code='MismatchedIBAN',
            )
        except InvalidIBAN as ex:
            return IBANOwnerVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='شماره شبا اشتباه است',
                err_code='InvalidIBAN',
            )

        if not is_valid:
            return IBANOwnerVerificationResult(
                result=False,
                confidence=100,
                apiresponse=json_result,
                message='نام کاربر با صاحب حساب مطابقت ندارد',
                err_code='NameDontMatch',
            )

        return IBANOwnerVerificationResult(
            result=True,
            confidence=100,
            apiresponse=json_result,
            message='ok',
            err_code='',
        )

    @multi_provider_inquiry('UserOwnsBankCard')
    def is_user_owner_of_bank_card(
        self, bank_card, provider: VerificationClientBase
    ) -> BankCardOwnerVerificationResult:
        user = bank_card.user
        try:
            is_valid, json_result = provider.is_user_owner_of_bank_card(
                user.get_full_name(),
                bank_card.card_number,
            )
        except InvalidCard as ex:
            return BankCardOwnerVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='شماره کارت اشتباه است',
                err_code='InvalidCard',
            )
        except InactiveCard as ex:
            return BankCardOwnerVerificationResult(
                result=False,
                confidence=100,
                apiresponse=ex.api_response,
                message='کارت فعال نیست',
                err_code='InactiveCard',
            )
        except MismatchedCard as ex:
            return BankCardOwnerVerificationResult(
                result=False,
                confidence=70,
                apiresponse=ex.api_response,
                message='نام کاربر با صاحب کارت مطابقت ندارد',
                err_code='MismatchedCard',
            )
        except UnknownCardQueryError as ex:
            return BankCardOwnerVerificationResult(
                result=False,
                confidence=70,
                apiresponse=ex.api_response,
                message='خطای متفرقه',
                err_code='UnknownCardQueryError',
            )

        if not is_valid:
            return BankCardOwnerVerificationResult(
                result=False,
                confidence=100,
                apiresponse=json_result,
                message='نام کاربر با صاحب کارت مطابقت ندارد',
                err_code='NameDoesNotMatchCardHolder',
            )

        return BankCardOwnerVerificationResult(
            result=True,
            confidence=100,
            apiresponse=json_result,
            message='ok',
            err_code='',
        )

    @multi_provider_inquiry('ConvertCardToIban', reraise_verification_error=True)
    def convert_card_number_to_iban(self, bank_card, *, provider: VerificationClientBase) -> CardToIbanResult:
        user = bank_card.user

        try:
            result = provider.convert_card_number_to_iban(bank_card.card_number)
        except CardToIbanError as ex:
            return CardToIbanResult(
                api_response=ex.api_response,
                error_message=ex.msg,
                err_code='CardToIbanError',
            )

        user_full_name = user.get_full_name()
        for name in result.owners:
            if compare_full_names(name, user_full_name):
                break
        else:
            return CardToIbanResult(
                api_response=result.api_response,
                error_message='نام کاربر با صاحب حساب مطابقت ندارد.',
                iban=result.iban,
                deposit=result.deposit,
                err_code='NameWontMatchDepositOwner',
            )

        return CardToIbanResult(deposit=result.deposit, iban=result.iban, api_response=result.api_response, err_code='')

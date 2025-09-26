import datetime
import random
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q

from exchange.accounts.exceptions import (
    CheckMobileIdentityError,
    HasActiveMergeRequestError,
    HasReferralProgramError,
    HasTransactionError,
    IncompatibleUserLevelError,
    MaxMergeRequestExceededError,
    SameUserError,
    UserHasEmailError,
)
from exchange.accounts.functions import expire_user_token
from exchange.accounts.models import ReferralProgram, Tag, User, UserEvent, UserMergeRequest, UserRestriction
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.api import NobitexAPIError
from exchange.base.calendar import get_earliest_time, ir_now
from exchange.base.models import Settings
from exchange.wallet.models import Transaction, Wallet


class MergeManager:
    merge_basis_field: str

    def __init__(self, main_account: User, second_account: User) -> None:
        self.main_account = main_account
        self.second_account = second_account

    def check_user_conditions(self):
        if self.main_account.id == self.second_account.id:
            raise SameUserError

        if self.main_account.user_type > User.USER_TYPES.level2:
            raise IncompatibleUserLevelError('Main Account level is too high')

        if self.second_account.user_type > User.USER_TYPES.level0:
            raise IncompatibleUserLevelError('Second Account level is too high')

        if self.second_account.national_code:
            raise IncompatibleUserLevelError('Second Account has national code')

        if self.main_account.user_type < User.USER_TYPES.level0:
            raise IncompatibleUserLevelError('Main account level is too low')

        if self.second_account.user_type < User.USER_TYPES.level0:
            raise IncompatibleUserLevelError('Second account level is too low')

    def _check_transactions(self):
        wallet_ids = Wallet.objects.filter(user=self.second_account)

        if Transaction.objects.filter(wallet__in=wallet_ids).exists():
            raise HasTransactionError

    def _check_referral_program(self):
        if ReferralProgram.objects.filter(user=self.second_account).exists():
            raise HasReferralProgramError

    def _check_merge_request_limit(self):
        accepted_merges = UserMergeRequest.objects.filter(
            Q(main_user=self.main_account) | Q(main_user=self.second_account), status=UserMergeRequest.STATUS.accepted
        )

        daily_count = accepted_merges.filter(
            merged_at__gte=get_earliest_time(ir_now()),
        ).count()
        daily_max_count = int(Settings.get_value('merge_daily_max_request_count', 1))
        if daily_count >= daily_max_count:
            raise MaxMergeRequestExceededError()

        count = accepted_merges.count()
        max_count = int(Settings.get_value('merge_max_request_count', 3))
        if count >= max_count:
            raise MaxMergeRequestExceededError()

    def _have_active_merge_request(self, exclude_request: Optional[UserMergeRequest] = None):
        active_merges = UserMergeRequest.get_active_merge_requests([self.main_account, self.second_account])

        if exclude_request:
            active_merges = active_merges.exclude(id=exclude_request.id)
        if active_merges.exists():
            raise HasActiveMergeRequestError

    def check_basic_conditions(self, request: Optional[UserMergeRequest] = None):
        """
        Raises:
            IncompatibleUserLevelError
            HasTransactionError
            HasReferralProgramError
            HasActiveMergeRequestError
        """
        self._check_merge_request_limit()
        self.check_user_conditions()
        self._check_transactions()
        self._check_referral_program()
        self._have_active_merge_request(exclude_request=request)

    def _add_restriction(self):
        UserRestriction.add_restriction(
            user=self.main_account,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations='ایجاد محدودیت 24 ساعته برداشت رمز ارز به علت  ادغام دو اکانت',
            duration=datetime.timedelta(hours=24),
            description=UserRestrictionsDescription.MERGE_ACCOUNTS,
        )

    def _logout_users(self):
        expire_user_token(self.second_account)
        expire_user_token(self.main_account)

    def check_merge_conditions(self, request: Optional[UserMergeRequest] = None):
        raise NotImplementedError

    def _update_second_user_in_merge(self):
        random_two_digit = random.randint(10, 99)
        if self.second_account.mobile == self.second_account.username:
            self.second_account.username = self.second_account.mobile + f'_{random_two_digit}' + '@merge.ntx.ir'
        else:
            email_username, domain = self.second_account.email.split('@')
            self.second_account.username = email_username + '&' + domain + f'_{random_two_digit}' + '@merge.ntx.ir'

        if self.second_account.email:
            self.second_account.email = self.second_account.username

        self.second_account.mobile = None
        self.second_account.is_active = False
        self.second_account.save(update_fields=['email', 'mobile', 'username', 'is_active'])

    def _get_merge_by_basis_field(self, account: User):
        return getattr(account, self.merge_basis_field)

    def _update_main_user_in_merge(self, bases_field: str):
        raise NotImplementedError

    def _update_main_user_verification_profile(self):
        raise NotImplementedError

    def _add_tag_to_second_user(self):
        merge_tag = Tag.get_builtin_tag('حساب ادغام شده')
        self.second_account.tags.add(merge_tag)

    def _merge(self):
        with transaction.atomic():
            basis_field = self._get_merge_by_basis_field(self.second_account)
            self._update_second_user_in_merge()
            self._add_tag_to_second_user()
            self._update_main_user_in_merge(basis_field)
            self._update_main_user_verification_profile()

    def _get_exception_description(self, _exception: str) -> Tuple[str, str]:
        exceptions = {
            'HasTransactionError': ('User has transaction.', 'حساب مرج شونده دارای تراکنش است.'),
            'HasReferralProgramError': ('User has referral program.', 'حساب مرج شونده کد ریفرال ساخته است.'),
            'HasActiveMergeRequestError': (
                'User has active merge request.',
                'حساب مرج شونده، درخواست فعالی برای ادغام حسابش دارد.',
            ),
            'UserHasEmailError': ('User has email.', 'حساب مرج کننده دارای ایمیل است.'),
            'SameUserError': ('User can not merge with self.', 'حساب مرج کننده و مرج شونده نباید یکسان باشد.'),
        }
        return exceptions[_exception]

    def _raise_api_error(self, message, description):
        raise NobitexAPIError(message=message, description=description, status_code=422)

    def merge(self, request: UserMergeRequest) -> None:
        try:
            with transaction.atomic():
                self.check_merge_conditions(request)
                # change status before merge for sending email
                request.change_to_accepted_status()
                self._merge()
                self._add_restriction()
                self._logout_users()

        except IncompatibleUserLevelError as e:
            try:
                type_error = {
                    'Main Account level is too high': 'حساب مرج کننده سطحی بالاتر از انتظار دارد.',
                    'Second Account level is too high': 'حساب مرج شونده سطحی بالاتر از انتظار دارد.',
                    'Second Account has national code': 'حساب مرج شونده دارای کد ملی است.',
                    'Main account level is too low': 'حساب مرج کننده سطحی پایین‌تر از انتظار دارد.',
                    'Second account level is too low': 'حساب مرج شونده سطحی پایین‌تر از انتظار دارد.',
                }[str(e)]
            except KeyError:
                type_error = str(e)

            request.change_to_rejected_status(
                description='سطح حساب‌های کاربری انتخاب شده، مناسب عملیات ادغام نیست: ' + type_error,
            )
            self._raise_api_error('IncompatibleUserLevelError', str(e))
        except (
            HasTransactionError,
            HasReferralProgramError,
            HasActiveMergeRequestError,
            UserHasEmailError,
            SameUserError,
        ) as e:
            error_class_name = e.__class__.__name__
            en_message, fa_message = self._get_exception_description(error_class_name)

            request.change_to_rejected_status(fa_message)
            self._raise_api_error(error_class_name, en_message)

        except CheckMobileIdentityError as e:
            if isinstance(self, MergeByMobile):
                self._add_user_event_mobile_identity_error_log(str(e))
            request.change_to_rejected_status('بررسی به نام بودن شماره‌ی تماس کاربر با خطا مواجه شده است:' + str(e))
            self._raise_api_error('CheckMobileIdentityError', 'Checking mobile identity has failed.')


class MergeByEmail(MergeManager):
    merge_basis_field: str = 'email'

    def _check_email(self):
        if self.main_account.email and self.main_account.is_email_verified:
            raise UserHasEmailError

    def check_merge_conditions(self, request: Optional[UserMergeRequest] = None):
        """
        Raises:
            IncompatibleUserLevelError
            HasTransactionError
            HasReferralProgramError
            HasActiveMergeRequestError
            UserHasEmailError
        """
        self.check_basic_conditions(request)
        self._check_email()

    def _update_main_user_verification_profile(self):
        verification_profile = self.main_account.get_verification_profile()
        if not verification_profile.email_confirmed:
            verification_profile.email_confirmed = True
            verification_profile.save(update_fields=['email_confirmed'])

    def _update_main_user_in_merge(self, new_email: str):
        update_fields = ['email']

        if self.main_account.email == self.main_account.username:
            self.main_account.username = new_email
            update_fields.append('username')

        self.main_account.email = new_email
        self.main_account.save(update_fields=update_fields)


class MergeByMobile(MergeManager):
    merge_basis_field: str = 'mobile'

    def _add_user_event_mobile_identity_error_log(self, description: Optional[str] = None):
        UserEvent.objects.create(
            user=self.main_account,
            action=UserEvent.ACTION_CHOICES.user_merge,
            action_type=UserEvent.USER_MERGE_ACTION_TYPES.fail_identity,
            description=description,
        )

    def _check_mobile_identity_confirmed(self):
        if self.main_account.user_type == User.USER_TYPES.level1:
            result, error_message = self.main_account.check_mobile_identity(
                self.second_account.mobile,
                self.main_account.national_code,
            )
            if not result:
                self._add_user_event_mobile_identity_error_log(
                    description=f'NewMobile:{self.second_account.mobile} Error:"{error_message}"',
                )
                raise CheckMobileIdentityError(error_message)

    def check_merge_conditions(self, request: Optional[UserMergeRequest] = None):
        """
        Raises:
            IncompatibleUserLevelError
            HasTransactionError
            HasReferralProgramError
            HasActiveMergeRequestError
            CheckMobileIdentityError
        """
        self.check_basic_conditions(request)
        self._check_mobile_identity_confirmed()

    def _update_main_user_verification_profile(self):
        verification_profile = self.main_account.get_verification_profile()
        update_fields = []

        if not verification_profile.mobile_confirmed:
            verification_profile.mobile_confirmed = True
            update_fields.append('mobile_confirmed')

        if not verification_profile.mobile_identity_confirmed and self.main_account.user_type > User.USER_TYPES.level0:
            verification_profile.mobile_identity_confirmed = True
            update_fields.append('mobile_identity_confirmed')

        if update_fields:
            verification_profile.save(update_fields=update_fields)

    def _update_main_user_in_merge(self, new_mobile: str):
        update_fields = ['mobile']

        if self.main_account.username == self.main_account.mobile:
            self.main_account.username = new_mobile
            update_fields.append('username')

            if not self.main_account.email or self.main_account.email.endswith('@mobile.ntx.ir'):
                self.main_account.email = new_mobile + '@mobile.ntx.ir'
                update_fields.append('email')

        self.main_account.mobile = new_mobile
        self.main_account.save(update_fields=update_fields)

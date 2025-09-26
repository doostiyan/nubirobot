from abc import ABC
from decimal import Decimal

from exchange.accounts.models import BankAccount
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.api import NobitexAPIError
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Settings, get_currency_codename
from exchange.credit.exportables import check_if_user_could_withdraw as credit_check_if_user_could_withdraw
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.withdraw_method import AutomaticWithdrawMethod


class BaseWithdrawRequestValidation(ABC):
    def __init__(self, user, wallet, target_address, amount, **kwargs):
        self.user = user
        self.wallet = wallet
        self.target_address = target_address
        self.amount = amount
        self.kwargs = kwargs

    def validate(self):
        raise NotImplemented


class CreditValidation(BaseWithdrawRequestValidation):
    def validate(self):
        if not credit_check_if_user_could_withdraw(self.user.id, self.wallet.currency, self.amount):
            raise NobitexAPIError(
                status_code=400,
                message='WithdrawUnavailableCreditDebt',
                description='با توجه به اعتبار vip دریافت شده، ایجاد درخواست برداشت ممکن نیست.',
            )


class UserRestrictionValidation(BaseWithdrawRequestValidation):
    def validate(self):
        is_restricted = WithdrawRequest.is_user_not_allowed_to_withdraw(self.user, self.wallet)
        if is_restricted and not self.kwargs.get('withdraw_permit'):
            raise NobitexAPIError(status_code=400, message='WithdrawUnavailable', description='WithdrawUnavailable')


class ProviderValidation(BaseWithdrawRequestValidation):
    def validate(self):
        bank_account = self.kwargs.get('bank_account')

        if bank_account.bank_id == BankAccount.BANK_ID.jibit and not Settings.get_json_object('withdraw_id').get(
            'jibit_withdraw_enabled'
        ):
            raise NobitexAPIError(
                status_code=400, message='JibitPaymentIdDisabled', description='jibit withdraw is disabled.'
            )
        if bank_account.bank_id == BankAccount.BANK_ID.vandar and not Settings.get_json_object('withdraw_id').get(
            'vandar_withdraw_enabled'
        ):
            raise NobitexAPIError(
                status_code=400, message='VandarPaymentIdDisabled', description='Vandar withdraw is disabled.'
            )


class UserWalletBalanceValidation(BaseWithdrawRequestValidation):
    def validate(self):
        if self.amount > self.wallet.active_balance:
            raise NobitexAPIError(status_code=400, message='InsufficientBalance', description='Insufficient Balance.')


class MaxAmountValidation(BaseWithdrawRequestValidation):
    def validate(self):
        network = self.kwargs.get('network')
        max_withdraw_amount = Decimal(CURRENCY_INFO[self.wallet.currency]['network_list'][network]['withdraw_max'])

        if self.kwargs.get('bank_account').bank_id == BankAccount.BANK_ID.vandar:
            max_withdraw_amount = Settings.get_decimal('vandar_max_withdrawal')
            if not max_withdraw_amount:
                raise NobitexAPIError(
                    status_code=400, message='MaxValueIsNotSet', description='maximum value is not set'
                )

        if max_withdraw_amount is not None and self.amount > max_withdraw_amount:
            raise NobitexAPIError(status_code=400, message='AmountTooHigh', description='Amount too high')


class MinAmountValidation(BaseWithdrawRequestValidation):
    def validate(self):
        network = self.kwargs.get('network')
        min_withdraw_amount = AutomaticWithdrawMethod.get_withdraw_min(self.wallet.currency, network)
        if self.amount < min_withdraw_amount:
            raise NobitexAPIError(
                status_code=400,
                message='AmountTooLow',
                description='Amount too low',
            )


class UserProfileValidation(BaseWithdrawRequestValidation):
    def validate(self):
        # Check if the user has valid mobile code which is required for withdraw
        if not self.user.get_verification_profile().has_verified_mobile_number:
            raise NobitexAPIError(
                status_code=422,
                message='InvalidMobileNumber',
                description='Verified mobile number is required for withdraw.',
            )


class WithdrawStatusValidation(BaseWithdrawRequestValidation):
    def validate(self):
        # Check withdraw for currency/network is enabled
        network = self.kwargs.get('network')
        if not CURRENCY_INFO[self.wallet.currency]['network_list'][network]['withdraw_enable']:
            raise NobitexAPIError(
                status_code=422,
                message='WithdrawCurrencyUnavailable',
                description='WithdrawCurrencyUnavailable',
            )

        # Check if withdrawal for rial is temporary disabled
        currency_name = get_currency_codename(self.wallet.currency)
        flag_key = 'withdraw_enabled_{}_{}'.format(currency_name, network.lower())

        if not Settings.get_trio_flag(
            flag_key,
            default='yes',  # all network in network_list filter by withdraw_enable=True
        ):
            raise NobitexAPIError(
                status_code=422,
                message='WithdrawDisabled',
                description='Withdrawals for rls is temporary disabled.',
            )


class CheckDailyShabaWithdrawLimitExceededValidation(BaseWithdrawRequestValidation):
    def validate(self):
        bank_account = self.kwargs.get('bank_account')
        if bank_account.bank_id and not WithdrawRequest.can_withdraw_shaba(
            wallet=self.wallet, target_account=bank_account, amount=self.amount
        ):
            raise NobitexAPIError(
                status_code=400,
                message='ShabaWithdrawCannotProceed',
                description='Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
            )


class UserLevelLimitationValidation(BaseWithdrawRequestValidation):
    def validate(self):
        if not WithdrawRequest.check_user_limit(self.user, self.wallet.currency):
            raise NobitexAPIError(
                status_code=400, message='WithdrawLimitReached', description='msgWithdrawLimitReached'
            )


class EligibleToWithdrawValidation(BaseWithdrawRequestValidation):
    def validate(self):
        if not UserLevelManager.is_eligible_to_withdraw(
            self.user, self.wallet.currency, self.amount, self.kwargs.get('network')
        ):
            raise NobitexAPIError(
                status_code=400, message='WithdrawAmountLimitation', description='WithdrawAmountLimitation'
            )
        is_vandar = self.kwargs.get('bank_account').bank_id == BankAccount.BANK_ID.vandar
        if is_vandar and not UserLevelManager.is_eligible_to_vandar_withdraw(self.user):
            raise NobitexAPIError(
                status_code=400,
                message='VandarWithdrawNotEnabled',
                description='Vandar withdraw is not available for this user.',
            )

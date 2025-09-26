from decimal import Decimal

from django.db import transaction

from exchange.asset_backed_credit.exceptions import (
    CloseUserServiceAlreadyRequestedError,
    ExternalProviderError,
    ThirdPartyError,
    UpdateClosedUserService,
    UserServiceHasActiveDebt,
    UserServiceIsNotInternallyCloseable,
)
from exchange.asset_backed_credit.models import AssetToDebtMarginCall, InternalUser, Service, UserService
from exchange.asset_backed_credit.services.liquidation import liquidate_margin_call
from exchange.asset_backed_credit.services.price import PricingService, get_ratios
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.services.user_service import close_user_service, decrease_user_service_current_debt
from exchange.base.logging import report_exception


class AdjustService:
    def __init__(self, margin_call_id: int):
        self.margin_call_id = margin_call_id

    @transaction.atomic
    def execute(self):
        self._prepare()
        self._update_margin_call()
        self._adjust_user_services()

    def _prepare(self):
        self.margin_call = (
            AssetToDebtMarginCall.objects.select_related('user')
            .select_for_update(of=('self',), no_key=True)
            .get(pk=self.margin_call_id)
        )
        self.user_services = UserService.objects.filter(
            user=self.margin_call.user, current_debt__gt=0, closed_at__isnull=True
        )
        pricing_service = PricingService(user=self.margin_call.user)
        self.total_debt = pricing_service.total_debt
        self.total_assets = pricing_service.total_assets

    def _update_margin_call(self):
        update_fields = []
        if self.margin_call.total_debt != self.total_debt:
            self.margin_call.total_debt = self.total_debt
            update_fields.append('total_debt')
        if self.margin_call.total_assets != self.total_assets:
            self.margin_call.total_assets = self.total_assets.total_mark_price
            update_fields.append('total_assets')
        self.margin_call.save(update_fields=update_fields)

    def _adjust_user_services(self):
        has_proper_collateral_ratio = self._discharge_user_services()

        if has_proper_collateral_ratio:
            return

        liquidate_margin_call(self.margin_call.id)

    def _discharge_user_services(self) -> bool:
        InternalUser.get_lock(self.margin_call.user.pk)
        user_services = (
            UserService.objects.filter(user=self.margin_call.user, current_debt__gt=0, closed_at__isnull=True)
            .select_related('service', 'user')
            .select_for_update(of=('self',), no_key=True)
        )

        has_proper_collateral_ratio = False
        has_any_discharge_op = False

        for user_service in user_services:
            discharged_amount = self._try_discharge_user_service(user_service)
            if discharged_amount <= 0:
                continue

            self.total_debt -= discharged_amount
            has_any_discharge_op = True

            wallet_type = Service.get_related_wallet_type(user_service.service.tp)
            ratio = PricingService(
                user=self.margin_call.user,
                total_debt=self.total_debt,
                total_assets=self.total_assets,
                wallet_type=wallet_type,
            ).get_margin_ratio()

            if ratio > get_ratios().get('liquidation'):
                has_proper_collateral_ratio = True
                break

        if has_any_discharge_op:
            self._update_last_action_and_notify()

        return has_proper_collateral_ratio

    @staticmethod
    def _try_discharge_user_service(user_service: UserService) -> Decimal:
        """
        Try to discharge credit user service based on available balance
        if the balance is greater than zero and the provider supports
        balance check and discharge or close loan user service entirely

        Returns:
            available_balance: the discharged amount
        """
        try:
            if user_service.service.tp == Service.TYPES.credit:
                available_balance = api_dispatcher(user_service).get_available_balance()
                if available_balance <= 0:
                    return Decimal(0)
                decrease_user_service_current_debt(user_service, -available_balance)
                return available_balance
            elif user_service.service.tp == Service.TYPES.loan:
                current_debt = user_service.current_debt
                close_user_service(user_service=user_service)
                return current_debt
            else:
                return Decimal(0)
        except (
            UpdateClosedUserService,
            CloseUserServiceAlreadyRequestedError,
            UserServiceHasActiveDebt,
            ExternalProviderError,
            UserServiceIsNotInternallyCloseable,
            ThirdPartyError,
            NotImplementedError,
        ):
            return Decimal(0)
        except Exception:
            report_exception()
            return Decimal(0)

    def _update_last_action_and_notify(self):
        self.margin_call.last_action = AssetToDebtMarginCall.ACTION.discharged
        self.margin_call.save(update_fields=['last_action'])

        from exchange.asset_backed_credit.tasks import task_margin_call_send_adjust_notifications

        task_margin_call_send_adjust_notifications.delay(self.margin_call.id)

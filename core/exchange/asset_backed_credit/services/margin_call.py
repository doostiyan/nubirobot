from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Type

from django.db import transaction
from django.db.models import OuterRef, Subquery, Sum
from django.utils.decorators import method_decorator

from exchange.accounts.models import User, UserSms
from exchange.asset_backed_credit.externals.notification import notification_provider
from exchange.asset_backed_credit.metrics import sentry_transaction
from exchange.asset_backed_credit.models import AssetToDebtMarginCall, Service, UserService, Wallet
from exchange.asset_backed_credit.services.price import get_batch_total_assets, get_ratios
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.asset_backed_credit.types import MarginCallCandidate
from exchange.base.models import RIAL, Settings
from exchange.base.money import money_is_zero


def execute_margin_calls():
    MarginCallProcessor(exclude_rial_only=True).run()


def execute_margin_calls_hourly():
    MarginCallProcessor(exclude_rial_only=False).run()


class MarginCallProcessor:
    def __init__(self, exclude_rial_only: bool):
        self.exclude_rial_only = exclude_rial_only
        self.ratios = get_ratios()

    @method_decorator(
        sentry_transaction(
            name='abc_margin_call', predicate=lambda: Settings.get_flag('abc_margin_call_sentry_transaction_enabled')
        )
    )
    def run(self):
        raw = fetch_raw_candidates()
        cached = self._prepare(raw, use_cache=True)
        self._execute_actions(cached, actions=[MarginCallResolveAction])

        # Only candidates not resolved go to next stage
        leftovers = {
            user_id: candidate
            for user_id, candidate in cached.items()
            if not (candidate.margin_call_id and candidate.ratio > self.ratios['margin_call'])
        }
        if leftovers:
            live = self._prepare(leftovers, use_cache=False)
            self._execute_actions(live, actions=[MarginCallNotifyAction, MarginCallAdjustAction])

        from exchange.asset_backed_credit.tasks import task_margin_call_cleanup

        task_margin_call_cleanup.delay()

    def _prepare(self, raw: Dict[int, MarginCallCandidate], use_cache: bool) -> Dict[int, MarginCallCandidate]:
        user_ids = list(raw.keys())
        users = User.objects.filter(id__in=user_ids)
        wallets = WalletService.get_wallets(users=users, wallet_type=Wallet.WalletType.COLLATERAL, cached=use_cache)
        total_assets_per_user = get_batch_total_assets(wallets)

        prepared = {}
        for user_id, candidate in raw.items():
            total_assets = total_assets_per_user[user_id]
            is_rial_only = all(
                wallet.currency == RIAL or money_is_zero(wallet.balance) for wallet in wallets.get(user_id, [])
            )
            ratio = (
                total_assets.total_mark_price / candidate.total_debt
                if candidate.total_debt > 0
                else self.ratios['collateral']
            )
            prepared[user_id] = MarginCallCandidate(
                user_id=user_id,
                internal_user_id=candidate.internal_user_id,
                margin_call_id=candidate.margin_call_id,
                total_debt=candidate.total_debt,
                total_assets=total_assets,
                is_rial_only=is_rial_only,
                ratio=ratio,
            )
        return prepared

    def _execute_actions(self, candidates: Dict[int, MarginCallCandidate], actions: List[Type['MarginCallAction']]):
        """Instantiate each action, collect eligible candidates, execute."""
        instances = [Action(self.ratios) for Action in actions]
        for candidate in candidates.values():
            if candidate.is_rial_only and self.exclude_rial_only:
                continue
            for action in instances:
                if action.supports(candidate.ratio):
                    action.collect(candidate)
                    break

        for action in instances:
            action.execute()


def fetch_raw_candidates() -> Dict[int, MarginCallCandidate]:
    """Fetch margin call candidates for users with open, positive-debt services."""
    margin_call_candidates = (
        UserService.objects.filter(
            closed_at__isnull=True,
            current_debt__gt=0,
            service__tp__in=[Service.TYPES.credit, Service.TYPES.loan],
        )
        .values('user_id', 'internal_user_id')
        .annotate(total_debt=Sum('current_debt'))
        .annotate(
            margin_call_id=Subquery(
                AssetToDebtMarginCall.objects.filter(user_id=OuterRef('user_id'), is_solved=False).values('id')[:1],
            ),
        )
    )
    return {
        item['user_id']: MarginCallCandidate(
            user_id=item['user_id'],
            internal_user_id=item['internal_user_id'],
            total_debt=item['total_debt'],
            margin_call_id=item['margin_call_id'],
        )
        for item in margin_call_candidates
    }


def cleanup_margin_call_resolved_candidates():
    """
    Mark margin calls as resolved if the user has zero current debt.
    """
    AssetToDebtMarginCall.objects.filter(
        is_solved=False,
        user_id__in=Subquery(
            UserService.objects.values('user_id')
            .annotate(total_debt=Sum('current_debt'))
            .filter(total_debt=0)
            .values('user_id')
        ),
    ).update(is_solved=True)


class MarginCallAction(ABC):
    def __init__(self, ratios: Dict[str, Decimal]):
        self.ratios = ratios
        self.new: List[MarginCallCandidate] = []
        self.existing_ids: List[int] = []

    def collect(self, candidate: MarginCallCandidate):
        if candidate.margin_call_id:
            self.existing_ids.append(candidate.margin_call_id)
        else:
            self.new.append(candidate)

    @abstractmethod
    def supports(self, ratio: Decimal) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def execute(self):
        raise NotImplementedError()

    def _bulk_create(self):
        if not self.new:
            return []
        margin_calls = [
            AssetToDebtMarginCall(
                user_id=candidate.user_id,
                internal_user_id=candidate.internal_user_id,
                total_debt=candidate.total_debt,
                total_assets=candidate.total_assets.total_mark_price,
            )
            for candidate in self.new
        ]
        return AssetToDebtMarginCall.objects.bulk_create(margin_calls)

    def _fetch_existing(self):
        if not self.existing_ids:
            return AssetToDebtMarginCall.objects.none()
        return AssetToDebtMarginCall.objects.filter(id__in=self.existing_ids)


class MarginCallResolveAction(MarginCallAction):
    """Resolve margin calls where ratio > margin_call threshold."""

    def supports(self, ratio):
        return ratio > self.ratios['margin_call']

    def execute(self):
        if not self.existing_ids:
            return
        AssetToDebtMarginCall.objects.filter(id__in=self.existing_ids).update(is_solved=True)


class MarginCallNotifyAction(MarginCallAction):
    """Notify users when in margin call danger zone."""

    def supports(self, ratio):
        return self.ratios['liquidation'] < ratio <= self.ratios['margin_call']

    def execute(self):
        from exchange.asset_backed_credit.tasks import task_margin_call_notify
        new_margin_calls = self._bulk_create()
        existing_margin_calls = self._fetch_existing().filter(is_margin_call_sent=False)
        for margin_call in list(new_margin_calls) + list(existing_margin_calls):
            task_margin_call_notify.delay(margin_call.id)


class MarginCallAdjustAction(MarginCallAction):
    """Trigger adjustment when user is below liquidation threshold."""

    def supports(self, ratio):
        return ratio <= self.ratios['liquidation']

    def execute(self):
        from exchange.asset_backed_credit.tasks import task_margin_call_adjust
        new_margin_calls = self._bulk_create()
        existing_margin_calls = self._fetch_existing()
        for margin_call in list(new_margin_calls) + list(existing_margin_calls):
            task_margin_call_adjust.delay(margin_call.id)


@transaction.atomic
def send_margin_call_notification(margin_call_id: int):
    margin_call = (
        AssetToDebtMarginCall.objects.filter(id=margin_call_id, is_margin_call_sent=False)
        .select_for_update(no_key=True)
        .first()
    )
    if not margin_call or margin_call.is_margin_call_sent:
        return

    notification_provider.send_notif(
        user=margin_call.user,
        message='وثیقه شما در اعتبار ریالی نوبیتکس در آستانه تبدیل قرار گرفته است.'
        ' در صورت تمایل هرچه سریعتر وثیقه خود را افزایش دهید.',
    )
    notification_provider.send_sms(
        user=margin_call.user,
        tp=UserSms.TYPES.abc_margin_call,
        text='اعتبار ریالی',
        template=UserSms.TEMPLATES.abc_margin_call,
    )

    if margin_call.user.is_email_verified:
        notification_provider.send_email(
            to_email=margin_call.user.email, template='abc/abc_margin_call', priority='high'
        )

    margin_call.is_margin_call_sent = True
    margin_call.save(update_fields=('is_margin_call_sent',))


@transaction.atomic
def send_liquidation_notification(margin_call_id: int):
    margin_call = (
        AssetToDebtMarginCall.objects.filter(id=margin_call_id, is_liquidation_notif_sent=False)
        .select_for_update(no_key=True)
        .first()
    )
    if not margin_call or margin_call.is_liquidation_notif_sent:
        return

    notification_provider.send_notif(
        user=margin_call.user,
        message='وثیقه شما در سرویس اعتبار ریالی نوبیتکس تبدیل شد.',
    )
    notification_provider.send_sms(
        user=margin_call.user,
        tp=UserSms.TYPES.abc_margin_call_liquidate,
        text='اعتبار ریالی',
        template=UserSms.TEMPLATES.abc_margin_call_liquidate,
    )

    if margin_call.user.is_email_verified:
        notification_provider.send_email(to_email=margin_call.user.email, template='abc/abc_margin_call_liquidate')

    margin_call.is_liquidation_notif_sent = True
    margin_call.save(update_fields=('is_liquidation_notif_sent',))


@transaction.atomic
def send_adjustment_notification(margin_call_id: int):
    margin_call = (
        AssetToDebtMarginCall.objects.filter(id=margin_call_id, is_adjustment_notif_sent=False)
        .select_for_update(no_key=True)
        .first()
    )
    if not margin_call or margin_call.is_adjustment_notif_sent:
        return

    notification_provider.send_notif(
        user=margin_call.user,
        message='به‌دلیل کاهش نسبت ارزش، باقیمانده‌ی اعتبار شما در تارا غیرفعال شد.',
    )
    notification_provider.send_sms(
        user=margin_call.user,
        tp=UserSms.TYPES.abc_margin_call_adjustment,
        text='تارا',
        template=UserSms.TEMPLATES.abc_margin_call_adjustment,
    )

    if margin_call.user.is_email_verified:
        notification_provider.send_email(
            to_email=margin_call.user.email, template='abc/abc_margin_call_adjustment', data={'service_name': 'تارا'}
        )

    margin_call.is_adjustment_notif_sent = True
    margin_call.save(update_fields=('is_adjustment_notif_sent',))

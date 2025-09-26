from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict

from django.core.cache import cache
from django.db.models import Sum

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.market.models import OrderMatching
from exchange.market.udf import UDFHistory
from exchange.marketing.exceptions import InvalidUserIDException
from exchange.marketing.services.campaign.base import get_campaign_settings
from exchange.marketing.services.mission.base import BaseMission
from exchange.marketing.types import UserInfo
from exchange.marketing.utils import parse_time
from exchange.xchange.models import ExchangeTrade


class MissionProgressStatus(Enum):
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    DONE = 'DONE'


class TradeMission(BaseMission):

    validity_duration = 10 * 24 * 60 * 60  # 10 days

    @classmethod
    def initiate(cls, user_info: UserInfo, campaign_id: str) -> Dict[str, Any]:
        if not user_info.user_id:
            raise InvalidUserIDException('user must have user id')

        history = cache.get(cls._get_cache_key(campaign_id, user_info.user_id))
        if history:
            return cls._get_progress_details(user_info, campaign_id, history)

        history = {'timestamp': ir_now()}
        cache.set(cls._get_cache_key(campaign_id, user_info.user_id), history, timeout=cls.validity_duration)
        return cls._get_progress_details(user_info, campaign_id, history)

    @classmethod
    def is_done(cls, user_info: UserInfo, campaign_id: str) -> bool:
        return cls.get_progress_details(user_info, campaign_id)['status'] == MissionProgressStatus.DONE.value

    @classmethod
    def get_progress_details(cls, user_info: UserInfo, campaign_id: str) -> Dict[str, Any]:
        history = cache.get(cls._get_cache_key(campaign_id, user_info.user_id))
        if not history:
            return {'status': MissionProgressStatus.NOT_STARTED.value}

        return cls._get_progress_details(user_info, campaign_id, history)

    @classmethod
    def _get_progress_details(cls, user_info: UserInfo, campaign_id: str, history: Dict[str, Any]) -> Dict[str, Any]:
        settings = get_campaign_settings(campaign_id)
        time_from = history['timestamp']
        time_to = parse_time(settings['end_time'], '%Y-%m-%d %H:%M:%S')
        total_trade = cls._get_total_trade_in_time(user_info.user_id, settings['currency'], time_from, time_to)

        if total_trade >= settings['threshold_amount']:
            data = {'status': MissionProgressStatus.DONE.value, 'remained_amount': 0}
        else:
            data = {
                'status': MissionProgressStatus.IN_PROGRESS.value,
                'remained_amount': int(settings['threshold_amount'] - total_trade),
            }

        data['user_level'] = user_info.level
        return data

    @classmethod
    def _get_total_trade_in_time(
        cls, user_id: int, currency: Currencies, start_time: datetime, end_time: datetime
    ) -> Decimal:
        return (
            cls._get_total_market_trade_in_time(user_id, currency, start_time, end_time) +
            cls._get_total_exchange_trade_in_time(user_id, currency, start_time, end_time)
        )

    @classmethod
    def _get_total_market_trade_in_time(
        cls, user_id: int, currency: Currencies, start_time: datetime, end_time: datetime
    ) -> Decimal:
        result = (
            OrderMatching.objects.select_related('market')
            .filter(
                buyer_id=user_id,
                market__src_currency=currency,
                created_at__gte=start_time,
                created_at__lte=end_time,
            )
            .aggregate(total_rial_amount=Sum('rial_value'))
        )
        amount = result.get('total_rial_amount', 0)
        return Decimal(amount) if amount else Decimal(0)

    @classmethod
    def _get_total_exchange_trade_in_time(
        cls, user_id: int, currency: Currencies, start_time: datetime, end_time: datetime
    ) -> Decimal:
        total_rial_amount = Decimal(0)

        ex_trades = ExchangeTrade.objects.filter(
            user_id=user_id,
            src_currency=currency,
            is_sell=False,
            status=ExchangeTrade.STATUS.succeeded,
            created_at__gte=start_time,
            created_at__lte=end_time,
        )
        for trade in ex_trades:
            if trade.dst_currency == Currencies.usdt:
                total_rial_amount += trade.dst_amount * cls._get_usdt_price_at_time(trade.created_at)
            else:
                total_rial_amount += trade.dst_amount

        return total_rial_amount

    @staticmethod
    def _get_usdt_price_at_time(date: datetime) -> Decimal:
        start_timestamp = int(date.replace(second=0, microsecond=0).timestamp())
        end_timestamp = int(date.replace(second=59, microsecond=999999).timestamp())
        data = UDFHistory.get_history('USDTIRT', '1', start_timestamp, end_timestamp)
        return Decimal(data['h'][0] * 10)

    @staticmethod
    def _get_cache_key(campaign_id: str, user_id: int) -> str:
        return f'campaign_mission:{campaign_id}:{user_id}'

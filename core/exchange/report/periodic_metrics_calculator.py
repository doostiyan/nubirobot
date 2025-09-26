from decimal import Decimal
from functools import partial
from typing import Any, ClassVar, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from post_office.models import Email as SentEmail

from exchange.accounts.models import User
from exchange.base.logging import report_exception
from exchange.base.metrics import broker_on_error
from exchange.base.models import PRICE_PRECISIONS, RIAL, TETHER, get_currency_codename
from exchange.base.producers import metric_producer
from exchange.broker.broker.schema import MetricSchema
from exchange.broker.broker.topics import Topics
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market


class PeriodicMetricsCalculator:
    IMPORTANT_CURRENCIES: ClassVar[List[str]] = ['btc', 'trx', 'doge', 'shib']
    CELERY_QUEUES: ClassVar[List[str]] = []

    def __init__(self, target: str = 'redis', selected_modules: Optional[List[str]] = None):
        self.target = target
        self.selected_modules = selected_modules
        self.__class__.CELERY_QUEUES = self.set_celery_queues()
        self._prices_binance = None
        self._usdt_price = None
        self._metric_prefix: str = 'nobitex_' if target == 'redis' else ''
        self._metrics: List[MetricSchema] = []

    @property
    def usdt_price(self):
        if self._usdt_price is None:
            self._usdt_price = 0
            try:
                usdt_irr_market = Market.get_for(TETHER, RIAL)
                if usdt_irr_market:
                    self._usdt_price = int(usdt_irr_market.get_last_trade_price() or 0)
            except Exception:  # noqa: BLE001
                report_exception()
        return self._usdt_price

    @property
    def prices_binance(self):
        if self._prices_binance is None:
            self._prices_binance = cache.get('binance_prices') or {}
        return self._prices_binance

    @staticmethod
    def set_celery_queues():
        queues = set()
        for task_route in settings.CELERY_TASK_ROUTES.values():
            if 'queue' in task_route:
                queues.add(task_route['queue'])
        queues.add('celery')
        queues.add('telegram_admin')
        return list(queues)

    @staticmethod
    def transform_metric(metric: MetricSchema) -> Dict[str, Any]:
        metric_name = metric.name
        if metric.labels:
            labels_str = ','.join([f'{k}="{v}"' for k, v in metric.labels.items()])
            metric_name = f'{metric.name}{{{labels_str}}}'
        return {metric_name: metric.value}

    def add_metric(self, **kwargs):
        self._metrics.append(MetricSchema(**kwargs))

    def is_module_selected(self, module: str) -> bool:
        if self.selected_modules is None:
            return True
        return module in self.selected_modules

    def set_user_level_metrics(self) -> None:
        try:
            users_by_level = User.objects.order_by('user_type').values('user_type').annotate(count=Count('user_type'))
            users_by_level = {d['user_type']: d['count'] for d in users_by_level}
            metrics = {
                f'{self._metric_prefix}registered_users_count': sum(users_by_level.values()),
                f'{self._metric_prefix}normal_users_count': users_by_level.get(User.USER_TYPES.normal, 0),
                f'{self._metric_prefix}level0_users_count': users_by_level.get(User.USER_TYPES.level0, 0),
                f'{self._metric_prefix}level1_users_count': users_by_level.get(User.USER_TYPES.level1, 0),
                f'{self._metric_prefix}level2_users_count': users_by_level.get(User.USER_TYPES.level2, 0),
                f'{self._metric_prefix}level3_users_count': users_by_level.get(User.USER_TYPES.verified, 0),
            }
            for metric, value in metrics.items():
                self.add_metric(type='gauge', name=metric, operation='set', value=value)

        except Exception:  # noqa: BLE001
            report_exception()

    def set_important_coins_price_metrics(self) -> None:
        metrics = {'price_usdt_irr': self.usdt_price}
        for currency in self.IMPORTANT_CURRENCIES:
            metrics[f'price_{currency}_usdt'] = self.prices_binance.get(currency) or 0
        for metric, value in metrics.items():
            self.add_metric(type='gauge', name=metric, operation='set', value=value)

    def set_market_prices_metrics(self) -> None:
        markets = Market.objects.all()
        for market in markets:
            src = get_currency_codename(market.src_currency)
            dst = get_currency_codename(market.dst_currency)
            symbol = market.symbol
            precision = PRICE_PRECISIONS.get(symbol, Decimal('0.01'))
            fmt = lambda k: (k or Decimal('0')).quantize(precision)  # noqa: B023, E731
            labels = {'src': src, 'dst': dst, 'symbol': symbol}
            add_market_metric = partial(self.add_metric, type='gauge', operation='set', labels=labels)
            add_market_metric(
                name=f'{self._metric_prefix}trades_count',
                value=cache.get(f'market_{market.id}_daily_count', 0),
            )
            add_market_metric(
                name=f'{self._metric_prefix}price',
                value=fmt(market.get_last_trade_price()),
            )
            add_market_metric(
                name=f'{self._metric_prefix}price_sell',
                value=fmt(cache.get(f'orderbook_{symbol}_best_active_sell')),
            )
            add_market_metric(
                name=f'{self._metric_prefix}price_buy',
                value=fmt(cache.get(f'orderbook_{symbol}_best_active_buy')),
            )
            # Global price
            binance_price = Decimal(self.prices_binance.get(src, 0))
            if market.dst_currency == RIAL:
                binance_price *= self.usdt_price
            if binance_price:
                add_market_metric(
                    name='binance_price',
                    value=fmt(binance_price),
                )

            mark_price = MarkPriceCalculator.get_mark_price(
                src_currency=market.src_currency,
                dst_currency=market.dst_currency,
            )
            add_market_metric(
                name='mark_price',
                value=fmt(mark_price),
            )

    def set_email_metrics(self) -> None:
        sent_email_status = SentEmail.objects.values('status').annotate(count=Count('*'))
        for status in sent_email_status:
            status_display = SentEmail.STATUS_CHOICES[status['status']][1]
            self.add_metric(
                type='gauge',
                name=f'{self._metric_prefix}emails',
                operation='set',
                value=status.get('count', 0),
                labels={'status': str(status_display)},
            )

    def set_celery_metrics(self) -> None:
        from exchange.celery import app

        for queue in self.CELERY_QUEUES:
            self.add_metric(
                type='gauge',
                name='celery_queue_len',
                operation='set',
                value=app.get_queue_len(queue),
                labels={'queue': queue},
            )

    def set_custom_metrics(self) -> None:
        self.add_metric(
            type='gauge',
            name='trade_processor_last_trade',
            operation='set',
            value=cache.get(f'{self._metric_prefix}tradeprocessor_last_trade_id') or 0,
        )

    def set_metrics(self) -> None:
        # User metrics
        if self.is_module_selected('userLevels'):
            self.set_user_level_metrics()

        # Global price of important coins
        if self.is_module_selected('importantPrices'):
            self.set_important_coins_price_metrics()

        # Market trade & price metrics
        if self.is_module_selected('marketPrices'):
            self.set_market_prices_metrics()

        # Email Metrics
        if self.is_module_selected('emails'):
            self.set_email_metrics()

        # Celery Tasks Monitoring
        if self.is_module_selected('celery'):
            self.set_celery_metrics()

        # Other metrics without standard format
        if self.is_module_selected('counters'):
            self.set_custom_metrics()

    def send_metrics(self):
        """Send periodic metrics to kafka"""
        for metric in self._metrics:
            metric_producer.write_event(
                Topics.METRIC,
                event=metric.serialize(),
                key=metric.name,
                on_error=broker_on_error,
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics in key value format to be scraped by prometheus"""
        metrics = {}
        for metric in self._metrics:
            metrics.update(PeriodicMetricsCalculator.transform_metric(metric))
        return metrics

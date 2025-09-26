from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar, Optional, Union

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic.detail import SingleObjectMixin
from django_ratelimit.decorators import ratelimit
from model_utils import Choices

from exchange.accounts.models import User
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.api import APIView, NobitexAPIError, email_required_api
from exchange.base.constants import ZERO
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import paginate
from exchange.base.logging import metric_incr
from exchange.base.models import CURRENCY_CODENAMES, PRICE_PRECISIONS, get_market_symbol
from exchange.base.parsers import parse_choices, parse_currency, parse_int, parse_money
from exchange.margin.models import Position, PositionFee
from exchange.margin.parsers import parse_extension_days, parse_leverage, parse_pnl_percent, parse_position_side
from exchange.margin.services import MarginCalculator, MarginManager
from exchange.market.marketmanager import MarketManager
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order
from exchange.market.parsers import parse_market, parse_order_type
from exchange.market.views import OrderCreateView
from exchange.pool.models import LiquidityPool, PoolAccess

if TYPE_CHECKING:
    from django.db.models import QuerySet


class MarginMarketListView(APIView):
    permission_classes: ClassVar = []

    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='marginMarketList'))
    def get(self, request):
        """View markets supporting margin trading

        This endpoint shows available margin markets based on pools state and user level.
        It can be accessed in both public mode and authorized mode. In the latter, user's
        access to private pools is taken into account and market max leverage is accurate
        according to user level. When using public mode, markets visible to level 1 users
        are shown with max leverage possible.

            URL:
                GET /margin/markets/list

            Request Headers:
                Authorization: user token -- optional

            Response Params:
                markets: dictionary of markets' symbol and config
        """
        markets = {}
        is_authenticated = request.user.is_authenticated
        pool_currencies = LiquidityPool.get_pools(
            user=request.user if is_authenticated else User(user_type=User.USER_TYPES.level1),
            access_type=PoolAccess.ACCESS_TYPES.trader,
            is_active=True,
        ).values_list('currency', flat=True)
        pool_currencies = list(pool_currencies)
        user_max_leverage = MarginManager.get_user_max_leverage(request.user) if is_authenticated else Decimal('Inf')

        active_margin_markets = Market.objects.filter(is_active=True, allow_margin=True).filter(
            Q(src_currency__in=pool_currencies) | Q(dst_currency__in=pool_currencies)
        )
        src_currencies = {market.src_currency for market in active_margin_markets}
        position_fees_map = PositionFee.fetch_fee_rates(src_currencies)
        for market in active_margin_markets:
            markets[market.symbol] = {
                'srcCurrency': CURRENCY_CODENAMES[market.src_currency].lower(),
                'dstCurrency': CURRENCY_CODENAMES[market.dst_currency].lower(),
                'positionFeeRate': position_fees_map[market.src_currency],
                'maxLeverage': min(market.max_leverage, user_max_leverage),
                'sellEnabled': market.src_currency in pool_currencies,
                'buyEnabled': market.dst_currency in pool_currencies,
            }

        return self.response(
            {
                'status': 'ok',
                'markets': markets,
            }
        )


class MarginFeeRatesListView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        """View position fee rate for Currencies available in active pools

        URL:
            GET /margin/fee-rates

        Request Headers:
            Authorization: user token -- optional

        Response Params:
            feeRates: dictionary of pools' currencies and their fee rates
        """
        pool_currencies = LiquidityPool.get_pools(
            user=request.user,
            access_type=PoolAccess.ACCESS_TYPES.trader,
            is_active=True,
        ).values_list('currency', flat=True)
        pool_currencies = list(pool_currencies)

        position_fees_map = PositionFee.fetch_fee_rates(pool_currencies)
        fee_rates = [
            {'currency': CURRENCY_CODENAMES[currency].lower(), 'positionFeeRate': position_fees_map[currency]}
            for currency in pool_currencies
        ]

        return self.response(
            {
                'status': 'ok',
                'feeRates': fee_rates,
            }
        )


class MarginDelegationLimitView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='12/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='marginDelegationLimit'))
    @method_decorator(email_required_api)
    def get(self, request):
        """GET /margin/delegation-limit"""
        currency = parse_currency(self.g('currency'), required=True)

        if not UserLevelManager.is_eligible_to_trade(self.request.user):
            raise NobitexAPIError('TradeLimitation')

        limit = MarginManager.get_user_pool_delegation_limit(request.user, currency=currency)

        return self.response({
            'status': 'ok',
            'limit': limit,
        })


@method_decorator(measure_api_execution(api_label='marginOrderCreate'), name='dispatch')
class MarginOrderCreateView(OrderCreateView):
    serialize_level = 3
    trade_type = Order.TRADE_TYPES.margin
    restrictions = ('Trading', 'Position')

    def _create_order(self, **kwargs) -> Order:
        leverage = parse_leverage(self.g('leverage'))
        try:
            return MarginManager.create_margin_order(**kwargs, leverage=leverage)
        except NobitexAPIError as e:
            if self.is_from_unsupported_app('long_buy'):
                metric_incr('metric_position_old_version_requests', labels=('margin_order_add',))
                if e.code == 'ExceedDelegationLimit':
                    raise NobitexAPIError('ExceedSellLimit', 'Amount Exceeds Sell Limit') from e

            if e.code == 'AmountUnavailable':
                symbol = get_market_symbol(kwargs['src_currency'], kwargs['dst_currency'])
                metric_incr(
                    'metric_amount_gt_pool_available_balance',
                    labels=(f'{symbol}', f"{Order.ORDER_TYPES[kwargs['order_type']]}"),
                )
            raise

    def get_initials(self) -> dict:
        if self.g('type'):
            return {}
        return {
            'order_type': Order.ORDER_TYPES.sell,
        }


class PositionFilterMixin:
    STATUS_CHOICES = Choices(
        ('active', 'Active'),
        ('past', 'Past'),
        ('all', 'All'),
    )

    def get_filtered_positions(
        self: Union[APIView, 'PositionFilterMixin'],
        status: str,
        src_currency: Optional[int] = None,
        dst_currency: Optional[int] = None,
        side: Optional[int] = None,
    ) -> 'QuerySet[Position]':
        positions = self.request.user.positions.exclude(opened_at=None).order_by('-id')
        if src_currency:
            positions = positions.filter(src_currency=src_currency)
        if dst_currency:
            positions = positions.filter(dst_currency=dst_currency)
        if side:
            positions = positions.filter(side=side)
        elif self.is_from_unsupported_app('long_buy'):
            metric_incr('metric_position_old_version_requests', labels=('position_list',))
            positions = positions.filter(side=Position.SIDES.sell)
        if status == self.STATUS_CHOICES.active:
            positions = positions.filter(pnl__isnull=True)
        elif status == self.STATUS_CHOICES.past:
            positions = positions.filter(pnl__isnull=False)
        return positions


class PositionsListView(PositionFilterMixin, APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/1m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='marginPositionList'))
    def get(self, request):
        """API for positions list

        GET /positions/list
        """
        src_currency = parse_currency(self.g('srcCurrency'))
        dst_currency = parse_currency(self.g('dstCurrency'))
        side = parse_position_side(self.g('side'))
        status = parse_choices(self.STATUS_CHOICES, self.g('status')) or self.STATUS_CHOICES.active

        positions = self.get_filtered_positions(status, src_currency, dst_currency, side)
        if status == self.STATUS_CHOICES.active:
            positions = positions.prefetch_related('orders')
        positions, has_next = paginate(positions, request=self, check_next=True, max_page=100, max_page_size=100)

        return self.response(
            {
                'status': 'ok',
                'positions': positions,
                'hasNext': has_next,
            },
            opts={'get_mark_price': lru_cache(MarkPriceCalculator.get_mark_price)},
        )


class ActivePositionsCountView(PositionFilterMixin, APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='15/1m', method='GET', block=True))
    def get(self, request):
        """API for active positions count

        GET /positions/active-count
        """
        count = self.get_filtered_positions(status=self.STATUS_CHOICES.active).count()

        return self.response(
            {
                'status': 'ok',
                'count': count,
            }
        )


class PositionStatusView(SingleObjectMixin, APIView):
    def get_queryset(self):
        return self.request.user.positions.exclude(status__in=(Position.STATUS.new, Position.STATUS.canceled))

    @method_decorator(ratelimit(key='user_or_ip', rate='100/10m', method='POST', block=True))
    def get(self, request, **_):
        """API for position status

            GET /positions/<pk>/status
        """
        position = self.get_object()
        return self.response({
            'status': 'ok',
            'position': position,
        })


class ActivePositionMixin(SingleObjectMixin):
    def get_queryset(self: Union[APIView, 'ActivePositionMixin']):
        return self.request.user.positions.filter(status=Position.STATUS.open)


@method_decorator(measure_api_execution(api_label='marginClosePosition'), name='dispatch')
class PositionCloseView(ActivePositionMixin, OrderCreateView):
    serialize_level = 3
    trade_type = Order.TRADE_TYPES.margin

    def _create_order(self, **kwargs) -> Order:
        for key in ('user', 'order_type', 'src_currency', 'dst_currency'):
            kwargs.pop(key, None)
        pid = self.kwargs.get(self.pk_url_kwarg)
        return MarginManager.create_position_close_order(pid, **kwargs)

    def get_initials(self):
        position = self.get_object()
        return {
            'order_type': Order.ORDER_TYPES.buy,
            'src_currency': position.src_currency,
            'dst_currency': position.dst_currency,
        }


class PositionCollateralEditOptionsView(ActivePositionMixin, APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='60/1m', method='GET', block=True))
    def get(self, request, **_):
        """API for acceptable range of collateral for edit

            GET /positions/<pk>/edit-collateral/options
        """
        position = self.get_object()
        min_collateral, max_collateral = MarginManager.get_position_collateral_range(position)
        return self.response({
            'status': 'ok',
            'collateral': {
                'min': min_collateral,
                'max': max_collateral,
            },
        })


class PositionCollateralEditView(ActivePositionMixin, APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='60/1m', method='POST', block=True))
    @method_decorator(measure_api_execution(api_label='marginCollateralEdit'))
    def post(self, request, **_):
        """API for editing position collateral

            POST /positions/<pk>/edit-collateral
        """
        collateral = parse_money(self.g('collateral'), required=True, allow_zero=True, field=Position.collateral)

        position_id = self.get_object().id
        position = MarginManager.change_position_collateral(position_id, new_collateral=collateral)

        return self.response({
            'status': 'ok',
            'position': position,
        })


class MarginCalculatorView(APIView):
    permission_classes = ()  # Both public and authenticated -- varies in trade fee rate

    @method_decorator(ratelimit(key='user_or_ip', rate='200/1m', method='POST', block=True))
    def post(self, request, mode):
        """API for position calculator

            GET /margin/calculator/<str:mode>
            mode: pnl | exit-price | liquidation-price
        """
        if mode not in ('pnl', 'exit-price', 'liquidation-price'):
            raise Http404()

        market = parse_market(self.g('symbol'), required=True)
        side = parse_position_side(self.g('side')) or Position.SIDES.sell
        entry_price = parse_money(self.g('entryPrice'), required=True)
        extension_days = parse_extension_days(self.g('extensionDays'))
        leverage = parse_leverage(self.g('leverage'))

        if request.user.is_authenticated:
            trade_fee_rate = MarketManager.get_trade_fee(market, request.user)
        else:
            trade_fee_rate = MarketManager.get_trade_fee(market)
        calculator = MarginCalculator(side, leverage, entry_price, extension_days, trade_fee_rate)
        precision = PRICE_PRECISIONS.get(market.symbol, Decimal('1E-8'))

        if mode == 'pnl':
            exit_price = parse_money(self.g('exitPrice'), required=True)
            amount = parse_money(self.g('amount'), required=True)
            pnl = calculator.get_pnl(exit_price, amount)
            pnl_percent = calculator.get_pnl_percent(pnl, amount)
            data = {
                'PNL': pnl.quantize(precision),
                'PNLPercent': pnl_percent.quantize(Decimal('1E-1')),
            }
        elif mode == 'exit-price':
            pnl_percent = parse_pnl_percent(self.g('PNLPercent'), required=True)
            exit_price = calculator.get_exit_price(pnl_percent)
            data = {
                'exitPrice': exit_price.quantize(precision),
            }
        else:
            amount = parse_money(self.g('amount'), required=True)
            added_collateral = parse_money(self.g('addedCollateral')) or ZERO
            liquidation_price = calculator.get_liquidation_price(market, amount, added_collateral)
            data = {
                'liquidationPrice': liquidation_price.quantize(precision),
            }
        return self.response({'status': 'ok', **data})


@method_decorator(ratelimit(key='user_or_ip', rate='60/1m', block=True), name='dispatch')
class MarginPredictView(ActivePositionMixin, APIView):
    """API for informative data calculations

    Useful in any UI-related calculations for margin values.
    """

    def get(self, request, category):
        """GET /margin/predict/<str:category>"""
        method_name = f'predict_{category.replace("-", "_")}'
        if not hasattr(self, method_name):
            raise Http404()
        return getattr(self, method_name)()

    def post(self, request, category):
        """POST /margin/predict/<str:category>"""
        return self.get(request, category)

    def predict_edit_collateral(self):
        """Predict effects of a collateral edit

            GET /margin/predict/edit-collateral

            positionId: position id
            Any of the two:
                - add: the amount to be added to collateral
                - sub: the amount to be subtracted from collateral
        """
        position_id = parse_int(self.g('positionId'), required=True)
        collateral_change = parse_money(self.g('add')) or -parse_money(self.g('sub'), required=True)

        position = get_object_or_404(self.get_queryset(), id=position_id)
        position.collateral = max(position.collateral + collateral_change, 0)
        position.set_liquidation_price()

        return self.response({
            'status': 'ok',
            'collateral': position.collateral,
            'marginRatio': position.margin_ratio,
            'liquidationPrice': position.liquidation_price,
        })

    def predict_add_order(self):
        """Predict fees and blocked values on adding a margin order

            POST /margin/predict/add-order

            srcCurrency, dstCurrency, amount, price: /margin/orders/add params
        """
        src_currency = parse_currency(self.g('srcCurrency'), required=True)
        dst_currency = parse_currency(self.g('dstCurrency'), required=True)
        order_type = parse_order_type(self.g('type')) or Order.ORDER_TYPES.sell
        leverage = parse_leverage(self.g('leverage'))
        amount = parse_money(self.g('amount'), required=True)
        price = max(parse_money(self.g(key)) or ZERO for key in ('price', 'stopPrice', 'stopLimitPrice'))

        position = Position(
            id=0,
            user=self.request.user,
            src_currency=src_currency,
            dst_currency=dst_currency,
            delegated_amount=amount,
            side=order_type,
        )
        MarginManager._check_market(position.market, use_200_status_code=False)

        position.collateral = MarginManager.get_collateral(position.market, leverage, order_type, amount, price)
        if position.is_short:  # for extension fee calculation
            position.entry_price = position.collateral * leverage / amount
            trade_fee = position.trade_fee_rate * position.collateral * leverage
        else:
            position.earned_amount = -position.collateral * leverage
            trade_fee = position.trade_fee_rate * amount

        return self.response({
            'status': 'ok',
            'collateral': position.collateral,
            'tradeFee': trade_fee,
            'extensionFee': position.extension_fee_amount,
        })

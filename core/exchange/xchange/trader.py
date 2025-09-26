""" Xchange Trade Matcher """
import datetime
import decimal
import functools
from decimal import ROUND_DOWN

from django.conf import settings
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.logging import report_event
from exchange.base.models import get_currency_codename
from exchange.base.money import quantize_number
from exchange.base.strings import _t
from exchange.wallet.helpers import (
    RefMod,
    create_and_commit_system_user_transaction,
    create_and_commit_transaction,
    has_balance,
)
from exchange.xchange import exceptions
from exchange.xchange.constants import GET_MISSED_CONVERSION_STATUS_COUNTDOWN
from exchange.xchange.helpers import get_exchange_trade_kwargs_from_quote, get_market_maker_system_user
from exchange.xchange.marketmaker.convertor import Convertor
from exchange.xchange.marketmaker.quotes import Estimator
from exchange.xchange.models import ExchangeTrade, MarketStatus
from exchange.xchange.tasks import get_missed_conversion_status_task
from exchange.xchange.types import Quote, RequiredCurrenciesInConvert


class XchangeTrader:
    """ Matcher for Xchange Trades"""
    QUOTE_CACHE_KEY_TEMPLATE = 'XCHANGE_QUOTE_{}'
    QUOTE_TTL = datetime.timedelta(seconds=settings.XCHANGE_PRICE_GUARANTEE_TTL)

    @classmethod
    def get_quote(
        cls,
        currencies: RequiredCurrenciesInConvert,
        is_sell: bool,
        amount: decimal.Decimal,
        user: User,
        market_status: MarketStatus,
    ):
        amount = cls._adjust_requested_amount_with_market_status(currencies, amount, market_status)
        return Estimator.estimate(
            base_currency=currencies.base,
            quote_currency=currencies.quote,
            is_sell=is_sell,
            amount=amount,
            user_id=user.id,
            reference_currency=currencies.ref,
        )

    @classmethod
    def _adjust_requested_amount_with_market_status(
        cls, currencies: RequiredCurrenciesInConvert, amount: decimal.Decimal, market_status: MarketStatus
    ) -> decimal.Decimal:
        if currencies.ref == currencies.base:
            min_amount = market_status.min_base_amount
            max_amount = market_status.max_base_amount
            precision = market_status.base_precision
        else:
            min_amount = market_status.min_quote_amount
            max_amount = market_status.max_quote_amount
            precision = market_status.quote_precision
        if amount < min_amount:
            raise exceptions.InvalidQuoteAmount(
                f'Amount should be more than {quantize_number(min_amount, precision.normalize())}'
            )
        amount = min(amount, max_amount)
        adjusted_amount = quantize_number(amount, precision=precision.normalize(), rounding=ROUND_DOWN)
        return adjusted_amount

    @classmethod
    @transaction.atomic
    def create_trade(
        cls,
        user_id: int,
        quote_id: str,
        user_agent: int,
        *,
        bypass_market_limit_validation=False,
        allow_user_wallet_negative_balance=False,
    ) -> ExchangeTrade:
        quote = Estimator.get_quote(quote_id, user_id)
        if quote.user_id != user_id:
            report_event('Convert.QuoteWontMatchUser', extras={'user_id': user_id})
            raise exceptions.QuoteIsNotAvailable('Invalid Quote')

        market_status = MarketStatus.get_available_market_status_based_on_side_filter(
            quote.base_currency,
            quote.quote_currency,
            is_sell=quote.is_sell,
        )

        if market_status is None:
            raise exceptions.MarketUnavailable('Market is not available.')

        if not bypass_market_limit_validation:
            cls._check_market_limitations(market_status, user_id, quote)

        cls._check_balances(user_id, quote)

        exchange_trade = ExchangeTrade.objects.create(
            **{
                **get_exchange_trade_kwargs_from_quote(quote),
                'user_id': user_id,
                'user_agent': user_agent,
            },
        )
        try:
            conversion = Convertor.call_conversion_api(quote)
            exchange_trade.convert_id = conversion.convert_id
        except exceptions.ConversionTimeout:
            cls._schedule_get_conversion_task(exchange_trade.pk)
            Estimator.invalidate_quote(quote_id, user_id)
            return exchange_trade
        except exceptions.FailedConversion:
            raise

        cls.create_and_commit_wallet_transactions(
            exchange_trade,
            allow_user_wallet_negative_balance=allow_user_wallet_negative_balance,
        )

        Estimator.invalidate_quote(quote_id, user_id)
        return exchange_trade

    @classmethod
    def _check_market_limitations(cls, market_status: MarketStatus, user_id: int, quote: Quote):
        if market_status.has_market_exceeded_limit(quote.reference_amount, quote.is_sell, quote.reference_currency):
            raise exceptions.MarketLimitationExceeded('Market limitation exceeded.')
        if market_status.has_user_exceeded_limit(
            user_id,
            quote.reference_amount,
            quote.is_sell,
            quote.reference_currency,
        ):
            raise exceptions.UserLimitationExceeded('User limitation exceeded.')

    @classmethod
    def _schedule_get_conversion_task(cls, trade_id: int):
        transaction.on_commit(
            functools.partial(
                get_missed_conversion_status_task.apply_async,
                args=(trade_id, 0),
                countdown=GET_MISSED_CONVERSION_STATUS_COUNTDOWN,
            )
        )

    @classmethod
    def create_and_commit_wallet_transactions(
        cls,
        trade: ExchangeTrade,
        *,
        allow_user_wallet_negative_balance=False,
    ):

        giving_currency = _t(get_currency_codename(trade.dst_currency))
        receiving_currency = _t(get_currency_codename(trade.src_currency))
        if trade.is_sell:
            giving_currency, receiving_currency = receiving_currency, giving_currency
        transactions_description = f'تبدیل {giving_currency} به {receiving_currency}'

        user_src_transaction_amount = (-1 if trade.is_sell else 1) * trade.src_amount
        user_dst_transaction_amount = (1 if trade.is_sell else -1) * trade.dst_amount
        try:
            trade.src_transaction = create_and_commit_transaction(
                user_id=trade.user_id,
                currency=trade.src_currency,
                amount=user_src_transaction_amount,
                ref_module=RefMod.convert_user_src,
                ref_id=trade.id,
                description=transactions_description,
                allow_negative_balance=allow_user_wallet_negative_balance,
            )
            trade.dst_transaction = create_and_commit_transaction(
                user_id=trade.user_id,
                currency=trade.dst_currency,
                amount=user_dst_transaction_amount,
                ref_module=RefMod.convert_user_dst,
                ref_id=trade.id,
                description=transactions_description,
                allow_negative_balance=allow_user_wallet_negative_balance,
            )
        except ValueError as e:
            raise exceptions.FailedAssetTransfer('Invalid wallet of insufficient balance.') from e

        try:
            trade.system_src_transaction = create_and_commit_system_user_transaction(
                user_id=get_market_maker_system_user().id,
                currency=trade.src_currency,
                amount=-user_src_transaction_amount,
                ref_module=RefMod.convert_system_src,
                ref_id=trade.id,
                description=transactions_description,
            )
            trade.system_dst_transaction = create_and_commit_system_user_transaction(
                user_id=get_market_maker_system_user().id,
                currency=trade.dst_currency,
                amount=-user_dst_transaction_amount,
                ref_module=RefMod.convert_system_dst,
                ref_id=trade.id,
                description=transactions_description,
            )
        except ValueError as e:
            raise exceptions.PairIsClosed('This pair is not convertible at the moment.') from e

        trade.status = ExchangeTrade.STATUS.succeeded
        trade.save()

    @classmethod
    def _check_balances(cls, user_id: int, quote: Quote) -> None:
        if quote.is_sell:
            user_required_currency = quote.base_currency
            user_required_amount = quote.base_amount
        else:
            user_required_currency = quote.quote_currency
            user_required_amount = quote.quote_amount

        if not has_balance(user_id, user_required_currency, user_required_amount):
            raise exceptions.FailedAssetTransfer('Insufficient balance.')

    @classmethod
    def trades_history(cls, user_id):
        return ExchangeTrade.objects.filter(user_id=user_id).order_by('-created_at')

    @classmethod
    def get_trade(cls, user_id: int, trade_id: int):
        return ExchangeTrade.objects.get(user_id=user_id, id=trade_id)

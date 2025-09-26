from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal


class BaseMarketStrategyInLimitation(ABC):
    def __init__(self, market: 'MarketStatus', input_amount: Decimal, is_sell: bool, reference_currency: int):
        """
        Base class for market strategies in limitations.
        :param market: The market status object.
        :param input_amount: The input amount from API.
        :param is_sell: Indicates if the transaction is a sell.
        :param reference_currency: The currency in which the amount is referenced.
        """
        self.market = market
        self.input_amount = input_amount
        self.reference_currency = reference_currency
        self.is_sell = is_sell
        if (
            self.reference_currency != self.market.base_currency
            and self.reference_currency != self.market.quote_currency
        ):
            raise ValueError('reference_currency must be equal to market.base_currency or market.quote_currency')

    @property
    @abstractmethod
    def amount(self) -> Decimal:
        """
        Calculates the amount to compare against the max_amount in MarketLimitation.
        :return: The calculated amount based on the strategy.
        """
        pass

    @property
    @abstractmethod
    def amount_field(self) -> str:
        """
        Retrieves the field name in ExchangeTrade used for summing trades over the interval.
        :return: The name of the amount field.
        """
        pass


class USDTRLSStrategyInLimitation(BaseMarketStrategyInLimitation):
    @property
    def amount(self) -> Decimal:
        """
        Calculates the amount for the USDTRLS market, ensuring it is based on USDT.
        In the USDTRLS market:
        - The base_currency is USDT.
        - The quote_currency is Rial (RLS).
        If the reference_currency is Rial (quote_currency), convert the input_amount to USDT,
        because the limitations are based on USDT.
        :return: The calculated amount in USDT.
        """
        if self.reference_currency == self.market.quote_currency:
            conversion_rate = (
                self.market.quote_to_base_price_sell if self.is_sell else self.market.quote_to_base_price_buy
            )
            return self.input_amount * conversion_rate
        return self.input_amount

    @property
    def amount_field(self) -> str:
        """
        Returns 'src_amount' as the amount field for summing trades.
        In this market, the source amount is USDT, and this market's limitation is based on USDT.
        :return: The name of the amount field ('src_amount').
        """
        return 'src_amount'


class DefaultStrategyInLimitation(BaseMarketStrategyInLimitation):
    @property
    def amount(self) -> Decimal:
        """
        Calculates the amount for markets.
        Typically:
        - The quote_currency is Rial (RLS) or USDT.
        If the reference_currency is the base_currency, convert the input_amount to the quote_currency,
        because limitations are based on the quote_currency.
        :return: The calculated amount in the quote_currency.
        """
        if self.reference_currency == self.market.base_currency:
            conversion_rate = (
                self.market.base_to_quote_price_sell if self.is_sell else self.market.base_to_quote_price_buy
            )
            return self.input_amount * conversion_rate
        return self.input_amount

    @property
    def amount_field(self) -> str:
        """
        Returns 'dst_amount' as the amount field for summing trades.
        In all markets except USDTRLS, the destination amount is Rial (RLS) or USDT,
        and limitations are based on the quote_currency.
        :return: The name of the amount field ('dst_amount').
        """
        return 'dst_amount'

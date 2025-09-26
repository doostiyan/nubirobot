from datetime import datetime, timedelta
from decimal import Decimal
from json import JSONDecodeError
from typing import Dict, Optional, Set

from django.db.models import Sum

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.logging import report_event
from exchange.base.models import TETHER, Settings
from exchange.base.parsers import parse_currency
from exchange.liquidator.models import LiquidationRequest
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, OrderMatching
from exchange.wallet.models import Wallet


class TradeFeeConversion:
    CONVERSION_CURRENCIES_RATE_KEY: str = 'conversion_currencies_rate_settings'
    CONVERSION_CURRENCIES_STARTTIME_KEY: str = 'conversion_currencies_starttime_settings'
    MINIMUM_VALUE_CONVERSION = 10

    @staticmethod
    def _get_dict_setting(key: str) -> Dict[str, str]:
        try:
            fee_currencies_settings = Settings.get_dict(key)
        except JSONDecodeError:
            report_event('InvalidJSON', extras={'key', key})
            return {}

        if not isinstance(fee_currencies_settings, dict):
            report_event('InvalidDict', extras={'key', key})
            return {}

        return fee_currencies_settings

    @classmethod
    def _convert_wallet_balance(
        cls,
        src_wallet: Wallet,
        dst_wallet: Wallet,
        start_date: datetime,
        end_date: datetime,
        fee_rate: Decimal,
    ) -> Optional[LiquidationRequest]:
        """
        Calculates the amount to convert from a source wallet based on collected fees
        and creates a LiquidationRequest if valid.

        This internal helper method determines the portion of fees collected in the
        `src_wallet`'s currency (between `start_date` and `end_date`) that
        should be converted. It then checks if this conversion is feasible
        based on the wallet's balance and a minimum conversion value in Tether.

        Args:
            src_wallet: The source `Wallet` object from which fees are converted.
            dst_wallet: The destination `Wallet` object (typically Tether) to which
                        the fees will be converted.
            start_date: The start datetime for calculating collected fees.
            end_date: The end datetime for calculating collected fees.
            fee_rate: The decimal rate to apply to the total collected fees
                      to determine the amount to convert.

        Returns:
            A `LiquidationRequest` object if the conversion is valid and meets
            all criteria (e.g., sufficient balance, minimum conversion value).
            Returns `None` if:
            - The calculated amount to convert exceeds the source wallet's balance.
            - No mark price is found for `src_wallet.currency` to Tether.
            - The USD equivalent of the amount to convert is less than `MINIMUM_VALUE_CONVERSION`.
        """
        fee_balance = (
            OrderMatching.objects.filter(
                market__src_currency=src_wallet.currency,
                created_at__lt=end_date,
                created_at__gte=start_date,
            ).aggregate(sum=Sum('buy_fee_amount'))['sum']
            or Decimal('0')
        )

        amount = fee_balance * fee_rate
        if amount > src_wallet.balance:
            report_event(
                'ConvertFeeInvalidBalanceError',
                extras={'wallet': src_wallet.id, 'currency': src_wallet.currency, 'amount': amount},
            )
            amount = min(amount, src_wallet.balance)

        price = MarkPriceCalculator.get_mark_price(src_wallet.currency, TETHER)
        if not price or amount * price < cls.MINIMUM_VALUE_CONVERSION:
            return None

        return LiquidationRequest(
            src_wallet=src_wallet,
            dst_wallet=dst_wallet,
            side=LiquidationRequest.SIDES.sell,
            amount=amount,
            service=LiquidationRequest.SERVICE_TYPES.fee_collector,
        )

    @staticmethod
    def _get_collector_wallets() -> Dict[int, Wallet]:
        user_fee = User.objects.get(username='system-fee')
        return {wallet.currency: wallet for wallet in Wallet.get_user_wallets(user_fee, tp=Wallet.WALLET_TYPE.spot)}

    @staticmethod
    def _get_existing_liquidation_requests(dst_wallet, start_time) -> Set[int]:
        return set(
            LiquidationRequest.objects.filter(
                dst_wallet=dst_wallet,
                created_at__gte=start_time,
                service=LiquidationRequest.SERVICE_TYPES.fee_collector,
            )
            .only('src_wallet__currency')
            .values_list('src_wallet__currency', flat=True),
        )

    @classmethod
    def run(cls):
        """
        Executes the conversion process for various currencies to Tether (USDT).

        This method processes fees for various currencies based on configured rates
        and converts them into the system's TETHER wallet. It ensures that fees
        for a specific currency on a given day are processed only once. The period
        for fee calculation is determined by a stored start time for each currency
        and an end time set to midnight of the current day.

        Steps:
        1.  Defines `end_time` as midnight of the current day.
        2.  Fetches conversion rate settings (`CONVERSION_CURRENCIES_RATE_KEY`) and
            the last processed start times for each currency
            (`CONVERSION_CURRENCIES_STARTTIME_KEY`).
        3.  Retrieves system fee collector wallets.
        4.  Checks for the existence of a TETHER collector wallet; exits if not found,
            reporting 'FeeConvertorNotFoundTetherWallet'.
        5.  Identifies currencies for which liquidation requests to TETHER already
            exist for the current `end_time`'s date using
            `_get_exist_liquidation_requests` to prevent reprocessing.
        6.  Iterates through each currency defined in the conversion rate settings:
            a.  Parses the currency and its conversion rate. Reports
                'FeeConvertorInvalidSettings' and skips on parsing errors.
            b.  Skips processing if the rate is zero or if a liquidation request
                for this currency to TETHER already exists for the current day.
                In such cases, updates the currency's start time in
                `start_time_currencies` to the current `end_time`.
            c.  If no stored start time exists for the currency, it defaults to
                one day before `end_time`. Stored start times are expected in
                ISO format.
            d.  Skips if the source currency wallet doesn't exist, has zero
                balance, or if its liquidation market to TETHER is disabled.
            e.  Calls `_convert_wallet_balance` to calculate the convertible fee
                amount and generate a `LiquidationRequest`. The start time passed
                is the ISO formatted string from `start_time_currencies`.
            f.  Appends valid `LiquidationRequest` objects to a list.
        7.  Bulk creates all generated `LiquidationRequest` objects in the database.
        8.  After successful creation, updates the `start_time_currencies` map for each
            processed currency to the current `end_time` (ISO format).
        9.  Persists the updated `start_time_currencies` map to settings using
            `Settings.set_dict` with `cls.CONVERSION_CURRENCIES_STARTTIME_KEY`.

        Reported Events (not exhaustive):
        - 'InvalidJSON', 'InvalidDict': For issues with settings retrieval.
        - 'FeeConvertorNotFoundTetherWallet': If system TETHER wallet is missing.
        - 'FeeConvertorInvalidSettings': For issues parsing currency/rate from settings.
        - (Via _convert_wallet_balance): 'ConvertFeeInvalidBalanceError',
          'FeeConvertorPriceError', 'InvalidStartDateISOFormat'.
        """

        end_time = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)

        convert_rate_currencies_settings: dict = cls._get_dict_setting(cls.CONVERSION_CURRENCIES_RATE_KEY)
        start_time_currencies: dict = cls._get_dict_setting(cls.CONVERSION_CURRENCIES_STARTTIME_KEY)

        wallets = cls._get_collector_wallets()

        if TETHER not in wallets:
            report_event('FeeConvertorNotFoundTetherWallet')
            return

        tether_wallet = wallets[TETHER]

        exist_liquidation_requests_currency = cls._get_existing_liquidation_requests(tether_wallet, end_time)

        liquidation_requests = []
        for currency, convert_rate_currency in convert_rate_currencies_settings.items():
            try:
                currency_id = parse_currency(currency)
                rate = Decimal(convert_rate_currency) if convert_rate_currency else 0
            except Exception:
                report_event(
                    'FeeConvertorInvalidSettings',
                    extras={'rate': convert_rate_currency, 'currency': currency},
                )
                continue

            if rate == 0 or currency_id in exist_liquidation_requests_currency:
                start_time_currencies[str(currency_id)] = end_time.isoformat()
                continue

            if str(currency_id) not in start_time_currencies:
                start_time_currencies[str(currency_id)] = (end_time - timedelta(days=1)).isoformat()

            wallet = wallets.get(currency_id)
            if (
                not wallet
                or wallet.balance == 0
                or not LiquidationRequest.is_market_enabled_in_liquidator(
                    Market(src_currency=currency_id, dst_currency=TETHER),
                )
            ):
                continue

            liquidation_request = cls._convert_wallet_balance(
                wallet,
                tether_wallet,
                start_time_currencies[str(currency_id)],
                end_time,
                rate,
            )
            if not liquidation_request:
                continue
            liquidation_requests.append(liquidation_request)

        LiquidationRequest.objects.bulk_create(liquidation_requests)
        for liquidation_request in liquidation_requests:
            start_time_currencies[str(liquidation_request.src_currency)] = end_time.isoformat()

        Settings.set_dict(cls.CONVERSION_CURRENCIES_STARTTIME_KEY, start_time_currencies)

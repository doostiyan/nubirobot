import datetime
import time
from typing import List

from django.db import transaction
from requests import HTTPError
from tqdm import tqdm

from exchange.base.calendar import get_latest_time, ir_today
from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.models import Currencies
from exchange.xchange.exceptions import ThereIsNoNewTradeError
from exchange.xchange.marketmaker.trade_history import GetTradeHistory
from exchange.xchange.models import ExchangeTrade, MarketMakerTrade
from exchange.xchange.types import MarketMakerTradeHistoryItem


class TradeCollector:
    """
    TradeCollector is responsible for fetching market maker trades from an external API,
    handling retries and errors, and upserting the retrieved data into the database.

    Class Attributes:
        guard (timedelta): A small time buffer subtracted from timestamps to avoid missing trades.
        max_retries (int): Maximum number of retry attempts when fetching data fails.
        retry_delay_seconds (int): Delay between retries in seconds.
        api_call_delay_seconds (int): Delay between each API call to avoid rate limits.
        page_size (int): Number of trade records to fetch per page from the API.
    """

    guard = datetime.timedelta(seconds=5)
    max_retries = 3
    retry_delay_seconds = 5
    api_call_delay_seconds = 1
    page_size = 1000

    def run(self):
        """
        Main method to start the trade collection process.
         The Market Maker Trade History API does not support traditional pagination using page and page_size parameters.
         Instead, data is fetched using a time window defined by from_date and to_date.
         Each API call is expected to return up to 1000 trades, which is the maximum allowed per request.
         To ensure continuity and avoid duplicates, the system retrieves the timestamp of the most recently stored trade and uses that as the new from_date for the next fetch cycle.
         This approach allows for consistent, incremental data collection.
                Steps:
                    - Determine the starting point for fetching trades using the last saved or first trade timestamp.
                    - Fetch trades in a paginated manner while handling retries and failures.
                    - Save trades to the database using bulk upsert operations.

                Raises:
                    Exception: If trade saving fails after retrieval.
        """
        yesterday = ir_today() - datetime.timedelta(days=1)
        to_date = get_latest_time(yesterday)
        has_next = True
        total_processed = 0

        with tqdm(desc='Fetching & saving trade pages', unit='page') as pbar:
            while has_next:
                last_trade = MarketMakerTrade.objects.order_by('-market_maker_created_at').first()
                if last_trade:
                    from_date = last_trade.market_maker_created_at - self.guard
                else:
                    first_trade = ExchangeTrade.objects.order_by('created_at').first()
                    from_date = first_trade.created_at - self.guard

                has_next, trades = self.fetch_trades_with_retry(
                    from_date=from_date,
                    to_date=to_date,
                )

                # Process the trades if fetch was successful
                try:
                    self.bulk_upsert_trades(trades)
                except Exception as e:
                    logstash_logger.error(
                        'Error saving market-maker trades.',
                        extra={
                            'params': {
                                'error': str(e),
                                'from_date': from_date.timestamp(),
                            },
                            'index_name': 'convert.save_marketmaker_trades',
                        },
                    )
                    raise

                processed_now = len(trades)
                total_processed += processed_now
                pbar.update(1)
                pbar.set_postfix(trades=processed_now)

                time.sleep(self.api_call_delay_seconds)

            pbar.set_postfix_str(f'done – {total_processed} trades total')

    def fetch_trades_with_retry(
        self, from_date: datetime, to_date: datetime, attempt=1
    ) -> (bool, List[MarketMakerTradeHistoryItem]):
        """
        Fetches trades from the external service with automatic retries on failure.

        Args:
            from_date (datetime): Start of the time range for which to fetch trades.
            to_date (datetime): End of the time range for which to fetch trades.
            attempt (int): Current retry attempt number.

        Returns:
            tuple: A boolean indicating if more pages are available, and a list of fetched trades.

        Raises:
            Exception: If the maximum number of retry attempts is exceeded or another fatal error occurs.
        """
        try:
            has_next, trades = GetTradeHistory(
                from_date=from_date, to_date=to_date, page_size=self.page_size
            ).get_trades_history()
            return has_next, trades

        except Exception as e:
            if isinstance(e, HTTPError) and hasattr(e, 'response'):
                error_msg = e.response.content.decode('utf-8')
            else:
                error_msg = str(e)
            logstash_logger.error(
                'Error fetching trades',
                extra={
                    'params': {
                        'attempt': attempt,
                        'from_data': from_date.timestamp(),
                        'to_data': to_date.timestamp(),
                        'error': error_msg,
                    },
                    'index_name': 'convert.fetch_marketmaker_trades',
                },
            )

            if attempt >= self.max_retries:
                logstash_logger.error(
                    'Max retries reached. Raising exception.',
                    extra={
                        'params': {'error': error_msg},
                        'index_name': 'convert.fetch_marketmaker_trades',
                    },
                )
                raise e
            else:
                time.sleep(self.retry_delay_seconds)
                return self.fetch_trades_with_retry(from_date, to_date, attempt=attempt + 1)

    @transaction.atomic
    def bulk_upsert_trades(self, trades: List[MarketMakerTradeHistoryItem]):
        """
        Performs a bulk upsert (update or insert) of the given trades into the database.

        Args:
            trades (List[MarketMakerTradeHistoryItem]): List of trade records to insert or update.

        Process:
            - Check if each trade already exists based on convert_id and client_id.
            - If exists, update specific fields (status and market_maker_response).
            - If not, create a new MarketMakerTrade object.
            - Perform bulk_create for new records and bulk_update for existing ones.

        Raises:
            ThereIsNoNewTradeError: If all trades are already present and up-to-date in the DB.
        """
        if not trades:
            return

        convert_ids = [t.convertId for t in trades]
        client_ids = [t.clientId for t in trades]
        # The Marketmaker said convert_ids are always unique, but I also check client_id
        existing_qs = MarketMakerTrade.objects.filter(convert_id__in=convert_ids, client_id__in=client_ids)
        existing_dict = {obj.convert_id: obj for obj in existing_qs}

        to_create = []
        to_update = []

        update_fields = [
            'status',
            'market_maker_response',
        ]

        for trade in trades:
            if trade.convertId in existing_dict:
                db_obj = existing_dict[trade.convertId]
                db_obj.status = trade.status
                db_obj.market_maker_response = trade.response or {}
                to_update.append(db_obj)
            else:
                new_obj = MarketMakerTrade(
                    convert_id=trade.convertId,
                    quote_id=trade.quoteId,
                    client_id=trade.clientId,
                    status=trade.status,
                    is_sell=(trade.side or '').lower() == 'sell',
                    base_currency=getattr(Currencies, trade.baseCurrency) if trade.baseCurrency else None,
                    quote_currency=getattr(Currencies, trade.quoteCurrency) if trade.quoteCurrency else None,
                    reference_currency=getattr(Currencies, trade.referenceCurrency)
                    if trade.referenceCurrency
                    else None,
                    reference_currency_amount=trade.referenceCurrencyAmount,
                    destination_currency_amount=trade.destinationCurrencyAmount,
                    market_maker_created_at=(
                        datetime.datetime.fromtimestamp(trade.createdAt / 1000, tz=datetime.timezone.utc)
                        if trade.createdAt
                        else None
                    ),
                    market_maker_response=trade.response or {},
                )
                to_create.append(new_obj)

        if to_create:
            MarketMakerTrade.objects.bulk_create(to_create, batch_size=500)

        if to_update:
            if len(to_update) == len(trades) == self.page_size:
                raise ThereIsNoNewTradeError('all market maker trades were created before')
            MarketMakerTrade.objects.bulk_update(to_update, fields=update_fields, batch_size=500)

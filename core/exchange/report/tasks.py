import datetime
from requests import HTTPError

from celery import shared_task

from exchange.base.logging import report_exception
from exchange.report.crons import SaveDailyDepositsV2, SaveDailyWithdrawsV2


@shared_task(name='fetch_jibit_history', max_retries=0)
def fetch_jibit_history(transaction_type: str, from_datetime: datetime.datetime, to_datetime: datetime.datetime):
    """
    Fetches transaction history data from Jibit for the specified transaction type
    within the given date range.

    Args:
        transaction_type (str): The type of transactions to fetch, either 'deposit' or 'withdraw'.
        from_datetime (datetime): The start date and time for the transaction history.
        to_datetime (datetime): The end date and time for the transaction history.

    Raises:
        ValueError: If an invalid transaction type is provided.
        HTTPError: If multiple consecutive HTTP errors are encountered while making API requests to Jibit.

    Note:
        This function uses a paginated approach to retrieve transaction data from Jibit,
        and it creates or updates corresponding records in the database.

    Examples:
        # Example 1: Call the Celery task directly
        fetch_jibit_history('deposit', datetime(2023, 1, 1), datetime(2023, 1, 31))

        # Example 2: Call the Celery task using celery_app.send_task
        try:
            transaction_type = 'withdraw'
            from_datetime = datetime(2023, 2, 1)
            to_datetime = datetime(2023, 2, 28)
            result = celery_app.send_task('admin.fetch_jibit_history',
             args=(transaction_type, from_datetime, to_datetime))
            print(f"Task sent with id: {result.id}")
        except Exception as e:
            print(f"Error: {e}")
    """
    if isinstance(from_datetime, str):
        from_datetime = datetime.datetime.fromisoformat(from_datetime)
    if isinstance(to_datetime, str):
        to_datetime = datetime.datetime.fromisoformat(to_datetime)
    if to_datetime <= from_datetime:
        raise ValueError('Invalid Report Range')
    if transaction_type not in ('deposit', 'withdraw'):
        raise ValueError('Invalid transaction type')
    cron = SaveDailyDepositsV2 if transaction_type == 'deposit' else SaveDailyWithdrawsV2
    cron.update_items(from_datetime, to_datetime)


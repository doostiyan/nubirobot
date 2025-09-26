import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.conf import Settings, settings
from django.core.management import CommandError
from django.core.management.base import BaseCommand
from django.utils.timezone import is_naive, now

from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.logstash_logging.loggers import logstash_logger as logger
from exchange.base.models import Settings, get_address_type_codename, get_currency_codename
from exchange.base.money import money_is_close_decimal
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.service_based import ServiceBasedExplorer
from exchange.wallet.models import ConfirmedWalletDeposit, Transaction

# Configs
MAX_WORKERS = 10
INDEX_NAME = 'data_correction'
PROVIDERS_CONFIGS = {  # todo: other networks must be added after testing the script
    'ONE': [
        {'provider': 'one_ankr_rpc', 'base_url': 'https://rpc.ankr.com/harmony'},
        {'provider': 'one_rpc_api', 'base_url': 'https://api.harmony.one'},
    ],
}
BULK_UPDATE_SIZE = 500


def log_info(message, extra=None):
    logger.info(message, extra={**(extra or {}), 'index_name': INDEX_NAME})


def log_error(message, extra=None):
    logger.error(message, extra={**(extra or {}), 'index_name': INDEX_NAME})


def fetch_tx_details(deposit: ConfirmedWalletDeposit) -> Optional[dict]:
    network = deposit.network
    tx_hash = deposit.tx_hash
    currency = deposit.wallet.currency

    providers = PROVIDERS_CONFIGS.get(network, [])
    if not providers:
        log_error('No providers configured for network', {"network": network})
        return None

    providers_shuffled = providers[:]
    random.shuffle(providers_shuffled)

    attempts = 2 * len(providers_shuffled)
    i = 0

    for attempt in range(attempts):
        provider_config = providers_shuffled[i % len(providers_shuffled)]
        i += 1

        try:
            result = ServiceBasedExplorer.get_transactions_details(
                tx_hashes=[tx_hash],
                provider=provider_config.get('provider'),
                base_url=provider_config.get('base_url'),
                network=network,
                currency=currency,
            )
            if not result:
                log_info(
                    'empty-response',
                    extra={
                        'deposit_pk': deposit.pk,
                        'tx_ref_module': deposit.transaction.ref_module if deposit.transaction else None,
                        'provider': provider_config.get('provider'),
                        'base_url': provider_config.get('base_url'),
                    },
                )
            result = result[list(result.keys())[0]]
            if result.get('success') and (result.get('transfers') or result.get('inputs')):
                return result
        except Exception as e:  # noqa: BLE001
            log_info(
                'retry-tx-detail-fail',
                extra={
                    'attempt': attempt + 1,
                    'attempts': attempts,
                    'provider': provider_config['provider'],
                    'deposit_pk': deposit.pk,
                    'error': str(e),
                },
            )

    return None


def check_and_update_rechecked(deposit, tx_details, deposit_updating_data):
    if deposit.rechecked:
        log_info('checked-already-set', extra=deposit_updating_data)
        return

    diff_check_is_ok: bool = True
    transfers = tx_details.get('transfers', [])
    value = Decimal(0)
    for transfer in transfers:
        currency = transfer.get('currency')
        network_key = deposit.address.network or CURRENCY_INFO[currency]['default_network']
        if transfer['to'] == deposit.address.address:
            value += transfer.get('value')
            network_deposit_info = (
                CURRENCY_INFO[currency]['network_list'][network_key]
                .get('deposit_info', {})
                .get(get_address_type_codename(deposit.address.type), {})
            )
            if settings.DEPOSIT_FEE_ENABLED:
                value -= Decimal(network_deposit_info.get('deposit_fee', '0.00000000'))

            if (
                deposit.contract_address
                and deposit.contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys()
            ):
                value -= Decimal(
                    Settings.get(
                        f'deposit_fee_{get_currency_codename(deposit.currency)}_{deposit.network.lower()}_{deposit.contract_address}',
                        '0',
                    )
                )

    if not money_is_close_decimal(value, deposit.amount, decimals=8):
        diff_check_is_ok = False

    tx_details_memo = str(tx_details.get('memo')).strip()
    if tx_details_memo.isnumeric():
        try:
            tx_details_memo = str(int(tx_details_memo))
        except:
            diff_check_is_ok = False

    if deposit.tag and str(deposit.tag.tag).strip() != tx_details_memo:
        diff_check_is_ok = False

    if diff_check_is_ok:
        deposit_updating_data['rechecked'] = deposit_updating_data['must_update'] = True
    else:
        log_info('deposit-diff-fail', extra=deposit_updating_data)


def check_and_update_tx_datetime(deposit, tx_details, deposit_updating_data):
    tx_datetime: datetime = tx_details.get('date')
    if not tx_datetime:
        log_info('provider-tx-detail-empty', extra=deposit_updating_data)
        return

    if (
        not deposit.tx_datetime
        or (deposit.tx_datetime > deposit.created_at)
        or (not isinstance(deposit.tx_datetime, datetime))
        or is_naive(deposit.tx_datetime)
    ):
        try:
            deposit_updating_data['must_update'] = True
            deposit_updating_data['tx_datetime'] = datetime.strftime(tx_datetime, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            log_info('invalid-date-format', extra={**deposit_updating_data, 'invalid_date': tx_datetime})

    else:
        log_info('tx-datetime-already-set', extra=deposit_updating_data)


def check_and_update_source_addresses(deposit, tx_details, deposit_updating_data):
    if deposit.source_addresses:
        log_info('source-addresses-already-set', extra=deposit_updating_data)
        return

    source_addresses = defaultdict(lambda: defaultdict())
    for transfer in tx_details.get('transfers', []):
        if addr := transfer.get('from'):
            source_addresses[addr] = defaultdict()

    if source_addresses:
        deposit_updating_data['source_addresses'] = source_addresses
        deposit_updating_data['must_update'] = True
    else:
        log_info('deposit-source_address_finding-fail', extra=deposit_updating_data)


class Command(BaseCommand):
    """
    Management command to fix malformed data in ConfirmedWalletDeposit records using the Explorer API.

    This script performs the following operations:
    1. Filters deposits for a given network created within the last X days.
    2. Excludes internal and manual deposits.
    3. Uses multiple RPC/API providers to fetch transaction details concurrently via a thread pool.
    4. Validates and optionally updates the following fields for each deposit:
       - `rechecked`: Set to True if deposit amount and tag match the fetched transaction data, and
        if not already present
       - `tx_datetime`: Filled in if missing and provided by the Explorer API.
       - `source_addresses`: Extracted from transaction transfer data if not already present.

    The command logs each update decision and tracks failed fetch attempts. Updates are currently prepared but not
    written to the database (bulk update code is commented out).

    Usage:
        python manage.py <command_name> --network=<NETWORK>

    Args:
        --network: The blockchain network name to filter deposits (e.g., ONE, ETH, BTC).

    Note:
        - Only the `ONE` network is currently configured with multiple providers.
        - Bulk update to the database is disabled; uncomment relevant sections to enable.
    """
    help = 'Fix malformed data for ConfirmedWalletDeposit using Explorer API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            help='Network to filter deposits by (e.g., ETH, TRX, BTC, DOGE)',
        )

    def handle(self, *args, **options):
        network = options.get('network')
        if not network:
            raise CommandError('network is required')
        log_info('start-of-script', extra={'network': network})

        deposits = list(
            ConfirmedWalletDeposit.objects.using(settings.READ_DB)
            .select_related('address', '_wallet')
            .filter(
                confirmed=True,
                address__network=network,  # todo tag based?
                created_at__gte=now() - timedelta(days=7),  # for testing, we first want to check the last 7 days data
                created_at__lte=now() - timedelta(days=1),  # exclude the previous day due to the deposit flow
            ).
            exclude(
                transaction__ref_module__in=[  # Internal and Manual Deposits
                    Transaction.REF_MODULES['InternalTransferDeposit'],
                    Transaction.REF_MODULES['ManualDepositRequest'],
                ],
                tx_hash__icontains='nobitex-internal-W',
            )
            .order_by('-created_at')
        )

        deposits = list(set(deposits))
        log_info(f'count-of-deposits', {'deposits': len(deposits)})

        failed = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_deposit = {executor.submit(fetch_tx_details, deposit): deposit for deposit in deposits}

            for future in as_completed(future_to_deposit):
                deposit: ConfirmedWalletDeposit = future_to_deposit[future]
                try:
                    tx_details: dict = future.result()
                    if not tx_details:
                        log_error('no-tx-detail', {'pk': deposit.pk})
                        failed.append(deposit.pk)
                        continue

                    deposit_updating_data: dict = {
                        'pk': deposit.pk,
                        'must_update': False,
                    }

                    # 1. check diff
                    check_and_update_rechecked(
                        deposit=deposit,
                        tx_details=tx_details,
                        deposit_updating_data=deposit_updating_data,
                    )

                    # 2. check missing tx_datetime
                    check_and_update_tx_datetime(
                        deposit=deposit,
                        tx_details=tx_details,
                        deposit_updating_data=deposit_updating_data,
                    )

                    # 3. check source_addresses field
                    check_and_update_source_addresses(
                        deposit=deposit,
                        tx_details=tx_details,
                        deposit_updating_data=deposit_updating_data,
                    )

                    log_info('deposit-update', extra=deposit_updating_data)

                except Exception as e:
                    log_info(
                        'Exception during processing deposit',
                        {
                            'pk': deposit.pk,
                            'error': str(e),
                        },
                    )
                    failed.append(deposit.pk)

        log_info(
            'end-of-the-script',
            {
                'network': network,
            },
        )

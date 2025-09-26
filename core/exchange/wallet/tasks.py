import datetime
from decimal import Decimal
from typing import List, Optional, Type

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import connections, transaction
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.audit.models import ExternalWallet, ExternalWithdraw
from exchange.base.connections import CONTRACT_CLIENT
from exchange.base.decorators import measure_time_cm
from exchange.base.emailmanager import EmailManager
from exchange.base.helpers import export_csv
from exchange.base.id_translation import encode_id
from exchange.base.logging import report_event, report_exception
from exchange.base.models import (
    ADDRESS_TYPE,
    BABYDOGE,
    CURRENCY_CODENAMES,
    Currencies,
    get_address_type_codename,
    get_currency_codename,
)
from exchange.base.parsers import parse_str, parse_timestamp
from exchange.base.serializers import serialize
from exchange.base.settings import NobitexSettings
from exchange.blockchain.contracts_conf import CONTRACT_INFO
from exchange.blockchain.models import MAIN_TOKEN_CURRENCIES_INFO
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.wallet.deposit import refresh_address_deposits
from exchange.wallet.functions import external_withdraw_log
from exchange.wallet.models import (
    AvailableHotWalletAddress,
    ConfirmedWalletDeposit,
    Transaction,
    TransactionHistoryFile,
    Wallet,
    WalletDepositAddress,
    WithdrawRequest,
)
from exchange.wallet.settlement import BaseSettlement, JibitSettlement, JibitSettlementV2, settle_withdraw


@shared_task(name='refresh_currency_deposits', max_retries=1)
def refresh_currency_deposits(email, currency):
    addresses = WalletDepositAddress.objects.filter(currency=currency, wallet__user__email=email)
    for address in addresses:
        refresh_address_deposits(address)


@shared_task(name='refresh_address_deposits', max_retries=1)
def task_refresh_currency_deposits(address, currency):
    address = WalletDepositAddress.objects.filter(currency=currency, address=address).first()
    if not address:
        return
    refresh_address_deposits(address, retry=True)


@shared_task(name='refresh_available_hot_wallet_address', max_retries=1)
def refresh_available_hot_wallet_address(address):
    addresses = AvailableHotWalletAddress.objects.filter(address=address)
    for address in addresses:
        address.update_balance()


@shared_task(name='get_jibit_withdraw_bank_ids', max_retries=1)
def get_jibit_withdraw_bank_ids():
    incomplete_withdraw_requests = list(WithdrawRequest.objects.filter(
        status=WithdrawRequest.STATUS.sent,
        target_account__isnull=False,
        created_at__gte=now() - datetime.timedelta(hours=2),
        created_at__lte=now() - datetime.timedelta(minutes=10)
    ).order_by('id')[:20])
    if not incomplete_withdraw_requests:
        return
    start_date = incomplete_withdraw_requests[0].created_at
    end_date = incomplete_withdraw_requests[-1].created_at
    jibit_transfers = JibitSettlement.get_transfers_by_date(start_date, end_date, 20)
    jibit_transfers += JibitSettlementV2.fetch_withdraws(start_date, end_date, size=20, done=True)
    for withdraw in incomplete_withdraw_requests:
        jibit_transfer = next((item for item in jibit_transfers if str(item.get('transferID')) == str(withdraw.id)), {})
        if jibit_transfer and jibit_transfer.get('bankTransferID'):
            withdraw.blockchain_url = jibit_transfer['bankTransferID']
            withdraw.save(update_fields=['blockchain_url'])


@shared_task(name='refresh_bnb_external_withdraw_log_range_time', max_retries=1)
def refresh_bnb_external_withdraw_log_in_range_time(date=None):
    from_datetime = None
    to_datetime = None
    if date:
        from_time = datetime.datetime.min.time()
        to_time = datetime.datetime.max.time()

        # from_datetime in Milliseconds
        from_datetime = int(datetime.datetime.combine(date, from_time).timestamp() * 1000)

        # to_datetime in Milliseconds
        to_datetime = int(datetime.datetime.combine(date, to_time).timestamp() * 1000)
    bnb_wallet_address = AvailableHotWalletAddress.objects.filter(currency=Currencies.bnb)
    for wallet_address in bnb_wallet_address:
        transactions_info = {}
        api_session = requests.Session()
        api_session.proxies.update(settings.DEFAULT_PROXY)
        api_session.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0'
        try:
            url = f'https://dex.binance.org/api/v1/transactions?address={wallet_address.address}&limit=1000'
            url += f'&startTime={from_datetime}&endTime={to_datetime}' if date else ''
            transactions_info = api_session.get(url, timeout=7).json()
        except Exception as e:
            print('Failed to get BNB transactions from BNB API server: {}'.format(str(e)))
            report_event('Failed to get BNB transactions from BNB API server: {}'.format(str(e)),
                         level='error', module='transactions', category='general',
                         runner='withdraw', details='Address: {}'.format(wallet_address.address)
                         )

        for tx_info in transactions_info.get('tx'):
            if tx_info.get('fromAddr') != wallet_address.address:
                continue
            tx_hash = tx_info.get('txHash')
            created_at = tx_info.get('timeStamp')
            from_addr = tx_info.get('fromAddr')
            to_addr = tx_info.get('toAddr')
            amount = tx_info.get('value')
            tag = tx_info.get('tag')
            try:
                ExternalWithdraw.objects.get(currency=Currencies.bnb, tx_hash=tx_hash, destination=to_addr)
            except ExternalWithdraw.DoesNotExist:
                ExternalWithdraw.objects.create(
                    created_at=created_at,
                    source=ExternalWallet.objects.get_or_create(
                        name='Hot {} {}'.format(get_currency_codename(Currencies.bnb).upper(), from_addr),
                        currency=Currencies.bnb,
                        tp=ExternalWallet.TYPES.hot,
                    )[0],
                    destination=to_addr,
                    tx_hash=tx_hash,
                    tag=tag,
                    currency=Currencies.bnb,
                    amount=amount,
                )


@shared_task(name='refresh_trx_external_withdraw_log_range_time', max_retries=1)
def refresh_trx_external_withdraw_log_in_range_time(date=None):
    from_datetime = None
    to_datetime = None
    if date:
        from_time = datetime.datetime.min.time()
        to_time = datetime.datetime.max.time()

        # from_datetime in Milliseconds
        from_datetime = int(datetime.datetime.combine(date, from_time).timestamp() * 1000)

        # to_datetime in Milliseconds
        to_datetime = int(datetime.datetime.combine(date, to_time).timestamp() * 1000)
    trx_wallet_address = AvailableHotWalletAddress.objects.filter(currency=Currencies.trx)
    for wallet_address in trx_wallet_address:

        transactions_info = {}
        api_session = requests.Session()
        #api_session.proxies.update(settings.DEFAULT_PROXY)
        api_session.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64; rv:75.0) Gecko/20100101 Firefox/75.0'
        try:
            url = f'https://api.trongrid.io/v1/accounts/{wallet_address.address}/transactions/' \
                  f'trc20?only_confirmed=true&limit=200&only_from=true&page=1'
            url += f'&min_timestamp={from_datetime}&max_timestamp={to_datetime}' if date else ''
            transactions_info = api_session.get(url, timeout=7).json()
        except Exception as e:
            print('Failed to get BNB transactions from TRX API server: {}'.format(str(e)))
            report_event('Failed to get TRX transactions from BNB API server: {}'.format(str(e)),
                         level='error', module='transactions', category='general',
                         runner='withdraw', details='Address: {}'.format(wallet_address.address)
                         )

        while transactions_info:
            for tx_info in transactions_info.get('data'):
                if tx_info.get('from') != wallet_address.address or tx_info.get('value') == 0:
                    continue
                tx_hash = tx_info.get('transaction_id')
                created_at = parse_timestamp((tx_info.get('block_timestamp')/1000))
                from_addr = tx_info.get('from')
                to_addr = tx_info.get('to')
                amount = tx_info.get('value')
                tag = tx_info.get('tag')
                try:
                    ExternalWithdraw.objects.get(currency=Currencies.trx, tx_hash=tx_hash, destination=to_addr)
                    print('ExternalWithdraw', ExternalWithdraw)
                except ExternalWithdraw.DoesNotExist:
                    ExternalWithdraw.objects.create(
                        created_at=created_at,
                        source=ExternalWallet.objects.get_or_create(
                            name='Hot {} {}'.format(get_currency_codename(Currencies.trx).upper(), from_addr),
                            currency=Currencies.trx,
                            tp=ExternalWallet.TYPES.hot,
                        )[0],
                        destination=to_addr,
                        tx_hash=tx_hash,
                        tag=tag,
                        currency=Currencies.trx,
                        amount=Decimal(amount),
                    )
            next_req = transactions_info.get('meta').get('links')
            transactions_info = api_session.get(next_req.get('next'), timeout=7).json() if next_req else None


@shared_task(name='refresh_external_withdraw_log', max_retries=1)
def refresh_external_withdraw_log():
    external_withdraw_log(Currencies.bnb)
    external_withdraw_log(Currencies.trx)


@shared_task(name='update_withdraw_status', max_retries=1)
def task_update_withdraw_status(
    withdraw_id: int,
    update_all: bool = False,
    settlement_method: Optional[Type[BaseSettlement]] = None,
):
    """ Call update_status on WithdrawRequest settlement manager """
    withdraw = WithdrawRequest.objects.get(pk=withdraw_id)
    settlement_manager = withdraw.get_settlement_manager(method=settlement_method)
    if settlement_manager:
        settlement_manager.update_status(update_all=update_all)
    else:
        report_event(f'Settlement Manager for WithdrawRequest #{withdraw_id} not found')


@shared_task(name='send_withdraw_email_otp', max_retries=1)
def send_withdraw_email_otp(
    email,
    withdraw_request_id,
    amount_display,
    destination,
    tag,
    verify_url,
    emergency_cancel_url,
    otp,
    short_message,
):
    if not WithdrawRequest.objects.filter(id=withdraw_request_id, status=WithdrawRequest.STATUS.new).exists():
        return

    EmailManager.send_email(
        email=email,
        template='withdraw_request_confirmation_code',
        data={
            'amount_display': amount_display,
            'destination': destination,
            'tag': tag,
            'verify_url': verify_url,
            'emergency_cancel_url': emergency_cancel_url,
            'otp': otp,
            'short_message': short_message,
        },
        priority='high',
    )


@shared_task(name='extract_contract_addresses', max_retries=1)
def task_extract_contract_addresses(network, gas_price=None, threshold=Decimal('100'), currency=None, address_type=ADDRESS_TYPE.contract, is_testnet=False):
    """ Call extract function on children """
    address_type_name = get_address_type_codename(address_type)
    excluded_currencies = [BABYDOGE]
    cache_key = f'latest_deposit_id_extracted_{network}_{address_type_name}'
    latest_deposit_id_extracted = cache.get(cache_key)

    if latest_deposit_id_extracted is None:
        latest_deposit_id_extracted = -1

    if gas_price:
        gas_price = gas_price * 10 ** 9

    if currency is not None:
        currency_name = get_currency_codename(currency)
        cache_key = f'latest_deposit_id_extracted_{network}_{address_type_name}_{currency_name}'
        latest_deposit_id_extracted_contract = cache.get(cache_key)
        if latest_deposit_id_extracted_contract is None:
            latest_deposit_id_extracted_contract = -1
        if latest_deposit_id_extracted < latest_deposit_id_extracted_contract:
            latest_deposit_id_extracted = latest_deposit_id_extracted_contract
    max_id = ConfirmedWalletDeposit.objects.latest('id').id
    contract_deposit_addresses_filter = ConfirmedWalletDeposit.objects.select_related('address').filter(
        id__gt=latest_deposit_id_extracted,
        id__lte=max_id,
        address__type=address_type,
        address__network=network,
    ).exclude(tx_hash__startswith='nobitex-internal-')

    if currency:
        contract_deposit_addresses_filter = contract_deposit_addresses_filter.filter(address__currency=currency)
    else:
        contract_deposit_addresses_filter = contract_deposit_addresses_filter.exclude(address__currency__in=excluded_currencies)
    contract_addresses_info = contract_deposit_addresses_filter.values_list(
        'address__address', 'address__salt', 'address__currency',
    ).distinct()

    contract_addresses_info_dictionary = dict()
    network_key = 'testnet' if is_testnet else 'mainnet'
    for address, salt, curr in contract_addresses_info:
        if f'{curr}-{network}' in MAIN_TOKEN_CURRENCIES_INFO.keys():
            contract_address = '0x0000000000000000000000000000000000000000'
            decimals = MAIN_TOKEN_CURRENCIES_INFO[f'{curr}-{network}']['decimals']
        else:
            if (curr, network) == (Currencies.gala, 'ETH'):
                contract_address = '0x15d4c048f83bd7e37d49ea4c83a07267ec4203da'
                decimals = 8
            else:
                contract_address = CONTRACT_INFO[network][network_key][curr]['address']
                decimals = CONTRACT_INFO[network][network_key][curr]['decimals']
        if curr in [Currencies.dai, Currencies.usdc, Currencies.busd]:
            currency_price = Decimal('1')
        elif curr in [Currencies.pgala, Currencies.gala]:
            currency_price = NobitexSettings.get_binance_price(Currencies.egala)
        else:
            currency_price = NobitexSettings.get_binance_price(curr)
        amount_threshold = Decimal(threshold) / currency_price
        amount_threshold = BlockchainUtilsMixin.to_unit(amount_threshold, precision=decimals)

        contract_addresses_info_dictionary.setdefault((address, salt), []).append({'token': contract_address, 'threshold': amount_threshold})

    update_cache = True
    contract_hotwallet = CONTRACT_CLIENT[network][address_type].get_client()
    for (address, salt), currencies in contract_addresses_info_dictionary.items():
        try:
            params = [{'child': address, 'salt': salt, 'tokens': currencies}, contract_hotwallet.password]
            if gas_price:
                params[0]['gas_price'] = gas_price
            response = contract_hotwallet.request(
                method='withdraw',
                params=params,
                rpc_id='curltext',
            )
            if response['status'] != 'success':
                update_cache = False
                report_event(f'{response}')

        except Exception as e:
            msg = '[Exception] {}'.format(str(e))
            print(msg)
            report_exception()
            update_cache = False

    if update_cache:
        cache.set(cache_key, max_id)


@shared_task(name='settle_rial_withdraws', max_retries=1)
def settle_rial_withdraws(withdraws, method, options):
    withdraws_ids = withdraws.split(',')
    results = []
    terminate = False
    for withdraw_id in withdraws_ids:
        if not terminate and cache.get('terminate_settlement_rial_withdraw'):
            terminate = True
            cache.delete("terminate_settlement_rial_withdraw")
        if terminate:
            settlement_result = {
                "withdraw_id": withdraw_id,
                "status": "failed",
                "error": "RejectByAdmin",
            }
            cache.set(f'settlement_rial_withdraw_{withdraw_id}', settlement_result, 3600)
            continue
        with transaction.atomic():
            try:
                withdraw = WithdrawRequest.objects.select_for_update().get(pk=withdraw_id)
                _ = settle_withdraw(withdraw, method, options)
                settlement_result = {
                    'withdraw_id': withdraw_id,
                    'status': 'success',
                    'error': '',
                }
                results.append(settlement_result)
            except Exception as e:
                settlement_result = {
                    'withdraw_id': withdraw_id,
                    'status': 'failed',
                    'error': parse_str(str(e), max_length=100),
                }
                results.append(settlement_result)

            cache.set(f'settlement_rial_withdraw_{withdraw_id}', settlement_result, 3600)
    return {
        'status': 'success',
        'result': results,
    }


@shared_task(name='export_transaction_history', max_retries=1)
def export_transaction_history(
    user_id: int,
    from_datetime: str,
    to_datetime: str,
    currency: Optional[int] = None,
    tps: Optional[List[int]] = None,
):
    read_db = 'replica' if 'replica' in settings.DATABASES else 'default'
    write_db = 'default'

    from_datetime = datetime.datetime.fromisoformat(from_datetime)
    to_datetime = datetime.datetime.fromisoformat(to_datetime)

    with transaction.atomic(using=read_db), connections[read_db].cursor() as cursor:
        user = User.objects.using(read_db).get(pk=user_id)
        user_wallets = Wallet.objects.using(read_db).filter(user=user)
        if currency:
            user_wallets = user_wallets.filter(currency=currency)

        user_wallets = dict(user_wallets.values_list('id', 'currency'))

        # Next line will force postgres planner to use index instead of seq scan
        cursor.execute('SET LOCAL random_page_cost = 0.1;')
        transactions = Transaction.objects.using(read_db).filter(
            wallet_id__in=user_wallets.keys(),
            created_at__gte=from_datetime,
            created_at__lt=to_datetime,
        )

        if tps:
            transactions = transactions.filter(tp__in=tps)

        transactions = transactions.order_by('-created_at', '-id').values(
            'id',
            'amount',
            'description',
            'created_at',
            'balance',
            'tp',
            'wallet_id',
        )

        # Serialize
        with measure_time_cm('transaction_history_task_query_milliseconds', verbose=False):
            transactions = list(transactions)

        tx_count = len(transactions)
        type_id_map = {v: k for k, v in Transaction.TYPE._identifier_map.items()}

        for tx in transactions:
            tx['id'] = encode_id(tx['id'])
            tx['type'] = Transaction.TYPES_HUMAN_DISPLAY.get(tx['tp'], 'سایر')
            tx['tp'] = type_id_map.get(tx['tp'], 'etc')
            tx['currency'] = CURRENCY_CODENAMES.get(user_wallets[tx['wallet_id']], '').lower()
            tx['createdAt'] = serialize(tx['created_at'])
            del tx['wallet_id']
            del tx['created_at']

        tps_str = '_'.join(map(str, sorted(tps))) if tps else ''
        transaction_history_file = (
            TransactionHistoryFile.objects.using(write_db)
            .filter(
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                user=user,
                tps=tps_str,
                currency=currency,
            )
            .first()
        )

        if transaction_history_file is None:
            transaction_history_file = TransactionHistoryFile(
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                user=user,
                tps=tps_str,
                currency=currency,
            )
        elif transaction_history_file.tx_count == tx_count:
            return

        transaction_history_file.tx_count = len(transactions)
        transaction_history_file.save(using=write_db)

    headers = ['id', 'createdAt', 'type', 'tp', 'currency', 'amount', 'balance', 'description']
    with measure_time_cm('transaction_history_task_export_milliseconds', verbose=False):
        export_csv(transaction_history_file.disk_path, transactions, headers, encoding='utf-8-sig')

    transaction_history_file.send_email()

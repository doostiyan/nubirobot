import re
import time
import datetime
import pytz
from decimal import Decimal

from django.db.models import Sum, Count
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.logging import report_exception
from exchange.base.models import Currencies, TAG_NEEDED_CURRENCIES, get_currency_codename, BABYDOGE
from exchange.base.money import money_is_close_decimal
from exchange.base.tasks import run_admin_task
from exchange.blockchain.contracts_conf import ton_contract_currency
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.models import get_decimal_places
from exchange.wallet.models import WithdrawRequest
from exchange.wallet.withdraw_commons import get_hot_wallet_addresses
from exchange.wallet.withdraw_method import AutomaticWithdrawMethod

NETWORKS = {
    Currencies.eos: CurrenciesNetworkName.EOS,
    Currencies.xrp: CurrenciesNetworkName.XRP,
    Currencies.xlm: CurrenciesNetworkName.XLM,
    Currencies.bnb: CurrenciesNetworkName.BNB,
    Currencies.atom: CurrenciesNetworkName.ATOM,
    Currencies.hbar: CurrenciesNetworkName.HBAR,
    Currencies.ton: CurrenciesNetworkName.TON,
}


def to_done_tagged_withdraws(currencies=None, return_failed_hashes=False):
    """
        This function does Diff HotWallet whole process for tag coins so currencies passed to it must be a bunch of
        tag needed currencies in system (other coins will be ignored) in a list. All tag needed currencies have
        their own network as default network in system. After grabbing hot wallet addresses of each currency
        we have a for-loop to iterate over each currency and its hot_wallet_addresses and for each of that addresses
        get_wallet_transactions runs and output (which will be a bunch of TXS) will pass here and if anyone of them
        was not authorized function send alert notification.
        Note 1: PMN completely ignored
        Note 2: return_failed_hashes parameter only used for testing purposes.
    """
    if currencies is None:
        return

    currencies = list(filter(lambda c: c in TAG_NEEDED_CURRENCIES, currencies))

    all_hot_wallet_addresses = list(map(lambda c: get_hot_wallet_addresses(currency=c, network_symbol=NETWORKS[c], keep_case=True), currencies))
    all_hot_wallet_addresses = dict(zip(currencies, all_hot_wallet_addresses))
    failed_withdraws = []
    for currency, hot_wallet_addresses in all_hot_wallet_addresses.items():
        network = NETWORKS[currency]
        for address in hot_wallet_addresses:
            print('Checking {} Address: {}'.format(get_currency_codename(currency), address), end='..\n')
            try:
                txs_object = BlockchainExplorer.get_wallet_withdraws(address=address, currency=currency, network=network)
                if currency == Currencies.hbar:
                    def change_tx_hash(tx):
                        tx.hash = tx.hash.replace('-', '@', 1).replace('-', '.', 1)
                        tx.hash = re.sub(r'(.*\.)0*(.*)', r'\1\2', tx.hash)
                        return tx
                    txs_object = list(map(lambda tx: change_tx_hash(tx), txs_object))
            except Exception as e:
                report_exception()
                time.sleep(0.5)
                print(f'BLOCKCHAIN GET WALLET WITHDRAWS FAILED! {e}')
                continue
            if not txs_object:  # wallet has no withdraw (with time condition in get_wallet_withdraws func) so let it go
                continue

            for tx in txs_object:
                if tx.timestamp and tx.timestamp < datetime.datetime.now(pytz.utc) - datetime.timedelta(hours=3):
                    continue
                total_amount_from_db, count_withdraws_from_db = (
                    WithdrawRequest.objects.filter(
                        blockchain_url__icontains=tx.hash,
                        status__in=[WithdrawRequest.STATUS.sent, WithdrawRequest.STATUS.done],
                        created_at__gte=now() - datetime.timedelta(days=4),
                        network=network,
                    )
                    .aggregate(Sum('amount'), Count('id'))
                    .values()
                )
                tx_currency = currency
                if network == 'TON' and tx.contract_address:
                    tx_currency = ton_contract_currency.get('mainnet').get(tx.contract_address)

                fee = AutomaticWithdrawMethod.get_withdraw_fee(tx_currency, network, total_amount_from_db)
                has_diff = False
                network_value = tx.value
                if total_amount_from_db is None:
                    has_diff = True
                else:
                    total_amount_from_db -= (fee * count_withdraws_from_db)
                total_amount_from_block = None
                if network_value is None:
                    has_diff = True
                else:
                    # withdraws have negative value by default but in the end-to compare with the value in database-
                    # we should consider it positive (obviously values of withdraw requests in database are positive)
                    total_amount_from_block = abs(tx.value)

                decimals = get_decimal_places(currency=tx_currency, network=network)
                if tx_currency == BABYDOGE:
                    total_amount_from_db = total_amount_from_db * Decimal('0.9')
                if not has_diff and money_is_close_decimal(total_amount_from_db, total_amount_from_block, decimals):
                    withdraws = WithdrawRequest.objects.filter(
                        blockchain_url__icontains=tx.hash,
                        status=WithdrawRequest.STATUS.sent,
                        created_at__gte=now() - datetime.timedelta(days=4),
                        network=network
                    )
                    for withdraw in withdraws:
                        withdraw.status = WithdrawRequest.STATUS.done
                        withdraw.save(
                            update_fields=[
                                'status',
                            ]
                        )
                else:
                    channel_name = 'important_ton' if network == 'TON' else 'important'

                    # To ignore ton fee transactions
                    if (
                        tx_currency == Currencies.ton
                        and total_amount_from_db
                        and total_amount_from_block
                        and total_amount_from_db > total_amount_from_block
                        and total_amount_from_block <= Decimal('2')
                        and total_amount_from_block % Decimal('0.05') == 0
                    ):
                        continue
                    message = (
                        f'*Currency:* {get_currency_codename(tx_currency)}\n'
                        f'*Network:* {network}\n*Hash*: {tx.hash}\n'
                        f'*Debug Parameters:*\n\t*Total Amount in System:* {total_amount_from_db}\n\t'
                        f'*Total Amount in Network:* {total_amount_from_block}'
                    )
                    title = '❌️ اختلاف در سیستم برداشت'
                    Notification.notify_admins(message=message, title=title, channel=channel_name)
                    run_admin_task('admin.add_notification_log', channel=channel_name, message=message, title=title)
                    run_admin_task(
                        'admin.add_withdraw_diff',
                        currency=tx_currency,
                        network=network,
                        tx_hash=tx.hash,
                        system_amount=total_amount_from_db,
                        network_amount=total_amount_from_block,
                    )
                    failed_withdraws.append(tx.hash)

    if return_failed_hashes:
        return failed_withdraws

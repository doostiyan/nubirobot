import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import BABYDOGE, Currencies
from exchange.base.money import money_is_close_decimal
from exchange.base.tasks import run_admin_task
from exchange.blockchain.api.bch.bch_blockbook import BitcoinCashBlockbookAPI
from exchange.blockchain.models import CurrenciesNetworkName, Transaction, get_decimal_places
from exchange.wallet.deposit import validate_transaction
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import ConfirmedWalletDeposit, WalletDepositAddress, WithdrawRequest, get_currency_codename
from exchange.wallet.tasks import task_refresh_currency_deposits
from exchange.wallet.withdraw_commons import get_hot_wallet_addresses
from exchange.wallet.withdraw_method import AutomaticWithdrawMethod


class NobitexBlockProcessing:
    currency: Currencies
    network_symbol = None  # overwrite in children (or grand children) and assign it all uppercase
    READ_DB: str = 'replica' if 'replica' in settings.DATABASES else 'default'

    @classmethod
    def addr_block_to_model(cls, address):
        return address

    @classmethod
    def addr_model_to_block(cls, address):
        return address

    @classmethod
    def get_hot_wallet_addresses(cls, limit=None):
        addresses = get_hot_wallet_addresses(currency=cls.currency, network_symbol=cls.network_symbol, limit=limit)
        if cls.network_symbol == CurrenciesNetworkName.BCH:
            # Needs to convert to legacy address to compare with api outputs
            change_bch_address = lambda address: BitcoinCashBlockbookAPI.convert_address(f'bitcoincash:{address}').lower() if bool(re.match(r'(q|p)[a-z0-9]{41}', address)) else address
            addresses = set([change_bch_address(address) for address in addresses])
        return addresses

    @classmethod
    def updating_wallet(cls, updated_addresses, currencies=None, transactions_info=None,
                        network=None, network_required=False):
        if currencies is None:
            currencies = []
        if not updated_addresses:
            return
        print(updated_addresses)
        updated_addresses_normalized = [cls.addr_block_to_model(updated_address)
                                        for updated_address in updated_addresses]
        currencies_filter = Q(currency__in=currencies)
        if network is not None:
            network_filter = Q(network=network)
            if not network_required:
                network_filter = network_filter | Q(network__isnull=True)
            currencies_filter = currencies_filter & network_filter
        deposit_address_wallets = WalletDepositAddress.objects.filter(address__in=updated_addresses_normalized).filter(
            currencies_filter
        ).select_related('wallet').all()

        # Update balances for addresses with block appearance
        for address in deposit_address_wallets:
            address.enqueue_for_balance_update()

        for address in deposit_address_wallets:
            transactions_related_address = transactions_info.get(cls.addr_model_to_block(address.address), {}).get(
                address.wallet.currency)
            if transactions_related_address:
                for tx_related_address in transactions_related_address:
                    tx_hash = tx_related_address.get('tx_hash')
                    tx_value = tx_related_address.get('value')
                    tx_contract_address = tx_related_address.get('contract_address')
                    tx = Transaction(
                        address=address,
                        hash=tx_hash,
                        timestamp=now(),
                        value=tx_value,
                        contract_address=tx_contract_address,
                    )

                    tx_info = validate_transaction(tx=tx, currency=address.wallet.currency, network=address.network,
                                                   address_type=address.type)
                    if tx_info is None:
                        continue
                    tx_hash, tx_value, tx_datetime, tx_contract_address = tx_info['hash'], tx_info['value'], tx_info['datetime'], tx_info.get('contract_address')
                    if tx_contract_address != address.contract_address:
                        continue
                    try:

                        deposit = ConfirmedWalletDeposit.objects.get(tx_hash=tx_hash,
                                                                     address=address,
                                                                     contract_address=tx_contract_address,)
                    except ConfirmedWalletDeposit.DoesNotExist:
                        rial_value = PriceEstimator.get_rial_value_by_best_price(tx_value, address.wallet.currency, 'sell')
                        deposit = ConfirmedWalletDeposit.objects.create(
                            _wallet=address.wallet,
                            tx_hash=tx_hash,
                            address=address,
                            amount=tx_value,
                            validated=False,
                            rial_value=rial_value,
                            contract_address=tx_contract_address,
                        )
                    print(deposit)

            task_refresh_currency_deposits.delay(address.address, address.currency)

    def update_withdraw_status(self, updated_hot_wallet_addresses, transactions_info):
        """
            Purpose: Diff HotWallet main func which generates final output
            Approach: get outgoing transactions from helper functions and see
            if a transaction is going out from hot wallet addresses we care
            about (which also provided by a helper function) analyze it
            and make decision (refer to doc to have more information)
        """
        for address in transactions_info:
            if address.lower() not in updated_hot_wallet_addresses:
                continue
            for coin in transactions_info[address]:
                for tx in transactions_info[address][coin]:
                    network = self.network_symbol
                    if network is None:
                        network = CURRENCY_INFO[coin]['default_network']
                    total_amount_from_db, count_withdraws_from_db, total_withdraw_fee = (
                        WithdrawRequest.objects.filter(
                            blockchain_url__icontains=tx.get('tx_hash'),
                            status__in=[WithdrawRequest.STATUS.sent, WithdrawRequest.STATUS.done],
                            created_at__gte=now() - timedelta(days=2),
                            network=network,
                        )
                        .aggregate(Sum('amount'), Count('id'), Sum('fee'))
                        .values()
                    )
                    decimals = get_decimal_places(currency=coin, network=network)
                    has_diff = False
                    network_value = tx.get('value')
                    if total_amount_from_db is None:
                        has_diff = True
                    else:
                        total_amount_from_db = total_amount_from_db - total_withdraw_fee
                    total_amount_from_block = None
                    if network_value is None:
                        has_diff = True
                    else:
                        total_amount_from_block = tx.get('value') - tx.get('fees', Decimal('0'))
                    if not has_diff and money_is_close_decimal(total_amount_from_db, total_amount_from_block, decimals):
                        WithdrawRequest.objects.filter(
                            blockchain_url__icontains=tx.get('tx_hash'),
                            status=WithdrawRequest.STATUS.sent,
                            created_at__gte=now() - timedelta(days=2),
                            network=network
                        ).update(status=WithdrawRequest.STATUS.done)
                    else:
                        message = f'*Currency:* {get_currency_codename(coin)}\n'\
                                  f'*Network:* {network}\n*Hash*: {tx.get("tx_hash")}\n'\
                                  f'*Debug Parameters:*\n\t*Total Amount in System:* {total_amount_from_db}\n\t'\
                                  f'*Total Amount in Network:* {total_amount_from_block}'
                        title = '❌️ اختلاف در سیستم برداشت'
                        Notification.notify_admins(
                            message=message,
                            title=title,
                            channel='important'
                        )
                        run_admin_task('admin.add_notification_log',
                                       channel='important',
                                       message=message,
                                       title=title)
                        run_admin_task('admin.add_withdraw_diff',
                                       currency=coin,
                                       network=network,
                                       tx_hash=tx.get("tx_hash"),
                                       system_amount=total_amount_from_db,
                                       network_amount=total_amount_from_block)

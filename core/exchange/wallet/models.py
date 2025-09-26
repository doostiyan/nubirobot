""" Financial Models """
from __future__ import annotations

import datetime
import json
import math
import random
import sys
import traceback
import uuid
from decimal import Decimal
from functools import reduce
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Union
from urllib.parse import urljoin

import pytz
from django.conf import settings
from django.core.cache import cache
from django.db import connection, models, transaction
from django.db.models import Index, JSONField, Q, Sum
from django.db.models.functions import Coalesce, Upper
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounting.models import DepositSystemBankAccount, SystemBankAccount
from exchange.accounts.models import BankAccount, Confirmed, Notification, UploadedFile, User, UserRestriction
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.cache import CacheManager
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.constants import MAX_PRECISION, MONETARY_DECIMAL_PLACES, ZERO
from exchange.base.crypto import random_string_digit
from exchange.base.decorators import measure_function_execution
from exchange.base.emailmanager import EmailManager
from exchange.base.helpers import context_flag, deterministic_hash
from exchange.base.internal.services import Services
from exchange.base.locker import Locker
from exchange.base.logging import report_event, report_exception
from exchange.base.models import (
    ACTIVE_CRYPTO_CURRENCIES,
    ACTIVE_CURRENCIES,
    ADDRESS_REUSED_NETWORK,
    ADDRESS_TYPE,
    CRYPTO_CURRENCIES,
    CURRENCY_CODENAMES,
    DST_CURRENCIES,
    MAIN_ADDRESS_CURRENCIES,
    RIAL,
    TAG_NEEDED_CURRENCIES,
    TAG_REUSE_MAP,
    TETHER,
    Currencies,
    IPLogged,
    ObjectReference,
    Settings,
    get_currency_codename,
    get_explorer_url,
)
from exchange.base.parsers import parse_int
from exchange.blockchain.contracts_conf import ton_contract_info
from exchange.blockchain.models import CONTRACT_NETWORKS, ETHEREUM_LIKE_NETWORKS, CurrenciesNetworkName
from exchange.blockchain.segwit_address import one_to_eth_address
from exchange.features.utils import is_feature_enabled
from exchange.multiversion_utils import multiversion_JSONField as JSONField
from exchange.security.models import IPBlackList
from exchange.wallet.constants import (
    BALANCE_MAX_DIGITS,
    DEPOSIT_MAX_DIGITS,
    TRANSACTION_MAX_DIGITS,
    WITHDRAW_MAX_DIGITS,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet

class Wallet(models.Model):
    WALLET_TYPE = Choices(
        (1, 'spot', 'Spot'),
        (2, 'margin', 'Margin'),
        (3, 'credit', 'Credit'),
        (4, 'debit', 'Debit'),
    )

    WALLET_VERBOSE_TYPE: ClassVar[Dict[int, str]] = {
        WALLET_TYPE.spot: 'اسپات',
        WALLET_TYPE.margin: 'تعهدی',
        WALLET_TYPE.credit: 'اعتباری',
        WALLET_TYPE.debit: 'نقدی',
    }

    user = models.ForeignKey(User, related_name='wallets', on_delete=models.CASCADE)
    currency = models.IntegerField(choices=Currencies)
    type = models.PositiveSmallIntegerField(choices=WALLET_TYPE, default=WALLET_TYPE.spot)
    balance = models.DecimalField(max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=0)
    balance_blocked = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=0
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'کیف پول داخلی'
        verbose_name_plural = verbose_name
        unique_together = ('user', 'currency', 'type')

    def __str__(self):
        return '{} {} Wallet: {}'.format(self.get_currency_display(), self.get_type_display(), str(self.user))

    @property
    def is_crypto_currency(self):
        return self.currency in CRYPTO_CURRENCIES

    @property
    def is_rial(self):
        return self.currency == Currencies.rls

    @property
    def is_tether(self):
        return self.currency == Currencies.usdt

    def get_address_type_not_none(self, network: str, address_type_unparsed: str = 'default') -> int:
        # Define condition functions
        def is_miner():
            return (
                settings.MINER_ENABLED
                and network == CurrenciesNetworkName.BTC
                and is_feature_enabled(self.user, 'miner')
            )
        def is_segwit():
            return (
                settings.SEGWIT_ENABLED
                and self.currency == Currencies.btc
                and network == CurrenciesNetworkName.BTC
                and address_type_unparsed == 'default'
            )

        def is_eoa_v1():
            return (
                settings.EOA_V1_ENABLED or is_feature_enabled(self.user, 'new_coins')
            ) and network in CONTRACT_NETWORKS

        def is_contract2():
            return (
                settings.ADDRESS_CONTRACT_ENABLED
                and settings.ADDRESS_CONTRACT_V2_ENABLED
                and network in CONTRACT_NETWORKS
                and network != CurrenciesNetworkName.TRX
            )

        def is_usdt_on_eth_standard():
            return (
                settings.ADDRESS_CONTRACT_ENABLED
                and network == CurrenciesNetworkName.ETH
                and self.currency == Currencies.usdt
            )

        def is_contract():
            return settings.ADDRESS_CONTRACT_ENABLED and network in CONTRACT_NETWORKS

        # Define the mapping of conditions to address types
        rules = [
            ('miner', is_miner, ADDRESS_TYPE.miner),
            ('segwit', is_segwit, ADDRESS_TYPE.segwit),
            ('eoa_v1', is_eoa_v1, ADDRESS_TYPE.eoa_v1),
            ('contract2', is_contract2, ADDRESS_TYPE.contract2),
            ('usdt_on_eth_standard', is_usdt_on_eth_standard, ADDRESS_TYPE.standard),
            ('contract', is_contract, ADDRESS_TYPE.contract),
        ]

        # Iterate over the rules and return the address type when the condition is met
        for name, condition_func, address_type in rules:
            if condition_func():
                return address_type

        # Default to standard address type if no conditions are met
        return ADDRESS_TYPE.standard

    def is_address_tag_required(self, network=None):
        """Return true if a tag/memo is required for depositing crypto to deposit addresses of this wallet."""
        currency_info = CURRENCY_INFO.get(self.currency)
        if not currency_info:
            return False  # Unknown currency, so we assume no tag should be generated for it
        default_network = currency_info.get('default_network')
        if network is None:
            network = default_network
        network_list = currency_info.get('network_list')
        return bool(network_list.get(network, network_list.get(default_network)).get('memo_required', False))

    def get_current_deposit_unique(self, network=None):
        if self.is_address_tag_required(network=network):
            return self.get_current_deposit_address(network=network), self.get_current_deposit_tag(network=network)
        return self.get_current_deposit_address(network=network)

    def get_current_deposit_address(self, create=False, network=None, address_type=None, use_cache=True, contract_address=None):
        if not self.is_crypto_currency:
            return None

        if self.currency not in CURRENCY_INFO:
            return None
        if network is None:
            default_network = CURRENCY_INFO[self.currency]['default_network']
            network = default_network

        address_type_not_none = address_type if address_type else self.get_address_type_not_none(network)

        deposit_address_cache_key = f'wallet_{self.pk}_deposit_address_{network}_{address_type_not_none}'
        if contract_address:
            deposit_address_cache_key += f'_{contract_address}'
        if use_cache:
            deposit_address = cache.get(deposit_address_cache_key)
            if deposit_address:
                return deposit_address
        # For tag based addresses, reuse an existing cold address
        if self.is_address_tag_required(network=network):
            tag = self.get_current_deposit_tag(create=create, network=network)
            if tag is None:
                return None
            latest_taggable_shared_address = AvailableDepositAddress.get_tagged_deposit_address(self.currency, network)
            if not latest_taggable_shared_address:
                return None
            if latest_taggable_shared_address.address and use_cache:
                cache.set(deposit_address_cache_key, latest_taggable_shared_address.address, 3600)
            return latest_taggable_shared_address.address
        # For normal addresses, assign a available address to the user
        # To support old addresses.
        network_model_filter = Q(network=network)
        if network == CURRENCY_INFO.get(self.currency, {}).get('default_network'):
            network_model_filter |= Q(network__isnull=True)
        address_type_filter = Q(type=address_type_not_none)
        if address_type_not_none == ADDRESS_TYPE.standard:
            address_type_filter |= Q(type__isnull=True)
        contract_address_filter = Q(contract_address__isnull=True) if not contract_address else Q(contract_address=contract_address)

        address_query_set = self.deposit_addresses.filter(network_model_filter, address_type_filter, contract_address_filter, is_disabled=False)
        # Invalid old addresses
        if self.currency == Currencies.ltc:
            address_query_set = address_query_set.filter(created_at__gt=settings.LAST_ADDRESS_ROTATION_LTC)
        else:
            address_query_set = address_query_set.filter(created_at__gt=settings.LAST_ADDRESS_ROTATION - datetime.timedelta(days=1))
        address = address_query_set.order_by('-created_at').first()
        if address is None and create:
            if (f'{network}' in ADDRESS_REUSED_NETWORK and f'{self.currency}-{network}' not in MAIN_ADDRESS_CURRENCIES) or contract_address:
                reused_wallet = Wallet.get_user_wallet(self.user, ADDRESS_REUSED_NETWORK[f'{network}'])
                reused_address_type = address_type_not_none
                if self.currency == Currencies.bch and network == 'BCH':
                    reused_address_type = ADDRESS_TYPE.standard
                reused_address = reused_wallet.get_current_deposit_address(create=create, address_type=reused_address_type)
                if not reused_address:
                    return None
                address = WalletDepositAddress.objects.create(wallet=self, currency=self.currency, contract_address=contract_address,
                                                              address=reused_address.address, network=network,
                                                              type=reused_address_type, salt=reused_address.salt)
            else:
                address = AvailableDepositAddress.get_deposit_address(self, address_type=address_type_not_none)
        if address and use_cache:
            cache.set(deposit_address_cache_key, address, 3600)
        return address

    def get_all_deposit_address(
        self, network=None, address_type=None, contract_address=None, use_cache=True
    ) -> Union[list, None]:
        """
        return list of deposit addresses of wallet including disabled and old ones
        """
        read_db = 'replica' if 'replica' in settings.DATABASES else 'default'

        if not self.is_crypto_currency:
            return None

        if self.currency not in CURRENCY_INFO:
            return None
        if network is None:
            default_network = CURRENCY_INFO[self.currency]['default_network']
            network = default_network

        deposit_address_cache_key = f'wallet_{self.pk}_all_deposit_address_{network}'
        if contract_address:
            deposit_address_cache_key += f'_{contract_address}'
        if use_cache:
            deposit_address = cache.get(deposit_address_cache_key)
            if deposit_address:
                return deposit_address

        # For tag based addresses, reuse an existing cold address
        if self.is_address_tag_required(network=network):
            tag = self.get_current_deposit_tag(create=False, network=network)
            if tag is None:
                return None
            tag_currency = self.currency
            if tag_currency in ton_contract_info['mainnet'].keys():
                tag_currency = Currencies.ton
            latest_taggable_shared_address = AvailableDepositAddress.objects.filter(currency=tag_currency)
            if not latest_taggable_shared_address:
                return None
            return list(latest_taggable_shared_address.values_list('address', flat=True))

        network_model_filter = Q()
        if network:
            network_model_filter &= Q(network=network)
        contract_address_filter = (
            Q(contract_address__isnull=True) if not contract_address else Q(contract_address=contract_address)
        )

        addresses = self.deposit_addresses.using(read_db).filter(network_model_filter, contract_address_filter)

        if addresses and use_cache:
            cache.set(deposit_address_cache_key, addresses, 3600)

        return list(addresses.values_list('address', flat=True))

    def get_current_deposit_tag(self, create=False, network=None):
        if not self.is_crypto_currency:
            return None
        if not self.is_address_tag_required(network=network):
            return None
        deposit_tag_cache_key = f'wallet_{self.pk}_deposit_tag_{network}'
        deposit_tag = cache.get(deposit_tag_cache_key)
        if deposit_tag and isinstance(deposit_tag, WalletDepositTag):
            return deposit_tag

        if self.currency not in TAG_REUSE_MAP.keys():
            tag = self.deposit_tags.all().order_by('-created_at').first()
            if tag is None and create:
                tag = WalletDepositTag.get_deposit_tag(self)
        else:
            if create:
                base_currency = TAG_REUSE_MAP[self.currency]
                base_currency_wallet = Wallet.get_user_wallet(user=self.user, currency=base_currency)
                base_currency_wallet.get_current_deposit_address(create=True, network=network)
                base_tag = base_currency_wallet.deposit_tags.all().order_by('-created_at').first().tag
                tag, _ = WalletDepositTag.objects.get_or_create(wallet=self, currency=self.currency, tag=base_tag)
            else:
                # either you create a new tag for wallet or you receive None instead of old one
                tag = self.deposit_tags.all().order_by('-created_at').first()
                try:
                    base_currency_wallet = Wallet.objects.get(user=self.user, currency=TAG_REUSE_MAP[self.currency])
                    if tag.tag != base_currency_wallet.deposit_tags.all().order_by('-created_at').first().tag:
                        tag = None
                except Exception:
                    tag = None
        if tag:
            cache.set(deposit_tag_cache_key, tag, 3600)

        return tag

    def get_current_deposit_tag_number(self, network=None):
        if not self.is_crypto_currency:
            return None
        if not self.is_address_tag_required(network=network):
            return None
        cache_key = 'wallet_{}_tag'.format(self.pk)  # TODO: consider network in cache key
        tag_number = cache.get(cache_key)
        if tag_number:
            return tag_number
        tag = self.get_current_deposit_tag(network=network)
        if tag is None:
            return None
        tag_number = tag.tag
        cache.set(cache_key, tag_number, 3600)  # TODO: Double cache?
        return tag_number

    def get_all_deposit_tag_numbers(self, network=None) -> list:
        """
        Return List of tag numbers for wallet
        """
        if not (self.is_crypto_currency and self.is_address_tag_required(network=network)):
            return list()
        return list(self.deposit_tags.values_list('tag', flat=True))

    def get_estimated_rls_balance(self, order_type='buy', is_gateway=False):
        from exchange.wallet.estimator import PriceEstimator
        balance = self.gateway_balance if is_gateway else self.balance
        return PriceEstimator.get_rial_value_by_best_price(balance, self.currency, order_type)

    def get_old_deposit_address(
        self,
        address: str,
        network=None,
        contract_address=None,
    ) -> Optional[WalletDepositAddress]:
        """
        Create or get wallet deposit address object if address belong to user.

        Used for admin to create manual deposit
        """
        # Check validity
        if not self.is_crypto_currency:
            return None

        if self.currency not in CURRENCY_INFO:
            return None

        if network is None:
            default_network = CURRENCY_INFO[self.currency]['default_network']
            network = default_network

        # Check if address belongs to user
        available_address = (
            AvailableDepositAddress.objects.select_related('used_for__wallet__user')
            .filter(address=address, used_for__wallet__user=self.user)
            .first()
        )
        if available_address is None:
            return None

        # Create address object
        if (
            f'{network}' in ADDRESS_REUSED_NETWORK and f'{self.currency}-{network}' not in MAIN_ADDRESS_CURRENCIES
        ) or contract_address is not None:
            try:
                wallet = WalletDepositAddress.objects.get(
                    wallet__currency=self.currency,
                    address=address,
                    type=available_address.type,
                    network=network,
                    contract_address=contract_address,
                )
            except WalletDepositAddress.DoesNotExist:
                wallet = WalletDepositAddress.objects.create(
                    wallet=self,
                    currency=self.currency,
                    address=address,
                    type=available_address.type,
                    network=network,
                    contract_address=contract_address,
                )
            return wallet
        # We don't want to support main network address creation. Use case for this function is giving old addresses.
        # Therefore, main addresses must be created by now
        return None

    @property
    def current_balance(self):
        if not self.pk:
            return self.balance
        return Wallet.objects.get(pk=self.pk).balance

    @property
    def blocked_balance(self) -> Decimal:
        """ Balance that is held and cannot be used
        """
        from exchange.usermanagement.block import BalanceBlockManager

        if self.type in [self.WALLET_TYPE.margin, self.WALLET_TYPE.credit, self.WALLET_TYPE.debit]:
            return self.balance_blocked
        blocked = BalanceBlockManager.get_blocked_balance(self)
        in_order = BalanceBlockManager.get_balance_in_order(self)
        return blocked + in_order

    def _change_balance_blocked(self, amount: Decimal):
        if amount.remainder_near(MAX_PRECISION):
            title = 'Over-precision blocked balance change'
            report_event(title, attach_stacktrace=True)
            Notification.notify_admins(
                f'Wallet: #{self.user.email} {self.get_currency_display()}, Amount: {amount}',
                title=f'🆘 {title}',
                channel='pool',
            )
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE wallet_wallet SET balance_blocked = balance_blocked + %(amount)s '
                'WHERE id = %(id)s AND balance_blocked + %(amount)s between 0 and balance '
                'RETURNING balance, balance_blocked',
                params={'amount': amount.quantize(MAX_PRECISION), 'id': self.id},
            )
            try:
                self.balance, self.balance_blocked = cursor.fetchone()
            except TypeError:  # cannot unpack non-iterable NoneType object
                raise ValueError('InsufficientBalance')

    def block(self, amount: Decimal):
        self._change_balance_blocked(amount)

    def unblock(self, amount: Decimal):
        self._change_balance_blocked(-amount)

    @property
    def active_balance(self):
        return self.balance - self.blocked_balance

    @property
    def gateway_balance(self):
        b = Transaction.objects.filter(wallet=self, tp=Transaction.TYPE.gateway).aggregate(total=Sum('amount'))['total']
        return b or Decimal('0')

    def create_transaction(
        self,
        tp=None,
        amount=None,
        description='',
        created_at=None,
        ref_module=None,
        ref_id=None,
        service=None,
        allow_negative_balance=False,
    ):
        if not self.is_active:
            return None
        if not isinstance(amount, Decimal):
            amount = Decimal(amount)
        amount = amount.quantize(MAX_PRECISION)
        balance_after_tx = self.balance + amount
        if not self.is_balance_allowed(balance_after_tx) and not allow_negative_balance:
            print('[Warning] Not allowing transaction: amount={} > balance={}'.format(amount, self.balance))
            return None

        tx = Transaction(
            wallet=self,
            tp=getattr(Transaction.TYPE, tp),
            amount=amount,
            description=description,
            created_at=created_at or now(),
            ref_module=ref_module,
            ref_id=ref_id,
            balance=balance_after_tx,
            service=service,
        )
        if not tx.check_transaction():
            raise ValueError('Invalid Transaction')

        return tx

    def is_balance_allowed(self, balance):
        return balance >= 0

    def is_current_balance_valid(self):
        return self.is_balance_allowed(self.balance)

    def update_balance_from_transactions(self):
        # TODO: lock DB first
        balance = self.transactions.all().aggregate(s=Sum('amount'))['s'] or Decimal('0')
        self.balance = balance
        self.save(update_fields=['balance'])

    @classmethod
    def get_user_wallet(cls, user, currency, tp=WALLET_TYPE.spot, *, create=True):
        """ Return the internal Wallet object for the given user and currency

            The user parameter can be either a User objects, or the user_id. The
              latter usage is recommended when the User object is not needed to
              prevent an extra query or join.
        """
        if tp == cls.WALLET_TYPE.margin and currency not in DST_CURRENCIES:
            return None
        params = {
            'currency': currency,
            'user_id' if isinstance(user, int) else 'user': user,
            'type': tp,
        }
        try:
            return cls.objects.get(**params)
        except cls.DoesNotExist:
            if not create:
                return None
            CacheManager.invalidate_user_wallets(user if isinstance(user, int) else user.id)
            return cls.objects.create(**params)

    @classmethod
    def create_user_wallet(cls, user, currency, tp=WALLET_TYPE.spot):
        CacheManager.invalidate_user_wallets(user if isinstance(user, int) else user.id)
        params = {
            'currency': currency,
            'user_id' if isinstance(user, int) else 'user': user,
            'type': tp,
        }
        return cls.objects.create(**params)

    @classmethod
    def create_user_wallets(cls, user):
        """ Create internal wallet objects for all currencies for this user
        """
        for currency in ACTIVE_CURRENCIES[:21]:
            cls.get_user_wallet(user=user, currency=currency)

    @classmethod
    def get_user_wallets(cls, user, tp=None):
        """ Return a list of user wallets
        """
        wallets = cls.objects.filter(user=user).order_by('id')
        if tp:
            wallets = wallets.filter(type=tp)
        if isinstance(user, User):
            for wallet in wallets:
                wallet.user = user
        return wallets

    @classmethod
    def get_fee_collector_wallet(cls, currency):
        return cls.get_user_wallet(User.objects.get(username='system-fee'), currency)

    @classmethod
    def get_position_fee_collector_wallet(cls, currency):
        return cls.get_user_wallet(User.objects.get(username='system-position-fee'), currency)

    @classmethod
    def validate_order(cls, order, only_active_balance=False):
        has_shared_fund = only_active_balance and order.pair and not order.pair.pair_id and order.pair.is_active
        if order.is_buy:
            order_required_funds = order.unmatched_total_price
            wallet = order.dst_wallet
            shared_funds = order.pair.unmatched_total_price if has_shared_fund else 0
        elif order.is_sell:
            order_required_funds = order.unmatched_amount
            wallet = order.src_wallet
            shared_funds = order.pair.unmatched_amount if has_shared_fund else 0
        else:
            return False, 'InvalidOrderType'
        # Check wallet activity
        if not wallet.is_active:
            return False, 'InactiveWallet'
        # Get user funds
        available_funds = wallet.active_balance + shared_funds if only_active_balance else wallet.balance
        # Special case for ranged buy orders
        range_allowance = Decimal('1.1') if order.is_market and order.is_buy else Decimal('1')
        # Check user funds
        if order_required_funds > available_funds * range_allowance:
            return False, 'OverValueOrder'
        return True, 'ok'

    @staticmethod
    def autocomplete_search_fields():
        return ['id', 'user__username']

    @classmethod
    def get_wallets_by_params(cls, query_params):
        """
        :param query_params: a list where each element is a dictionary with the following keys:
            - uid (uuid): user uid
            - type (integer): wallet type
            - currency (integer): wallet currency
        """
        query = Q()
        for query_param in query_params:
            query |= Q(
                user__uid=query_param.get('uid'), type=query_param.get('type'), currency=query_param.get('currency')
            )
        return (
            cls.objects.filter(query)
            .select_related('user')
            .only('user__uid', 'type', 'currency', 'balance', 'balance_blocked')
        )


class WalletCreditBalance(models.Model):
    """Store manually given credits for user wallets"""

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    credit = models.DecimalField(max_digits=25, decimal_places=10)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    credit_change = models.DecimalField(max_digits=25, decimal_places=10)
    credit_transaction = models.OneToOneField('Transaction', on_delete=models.CASCADE, related_name='+')

    class Meta:
        verbose_name = 'اعتبار کاربر'
        verbose_name_plural = verbose_name

    @classmethod
    def get_current_user_credit(cls, user, currency):
        """ Get current net credit for the given user and currency based on
             the credit computed field of last WalletCreditBalance
        """
        if isinstance(user, Wallet):
            user_wallet = user
        else:
            user_wallet = Wallet.get_user_wallet(user, currency)
        last_credit_balance = cls.objects.filter(wallet=user_wallet).order_by('-created_at').first()
        if not last_credit_balance:
            return Decimal('0')
        return last_credit_balance.credit

    @classmethod
    def give_credit_to_user(cls, user, currency, amount):
        """ Add amount to the credit balance of the user. The user wallet
             is also charged with a manual transaction for the credit to be
             usable.
        """
        with transaction.atomic():
            user_wallet = Wallet.objects.select_for_update().get(user=user, currency=currency)
            credit_transaction = user_wallet.create_transaction('manual', amount, description=json.dumps({
                'type': 'Credit',
            }))
            credit_transaction.commit(ref=Transaction.Ref('Credit', -user_wallet.id))
            credit = cls.get_current_user_credit(user_wallet, currency) + amount
            credit_balance = cls.objects.create(
                wallet=user_wallet,
                credit=credit,
                credit_change=amount,
                credit_transaction=credit_transaction,
            )
            Transaction.objects.filter(pk=credit_transaction.pk).update(ref_id=credit_balance.pk)


class WalletBlockedBalance(ObjectReference):
    """ Used by all apps to signal blocked balance for a user wallet

        Note: Data model only, not implemented yet
    """
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    balance_blocked = models.DecimalField(max_digits=25, decimal_places=10, default=0)

    class Meta:
        verbose_name = 'موجودی بلوکه'
        verbose_name_plural = verbose_name


class WalletDepositTag(models.Model):
    """ Wallet tags assigned to user -- like xrp tags
    """
    wallet = models.ForeignKey(Wallet, related_name='deposit_tags', on_delete=models.CASCADE)
    tag = models.IntegerField(verbose_name='تگ')
    currency = models.IntegerField(choices=Currencies, default=Currencies.unknown)
    created_at = models.DateTimeField(auto_now_add=True)
    total_received = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    total_sent = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    last_update = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'تگ‌های واریز'
        verbose_name_plural = verbose_name
        unique_together = [
            'currency',
            'tag',
        ]

    def __str__(self):
        return str(self.wallet)

    @classmethod
    def get_deposit_tag(cls, wallet):
        max_try = 10
        while max_try > 0:
            max_try -= 1
            new_tag = random.SystemRandom().randrange(2**31)
            if cls.objects.filter(tag=new_tag).exists():
                continue
            new_tag_object = cls.objects.create(wallet=wallet, currency=wallet.currency, tag=new_tag)
            return new_tag_object
        return None


class BalanceWatch(models.Model):
    last_update = models.DateTimeField(null=True, blank=True)
    last_update_check = models.DateTimeField(null=True, blank=True)

    @classmethod
    def get_outdated_queryset(cls, hours=1) -> QuerySet:
        last_update_check_filter = Q(last_update_check__isnull=True) | Q(
            last_update_check__lt=now() - datetime.timedelta(hours=hours)
        )
        return cls.objects.filter(last_update_check_filter)

    class Meta:
        abstract = True


class WalletDepositAddress(BalanceWatch):
    """ Wallet addresses assigned to users for deposit
    """
    wallet = models.ForeignKey(Wallet, related_name='deposit_addresses', on_delete=models.CASCADE)
    currency = models.IntegerField(choices=Currencies, default=Currencies.unknown)
    address = models.CharField(max_length=200)
    is_disabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    total_received = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    total_sent = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    last_deposit = models.DateTimeField(null=True, blank=True)
    last_deposit_check = models.DateTimeField(null=True, blank=True)
    needs_update = models.BooleanField(default=False)
    network = models.CharField(max_length=200, null=True, blank=True)
    type = models.IntegerField(choices=ADDRESS_TYPE, null=True, blank=True, default=ADDRESS_TYPE.standard)
    salt = models.CharField(max_length=256, null=True, blank=True)
    contract_address = models.CharField(max_length=256, null=True, blank=True, default=None)

    class Meta:
        verbose_name = 'آدرس واریز'
        verbose_name_plural = verbose_name
        unique_together = ['currency', 'address', 'network', 'contract_address']

    def __str__(self):
        return str(self.wallet)

    def is_eligible_to_update(self):
        if self.is_disabled:
            return False
        if self.currency not in ACTIVE_CRYPTO_CURRENCIES:
            return False
        # User level check
        user_level = self.wallet.user.user_type
        is_eligible = False
        if user_level >= User.USER_TYPES.level2:
            is_eligible = True
        # User activity check
        return self.wallet.user.is_online and is_eligible

    def is_balance_outdated(self):
        old_date = now()
        old_date -= datetime.timedelta(minutes=45)
        if not self.last_update_check or self.last_update_check < old_date:
            return True
        return False

    @property
    def current_balance(self):
        """ Return an estimate of current balance of this wallet,
             note that this is an estimate and may be out of date
        """
        return self.total_received - self.total_sent

    @property
    def is_stale(self):
        if self.currency == Currencies.ltc:
            return self.created_at < settings.LAST_ADDRESS_ROTATION_LTC
        rotated_currencies = [
            Currencies.btc, Currencies.bch, Currencies.eth, Currencies.usdt,
            Currencies.etc, Currencies.trx, Currencies.doge,
        ]
        return self.currency in rotated_currencies and self.created_at < settings.LAST_ADDRESS_ROTATION

    def get_network(self):
        network = self.network
        if network is None:
            currency = self.currency
            if currency == Currencies.unknown:
                currency = self.wallet.currency
            network = CURRENCY_INFO.get(currency).get('default_network')
        return network

    def enqueue_for_update(self):
        """ Suggest this address for balance update
            TODO: DB router incorrectly selects replica for the save
        """
        WalletDepositAddress.objects.using('default').filter(pk=self.pk).update(needs_update=True)

    def enqueue_for_balance_update(self):
        """ Add wallet to sequential balance updater queue """
        self.last_update_check = now() - datetime.timedelta(days=7)
        self.save(update_fields=['last_update_check'])

    @classmethod
    def get_unique_instance(cls, address, currency, network, contract_address=None):
        contract_address_filter = Q(contract_address__isnull=True) if not contract_address else Q(contract_address=contract_address)
        network_model_filter = Q(network=network)
        if network == CURRENCY_INFO[currency]['default_network']:
            network_model_filter |= Q(network__isnull=True)
        return WalletDepositAddress.objects.get(network_model_filter, contract_address_filter, address=address, wallet__currency=currency)


class ConfirmedWalletDeposit(models.Model):
    tx_hash = models.CharField(max_length=200)
    address = models.ForeignKey(WalletDepositAddress, null=True, blank=True, related_name='confirmed_deposits',
                                on_delete=models.CASCADE)
    _wallet = models.ForeignKey(Wallet, null=True, blank=True, related_name='confirmed_deposits', on_delete=models.CASCADE,
                                db_column='wallet')
    transaction = models.ForeignKey('Transaction', related_name='+', null=True, blank=True, on_delete=models.CASCADE)
    confirmed = models.BooleanField(default=False)
    tx_datetime = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=now, db_index=True)
    confirmations = models.IntegerField(default=0)
    amount = models.DecimalField(max_digits=DEPOSIT_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO)
    tag = models.ForeignKey(WalletDepositTag, null=True, blank=True, related_name='confirmed_deposits',
                            on_delete=models.CASCADE)
    validated = models.BooleanField(default=True)
    rial_value = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='ارزش ریالی')
    invoice = models.CharField(max_length=4300, null=True, blank=True)
    expired = models.BooleanField(default=False)
    rechecked = models.BooleanField(default=False, null=True, blank=True)
    source_addresses = JSONField(null=True, blank=True)
    contract_address = models.CharField(max_length=256, null=True, blank=True, default=None)

    class Meta:
        verbose_name = 'واریز تایید شده'
        verbose_name_plural = verbose_name
        unique_together = [('tx_hash', 'address'), ('tx_hash', 'tag'), ('tx_hash', 'invoice')]

    def __str__(self):
        return 'ConfirmedWalletDeposit#{}'.format(self.pk)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_source_addresses = self.source_addresses

    @property
    def wallet(self):
        """Return related wallet object
           # TODO: All deposits are assigned a wallet so this may be replaced by the field.
        """
        if self._wallet:
            return self._wallet
        if self.address:
            self._wallet = self.address.wallet
            self.save(update_fields=['_wallet'])
        if self.tag:
            self._wallet = self.tag.wallet
            self.save(update_fields=['_wallet'])
        return self._wallet

    @property
    def currency(self):
        return self.wallet.currency

    @property
    def currency_display(self):
        return self.wallet.get_currency_display()

    @property
    def network(self):
        if self.address:
            return self.address.get_network()
        if self.invoice:
            if self.currency == Currencies.btc:
                return 'BTCLN'
        return CURRENCY_INFO.get(self.currency).get('default_network')

    @property
    def required_confirmations(self):
        network = self.network
        if network is None:
            default_network = CURRENCY_INFO[self.currency]['default_network']
            network = default_network
        return CURRENCY_INFO[self.currency]['network_list'][network]['min_confirm']

    @property
    def is_confirmed(self):
        return self.confirmations >= self.required_confirmations and self.validated

    @property
    def effective_date(self):
        if self.transaction:
            return self.transaction.created_at
        return self.created_at

    @property
    def is_lightning(self):
        return self.invoice is not None

    def get_source_address_in_blacklist(self):
        if self.source_addresses:
            q_list = reduce(lambda a, b: a | b, map(lambda n: Q(address__iexact=n), self.source_addresses.keys()))
            return BlacklistWalletAddress.objects.filter(q_list, is_active=True, is_deposit=True).filter(
                Q(currency=self.wallet.currency) | Q(currency__isnull=True)
            ).values_list('address', flat=True)
        return []

    def check_deposit_source(self, block_user=True):
        blacklist_addresses = self.get_source_address_in_blacklist()
        if blacklist_addresses:
            is_blacklisted = True
            blacklist_type = 'آدرس مبدا'
        else:
            is_blacklisted = False
            blacklist_type = None
        if is_blacklisted and block_user:
            from exchange.base.tasks import run_admin_task
            UserRestriction.add_restriction(
                self.wallet.user,
                UserRestriction.RESTRICTION.WithdrawRequest,
                considerations='ایجاد خودکار محدودیت برداشت به دلیل وجود {} در لیست سیاه برای شماره واریز {}'.format(
                    blacklist_type,
                    self.pk,
                ),
                description=UserRestrictionsDescription.DEPOSIT_NUMBER_IS_IN_BLACKLIST,
            )
            transaction.on_commit(
                lambda: run_admin_task('admin.assign_deposit_blacklist_tag', deposit_id=self.pk)
            )
            for channel in ['critical', 'operation']:
                Notification.notify_admins('* ConfirmedWalletDeposit:* #{}\n*Address:* {}'.format(
                    self.pk,
                    ' ، '.join(blacklist_addresses)
                ), title=f'⛔️ *واریز از {blacklist_type} لیست سیاه!!*', channel=channel)

    def get_external_url(self):
        # Before this date, we used OMNI-USDT, so transaction external link should be
        #  generated using OMNI explorer
        if self.currency == TETHER and self.created_at.date() < datetime.date(2019, 7, 5):
            return 'https://omniexplorer.info/tx/{}'.format(self.tx_hash)
        network = self.network
        return get_explorer_url(self.currency, txid=self.tx_hash, network=network)

    def save(self, *args, **kwargs):
        created = True if not self.pk else False
        if not self.address and not self.tag and not self.invoice:
            raise ValueError('All of address and tag and invoice cannot be null')
        super(ConfirmedWalletDeposit, self).save(*args, **kwargs)
        if created or (self.source_addresses != self.__original_source_addresses):
            self.check_deposit_source()


class AvailableDepositAddress(models.Model):
    """ Available Cold Wallet Addresses
    """
    currency = models.IntegerField(choices=Currencies)
    address = models.CharField(max_length=200)
    used_for = models.ForeignKey(WalletDepositAddress, null=True, blank=True, related_name='+', on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    type = models.IntegerField(choices=ADDRESS_TYPE, null=True, blank=True, default=ADDRESS_TYPE.standard)
    salt = models.CharField(max_length=256, null=True, blank=True)

    class Meta:
        unique_together = ['currency', 'address']
        verbose_name = 'آدرس سرد'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=['currency'],
                condition=Q(currency__in=TAG_NEEDED_CURRENCIES),
                name='idx_tagged_currencies_address',
            ),
        ]

    def __str__(self):
        s = '{}: {}'.format(self.get_currency_display(), self.address)
        if self.used_for:
            s += ' (Used)'
        return s

    @property
    def is_used(self):
        return self.used_for is not None

    @classmethod
    def get_deposit_address(cls, wallet, address_type=None, network=None):
        # TODO: double check for race conditions
        # LQw8fD9161Wc32GJibs7zo75f2CMGcZxr8
        if network is None:
            default_network = CURRENCY_INFO[wallet.currency]['default_network']
            network = default_network

        address_type_not_none = address_type if address_type else wallet.get_address_type_not_none(network)
        address_type_filter = Q(type=address_type_not_none)
        if address_type_not_none == ADDRESS_TYPE.standard:
            address_type_filter |= Q(type__isnull=True)
        available_addresses = cls.objects.select_for_update().filter(currency=wallet.currency, used_for__isnull=True).filter(address_type_filter)[:100]
        for addr in available_addresses:
            if addr.is_used:
                continue
            if WalletDepositAddress.objects.filter(address=addr.address).exists():
                continue
            da = WalletDepositAddress.objects.create(wallet=wallet, currency=wallet.currency, address=addr.address, type=addr.type, network=network, salt=addr.salt)
            addr.used_for = da
            addr.save()
            return da
        return None

    @classmethod
    def get_tagged_deposit_address(cls, currency, network=None):
        """ Coins with tags have a few deposit addresses that are shared among all
             users wallet using deposit tags. This method returns currently active
             address used by system for coin deposits of the given currency.
        """
        if currency in ton_contract_info['mainnet'].keys():
            currency = Currencies.ton
        return cls.objects.filter(currency=currency, used_for__isnull=True).order_by('-pk').first()


class AvailableHotWalletAddress(BalanceWatch):
    currency = models.IntegerField(choices=Currencies)
    address = models.CharField(max_length=200)
    total_received = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    total_sent = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    network = models.CharField(max_length=200, null=True, blank=True)
    active = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'کیف‌ پول گرم'
        verbose_name_plural = verbose_name

    def __str__(self):
        return 'HotWallet {}: {}'.format(get_currency_codename(self.currency), self.address)

    @property
    def current_balance(self):
        """ Return an estimate of current balance of this wallet,
             note that this is an estimate and may be out of date
        """
        return self.total_received - self.total_sent

    @property
    def currency_display(self):
        return self.get_currency_display()

    def update_balance(self):
        from .deposit import update_address_balances_for_currency
        update_address_balances_for_currency([self])

    def get_network(self):
        network = self.network
        if network is None:
            currency = self.currency
            network = CURRENCY_INFO.get(currency).get('default_network')
        return network


class BlacklistWalletAddress(BalanceWatch):
    PRIORITY_CHOICES = Choices(
        (100, 'low_risk', 'Low Risk'),
        (200, 'medium_risk', 'Medium Risk'),
        (300, 'high_risk', 'High Risk'),
    )
    currency = models.IntegerField(choices=Currencies, null=True)
    address = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    network = models.CharField(max_length=200, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=now, null=True, blank=True)
    is_withdraw = models.BooleanField(verbose_name='برداشت')
    is_deposit = models.BooleanField(verbose_name='واریز')
    image = models.ForeignKey(UploadedFile, null=True, related_name='+', on_delete=models.CASCADE)
    priority = models.SmallIntegerField(choices=PRIORITY_CHOICES, default=PRIORITY_CHOICES.low_risk)

    class Meta:
        verbose_name = 'لیست سیاه آدرس‌ها'
        verbose_name_plural = verbose_name

        indexes = [
            Index(Upper('address'), name='idx_wallet_blacklist_address'),
        ]

    def __str__(self):
        return '‌Blacklist Address {}: {}'.format(get_currency_codename(self.currency), self.address)

    @property
    def currency_display(self):
        return self.get_currency_display()

    def get_network(self):
        network = self.network
        if network is None:
            currency = self.currency
            network = CURRENCY_INFO.get(currency).get('default_network')
        return network


class SystemColdAddress(BalanceWatch):
    """ System Cold Address
    """
    currency = models.IntegerField(choices=Currencies)
    address = models.CharField(max_length=200)
    total_received = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    total_sent = models.DecimalField(max_digits=20, decimal_places=10, default=0)
    is_disabled = models.BooleanField(default=False)
    network = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        verbose_name = 'کیف‌ پول سرد سیستمی'
        verbose_name_plural = verbose_name

    @property
    def current_balance(self):
        """ Return an estimate of current balance of this wallet,
             note that this is an estimate and may be out of date
        """
        return self.total_received - self.total_sent

    @property
    def currency_display(self):
        return self.get_currency_display()

    def get_network(self):
        network = self.network
        if network is None:
            currency = self.currency
            network = CURRENCY_INFO.get(currency).get('default_network')
        return network


class BankDeposit(Confirmed, IPLogged):
    user = models.ForeignKey(User, related_name='bank_deposits', on_delete=models.CASCADE)
    receipt_id = models.CharField(max_length=255, verbose_name='شناسه رسید بانکی')
    src_bank_account = models.ForeignKey(BankAccount, verbose_name='حساب بانکی مبدا', on_delete=models.CASCADE)
    dst_bank_account = models.CharField(max_length=50, verbose_name='حساب بانکی مقصد', help_text='شماره حساب بانکی مقصد')
    dst_system_account = models.ForeignKey(DepositSystemBankAccount, null=True, blank=True, on_delete=models.PROTECT)
    deposited_at = models.DateField(verbose_name='تاریخ واریز', db_index=True, help_text='تاریخ واریز')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    description = models.TextField(null=True)

    # Financial
    amount = models.BigIntegerField(verbose_name='مبلغ واریزی', help_text='ریال')
    fee = models.BigIntegerField(default=0, verbose_name='کارمزد', help_text='ریال')
    transaction = models.ForeignKey('Transaction', null=True, blank=True, verbose_name='تراکنش', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'واریز بانکی'
        verbose_name_plural = verbose_name
        unique_together = ('receipt_id', 'deposited_at', 'user')

    def __str__(self):
        return 'BankDeposit ({}) for {}: {}'.format(self.receipt_id, self.user, self.status)

    @property
    def net_amount(self):
        return self.amount - self.fee

    @property
    def effective_date(self):
        if self.transaction:
            return self.transaction.created_at
        return self.created_at

    def get_fee(self):
        return int(self.amount * settings.NOBITEX_OPTIONS['bankFee'])

    def send_notif(self):
        Notification.objects.create(
            user=self.user,
            message='واریز بانکی به شناسه {} تایید و مبلغ {} تومان به کیف پول ریالی شما واریز گردید'.
                format(self.receipt_id, round(self.net_amount/10)),
        )
        Notification.notify_admins(
            'واریز بانکی کاربر {} به شناسه {} تایید شد.'.format(str(self.user), self.receipt_id),
            channel='critical',
        )
        if self.user.is_email_verified:
            # Email user
            EmailManager.send_email(
                self.user.email,
                'deposit',
                data={
                    'amount': self.net_amount,
                    'currency': 'ریال'
                },
                priority='low',
            )

    def commit_deposit(self):
        if self.transaction:
            return True
        # Create transaction and set fee
        wallet = Wallet.get_user_wallet(self.user, RIAL)
        description = 'واریز بانکی - شماره حساب: {} - شماره رسید بانکی: {}'.format(self.src_bank_account.account_number, self.receipt_id)
        transaction = wallet.create_transaction(tp='deposit', amount=self.net_amount, description=description, allow_negative_balance=True)
        transaction.commit(ref=self, allow_negative_balance=True)
        self.transaction = transaction
        self.status = self.STATUS.confirmed
        self.save(update_fields=['transaction', 'status'])
        self.send_notif()
        return True


class WithdrawRequest(models.Model):
    # Withdraw Status
    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'verified', 'Verified'),
        (3, 'accepted', 'Accepted'),
        (4, 'sent', 'Sent'),
        (5, 'done', 'Done'),
        (6, 'rejected', 'Rejected'),
        (7, 'processing', 'Processing'),
        (8, 'canceled', 'Canceled'),
        (9, 'waiting', 'Waiting'),
        (10, 'manual_accepted', 'Manual Accepted'),
    )
    STATUSES_INACTIVE = [STATUS.new, STATUS.canceled, STATUS.rejected]  # Waiting for the user/admin, no action required
    STATUSES_ACCEPTABLE = [STATUS.verified, STATUS.waiting]  # Can be moved to accepted state
    STATUSES_PENDING = [STATUS.verified, STATUS.accepted, STATUS.manual_accepted, STATUS.processing, STATUS.waiting]  # Eligible to enter automatic processing flow
    STATUSES_COMMITED = [STATUS.sent, STATUS.done]  # In finalizing state, can be considered done
    STATUSES_ACTIVE = STATUSES_PENDING + STATUSES_COMMITED
    STATUSES_CANCELABLE = STATUSES_ACCEPTABLE + [STATUS.new, STATUS.accepted, STATUS.processing]
    STATUSES_CANCELED = [STATUS.canceled, STATUS.rejected]
    # Reject transition to lower states
    STATUSES_STATE_INDEX = {
        STATUS.new: 1,
        STATUS.verified: 2,
        STATUS.waiting: 3,
        STATUS.accepted: 4,
        STATUS.manual_accepted: 4,
        STATUS.processing: 5,
        STATUS.sent: 6,
        STATUS.done: 7,
        STATUS.canceled: 8,
        STATUS.rejected: 9,
    }
    STATUSES_ORDER = [STATUS.accepted, STATUS.manual_accepted, STATUS.processing, STATUS.waiting, STATUS.verified]
    # Withdraw Types
    TYPE = Choices(
        (0, 'normal', 'Normal'),
        (1, 'internal', 'Internal'),
        (2, 'gateway', 'Gateway'),
    )
    # Settlement Methods
    SETTLE_METHOD = Choices(
        (0, 'payir', 'PayIR'),
        (1, 'vandar', 'Vandar'),
        (2, 'jibit', 'Jibit'),
        (3, 'jibit_v2', 'JibitV2'),
        (4, 'toman', 'Toman'),
    )

    tp = models.IntegerField(choices=TYPE, default=TYPE.normal)
    wallet = models.ForeignKey(Wallet, related_name='withdraw_requests', on_delete=models.CASCADE)
    target_address = models.CharField(max_length=200, blank=True)
    target_account = models.ForeignKey(BankAccount, null=True, blank=True, related_name='withdraw_requests', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=WITHDRAW_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES)
    status = models.IntegerField(choices=STATUS, default=STATUS.new, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    explanations = models.TextField(default='', blank=True)
    updates = models.TextField(default='', blank=True)
    transaction = models.ForeignKey('Transaction', null=True, blank=True, on_delete=models.CASCADE)
    blockchain_url = models.CharField(max_length=1000, null=True, blank=True)
    withdraw_from = models.ForeignKey(SystemBankAccount, null=True, blank=True, on_delete=models.CASCADE)
    tag = models.CharField(max_length=100, null=True, blank=True)
    rial_value = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='ارزش ریالی')
    fee = models.DecimalField(max_digits=25, decimal_places=10, null=True, blank=True, verbose_name='کارمزد')
    network = models.CharField(max_length=200, null=True, blank=True)
    invoice = models.CharField(max_length=4300, null=True, blank=True)
    # Verification
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    otp = models.CharField(max_length=6, null=True, blank=True)
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    ip = models.GenericIPAddressField(null=True, blank=True)
    contract_address = models.CharField(max_length=256, null=True, blank=True, default=None)

    anomaly_score = models.SmallIntegerField(null=True, blank=True)
    is_otp_required = True

    requester_service = models.CharField(choices=Services.choices(), max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = 'درخواست برداشت'
        verbose_name_plural = verbose_name
        indexes = (
            models.Index(
                fields=('wallet_id', 'created_at'),
                condition=Q(status=1),
                name='idx_withdraw_news',
            ),
        )

    def __str__(self):
        return 'WithdrawRequest#{}'.format(self.pk)

    @property
    def effective_date(self):
        if self.transaction:
            return self.transaction.created_at
        return self.created_at

    @property
    def currency(self):
        return self.wallet.currency

    @property
    def is_rial(self):
        return self.wallet.is_rial

    @property
    def is_internal(self):
        """Whether this withdraw is detected as an internal Nobitex transfer."""
        return self.tp == self.TYPE.internal

    @property
    def is_expired(self):
        """ Whether this request is old and should not be accepted
            Expiration is only for verifying new requests by the user,
            so when a request is verified and is waiting to be processed,
            expiration will not be checked for it.
        """
        return self.status == self.STATUS.new and now() - self.created_at > datetime.timedelta(minutes=30)

    @property
    def is_accepted(self):
        accepted_statuses = [self.STATUS.accepted, self.STATUS.manual_accepted]

        if self.status in accepted_statuses:
            return True
        return False

    @property
    def settlement_method(self):
        """ Find the method used for settlement of this withdraw
        """
        if not self.blockchain_url:
            return None
        if '/WJ' in self.blockchain_url:
            if self.created_at and self.created_at < datetime.datetime(2022, 1, 19, 10, 0, 0, 0, pytz.utc):
                return self.SETTLE_METHOD.jibit
            return self.SETTLE_METHOD.jibit_v2
        if '/WV' in self.blockchain_url:
            return self.SETTLE_METHOD.vandar
        if '/WP' in self.blockchain_url:
            return self.SETTLE_METHOD.payir
        if '/WT' in self.blockchain_url:
            return self.SETTLE_METHOD.toman
        return None

    @property
    def is_lightning(self):
        return self.network == 'BTCLN'

    @property
    def is_vandar(self):
        return self.target_account and self.target_account.bank_id == BankAccount.BANK_ID.vandar

    def get_settlement_manager(self, method=None):
        """ Return the instantiated BaseSettlement object for this withdraw
        """
        from .settlement import JibitSettlement, JibitSettlementV2, TomanSettlement, VandarSettlement
        if method is None:
            method = self.settlement_method
        if method == self.SETTLE_METHOD.jibit:
            return JibitSettlement(self)
        if method == self.SETTLE_METHOD.jibit_v2:
            return JibitSettlementV2(self)
        if method == self.SETTLE_METHOD.toman:
            return TomanSettlement(self)
        if method == self.SETTLE_METHOD.vandar:
            return VandarSettlement(self)
        return None

    def get_target_display(self):
        if self.is_rial:
            return self.target_account.shaba_number if self.target_account else '-'
        return self.target_address or '-'

    def verify_otp(self, otp: str) -> bool:
        if not otp or not self.otp:
            return False
        otp = str(otp)
        if len(otp) != 6:
            return False
        if self.is_expired:
            return False
        if otp != self.otp:
            return False
        return True

    def check_status_transition(self, old_status):
        # TODO: check all transitions based on complete transition graph
        new_status = self.status
        if not old_status:
            return True
        if new_status == old_status:
            return True

        if self.STATUSES_STATE_INDEX.get(new_status) < self.STATUSES_STATE_INDEX.get(old_status):
            return False

        extra_deny_transition = [
            (self.STATUS.sent, self.STATUS.canceled),
            (self.STATUS.done, self.STATUS.canceled),
        ]
        if (old_status, new_status) in extra_deny_transition:
            return False
        return True

    def recheck_request(self):
        """ Check whether this request fields are valid, and reject request if not
             This does not check user wallet balances.
        """
        if self.status in [self.STATUS.canceled, self.STATUS.rejected]:
            return
        reject = False
        # Only do minimal checks after the transaction is created
        if self.transaction:
            if self.transaction.wallet != self.wallet:
                reject = True
            if self.transaction.amount >= Decimal('0'):
                reject = True
            if reject:
                self.transaction = None
                self.status = self.STATUS.rejected
                self.save(update_fields=['status', 'transaction'])
            return
        # Do more check before the request is verified
        if self.status and self.status > self.STATUS.verified:
            return
        if self.amount <= Decimal('0'):
            reject = True
        if self.is_rial:
            if self.target_account:
                if not self.target_account.confirmed:
                    reject = True
                if self.target_account.user != self.wallet.user:
                    if (
                        self.target_account != BankAccount.get_generic_system_account() and
                        self.target_account != BankAccount.get_system_gift_account()
                    ):
                        reject = True
            else:
                reject = True
        if reject:
            self.system_reject_request()

    def system_reject_request(self, save=True):
        self.status = self.STATUS.rejected
        if save:
            self.save(update_fields=['status'])

    def cancel_request(self):
        """Cancel a request because of user request if it is not processed yet.

        Note that the caller should check for WITHDRAW_ENABLE_CANCEL settings itself and
        only call this method if it is really sure to cancel the withdraw.
        """
        if not self.is_cancelable:
            return False
        with transaction.atomic():
            self.status = WithdrawRequest.STATUS.canceled
            self.save(update_fields=['status'])
            if settings.WITHDRAW_CREATE_TX_VERIFY and self.transaction:
                t = self.create_reverse_transaction()
                if not t:
                    return False
        return True

    def is_in_blacklist(self):
        return BlacklistWalletAddress.objects.filter(address__iexact=self.target_address, is_active=True, is_withdraw=True).filter(
            Q(currency=self.wallet.currency) | Q(currency__isnull=True)
        ).exists()

    def is_ip_in_blacklist(self):
        return IPBlackList.contains(self.ip)

    def check_withdraw_destination(self, block_user=True):
        if self.is_in_blacklist():
            is_blacklisted = True
            blacklist_type = 'آدرس مقصد'
        elif self.is_ip_in_blacklist():
            is_blacklisted = True
            blacklist_type = 'آی‌پی مبدا'
        else:
            is_blacklisted = False
            blacklist_type = None
        if is_blacklisted and block_user:
            from exchange.base.tasks import run_admin_task
            UserRestriction.add_restriction(
                self.wallet.user,
                UserRestriction.RESTRICTION.WithdrawRequest,
                considerations='ایجاد خودکار محدودیت برداشت به دلیل وجود {} در لیست سیاه برای شماره درخواست {}'.format(
                    blacklist_type,
                    self.pk,
                ),
                description=UserRestrictionsDescription.REQUEST_NUMBER_IS_IN_BLACKLIST,
            )
            transaction.on_commit(
                lambda: run_admin_task('admin.assign_blacklist_tag', withdraw_id=self.pk)
            )
            for channel in ['critical', 'operation']:
                Notification.notify_admins('*WithdrawRequest:* #{}\n*Address:* {}'.format(
                    self.pk,
                    self.target_address,
                ), title=f'⛔️ *برداشت به {blacklist_type} لیست سیاه!!*', channel=channel)

    def create_transaction(self):
        if self.transaction and self.transaction.pk:
            return
        # Prepare a description for transaction
        if self.tp == self.TYPE.internal and self.wallet.user_id == User.get_gift_system_user().id:
            transaction_description = 'دریافت کارت هدیه توسط کاربر'
        elif self.explanations == 'بابت صدور کارت هدیه':
            transaction_description = self.explanations
        elif self.explanations.startswith('تسویه نهایی با سرویس دهنده'):
            transaction_description = 'تسویه نهایی با سرویس دهنده در سرویس اعتبار‌ریالی'
        else:
            transaction_description = 'Withdraw to "{}"'.format(self.target_address)
        # Create withdraw transaction
        transaction = self.wallet.create_transaction(
            tp='gateway' if self.tp == self.TYPE.gateway else 'withdraw',
            amount=-self.amount,
            description=transaction_description,
        )
        if not transaction:
            self.system_reject_request()
            return
        transaction.commit(ref=self)
        self.transaction = transaction
        self.save(update_fields=['transaction'])

    def create_reverse_transaction(self):
        if not self.transaction or not self.transaction.pk:
            return
        with transaction.atomic():
            target_address = self.get_internal_target_wallet()
            if target_address:
                if isinstance(target_address, Wallet):
                    target_wallet = target_address
                else:
                    target_wallet = target_address.wallet
                internal_deposit_transaction = Transaction.objects.filter(
                    wallet=target_wallet,
                    ref_module=Transaction.REF_MODULES['InternalTransferDeposit'],
                    ref_id=self.pk,
                ).first()
                deposit_reverse_transaction = target_wallet.create_transaction(
                    tp='refund',
                    amount=-internal_deposit_transaction.amount,
                    description='تراکنش اصلاحی بازگشت درخواست برداشت #{} و تراکنش #{}'.format(self.pk, internal_deposit_transaction.pk),
                )
                if not deposit_reverse_transaction:
                    return
                deposit_reverse_transaction.commit(ref=Transaction.Ref('ReverseTransaction', internal_deposit_transaction.pk))
                if target_wallet == self.wallet:
                    self.wallet.refresh_from_db()

            withdraw_transaction = self.wallet.create_transaction(
                tp='refund',
                amount=-self.transaction.amount,
                description='تراکنش اصلاحی بازگشت درخواست برداشت #{} و تراکنش #{}'.format(self.pk, self.transaction.pk),
            )
            if not withdraw_transaction:
                return
            withdraw_transaction.commit(ref=Transaction.Ref('ReverseTransaction', self.transaction.pk))
            return withdraw_transaction

    def do_verify(self):
        """ Update status of unverified (new) requests from new to verified
        """
        # TODO: can a race condition cause a status transition from (x!=new)->(verified) ?
        if self.status != self.STATUS.new:
            return
        with transaction.atomic():
            if settings.WITHDRAW_CREATE_TX_VERIFY:
                self.refresh_from_db()
                self.create_transaction()
                if not self.transaction or not self.transaction.pk:
                    return
            self.status = self.STATUS.verified
            self.save(update_fields=['status'])
        self.split_if_needed()

    def split_if_needed(self):
        """ Splitting large rial deposit
              e.g. [ Withdraw(90m) = Withdraw(50m) + Withdraw(40) ]
        """
        withdraw_requests = [self]
        if not self.is_rial:
            return None

        is_vandar = self.is_vandar
        max_fee = (
            int(settings.NOBITEX_OPTIONS['withdrawFees'][Currencies.rls])
            if not is_vandar
            else Decimal(Settings.get_value('vandar_withdraw_max_fee', settings.VANDAR_WITHDRAW_MAX_FEE_DEFAULT))
        )
        min_amount = 15_000_0
        max_amount = (
            Decimal(Settings.get_value(
                key='vandar_withdraw_max_settlement',
                default=settings.VANDAR_WITHDRAW_MAX_SETTLEMENT_DEFAULT
            ))
            if is_vandar
            else 50_000_000_0
        )
        # Detect splits if necessary
        total_amount = int(self.amount)
        if total_amount <= max_amount:
            self.fee = min(total_amount // 100, max_fee)
            self.save(update_fields=['fee'])
            return withdraw_requests

        split_count = math.ceil(total_amount / max_amount)
        adjust_amount = 0
        remaining_amount = total_amount % max_amount
        if remaining_amount and remaining_amount < min_amount:
            adjust_amount = min_amount - remaining_amount
            remaining_amount += adjust_amount

        # Update this requests properties
        self.fee = max_fee
        self.amount = max_amount - adjust_amount
        self.rial_value = self.amount
        self.save(update_fields=['amount', 'rial_value', 'fee'])

        # Create remaining requests
        for i in range(1, split_count):
            amount = max_amount
            if i == split_count - 1 and remaining_amount:
                amount = remaining_amount

            new_withdraw = WithdrawRequest.objects.create(
                tp=self.tp,
                wallet_id=self.wallet_id,
                target_address=self.target_address,
                target_account_id=self.target_account_id,
                amount=amount,
                status=self.status,
                created_at=self.created_at,
                explanations=self.explanations,
                updates=self.updates,
                transaction_id=self.transaction_id,
                blockchain_url=self.blockchain_url,
                withdraw_from_id=self.withdraw_from_id,
                tag=self.tag,
                rial_value=amount,
                fee=min(amount // 100, max_fee),
                network=self.network,
                invoice=self.invoice,
                token=self.token,
                otp=self.otp,
                uid=self.uid,
                ip=self.ip,
                contract_address=self.contract_address,
                anomaly_score=self.anomaly_score,
            )  # Create a new instance
            withdraw_requests.append(new_withdraw)

        return withdraw_requests

    ###########
    #  Other  #
    ###########
    def save(self, *args, update_fields=None, **kwargs):
        if not self.otp:
            self.otp = random_string_digit(6)
            if update_fields:
                update_fields = (*update_fields, 'otp')

        old_object = WithdrawRequest.objects.filter(pk=self.pk).first() if self.pk else None
        old_status = old_object.status if old_object else None
        # Check status transition and revert if invalid
        if not self.check_status_transition(old_status):
            Notification.notify_admins(
                'WithdrawRequest #{} changed from "{}" to "{}"! Change prevented.'.format(self.pk, old_object.status, self.status),
                title='Invalid Status Transition',
                channel='critical',
            )
            self.status = old_status or self.STATUS.new
            if update_fields:
                update_fields = (*update_fields, 'status')

        # Save to database
        super(WithdrawRequest, self).save(*args, update_fields=update_fields, **kwargs)
        # On-save checks
        self.recheck_request()
        self.check_withdraw_destination()
        if self.status in self.STATUSES_COMMITED:
            self.create_transaction()
        # Send notifications if status is updated
        if not update_fields or 'status' in update_fields:
            self.send_withdraw_email(old_status)

    def calculate_fee(self):
        """ Withdraw fee for rial deposits

            Note: the amount of fee is rounded down to not over-charge customers
        """
        if not self.is_rial:
            raise ValueError('Invalid call to calculate_fee in coin withdraw')
        if self.fee is not None:
            return self.fee

        max_fee = (
            int(settings.NOBITEX_OPTIONS['withdrawFees'][Currencies.rls])
            if not self.is_vandar
            else Settings.get_decimal('vandar_withdraw_max_fee', settings.VANDAR_WITHDRAW_MAX_FEE_DEFAULT)
        )
        return min(self.amount // 100, max_fee)

    def send_withdraw_email(self, previous_status):
        if self.target_address == BankAccount.get_generic_system_account():
            # Ignore special-case withdraw that are owned by the system account
            return

        if not previous_status:
            return
        if previous_status not in self.STATUSES_COMMITED and self.status in self.STATUSES_COMMITED:
            EmailManager.send_withdraw_request_status_update(self)

    @property
    def is_internal_service(self):
        return self.requester_service is not None

    ########################
    #  Automatic Withdraw  #
    ########################
    @property
    def is_cancelable(self):
        """Check if this request can be canceled based on the status of request itself and
        its possibly related AutomaticWithdraw objects.
        """
        if self.is_rial:
            return self.status in self.STATUSES_CANCELABLE
        # Check if AutomaticWithdraw is retrying
        try:
            already_processed = self.auto_withdraw.status not in AutomaticWithdraw.STATUSES_AUTOMATIC_RETRY
        except AutomaticWithdraw.DoesNotExist:
            already_processed = False
        if already_processed:
            return False
        return self.status in self.STATUSES_CANCELABLE

    def can_automatically_send(self, timestamp=None):
        if self.is_rial and not self.is_internal:
            if not Settings.get_trio_flag('withdraw_enabled_rls_auto', default='yes'):
                return False
            nw = timestamp or ir_now()
            if not 8 <= nw.hour <= 20:
                return False
            to_minute = 45
            if self.status == self.STATUS.processing:
                # There is a 3m delay in sending requests to allow users to cancel,
                #  so a request accepted on 45' is processed on 48'. Here we consider
                #  a 4m window to ensure all such requests are handled.
                to_minute += 4
            if not 35 <= nw.minute <= to_minute:
                return False
        return self.status in self.STATUSES_PENDING

    ############################
    #  Internal Coin Transfer  #
    ############################
    def get_internal_target_wallet_tagged(self) -> WalletDepositTag | None:
        """for internal transfer of tag coins corresponding destination tag is required
        this function do the detection job (so it returns WalletDepositTag object as result or None
        if it didn't find
        """
        currency = self.currency
        if currency in ton_contract_info['mainnet'].keys():
            shared_tagged_addresses = AvailableDepositAddress.objects.filter(
                address=self.target_address, currency=Currencies.ton
            ).first()
        else:
            shared_tagged_addresses = AvailableDepositAddress.objects.filter(
                address=self.target_address, currency=currency
            ).first()
        if not shared_tagged_addresses:
            return None
        tag = parse_int(self.tag, currency in TAG_NEEDED_CURRENCIES)
        tag_object = WalletDepositTag.objects.filter(tag=tag, currency=currency).first()
        if tag_object:
            return tag_object
        #  in case of destination user didn't make the wallet for this coin
        base_tag = WalletDepositTag.objects.filter(tag=tag).first()
        if not base_tag:
            return None
        currency_wallet = Wallet.get_user_wallet(user=base_tag.wallet.user, currency=currency)
        new_tag = currency_wallet.get_current_deposit_tag(create=True)
        if new_tag.tag == tag:
            return new_tag
        return None

    def get_internal_target_wallet(self):
        """ Return the address object for this withdraw request's target address, or
             None if the withdraw request is not Nobitex-internal.
        """
        currency = self.wallet.currency
        network = self.network or CURRENCY_INFO[currency]['default_network']
        # IRR Internal System Transfer
        if currency == RIAL:
            if self.tp == self.TYPE.internal:
                gift_user = User.get_gift_system_user()
                if self.target_account and self.target_account.user_id == gift_user.id:
                    return Wallet.get_user_wallet(gift_user, RIAL)
            return None
        # Tag-based deposits
        if self.wallet.is_address_tag_required(network=network):
            deposit_tag = self.get_internal_target_wallet_tagged()
            return deposit_tag
        # Normal deposits
        target_address = self._internal_address_convertor(network)
        is_address_case_sensitive = network not in ETHEREUM_LIKE_NETWORKS
        if is_address_case_sensitive:
            target_address_query = Q(address=target_address)
        else:
            target_address_query = Q(address=target_address.lower())
        network_model_filter = Q(network=network)
        if network == CURRENCY_INFO[currency]['default_network']:
            network_model_filter |= Q(network__isnull=True)
        contract_address_filter = Q(contract_address=self.contract_address) if self.contract_address else Q(contract_address__isnull=True)
        try:
            return WalletDepositAddress.objects.get(target_address_query, network_model_filter, contract_address_filter, wallet__currency=currency)
        except WalletDepositAddress.DoesNotExist:
            if f'{network}' in ADDRESS_REUSED_NETWORK and f'{currency}-{network}' not in MAIN_ADDRESS_CURRENCIES:
                source_currency = ADDRESS_REUSED_NETWORK[f'{network}']
                source_address = WalletDepositAddress.objects.filter(
                    target_address_query,
                    wallet__currency=source_currency,
                ).first()
                if source_address is None:
                    return None
                target_address = Wallet.get_user_wallet(source_address.wallet.user, currency).get_current_deposit_address(create=True, network=network, address_type=source_address.type, contract_address=self.contract_address)
                if target_address and target_address.address == self.target_address:
                    return target_address
            return None

    def _internal_address_convertor(self, network) -> str:
        if network == CurrenciesNetworkName.ONE:
            try:
                return one_to_eth_address(self.target_address)
            except Exception:
                report_exception()
                exc_type, exc_value, exc_tb = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_tb)
                return self.target_address
        return self.target_address

    @classmethod
    def check_user_limit(cls, user: User, currency) -> bool:
        """Check if the user is allowed to submit a new withdraw request for
        this currency or not.
        """
        if cls.is_new_requests_limit_exceeded(user):
            return False
        if cls.is_verified_requests_limit_exceeded(user, currency):
            return False
        return True

    @classmethod
    def is_new_requests_limit_exceeded(cls, user: User) -> bool:
        """Check for excessive requests with "New" status.

        See: https://bitex-doc.nobitex.ir/doc/withdraw-cQ7fhq3vDG#h-محدودیت-ثبت-درخواست-برداشت
        """
        recent_new_requests_count = cls.objects.filter(
            wallet__user=user,
            status=cls.STATUS.new,
            created_at__gte=now() - datetime.timedelta(hours=4),
        ).count()
        return recent_new_requests_count >= int(Settings.get_value('max_new_withdrawal_request', 40))

    @classmethod
    def is_verified_requests_limit_exceeded(cls, user: User, currency: int) -> bool:
        """Check for excessive requests with "Verified" status.

        See: https://bitex-doc.nobitex.ir/doc/withdraw-cQ7fhq3vDG#h-محدودیت-ثبت-درخواست-برداشت
        """
        withdraws = cls.objects.filter(
            wallet__user=user,
            status=cls.STATUS.verified,
            created_at__gte=now() - datetime.timedelta(days=1),
        )
        if currency == RIAL:
            withdraws = withdraws.filter(wallet__currency=currency)
        return withdraws.count() >= int(Settings.get_value('max_verified_withdrawal_request', 10))

    @classmethod
    def get_financially_pending_requests(cls, wallet=None):
        pending_withdraws = cls.objects.filter(transaction__isnull=True).exclude(status__in=cls.STATUSES_INACTIVE)
        if wallet:
            pending_withdraws = pending_withdraws.filter(wallet=wallet)
        return pending_withdraws

    @classmethod
    def get_rial_value_summation(cls, user, dt_from, just_rial=False, currency=None):
        """ Return the total value for user withdraws for all crypto coins
            or for a specific given currency.
        """
        withdraws = cls.objects.filter(wallet__user=user, status__in=cls.STATUSES_ACTIVE)
        if just_rial:
            currency = RIAL
        if currency:
            withdraws = withdraws.filter(wallet__currency=currency)
        else:
            # TODO: This can be simplified to: exclude(RIAL)
            withdraws = withdraws.filter(wallet__currency__in=ACTIVE_CRYPTO_CURRENCIES)
        withdraws = withdraws.filter(Q(transaction__created_at__gte=dt_from) | Q(created_at__gte=dt_from))
        return withdraws.aggregate(sum=Sum('rial_value'))['sum'] or Decimal('0')

    @classmethod
    def get_rial_value_summation_for_rial_and_coin(cls, user, dt_from):
        """Return the total values for both user withdraws with all crypto coins
        and with rls currency.
        """
        currencies = ACTIVE_CRYPTO_CURRENCIES + [Currencies.rls]
        withdraws = cls.objects.filter(
            wallet__user=user, status__in=cls.STATUSES_ACTIVE, wallet__currency__in=currencies
        )
        withdraws = withdraws.filter(Q(transaction__created_at__gte=dt_from) | Q(created_at__gte=dt_from))
        withdraws = withdraws.values('wallet__currency').annotate(sum_rial_value=Coalesce(Sum('rial_value'), ZERO))

        coin_withdrawals_value = Decimal('0')
        rial_withdrawals_value = Decimal('0')
        for withdraw in withdraws:
            if withdraw['wallet__currency'] == Currencies.rls:
                rial_withdrawals_value += withdraw['sum_rial_value']
            else:
                coin_withdrawals_value += withdraw['sum_rial_value']
        return coin_withdrawals_value, rial_withdrawals_value

    @classmethod
    def get_total_amount(cls, user, currency, dt_from=None, network=None):
        """ Return total user withdraw amount for currency
        """
        withdraws = cls.objects.filter(
            wallet__user=user,
            wallet__currency=currency,
            status__in=cls.STATUSES_ACTIVE,
        )
        if network:
            withdraws = withdraws.filter(network=network)
        if dt_from:
            withdraws = withdraws.filter(Q(transaction__created_at__gte=dt_from) | Q(created_at__gte=dt_from))
        return withdraws.aggregate(sum=Sum('amount'))['sum'] or Decimal('0')

    @classmethod
    def status_display(cls, status):
        for k, v in cls.STATUS._identifier_map.items():
            if v == status:
                return k
        return None

    @classmethod
    def is_over_shaba_limit(cls, wallet: Wallet, amount: Decimal, target_account: BankAccount,
                            just_committed_statuses: bool = False) -> bool:
        """
        Check total rial withdraw to a specific SHEBA
        """

        # acquire an ADVERSITY lock on db.
        # the lock will be released after outer transaction commit or rollback,
        # if no outer transaction exist, no lock will be acquired.
        Locker.require_lock(lock_type=Locker.WITHDRAW_VERIFICATION, lock_id=wallet.id)

        accepted_statuses = WithdrawRequest.STATUSES_ACTIVE
        if just_committed_statuses:
            accepted_statuses = WithdrawRequest.STATUSES_COMMITED

        amount_withdrawn_today = (
            wallet.withdraw_requests.filter(
                status__in=accepted_statuses,
                created_at__date=ir_now().date(),
                target_account=target_account,
            ).aggregate(sum=Sum('amount'))['sum']
            or 0
        )
        return amount_withdrawn_today + amount > 500_000_000_0

    @classmethod
    def can_withdraw_shaba(cls, wallet: Wallet, amount: Decimal, target_account: BankAccount) -> bool:
        """
        Withdrawal limit for each Shaba number in one day
        Except those have a specific tag (برداشت بیشتر از محدودیت شبا)
        In production, transactions are created when the withdrawal is sent to the bank.
        """
        has_over_shaba_limit_tag = wallet.user.tags.filter(name='برداشت بیشتر از محدودیت شبا').exists()
        if has_over_shaba_limit_tag:
            return True
        return not cls.is_over_shaba_limit(wallet, amount, target_account)

    @classmethod
    def is_user_not_allowed_to_withdraw(cls, user: User, wallet: Wallet) -> bool:
        restrictions = [
            ur.restriction
            for ur in user.get_restrictions(
                UserRestriction.RESTRICTION.WithdrawRequest,
                UserRestriction.RESTRICTION.WithdrawRequestRial,
                UserRestriction.RESTRICTION.WithdrawRequestCoin,
            )
        ]

        if UserRestriction.RESTRICTION.WithdrawRequest in restrictions:
            return True
        if wallet.is_rial and UserRestriction.RESTRICTION.WithdrawRequestRial in restrictions:
            return True
        if wallet.is_crypto_currency and UserRestriction.RESTRICTION.WithdrawRequestCoin in restrictions:
            return True
        if wallet.is_crypto_currency and settings.IS_TESTNET:
            return True
        if Wallet.objects.filter(user=user, balance__lt=0).exists():
            return True

        return False


class AutomaticWithdraw(models.Model):
    TYPE = Choices(
        (1, 'fake', 'Fake'),
        (2, 'fake_batch', 'Fake Batch'),
        (10, 'binance', 'Binance'),
        (20, 'electrum', 'Electrum'),
        (21, 'lnd_hotwallet', 'LND Hot Wallet'),
        (30, 'geth', 'Geth'),
        (31, 'geth_erc20', 'Geth(ERC20)'),
        (32, 'eth_hotwallet', 'ETH Hot Wallet'),
        (33, 'eth_erc20_hotwallet', 'ETH ERC20 Hot Wallet'),
        (34, 'eth_hd_hotwallet', 'ETH HD Hot Wallet'),
        (35, 'eth_hd_hotwallet_erc20', 'ETH HD Hot Wallet(ERC20)'),
        (36, 'eth_only_hd_hotwallet', 'ETH Only HD Hot Wallet'),
        (37, 'eth_hd_hotwallet_erc20_n2', 'ETH HD #2 Hot Wallet(ERC20)'),
        (40, 'electrum_ltc', "Electrum LTC"),
        (50, 'parity', "Parity"),
        (60, 'ripple_api', "Ripple API"),
        (61, 'xrp_hotwallet', "XRP Hot Wallet"),
        (70, 'tether_erc20', "Tether(ERC20)"),
        (71, 'usdt_trx', "Tether(TRC20)"),
        (72, 'trx_trc20_hotwallet', 'TRX TRC20 NEW'),
        (80, 'electron_cash', 'Electron Cash'),
        (90, 'bnb_hot_wallet_api', "BNB API"),
        (100, 'vandar_api', 'Vandar API'),
        (110, 'trx_hotwallet', 'TRX Hot Wallet'),
        (111, 'ztrx_hotwallet', 'TRX ZAddress Hot Wallet'),
        (112, 'trx_hd_hotwallet_trc20', 'TRX HD Hot Wallet(TRC20)'),
        (113, 'trx_only_hd_hotwallet', 'TRX Only HD Hot Wallet'),
        (120, 'xlm_hotwallet', 'XLM Hot Wallet'),
        (130, 'pmn_hotwallet', 'PMN Hot Wallet'),
        (140, 'doge_hotwallet', 'DOGE Hot Wallet'),
        (150, 'etc_hotwallet', 'ETC Hot Wallet'),
        (151, 'etc_hd_hotwallet', 'ETC HD Hot Wallet'),
        (160, 'eos_hotwallet', 'EOS Hot Wallet'),
        (170, 'bsc_hotwallet', 'BSC Hot Wallet'),
        (171, 'bsc_hotwallet_bep20', 'BSC Hot Wallet(BEP20)'),
        (172, 'bsc_geth', 'BSC Geth Wallet'),
        (173, 'bsc_geth_bep20', 'BSC Geth Wallet(BEP20)'),
        (174, 'bsc_hd_hotwallet', 'BSC HD Hot Wallet'),
        (175, 'bsc_hd_hotwallet_bep20', 'BSC HD Hot Wallet(BEP20)'),
        (180, 'dot_hotwallet', 'DOT Hot Wallet'),
        (190, 'ada_hotwallet', 'ADA Hot Wallet'),
        (200, 'ftm_hotwallet', 'FTM Hot Wallet'),
        (201, 'ftm_hotwallet_erc20', 'FTM Hot Wallet(ERC20)'),
        (202, 'ftm_hd_hotwallet', 'FTM HD Hot Wallet'),
        (210, 'polygon_hotwallet', 'POLYGON Hot Wallet'),
        (211, 'polygon_hotwallet_erc20', 'POLYGON Hot Wallet(ERC20)'),
        (212, 'matic_hd_hotwallet', 'POLYGON HD Hot Wallet'),
        (213, 'matic_hd_hotwallet_erc20', 'POLYGON HD Hot Wallet(ERC20)'),
        (220, 'avax_hotwallet', 'AVAX Hot Wallet'),
        (221, 'avax_hd_hotwallet', 'AVAX HD Hot Wallet'),
        (230, 'harmony_hotwallet', 'HARMONY Hot Wallet'),
        (231, 'harmony_hd_hotwallet', 'HARMONY HD Hot Wallet'),
        (240, 'atom_hotwallet', 'ATOM Hot Wallet'),
        (250, 'near_hotwallet', 'NEAR Hot Wallet'),
        (260, 'solana_hotwallet', 'SOLANA Hot Wallet'),
        (261, 'solana_hotwallet_tokens', 'SOLANA Tokens Hot Wallet'),
        (270, 'monero_hotwallet', 'MONERO Hot Wallet'),
        (280, 'algo_hotwallet', 'ALGO Hot Wallet'),
        (290, 'hbar_hotwallet', "HBAR Hot Wallet"),
        (300, 'flow_hotwallet', "FLOW Hot Wallet"),
        (310, 'aptos_hotwallet', "APTOS Hot Wallet"),
        (320, 'fil_hotwallet', "FILECOIN Hot Wallet"),
        (330, 'flare_hotwallet', "FLARE Hot Wallet"),
        (340, 'egld_hotwallet', "EGLD Hot Wallet"),
        (350, 'arb_hotwallet', "ARB Hot Wallet"),
        (351, 'arb_hotwallet_erc20', "ARB Hot Wallet(ERC20)"),
        (352, 'usdt_arbitrum', "Tether(Arbitrum)"),
        (353, 'arb_hd_hotwallet', "ARB HD Hot Wallet"),
        (354, 'arb_hd_hotwallet_erc20', "ARB HD Hot Wallet(ERC20)"),
        (360, 'ton_hotwallet', "TON Hot Wallet"),
        (361, 'ton_hlv2_hotwallet', "TON Highload V2 Hot Wallet"),
        (362, 'ton_token_hlv2_hotwallet', "TON Token Highload V2 Hot Wallet"),
        (370, 'xtz_hotwallet', "Tezos Hot Wallet"),
        (380, 'enj_hotwallet', "Enjin Hot Wallet"),
        (390, 's_hd_hotwallet', "Sonic HD Hot Wallet"),
        (400, 'base_hd_hotwallet', "Base HD Hot Wallet"),
        (401, 'base_hd_hotwallet_erc20', "Base HD Hot Wallet(ERC20)"),
    )
    STATUS = Choices(
        (0, 'new', 'New'),
        (1, 'failed', 'Failed'),
        (2, 'done', 'Done'),
        (3, 'canceled', 'Canceled'),
        (4, 'sending', 'Sending'),
        (5, 'waiting', 'Waiting'),
        (6, 'diff', 'Diff-Non-Zero'),
        (7, 'accepted', 'Accepted')
    )
    STATUSES_RETRY = [STATUS.new, STATUS.failed, STATUS.waiting, STATUS.diff, STATUS.accepted]
    STATUSES_AUTOMATIC_RETRY = [STATUS.new, STATUS.waiting, STATUS.accepted]
    STATUSES_COMMITED = [STATUS.sending, STATUS.done]

    withdraw = models.OneToOneField(WithdrawRequest, related_name='auto_withdraw', on_delete=models.CASCADE)
    tp = models.IntegerField(choices=TYPE)
    binance_id = models.CharField(max_length=300, null=True, blank=True)
    transaction_id = models.CharField(max_length=300, null=True, blank=True)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_type_codename(cls, withdraw_type):
        for k, v in cls.TYPE._identifier_map.items():
            if v == withdraw_type:
                return k
        return None

    def processing_timeout(self, timeout=None):
        if timeout is None:
            timeout = 180
            if self.tp == self.TYPE.parity:
                timeout = 300

        _now = now()
        created_at = self.created_at
        tdelta = _now - created_at
        if tdelta.seconds >= timeout:
            return True
        return False


class AutomaticWithdrawLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    withdraw = models.ForeignKey(WithdrawRequest, on_delete=models.CASCADE)
    status = models.IntegerField(default=0)
    description = models.CharField(max_length=1000, blank=True, default='')

    def save(self, *args, update_fields=None, **kwargs):
        if self.description and len(str(self.description)) > 1000:
            self.description = str(self.description)[:1000]
            if update_fields:
                update_fields = (*update_fields, 'description')

        super().save(*args, update_fields=update_fields, **kwargs)


class Transaction(models.Model):
    TYPE = Choices(
        (10, 'deposit', 'Deposit'),
        (20, 'withdraw', 'Withdraw'),
        (30, 'buy', 'Buy'),
        (40, 'sell', 'Sell'),
        (50, 'fee', 'Fee'),
        (60, 'manual', 'Manual'),
        (70, 'gateway', 'Gateway'),
        (80, 'convert', 'Convert'),
        (81, 'ex_src', 'Exchange Src'),
        (82, 'ex_dst', 'Exchange Dst'),
        (90, 'transfer', 'Transfer'),
        (100, 'delegate', 'Pool Delegate'),
        (110, 'pnl', 'Profit and Loss'),
        (120, 'discount', 'discount'),
        (130, 'staking', 'staking'),
        (150, 'credit', 'credit'),
        (160, 'yield_farming', 'yield_farming'),
        (170, 'social_trade', 'SocialTrade'),
        (180, 'asset_backed_credit', 'assetBackedCredit'),
        (190, 'direct_debit', 'DirectDebit'),
        (200, 'refund', 'Refund'),
        (210, 'reward', 'Reward'),
        (220, 'referral', 'Referral'),
        (230, 'bot_charge', 'BotCharge'),
        (240, 'debit', 'Debit'),
        (250, 'external_liquidation', 'External Liquidation'),
    )
    TYPES_HUMAN_DISPLAY = {
        TYPE.deposit: 'واریز',
        TYPE.withdraw: 'برداشت',
        TYPE.buy: 'معامله',
        TYPE.sell: 'معامله',
        TYPE.fee: 'کارمزد',
        TYPE.manual: 'سیستمی',
        TYPE.gateway: 'درگاه',
        TYPE.convert: 'صرافی',
        TYPE.ex_src: 'صرافی',
        TYPE.ex_dst: 'صرافی',
        TYPE.transfer: 'انتقال',
        TYPE.delegate: 'مشارکت',
        TYPE.pnl: 'سود/زیان',
        TYPE.discount: 'تخفیف',
        TYPE.staking: 'استیکینگ',
        TYPE.credit: 'اعتبار',
        TYPE.debit: 'نقدی',
        TYPE.yield_farming: 'ییلد فارمینگ',
        TYPE.social_trade: 'سوشال ترید',
        TYPE.asset_backed_credit: 'تسویه با سرویس‌دهنده',
        TYPE.direct_debit: 'واریز مستقیم ریالی',
        TYPE.refund: 'بازگردانی موجودی',
        TYPE.reward: 'جایزه',
        TYPE.referral: 'ریفرال',
        TYPE.bot_charge: 'شارژ بات',
        TYPE.external_liquidation: 'لیکویید شدن',
    }
    REF_MODULES = {
        'ConfirmedWalletDeposit': 30,
        'ShetabDeposit': 31,
        'WithdrawRequest': 32,
        'InternalTransferDeposit': 33,
        'BankDeposit': 34,
        'WithdrawDoubleSpend': 35,
        'TradeSellA': 41,
        'TradeSellB': 42,
        'TradeBuyA': 43,
        'TradeBuyB': 44,
        'TradeFeeA': 45,
        'TradeFeeB': 46,
        'FeeAggregate': 47,
        'ReverseTransaction': 51,
        'Credit': 52,
        'ShetabBlock': 53,
        'RedeemRequest': 54,
        'TransferSrc': 61,
        'TransferDst': 62,
        'ExchangeSrc': 81,
        'ExchangeDst': 82,
        'BotDst': 83,
        'ExchangeSystemSrc': 84,
        'ExchangeSystemDst': 85,
        'PositionFeeSrc': 91,
        'PositionFeeAggregate': 92,
        'DelegationSrc': 101,
        'DelegationDst': 102,
        'DelegationRevokeSrc': 103,
        'DelegationRevokeDst': 104,
        'DelegationProfitSrc': 105,
        'DelegationProfitDst': 106,
        'DelegationProfitSrc+': 107,
        'DelegationProfitDst+': 108,
        'RecoveryFeeSrc': 111,
        'RecoveryFeeDst': 112,
        'ReturnRecoveryFeeSrc': 109,
        'ReturnRecoveryFeeDst': 110,
        'PositionUserPNL': 113,
        'PositionPoolPNL': 114,
        'PositionAdjustPNL': 115,
        'PositionCollateralRestitution': 116,
        'DiscountDst': 121,
        'StakingFee': 131,
        'StakingRequest': 132,
        'StakingReward': 133,
        'StakingRelease': 134,
        'BlockedOrder': 141,
        'CreditLend': 151,
        'CreditSystemLend': 152,
        'CreditRepay': 153,
        'CreditSystemRepay': 154,
        'YieldFarmingReward': 661537800,
        'YieldFarmingRequest': 162,
        'YieldFarmingRelease': 163,
        'CampaignLevel2Reward1402': 164,
        'SocialTradeUserTransaction': 171,
        'SocialTradeLeaderTransaction': 172,
        'SocialTradeSystemTransaction': 173,
        'AssetBackedCreditUserSettlement': 181,
        'AssetBackedCreditProviderSettlement': 182,
        'AssetBackedCreditInsuranceSettlement': 183,
        'AssetBackedCreditUserSettlementReverse': 184,
        'AssetBackedCreditProviderSettlementReverse': 185,
        'AssetBackedCreditInsuranceSettlementReverse': 186,
        'AssetBackedCreditUserFeeSettlement': 187,
        'AssetBackedCreditUserFeeSettlementReverse': 188,
        'AssetBackedCreditFeeSettlement': 189,
        'AssetBackedCreditFeeSettlementReverse': 190,
        'CampaignReferral1402': 201,
        'VIPCharge': 301,
        'DirectDebitUserTransaction': 302,
        'CampaignGiveawaySrc': 311,
        'CampaignGiveawayDst': 312,
        'CampaignGiveawayAzadUni1403Src': 401,
        'CampaignGiveawayAzadUni1403Dst': 402,
        'CampaignGiveawayLevelUp1403Src': 403,
        'CampaignGiveawayLevelUp1403Dst': 404,
        'CampaignGiveawayHamsterPreLaunchSrc': 405,
        'CampaignGiveawayHamsterPreLaunchDst': 406,
        'ManualDepositRequest': 501,
        'ManualDepositRequestFee': 502,
        'CoBankDeposit': 601,
        'LiquidationRequestSrc': 701,
        'LiquidationRequestDst': 702,
        'LiquidationSrc': 703,
        'LiquidationDst': 704,
        'ExchangeSmallAssetSrc': 710,
        'ExchangeSmallAssetDst': 711,
        'ExchangeSmallAssetSystemSrc': 712,
        'ExchangeSmallAssetSystemDst': 713,
    }

    REF_MODULES_CHOICES = [(v, k) for k, v in REF_MODULES.items()]
    RIAL_DEPOSIT_REF_MODULES = {
        v: k
        for k, v in REF_MODULES.items()
        if k in ['ShetabDeposit', 'BankDeposit', 'DirectDebitUserTransaction', 'CoBankDeposit']
    }

    wallet = models.ForeignKey(Wallet, related_name='transactions', on_delete=models.CASCADE, verbose_name='کیف پول')
    tp = models.IntegerField(choices=TYPE, verbose_name='نوع تراکنش')
    amount = models.DecimalField(
        max_digits=TRANSACTION_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, verbose_name='مبلغ تراکنش'
    )
    balance = models.DecimalField(
        max_digits=BALANCE_MAX_DIGITS,
        decimal_places=MONETARY_DECIMAL_PLACES,
        null=True,
        blank=True,
        verbose_name='موجودی',
    )
    created_at = models.DateTimeField()
    description = models.TextField(verbose_name='توضیحات')
    service = models.CharField(choices=Services.choices(), null=True, blank=True)
    ref_module = models.IntegerField(choices=REF_MODULES_CHOICES, null=True, blank=True)
    ref_id = models.IntegerField(null=True, blank=True)

    class Ref:
        def __init__(self, ref_module, ref_id):
            self.ref_module = ref_module
            self.ref_id = ref_id

    class Meta:
        verbose_name = 'تراکنش'
        verbose_name_plural = verbose_name
        unique_together: ClassVar = [['ref_module', 'ref_id']]
        indexes: ClassVar = [
            Index(
                name='wallet_transaction_idx_srv_ref',
                fields=['service', 'ref_module', 'ref_id'],
                condition=Q(service__isnull=False),
            ),
            Index(
                fields=['created_at', 'wallet_id'],
            ),
        ]

    def __str__(self):
        return 'T#{}: {} {} {}'.format(self.pk, self.get_tp_display(), self.amount, self.wallet.get_currency_display())

    @property
    def currency(self):
        return self.wallet.currency

    @property
    def is_for_referral_fee(self):
        return self.description and self.description.startswith('Charge for Referral Fee: ')

    def check_transaction(self):
        if not all([self.tp, self.amount is not None, self.wallet, self.created_at]):
            return False
        if not self.wallet.is_active:
            return False
        if self.tp in [self.TYPE.deposit, self.TYPE.buy]:
            if self.amount < 0:
                return False
        if self.tp in [self.TYPE.withdraw, self.TYPE.sell]:
            # TODO: check negative fee for non-system users
            if self.amount > 0:
                return False
            # Check balance
            if not self.wallet.is_balance_allowed(self.wallet.balance + self.amount):
                return False
        return True

    def set_ref(self, obj):
        if obj is None:
            return
        ref_module = 0
        ref_id = 0
        if isinstance(obj, self.Ref):
            ref_module = obj.ref_module
            ref_id = obj.ref_id
        else:
            ref_module = obj.__class__.__name__
            ref_id = obj.pk
        if ref_module in self.REF_MODULES:
            self.ref_module = self.REF_MODULES[ref_module]
        else:
            self.ref_module = deterministic_hash(ref_module) % 2**30
        self.ref_id = ref_id

    @measure_function_execution(metric='commit', metric_prefix='transaction', metrics_flush_interval=15)
    def commit(self, ref=None, allow_negative_balance=False):
        """Save the transaction to DB, updating wallet's balance."""
        self.set_ref(ref)

        if not connection.in_atomic_block and context_flag.get('NOTIFY_NON_ATOMIC_TX_COMMIT', True):
            message = 'Non-atomic block transaction commit'
            report_event(message, attach_stacktrace=True)
            message += f'\ntp={self.tp} ref={self.ref_module}-{self.ref_id}'
            Notification.notify_admins(message, title='⚠️ Warning', channel='system_diff')

        with transaction.atomic(savepoint=not connection.in_atomic_block):  # Ensure atomicity but avoid extra load
            # Update wallet balance
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE wallet_wallet SET balance = balance + %s WHERE id = %s RETURNING balance',
                    [self.amount, self.wallet_id],
                )
                result = cursor.fetchone()
            updated_balance = result[0]

            # Safe-guard check to prevent over spending
            if updated_balance < Decimal('0') and not allow_negative_balance:
                Notification.notify_admins('Negative Balance', title='📤 Commit Error', channel='matcher')
                raise ValueError('Balance Error In Commiting Transaction')

            self.wallet.balance = self.balance = updated_balance
            self.save()

    def get_type_human_display(self):
        return self.TYPES_HUMAN_DISPLAY.get(self.tp, 'سایر')

    @staticmethod
    def autocomplete_search_fields():
        return ['id']


class WithdrawRequestPermit(models.Model):
    user = models.ForeignKey(User, related_name='user_withdraw_request_permits', on_delete=models.CASCADE)
    admin_user = models.ForeignKey(User, related_name='withdraw_request_permits', on_delete=models.SET_NULL, null=True)
    withdraw_request = models.ForeignKey(
        WithdrawRequest, null=True, blank=True, related_name='withdraw_request_permits', on_delete=models.SET_NULL
    )
    amount_limit = models.DecimalField(
        max_digits=WITHDRAW_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO
    )
    currency = models.IntegerField(choices=Currencies)
    is_active = models.BooleanField(default=True)
    effective_time = models.DateTimeField()
    created_at = models.DateTimeField(default=now)

    @classmethod
    def get(cls, user, currency, amount):
        return cls.objects.filter(
            user=user,
            currency=currency,
            amount_limit__gte=amount,
            is_active=True,
            withdraw_request__isnull=True,
            effective_time__gte=now(),
        ).order_by('created_at').first()

    def mark_as_used(self, withdraw_request: WithdrawRequest):
        self.is_active = False
        self.withdraw_request = withdraw_request
        self.save(update_fields=['is_active', 'withdraw_request'])


class WithdrawRequestLimit(models.Model):
    """ User-specific override for withdrawLimits settings
    """
    LIMITATION_TYPE = Choices(
        (1, 'daily_coin', 'dailyCoin'),
        (2, 'daily_rial', 'dailyRial'),
        (3, 'daily_sum', 'dailySummation'),
        (4, 'monthly_sum', 'monthlySummation'),
        (5, 'daily_currency', 'dailyCurrency'),
        (6, 'monthly_currency', 'monthlyCurrency'),
    )

    user = models.ForeignKey(User, related_name='user_withdraw_limits', on_delete=models.CASCADE)
    tp = models.IntegerField(choices=LIMITATION_TYPE)
    limitation = models.DecimalField(
        max_digits=WITHDRAW_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO
    )
    currency = models.IntegerField(choices=Currencies, null=True, default=None)
    network = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        verbose_name = 'محدودیت برداشت کاربر'
        verbose_name_plural = verbose_name


class WithdrawRequestRestriction(models.Model):
    LIMITATION_TYPE = Choices(
        (1, 'daily_coin', 'dailyCoin'),
        (2, 'daily_rial', 'dailyRial'),
        (3, 'daily_sum', 'dailySummation'),
        (4, 'monthly_sum', 'monthlySummation'),
        (5, 'daily_currency', 'dailyCurrency'),
        (6, 'monthly_currency', 'monthlyCurrency'),
    )
    limitation = models.DecimalField(
        max_digits=WITHDRAW_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO
    )
    currency = models.IntegerField(choices=Currencies)
    network = models.CharField(max_length=200)
    created_at = models.DateTimeField(default=now)
    tp = models.IntegerField(choices=LIMITATION_TYPE)

    class Meta:
        verbose_name = 'محدودیت برداشت کلی'
        verbose_name_plural = verbose_name



class ManualDepositRequest(Confirmed):
    created_at = models.DateTimeField(default=now, verbose_name='زمان')
    wallet = models.ForeignKey(
        Wallet, related_name='manual_deposits_wallet', on_delete=models.CASCADE, verbose_name='کیف پول'
    )
    address = models.ForeignKey(
        WalletDepositAddress,
        null=True,
        blank=True,
        related_name='manual_deposits_address',
        on_delete=models.CASCADE,
        verbose_name='آدرس واریز',
    )
    amount = models.DecimalField(
        max_digits=DEPOSIT_MAX_DIGITS, decimal_places=MONETARY_DECIMAL_PLACES, default=ZERO, verbose_name='مقدار'
    )
    fee = models.DecimalField(max_digits=25, decimal_places=10, null=True, blank=True, verbose_name='مقدار کارمزد')
    tx_hash = models.CharField(max_length=200, verbose_name='هش تراکنش')
    tag = models.ForeignKey(WalletDepositTag, null=True, blank=True, related_name='manual_deposits',
                            on_delete=models.CASCADE)
    image = models.ForeignKey(UploadedFile, null=True, blank=True, related_name='wallet_image', on_delete=models.CASCADE,
                              verbose_name='اسکرین ولت')
    rial_value = models.DecimalField(max_digits=30, decimal_places=10, null=True, blank=True, verbose_name='ارزش ریالی')
    is_auto_validated = models.BooleanField(default=False, verbose_name='تایید خودکار؟')
    tagged_deposit_address = models.ForeignKey(
        AvailableDepositAddress, null=True, blank=True,
        related_name='manual_deposits_address',
        on_delete=models.CASCADE, verbose_name='آدرس واریز تگ دار')
    is_withdraw_valid = models.BooleanField(default=False, verbose_name='صحت برداشت')
    is_deposit_valid = models.BooleanField(default=False, verbose_name='صحت واریز')
    created_by_chatbot = models.BooleanField(default=None, verbose_name='ایجاد شده توسط چت‌بات', null=True, blank=True)


    class Meta:
        verbose_name = 'درخواست واریز دستی'
        verbose_name_plural = verbose_name
        constraints = (
            models.UniqueConstraint(
                fields=['tx_hash'],
                condition=~Q(status=Confirmed.STATUS.rejected),
                name='unique_tx_hash'
            ),
        )
    def __str__(self):
        return str(self.wallet)


class TransactionHistoryFile(models.Model):
    DIRECTORY_NAME = 'transactions_history'
    MAX_PER_USER = 12
    MAX_AGE = datetime.timedelta(days=1)

    created_at = models.DateTimeField(default=now, verbose_name='زمان')
    from_datetime = models.DateTimeField(verbose_name='زمان شروع')
    to_datetime = models.DateTimeField(verbose_name='زمان پایان')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=256, unique=True, verbose_name='نام فایل')
    tps = models.CharField(max_length=128, verbose_name='نوع تراکنش', null=True, blank=True)
    currency = models.IntegerField(choices=Currencies, verbose_name='ارز', null=True)
    tx_count = models.IntegerField(default=0, verbose_name='تعداد تراکنش ها')

    class Meta:
        verbose_name = 'فایل تاریخچه تراکنش'
        verbose_name_plural = 'فایل تاریخچه تراکنش ها'

    @property
    def link(self):
        domain = settings.PROD_FRONT_URL if settings.IS_PROD else settings.TESTNET_FRONT_URL
        return urljoin(domain, f'/panel/turnover/transaction/tx-download/{self.pk}')

    @property
    def relative_path(self):
        return 'uploads' / Path(self.DIRECTORY_NAME) / self.file_name

    @property
    def disk_path(self):
        return Path(settings.MEDIA_ROOT) / self.relative_path

    def set_file_name(self):
        """
        Set the file name for the transaction history file based on various attributes.

        The file name is composed of the following components:
            - 'transactions'
            - User ID
            - Start date and time (from_datetime) timestamp
            - End date and time (to_datetime) timestamp
            - Transaction types (tps) if available
            - Currency code (if available)

        Example:
            If user_id is 123, from_datetime timestamp is 1632552000, to_datetime timestamp is 1635144000,
            tps is 'type1_type2', and currency code is 'USD', the resulting file name would be:
            'transactions_123_1632552000_1635144000_type1_type2_usd.csv'
        """

        self.file_name = (
            'transactions'
            + f'_{self.user_id}'
            + f'_{int(self.from_datetime.timestamp())}'
            + f'_{int(self.to_datetime.timestamp())}'
            + (f'_{self.tps}' if self.tps else '')
            + (f'_{CURRENCY_CODENAMES.get(self.currency).lower()}' if self.currency else '')
            + '.csv'
        )

    @classmethod
    def get_remove_candidates(cls):
        return cls.objects.filter(created_at__lt=ir_now() - cls.MAX_AGE)

    @classmethod
    def generate_tps_str(cls, tps: Union[int, List[int]]) -> str:
        """
        Generate a string representation of transaction types (tps).

        Args:
            tps (Union[int, List[int]]): An integer or a list of integers representing transaction types.

        Returns:
            str: A string representing the transaction types, separated by underscores.

        Example:
            >>> generate_tps_str(1)
            'type1'
            >>> generate_tps_str([1, 2, 3])
            'type1_type2_type3'
        """

        if not tps:
            return ''

        if isinstance(tps, int):
            tps = [tps]

        type_id_map = {v: k for k, v in Transaction.TYPE._identifier_map.items()}
        return '_'.join([type_id_map.get(tp) for tp in sorted(tps)])

    def delete(self, *args, **kwargs):
        Path(self.disk_path).unlink(missing_ok=True)
        super().delete(*args, **kwargs)

    def send_email(self):
        EmailManager.send_email(
            self.user.email,
            'transaction_history',
            data={
                'link': self.link,
                'from': self.from_datetime,
                'to': self.to_datetime,
                'tx_count': self.tx_count,
            },
            priority='medium',
        )


class WalletBulkTransferRequest(models.Model):

    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'done', 'Done'),
        (3, 'rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.new)
    rejection_reason = models.CharField(max_length=256, blank=True)

    src_wallet_type = models.SmallIntegerField(choices=Wallet.WALLET_TYPE)
    dst_wallet_type = models.SmallIntegerField(choices=Wallet.WALLET_TYPE)

    currency_amounts = JSONField()
    transactions = models.ManyToManyField(Transaction)

    @classmethod
    def has_pending_transfer(cls, user: User, src_type: Optional[int] = None) -> bool:
        src_type_q = Q()
        if src_type is not None:
            src_type_q = Q(src_wallet_type=src_type)

        return cls.objects.filter(src_type_q, user=user, status=cls.STATUS.new).exists()

    @classmethod
    def get_pending_transfers(cls, src_wallet_types: list[int] = None):
        if not src_wallet_types:
            src_wallet_types = [Wallet.WALLET_TYPE.credit, Wallet.WALLET_TYPE.debit]
        return cls.objects.filter(
            src_wallet_type__in=src_wallet_types,
            status=WalletBulkTransferRequest.STATUS.new,
        )

    def reject(self, rejection_reason: str):
        self.status = self.STATUS.rejected
        self.rejection_reason = rejection_reason
        self.save(update_fields=('status', 'rejection_reason'))

    def accept(self, transactions: List[Transaction]):
        self.status = self.STATUS.done
        self.save(update_fields=('status',))
        self.transactions.set(transactions)


class ManualDepositTransaction(models.Model):
    TYPES = Choices(
        (1, 'deposit_fee', 'کسر کارمزد کاربر'),
    )
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name='+', verbose_name='تراکنش')
    manual_deposit_request = models.ForeignKey(ManualDepositRequest, on_delete=models.PROTECT, related_name='manual_deposit_transactions')
    tp = models.PositiveSmallIntegerField(choices=TYPES, default=TYPES.deposit_fee)
    amount = models.DecimalField(max_digits=20, decimal_places=10, verbose_name='مقدار')

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=['manual_deposit_request', 'tp'],
                name='unique_manual_deposit_request_tp',
            ),
        )

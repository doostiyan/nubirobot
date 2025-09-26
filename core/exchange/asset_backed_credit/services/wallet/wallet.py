from decimal import Decimal
from typing import Dict, List, Optional, Union
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable, PriceNotAvailableError
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.externals.wallet import WalletProvider
from exchange.asset_backed_credit.models import InternalUser
from exchange.asset_backed_credit.models.wallet import Wallet, wallet_cache_manager
from exchange.asset_backed_credit.types import WalletDepositInput, WalletSchema, WalletType
from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.models import CURRENCY_CODENAMES, Settings
from exchange.wallet.models import Wallet as ExchangeWallet


class WalletService:
    @classmethod
    def get_user_wallet(cls, user: User, currency: int, wallet_type: Wallet.WalletType):
        if wallet_type == Wallet.WalletType.DEBIT:
            if Settings.get_flag('abc_debit_internal_wallet_enabled'):
                return Wallet.objects.filter(user_id=user.uid, currency=currency, type=Wallet.WalletType.DEBIT)
            else:
                return WalletProvider.get_user_wallet(
                    user_id=user.id, wallet_type=ExchangeWallet.WALLET_TYPE.debit, currency=currency
                )
        # currently we do not support internal wallet for credit and loan, thus fallback to the old way!
        return WalletProvider.get_user_wallet(
            user_id=user.id, wallet_type=WalletMapper.to_exchange_wallet_type(wallet_type), currency=currency
        )

    @classmethod
    def get_user_wallets(cls, user_id: UUID, exchange_user_id: int, wallet_type: Wallet.WalletType, **kwargs):
        if wallet_type == Wallet.WalletType.DEBIT:
            if Settings.get_flag('abc_debit_internal_wallet_enabled'):
                return Wallet.objects.filter(user_id=exchange_user_id, type=Wallet.WalletType.DEBIT)
            else:
                return WalletProvider.get_user_wallets(
                    user_id=user_id,
                    exchange_user_id=exchange_user_id,
                    wallet_type=ExchangeWallet.WALLET_TYPE.debit,
                    **kwargs,
                )
        # currently we do not support internal wallet for credit and loan, thus fallback to the old way!
        return WalletProvider.get_user_wallets(
            user_id=user_id, exchange_user_id=exchange_user_id, wallet_type=ExchangeWallet.WALLET_TYPE.credit, **kwargs
        )

    @classmethod
    def get_user_wallets_by_currencies(
        cls, user_id: UUID, exchange_user_id: int, wallet_type: Wallet.WalletType
    ) -> QuerySet:
        if wallet_type == Wallet.WalletType.DEBIT:
            if Settings.get_flag('abc_debit_internal_wallet_enabled'):
                return Wallet.objects.filter(user_id=exchange_user_id, type=Wallet.WalletType.DEBIT).values(
                    'id', 'currency'
                )
            else:
                return WalletProvider.get_user_wallets_by_currency(
                    user_id=user_id, exchange_user_id=exchange_user_id, wallet_type=ExchangeWallet.WALLET_TYPE.debit
                )

        # currently we do not support internal wallet for credit and loan, thus fallback to the old way!
        return WalletProvider.get_user_wallets_by_currency(
            user_id=user_id, exchange_user_id=exchange_user_id, wallet_type=ExchangeWallet.WALLET_TYPE.credit
        )

    @classmethod
    def get_wallets(cls, users: List[User], wallet_type: Wallet.WalletType, **kwargs):
        if wallet_type == Wallet.WalletType.DEBIT:
            if Settings.get_flag('abc_debit_internal_wallet_enabled'):
                return Wallet.objects.filter(user__in=users, type=Wallet.WalletType.DEBIT)
            else:
                return WalletProvider.get_wallets(
                    users=users, wallet_type=ExchangeWallet.WALLET_TYPE.debit, **kwargs
                )
        # currently we do not support internal wallet for credit and loan, thus fallback to the old way!
        return WalletProvider.get_wallets(users=users, wallet_type=ExchangeWallet.WALLET_TYPE.credit, **kwargs)

    @classmethod
    @transaction.atomic
    def deposit(cls, user: User, deposit_input: WalletDepositInput):
        if Settings.get_flag('abc_debit_internal_wallet_enabled'):
            raise FeatureUnavailable
        transfer_result, transfer_request = WalletProvider.deposit(user, deposit_input)
        wallet_cache_manager.invalidate(user_id=user.id)
        return transfer_result, transfer_request

    @classmethod
    def get_user_wallets_with_rial_balance(cls, user: User, wallet_type: Wallet.WalletType) -> List[WalletSchema]:
        wallets = cls.get_user_wallets(user_id=user.uid, exchange_user_id=user.id, wallet_type=wallet_type)
        is_internal = Settings.get_flag('abc_debit_internal_wallet_enabled')

        result = []
        for wallet in wallets:
            if not wallet.balance > 0:
                continue

            try:
                price = PriceProvider(src_currency=wallet.currency).get_nobitex_price()
                rial_balance = int(price * wallet.balance)
            except PriceNotAvailableError:
                rial_balance = 0

            if is_internal:
                available_balance = wallet.available_balance
                blocked_balance = wallet.blocked_balance
            else:
                available_balance = wallet.balance - wallet.blocked_balance
                blocked_balance = wallet.blocked_balance

            result.append(
                WalletSchema(
                    id=getattr(wallet, 'id', None),
                    currency=CURRENCY_CODENAMES[wallet.currency],
                    type=wallet_type,
                    type_str=wallet_type.name,
                    balance=wallet.balance,
                    active_balance=available_balance,
                    blocked_balance=blocked_balance,
                    rial_balance=rial_balance,
                    rial_balance_sell=rial_balance,
                )
            )

        return result

    @classmethod
    def get_user_wallets_with_balances(cls, user_id: UUID, wallet_type: Wallet.WalletType) -> list:
        user = User.objects.get(uid=user_id)
        return [
            w
            for w in cls.get_user_wallets(user_id=user_id, exchange_user_id=user.id, wallet_type=wallet_type)
            if w.balance > Decimal('0')
        ]

    @classmethod
    def invalidate_user_wallets_cache(cls, user_id: UUID) -> None:
        wallet_cache_manager.invalidate(user_id=user_id)


class WalletMapper:
    @classmethod
    def to_exchange_wallet_type(cls, wallet_type: Wallet.WalletType) -> int:
        if wallet_type == Wallet.WalletType.SYSTEM:
            return ExchangeWallet.WALLET_TYPE.spot
        elif wallet_type == Wallet.WalletType.COLLATERAL:
            return ExchangeWallet.WALLET_TYPE.credit
        elif wallet_type == Wallet.WalletType.DEBIT:
            return ExchangeWallet.WALLET_TYPE.debit
        else:
            raise ValueError

    @classmethod
    def to_wallet_type(cls, exchange_wallet_type: Union[int, WalletType]) -> Wallet.WalletType:
        if isinstance(exchange_wallet_type, WalletType):
            if exchange_wallet_type == WalletType.SPOT or exchange_wallet_type == WalletType.MARGIN:
                return Wallet.WalletType.SYSTEM
            elif exchange_wallet_type == WalletType.COLLATERAL:
                return Wallet.WalletType.COLLATERAL
            elif exchange_wallet_type == WalletType.DEBIT:
                return Wallet.WalletType.DEBIT
            else:
                raise ValueError

        if exchange_wallet_type == ExchangeWallet.WALLET_TYPE.spot:
            return Wallet.WalletType.SYSTEM
        elif exchange_wallet_type == ExchangeWallet.WALLET_TYPE.credit:
            return Wallet.WalletType.COLLATERAL
        elif exchange_wallet_type == ExchangeWallet.WALLET_TYPE.debit:
            return Wallet.WalletType.DEBIT
        else:
            raise ValueError


def check_wallets_cache_consistency(batch_size: int = 1000) -> Optional[Dict[UUID, List[str]]]:
    if not Settings.get_flag('abc_wallets_cache_consistency_checker_enabled'):
        return None

    errors: Dict[UUID, List[str]] = {}
    batch_user_ids: List[UUID] = []

    for user_id in InternalUser.objects.values_list('uid', flat=True).iterator(chunk_size=batch_size):
        batch_user_ids.append(user_id)
        if len(batch_user_ids) >= batch_size:
            _check_wallets_cache_consistency(batch_user_ids, errors)
            batch_user_ids.clear()

    if batch_user_ids:
        _check_wallets_cache_consistency(batch_user_ids, errors)

    logstash_logger.info(
        'Checking wallets cache consistency', extra={'params': {'errors': errors}, 'index_name': 'abc'}
    )
    return errors


def _check_wallets_cache_consistency(user_ids: List[UUID], errors: Dict[UUID, List[str]]) -> None:
    users_in_batch: Dict[UUID, User] = User.objects.filter(uid__in=user_ids).only('id').in_bulk(field_name='uid')

    for user_id in user_ids:
        user_errors = []
        exchange_user = users_in_batch.get(user_id)
        if not exchange_user:
            user_errors.append(f'Missing user in exchange! for user_id: {user_id}')
            continue

        cached_wallets = wallet_cache_manager.get_by_type(
            user_id=user_id,
            wallet_type=ExchangeWallet.WALLET_TYPE.credit,
        )
        cached_map = {(w.type, w.currency): w for w in cached_wallets}
        if not cached_map:
            continue

        db_wallets = WalletProvider.get_user_wallets(
            user_id=user_id,
            exchange_user_id=exchange_user.id,
            wallet_type=ExchangeWallet.WALLET_TYPE.credit,
            cached=False,
        )
        db_map = {(w.type, w.currency): w for w in db_wallets}

        all_keys = set(cached_map.keys()) | set(db_map.keys())

        for key in all_keys:
            cache_wallet = cached_map.get(key)
            db_wallet = db_map.get(key)

            if cache_wallet is None:
                user_errors.append(f'Missing from cache: type={key[0]} currency={key[1]}')
                continue

            if db_wallet is None:
                user_errors.append(f'Missing from DB: type={key[0]} currency={key[1]}')
                continue

            for field_name in ('balance', 'blocked_balance'):
                cache_val = getattr(cache_wallet, field_name)
                db_val = getattr(db_wallet, field_name)
                if cache_val != db_val:
                    user_errors.append(
                        f'Mismatch for {field_name} type={key[0]} currency={key[1]}: ' f'cache={cache_val} db={db_val}'
                    )

        if user_errors:
            errors[user_id] = user_errors

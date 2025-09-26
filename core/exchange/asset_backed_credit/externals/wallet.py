import datetime
from collections import defaultdict
from decimal import Decimal
from enum import Enum, IntEnum
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.exceptions import ClientError, FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, InternalAPI
from exchange.asset_backed_credit.models.wallet import WalletCache, wallet_cache_manager
from exchange.asset_backed_credit.types import WalletDepositInput
from exchange.asset_backed_credit.types import WalletType as ABCInternalWallet
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time_cm
from exchange.base.internal.idempotency import IDEMPOTENCY_HEADER
from exchange.base.logging import metric_incr, report_event
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.base.parsers import WalletBulkTransferData, parse_currency
from exchange.wallet.functions import create_bulk_transfer
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WalletBulkTransferRequest
from exchange.wallet.types import TransferResult


class WalletType(IntEnum):
    spot = 1
    margin = 2
    credit = 3
    debit = 4


class TransactionType(IntEnum):
    transfer = 1


class WalletSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: Optional[int] = None
    user_id: UUID
    currency: int
    balance: Decimal
    blocked_balance: Decimal
    type: WalletType


class WalletProvider:
    @classmethod
    def get_user_wallet(cls, user_id: int, wallet_type: int, currency: int) -> ExchangeWallet:
        return ExchangeWallet.get_user_wallet(user=user_id, tp=wallet_type, currency=currency)

    @classmethod
    def get_user_wallets(
        cls, user_id: UUID, exchange_user_id: int, wallet_type: int, *, cached: bool = True
    ) -> List[WalletSchema]:
        """
        Returns all wallets for a user of a given type, as a list of WalletSchema.
        Tries cache first if enabled, falls back to source and always refreshes cache if used.
        """
        if cached and Settings.get_flag('abc_wallet_cache_read_enabled'):
            cached_wallets = cls._get_user_wallets_from_cache(user_id, wallet_type)
            if cached_wallets is not None:
                return cached_wallets

        if Settings.get_flag('abc_use_wallet_list_internal_api'):
            raw_wallets = cls._get_wallets([exchange_user_id], wallet_type).get(exchange_user_id, [])
        else:
            raw_wallets = list(ExchangeWallet.objects.filter(user_id=exchange_user_id, type=wallet_type))

        wallets = [
            wallet
            if isinstance(wallet, WalletSchema)
            else WalletSchema(
                id=wallet.id,
                user_id=wallet.user.uid,
                type=wallet.type,
                currency=wallet.currency,
                balance=wallet.balance,
                blocked_balance=wallet.blocked_balance,
            )
            for wallet in raw_wallets
        ]

        cls._update_user_wallets_cache(user_id, wallets)

        return wallets

    @classmethod
    def _get_user_wallets_from_cache(cls, user_id: UUID, wallet_type: int) -> Optional[List[WalletSchema]]:
        """
        Returns a list of WalletSchema from cache or None if not found.
        """
        metric_incr(f'metric_abc_calls__walletCache_read')
        cached_wallets = wallet_cache_manager.get_by_type(user_id=user_id, wallet_type=wallet_type)
        if not cached_wallets:
            return None
        return [
            WalletSchema(
                id=wallet.id,
                user_id=user_id,
                type=wallet.type,
                currency=wallet.currency,
                balance=wallet.balance,
                blocked_balance=wallet.blocked_balance,
            )
            for wallet in cached_wallets
        ]

    @classmethod
    def _update_user_wallets_cache(cls, user_id: UUID, wallets: List[WalletSchema]) -> None:
        """
        Updates wallet cache for user.
        """
        if not Settings.get_flag('abc_wallet_cache_write_enabled'):
            return

        metric_incr(f'metric_abc_calls__walletCache_write')
        updated_at = ir_now()
        wallet_cache_manager.bulk_set(
            user_id=user_id,
            wallets=[
                WalletCache(
                    id=wallet.id,
                    currency=wallet.currency,
                    type=wallet.type,
                    balance=wallet.balance,
                    blocked_balance=wallet.blocked_balance,
                    updated_at=updated_at.timestamp(),
                )
                for wallet in wallets
            ],
        )

    @classmethod
    def get_user_wallets_by_currency(cls, user_id: UUID, exchange_user_id: int, wallet_type: 'WalletType') -> QuerySet:
        """Return all user wallets by currency (not using internal API)."""
        if Settings.get_flag('abc_use_wallet_list_internal_api'):
            raise ValueError('abc_use_wallet_list_internal_api flag not supported here')
        return ExchangeWallet.objects.filter(user_id=exchange_user_id, type=wallet_type).values('id', 'currency')

    @classmethod
    def get_wallets(cls, users: List[User], wallet_type: int, *, cached: bool = True) -> Dict[int, List[WalletSchema]]:
        """
        Returns a dict of user_id -> List[WalletSchema] for the given user_ids and wallet_type.
        Tries cache first (if enabled), fetches only for users not found in cache, always refreshes cache for fetched users.
        """
        if not users:
            return {}

        user_id_map = {user.id: user.uid for user in users}
        result: Dict[int, List[WalletSchema]] = {}
        users_to_fetch: List[int] = []

        if cached and Settings.get_flag('abc_wallet_cache_read_enabled'):
            cached_wallets = cls._get_wallets_from_cache(list(user_id_map.values()), wallet_type)
            for user in users:
                wallets = cached_wallets.get(user.uid)
                if wallets is not None:
                    result[user.id] = wallets
                else:
                    users_to_fetch.append(user.id)
        else:
            users_to_fetch = list(user_id_map.keys())

        if not users_to_fetch:
            return result

        # Only fetch for users not found in cache
        if Settings.get_flag('abc_use_wallet_list_internal_api'):
            raw_wallets_map = cls._get_wallets(users_to_fetch, wallet_type)
        else:
            raw_wallets_map = cls._fetch_wallets_from_db(users_to_fetch, wallet_type)

        for user_id, raw_wallets in raw_wallets_map.items():
            wallets = [
                w
                if isinstance(w, WalletSchema)
                else WalletSchema(
                    id=w.id,
                    user_id=w.user.uid,
                    type=w.type,
                    currency=w.currency,
                    balance=w.balance,
                    blocked_balance=w.blocked_balance,
                )
                for w in raw_wallets
            ]
            result[user_id] = wallets
            cls._update_user_wallets_cache(user_id_map.get(user_id), wallets)

        return result

    @classmethod
    def _get_wallets_from_cache(cls, user_ids: List[UUID], wallet_type: int) -> Dict[UUID, List[WalletSchema]]:
        """
        Returns {user_id: List[WalletSchema]} from cache if found, else skips the user_id.
        """
        metric_incr(f'metric_abc_calls__walletCache_read')
        cached_wallets_map = (
            wallet_cache_manager.get_by_users_and_type(user_ids=user_ids, wallet_type=wallet_type) or {}
        )
        result = {}
        for user_id, wallets in cached_wallets_map.items():
            if wallets:
                result[user_id] = [
                    WalletSchema(
                        user_id=user_id,
                        type=wallet.type,
                        currency=wallet.currency,
                        balance=wallet.balance,
                        blocked_balance=wallet.blocked_balance,
                    )
                    for wallet in wallets
                ]
        return result

    @classmethod
    def _fetch_wallets_from_db(cls, user_ids: List[int], wallet_type: int) -> Dict[int, List[ExchangeWallet]]:
        """
        Fetch wallets from DB for a list of users, returns {user_id: [ExchangeWallet, ...]}
        """
        wallets = ExchangeWallet.objects.filter(user_id__in=user_ids, type=wallet_type)
        result = defaultdict(list)
        for wallet in wallets:
            result[wallet.user_id].append(wallet)
        return dict(result)

    @staticmethod
    @transaction.atomic
    def deposit(
        user: User, deposit_input: WalletDepositInput
    ) -> Tuple[List[TransferResult], WalletBulkTransferRequest]:
        """
        Handle deposit transactions between wallets.
        """
        transfers = {parse_currency(item.currency): item.amount for item in deposit_input.transfers}

        if deposit_input.src_type == ABCInternalWallet.SPOT:
            src_type = ExchangeWallet.WALLET_TYPE.spot
        elif deposit_input.src_type == ABCInternalWallet.MARGIN:
            src_type = ExchangeWallet.WALLET_TYPE.margin
        else:
            raise ValueError('Invalid source type for deposit')

        if deposit_input.dst_type == ABCInternalWallet.COLLATERAL:
            dst_type = ExchangeWallet.WALLET_TYPE.credit
        elif deposit_input.dst_type == ABCInternalWallet.DEBIT:
            dst_type = ExchangeWallet.WALLET_TYPE.debit
        else:
            raise ValueError('Invalid destination type for deposit')

        result, wallet_bulk_transfer = create_bulk_transfer(
            user,
            WalletBulkTransferData(
                src_type=src_type,
                dst_type=dst_type,
                transfers=transfers,
            ),
        )
        return result, wallet_bulk_transfer

    @staticmethod
    def transfer(
        transfer_log: 'WalletTransferLog',
    ) -> Tuple[Optional['WalletTransferSchema'], 'WalletTransferAPI']:
        """
        Perform a transfer operation via internal API.
        """
        converted_transfers = [
            WalletTransferItem(currency=get_currency_codename(int(currency)), amount=amount)
            for currency, amount in transfer_log.transfer_items.items()
        ]

        request_data = WalletTransferRequest(
            userId=transfer_log.user.uid,
            data=WalletTransferData(
                srcType=InternalWalletType.from_db_value(transfer_log.src_wallet_type),
                dstType=InternalWalletType.from_db_value(transfer_log.dst_wallet_type),
                transfers=converted_transfers,
            ),
        )

        internal_api = WalletTransferAPI()
        try:
            response_schema = internal_api.request(data=request_data, idempotency=transfer_log.idempotency)
            return response_schema, internal_api
        except InternalAPIError:
            return None, internal_api

    @classmethod
    def _get_wallets(cls, user_ids: List[int], wallet_type: int) -> Dict[int, List[WalletSchema]]:
        """
        Call internal API to get list of wallets for given users and wallet_type.
        Returns a dictionary of user_id -> list of WalletSchema.
        """
        users = User.objects.filter(id__in=user_ids)
        request_data = cls._prepare_wallet_internal_api_data(users, wallet_type)

        response_schema = WalletListAPI().request(request_data)

        grouped_wallets: Dict[int, List[WalletSchema]] = defaultdict(list)
        for user in users:
            wallets = response_schema.get(user.uid, [])
            grouped_wallets[user.id] = [
                WalletSchema(
                    user_id=user.uid,
                    currency=getattr(Currencies, wallet.currency),
                    balance=wallet.balance,
                    blocked_balance=wallet.blockedBalance,
                    type=getattr(WalletType, wallet.type),
                )
                for wallet in wallets
            ]
        return grouped_wallets

    @classmethod
    def _prepare_wallet_internal_api_data(cls, users: QuerySet[User], wallet_type: int) -> List['WalletRequestItem']:
        """
        Prepares request data for internal API using all ABC_CURRENCIES.
        """
        return [
            WalletRequestItem(
                type=InternalWalletType.from_db_value(wallet_type),
                uid=user.uid,
                currency=get_currency_codename(currency),
            )
            for user in users
            for currency in ABCCurrencies.get_internal_wallet_api_currencies()
        ]


class InternalWalletType(str, Enum):
    SPOT = "spot"
    MARGIN = "margin"
    CREDIT = "credit"
    DEBIT = "debit"

    @classmethod
    def from_db_value(cls, value: int):
        mapping = {1: cls.SPOT, 2: cls.MARGIN, 3: cls.CREDIT, 4: cls.DEBIT}
        return mapping.get(value)


class WalletTransferItem(BaseModel):
    currency: str
    amount: Decimal


class WalletTransferData(BaseModel):
    srcType: InternalWalletType
    dstType: InternalWalletType
    transfers: List[WalletTransferItem]


class WalletTransferRequest(BaseModel):
    userId: UUID
    data: WalletTransferData


class WalletTransferSchema(BaseModel):
    id: int
    srcType: InternalWalletType
    dstType: InternalWalletType
    transfers: List[WalletTransferItem]

    createdAt: datetime.datetime = ir_now()
    rejectionReason: str = ''
    status: str = "new"


class WalletTransferAPI(InternalAPI):
    class FailedPermanentlyReasonEnum(str, Enum):
        InsufficientBalance = 'موجودی آزاد کیف پول کمتر از مقدار درخواست شده است'

    none_retryable_api_errors = ['InsufficientBalance']
    url = NOBITEX_BASE_URL + '/internal/wallets/bulk-transfer'
    method = 'post'
    need_auth = True
    service_name = 'wallet'
    endpoint_key = 'walletTransfer'
    error_message = 'WalletTransfer'

    @measure_time_cm(metric='abc_wallet_walletTransfer')
    def request(self, data: WalletTransferRequest, idempotency: UUID) -> WalletTransferSchema:
        if not Settings.get_flag('abc_use_wallet_transfer_internal_api'):
            raise FeatureUnavailable

        formatted_data = self._prepare_request_data(data)
        try:
            response = self._request(json=formatted_data, headers={IDEMPOTENCY_HEADER: str(idempotency)})
            result = self.jsonify_response_data(response)

            return self._prepare_response_data(request_data=formatted_data, response_data=result)
        except (TypeError, ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: bulk transfer action failure') from e

    def _prepare_request_data(self, data: WalletTransferRequest) -> dict:
        return data.model_dump(mode='json')

    def _prepare_response_data(self, request_data: dict, response_data: dict) -> WalletTransferSchema:
        response_data = {'userId': request_data['userId'], **request_data['data'], **response_data}
        return WalletTransferSchema.model_validate(response_data)

    @lru_cache
    def get_none_retryable_error_key_and_reason(self) -> Tuple[Optional[str], Optional[str]]:
        if self.response is None:
            return None, None
        if self.response.status_code == status.HTTP_200_OK:
            return None, None

        for error in self.none_retryable_api_errors:
            if error in self.response.text:
                return error, getattr(self.FailedPermanentlyReasonEnum, error).value
        return None, None

    def has_none_retryable_error(self) -> bool:
        error, _ = self.get_none_retryable_error_key_and_reason()
        return error is not None

    def get_response_code(self) -> Optional[int]:
        if self.response is None:
            return None

        return self.response.status_code

    def get_response_body(self) -> Optional[dict]:
        if self.response is None:
            return None

        return self.jsonify_response_data(self.response)


class InternalWalletSchema(BaseModel):
    activeBalance: Decimal
    balance: Decimal
    blockedBalance: Decimal
    currency: str
    type: InternalWalletType
    userId: UUID


class WalletRequestItem(BaseModel):
    uid: UUID
    type: InternalWalletType
    currency: str


class WalletListAPI(InternalAPI):
    url = f'{NOBITEX_BASE_URL}/internal/wallets/list'
    method = 'post'
    need_auth = True
    service_name = 'wallet'
    endpoint_key = 'walletList'
    error_message = 'WalletList'

    @measure_time_cm(metric='abc_wallet_walletList')
    def request(self, data: List[WalletRequestItem]) -> Dict[UUID, List[InternalWalletSchema]]:
        if not Settings.get_flag('abc_use_wallet_list_internal_api'):
            raise FeatureUnavailable

        request_data = self._prepare_request_data(data)
        result = list()
        for i in range(0, len(request_data), 100):
            try:
                response = self._request(json=request_data[i : i + 100])
                result.append(self._validate_response_data(self.jsonify_response_data(response)))
            except (TypeError, ValueError, ClientError, ValidationError) as e:
                report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
                raise InternalAPIError(f'{self.error_message}: wallet list failure') from e

        merged_result = defaultdict(list)
        for dict_ in result:
            for uid, wallet_list in dict_.items():
                merged_result[uid].extend(wallet_list)

        return merged_result

    def _prepare_request_data(self, data: List[WalletRequestItem]) -> List[Dict]:
        return [d.model_dump(mode='json', exclude_none=True) for d in data]

    def _validate_response_data(self, data: Dict[str, List]) -> Dict[UUID, List[InternalWalletSchema]]:
        """returns a dict of user uuid mapped to a list of its wallets"""
        try:
            users_wallets = defaultdict(list)
            for user_uuid, user_wallets in data.items():
                for wallet in user_wallets:
                    users_wallets[UUID(user_uuid)].append(InternalWalletSchema.model_validate(wallet))
        except Exception as e:
            raise ValidationError(str(e))

        return users_wallets

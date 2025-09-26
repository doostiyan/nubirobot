import random
import uuid
from datetime import datetime
from decimal import Decimal
from math import ceil
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import (
    AssetToDebtMarginCall,
    Card,
    DebitSettlementTransaction,
    IncomingAPICallLog,
    InternalUser,
    OutgoingAPICallLog,
    Service,
    SettlementTransaction,
    UserService,
    UserServicePermission,
)
from exchange.asset_backed_credit.models.debit import CardSetting
from exchange.asset_backed_credit.types import UserInfo, UserServiceCreateRequest
from exchange.base.calendar import ir_now
from exchange.base.crypto import random_string
from exchange.base.models import Currencies
from exchange.market.markprice import MarkPriceCalculator
from exchange.market.models import Market, Order, OrderMatching
from exchange.wallet.models import Transaction as ExchangeTransaction
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WalletBulkTransferRequest as ExchangeWalletBulkTransferRequest


class ABCMixins:
    def create_user(self, is_active=True):
        username = random_string(12)
        user = User.objects.create(
            username=username,
            email=username + '@gmail.com',
            first_name='first_name',
            birthday=datetime(year=1993, month=11, day=15),
            gender=User.GENDER.female,
            city='Tehran',
            requires_2fa=True,
            is_active=is_active,
            mobile=str(9980000001 + random.randrange(1, 10 ** 6)),
            national_code="1234567890",
        )
        return user

    def create_internal_user(self, user: User):
        if user:
            return InternalUser.objects.get_or_create(
                uid=user.uid,
                defaults=dict(
                    uid=user.uid,
                    user_type=user.user_type,
                    national_code=user.national_code,
                    mobile=user.mobile,
                    email=user.email,
                ),
            )[0]

        uid = random_string(12)
        user = InternalUser.objects.create(
            uid=uid,
            user_type=InternalUser.USER_TYPES.normal,
            national_code='4980011222',
            mobile=str(9980000001 + random.randrange(1, 10 ** 6)),
            email=uid + '@gmail.com',
        )
        return user

    @staticmethod
    def create_service(
        provider=Service.PROVIDERS.tara,
        tp=Service.TYPES.credit,
        contract_id=None,
        *,
        is_active=True,
        is_available=True,
        interest=0,
        options=None,
    ):
        contract_id = contract_id or random.randrange(1, 10 ** 6)
        if options is None:
            options = dict()

        return Service.objects.get_or_create(
            provider=provider,
            tp=tp,
            defaults=dict(
                contract_id=contract_id,
                is_active=is_active,
                interest=interest,
                options=options,
                is_available=is_available,
            ),
        )[0]

    def create_user_service_permission(self, user=None, service=None, *, is_active=True):
        service = service or self.create_service()
        user = user or self.create_user()
        return UserServicePermission.objects.create(
            user=user,
            service=service,
            created_at=ir_now() if is_active else None,
        )

    def create_user_service(
        self,
        user=None,
        service=None,
        permission=None,
        current_debt=None,
        initial_debt=Decimal(10000),
        closed_at=None,
        account_number='',
        internal_user=None,
        status=UserService.STATUS.initiated,
    ) -> UserService:
        service = service or self.create_service()
        user = user or self.create_user()
        internal_user = internal_user or self.create_internal_user(user)
        permission = permission or self.create_user_service_permission(user, service)
        return UserService.objects.create(
            user=user,
            internal_user=internal_user,
            service=service,
            user_service_permission=permission,
            current_debt=current_debt or initial_debt,
            initial_debt=initial_debt,
            closed_at=closed_at,
            account_number=account_number,
            status=status,
        )

    def create_loan_user_service(
        self,
        user=None,
        service=None,
        permission=None,
        current_debt=None,
        initial_debt=10000,
        principal=10000,
        total_repayment=None,
        installment_amount=None,
        installment_period=12,
        closed_at=None,
        account_number='',
        extra_info=None,
        external_id=None,
        status=None,
    ) -> UserService:
        service = service or self.create_service(tp=Service.TYPES.loan, interest=13)
        user = user or self.create_user()
        permission = permission or self.create_user_service_permission(user, service)
        total_repayment = total_repayment or principal * (1 + service.interest)
        initial_debt = initial_debt or total_repayment
        current_debt = current_debt or initial_debt
        installment_amount = installment_amount or ceil(total_repayment / installment_period)
        if status is None:
            status = UserService.STATUS.initiated

        return UserService.objects.create(
            user=user,
            service=service,
            status=status,
            user_service_permission=permission,
            principal=principal,
            total_repayment=total_repayment,
            initial_debt=initial_debt,
            current_debt=current_debt,
            installment_amount=installment_amount,
            installment_period=installment_period,
            closed_at=closed_at,
            account_number=account_number,
            extra_info=extra_info or {},
            external_id=external_id or uuid.uuid4(),
        )

    def get_user_service_create_request(
        self, user_info: UserInfo, amount: int, unique_id: str, period=None, extra_info=None
    ) -> UserServiceCreateRequest:
        return UserServiceCreateRequest(
            user_info=user_info,
            amount=amount,
            unique_id=unique_id,
            period=period,
            extra_info=extra_info,
        )

    def create_settlement(
        self,
        amount: Decimal,
        user_service=None,
        user_withdraw_transaction: Optional[ExchangeTransaction] = None,
        provider_deposit_transaction: Optional[ExchangeTransaction] = None,
        orders: Optional[List[Order]] = None,
        status=SettlementTransaction.STATUS.confirmed,
    ) -> SettlementTransaction:
        user_service = user_service or self.create_user_service(current_debt=amount, initial_debt=amount)
        settlement = SettlementTransaction.objects.create(
            user_service=user_service,
            amount=amount,
            user_withdraw_transaction=user_withdraw_transaction,
            provider_deposit_transaction=provider_deposit_transaction,
            status=status,
        )
        if orders:
            settlement.orders.add(orders)
        return settlement

    def create_debit_settlement(
        self,
        amount: Decimal = 1000,
        user_service=None,
        card=None,
        status=DebitSettlementTransaction.STATUS.initiated,
        trace_id='trace-id',
        terminal_id='terminal-id',
        **kwargs,
    ) -> DebitSettlementTransaction:
        service = self.create_service(tp=Service.TYPES.debit)
        user_service = user_service or self.create_user_service(initial_debt=0, service=service)
        card = card or self.create_card(
            pan=self.generate_random_pan(), user_service=user_service, setting=self.create_card_setting()
        )
        return DebitSettlementTransaction.objects.create(
            pan=card.pan,
            user_service=user_service,
            amount=amount,
            status=status,
            transaction_datetime=ir_now(),
            trace_id=trace_id,
            terminal_id=terminal_id,
            **kwargs,
        )

    def create_card_setting(
        self,
        level: int = 1,
        per_trx_limit: int = 100_000_000,
        daily_limit: int = 200_000_000,
        monthly_limit: int = 1_000_000_000,
        cashback_percentage: Decimal = 0.0,
    ) -> CardSetting:
        return CardSetting.objects.create(
            level=level,
            per_transaction_amount_limit=per_trx_limit,
            daily_transaction_amount_limit=daily_limit,
            monthly_transaction_amount_limit=monthly_limit,
            cashback_percentage=cashback_percentage,
        )

    def create_margin_call(
        self,
        total_debt: Decimal,
        total_assets: Decimal,
        user: Optional[User] = None,
        orders: Optional[List[Order]] = None,
        *,
        is_margin_call_sent=False,
        is_solved=False,
        last_action=AssetToDebtMarginCall.ACTION.noop,
    ):
        user = user or self.create_user()
        margin_call = AssetToDebtMarginCall.objects.create(
            user=user,
            total_debt=total_debt,
            total_assets=total_assets,
            is_margin_call_sent=is_margin_call_sent,
            is_solved=is_solved,
            last_action=last_action,
        )
        if orders:
            margin_call.orders.add(*orders)
        return margin_call

    def charge_exchange_wallet(self, user, currency, amount, tp=ExchangeWallet.WALLET_TYPE.credit):
        wallet = ExchangeWallet.get_user_wallet(user, currency, tp=tp)
        wallet.create_transaction(tp='manual', amount=amount).commit()
        wallet.refresh_from_db()
        return wallet

    def set_usdt_mark_price(self, price: Decimal):
        currency = Currencies.usdt
        cache.set(MarkPriceCalculator.CACHE_KEY.format(src_currency=currency), Decimal(price))
        cache.set(f'market_{Market.get_for(currency, Currencies.rls).id}_last_price', 1)

    def create_order_matching(
        self,
        seller: User,
        buyer: User,
        sell_order,
        buy_order=None,
        price: Decimal = None,
        amount: Decimal = None,
        src_currency=Currencies.btc,
        dst_currency=Currencies.rls,
    ):
        market = Market.objects.get(src_currency=src_currency, dst_currency=dst_currency)
        if amount is None:
            amount = Decimal('0.001') * random.randint(1, 200)
        if price is None:
            price = Decimal('310_000_0') * random.randint(900, 1100)
        if buy_order is None:
            buy_order = self.create_order(
                user=buyer,
                net_matched_total_price=sell_order.net_matched_total_price,
                src_currency=sell_order.src_currency,
                status=sell_order.status,
            )
        OrderMatching.objects.create(
            created_at=ir_now(),
            market=market,
            seller=seller,
            buyer=buyer,
            sell_order=sell_order,
            buy_order=buy_order,
            is_seller_maker=True,
            matched_price=price,
            matched_amount=amount,
            sell_fee_amount=None,
            buy_fee_amount=None,
            rial_value=None,
        )

    def create_order(
        self,
        user: User,
        net_matched_total_price: Decimal,
        src_currency=Currencies.btc,
        status=Order.STATUS.done,
    ):
        fee = net_matched_total_price * Decimal('0.001')
        return Order.objects.create(
            user=user,
            order_type=Order.ORDER_TYPES.sell,
            src_currency=src_currency,
            dst_currency=Currencies.rls,
            execution_type=Order.EXECUTION_TYPES.market,
            trade_type=Order.TRADE_TYPES.credit,
            amount=Decimal('100'),
            price=Decimal('100_0'),
            status=status,
            matched_total_price=net_matched_total_price + fee,
            fee=fee,
        )

    def create_wallet_bulk_transfer(
        self,
        user: User,
        src_type=ExchangeWallet.WALLET_TYPE.credit,
        dst_type=ExchangeWallet.WALLET_TYPE.spot,
        status=ExchangeWalletBulkTransferRequest.STATUS.new,
        created_at: Optional[datetime] = None,
        currency_amounts: Optional[Dict[int, str]] = None,
    ):

        wallet_bulk_transfer = ExchangeWalletBulkTransferRequest.objects.create(
            user=user,
            src_wallet_type=src_type,
            dst_wallet_type=dst_type,
            status=status,
            currency_amounts=currency_amounts or {Currencies.usdt: str(Decimal(10))},
        )
        if created_at:
            wallet_bulk_transfer.created_at = created_at
            wallet_bulk_transfer.save()

        return wallet_bulk_transfer

    def create_card(
        self, pan: str, user_service: UserService, status=Card.STATUS.activated, user=None, **kwargs
    ) -> Card:
        user = user or user_service.user
        return Card.objects.create(pan=pan, user_service=user_service, user=user, status=status, **kwargs)

    def generate_random_pan(self) -> str:
        return ''.join(str(random.randint(0, 9)) for _ in range(DebitSettlementTransaction.pan.field.max_length))

    def check_incoming_log(
        self,
        request_body: dict,
        response_body: dict,
        provider: Optional[int] = None,
        service: Optional[int] = None,
        response_code: int = 400,
        log_status: int = 0,  # success
        api_url: str = '/asset-backed-credit/v1/estimate',
        user: User = None,
        user_service=None,
    ):
        log = IncomingAPICallLog.objects.order_by('pk').last()

        assert log.response_code == response_code
        assert log.status == log_status
        assert log.response_body == response_body
        assert log.request_body == request_body
        assert log.user == user
        assert log.api_url == api_url
        assert log.service == service
        assert log.provider == provider
        assert log.user_service == user_service

    def check_outgoing_log(self, api_call_log: OutgoingAPICallLog):
        api_log = OutgoingAPICallLog.objects.order_by('created_at').last()
        assert api_log
        assert api_log.service == api_call_log.service
        assert api_log.user_service == api_call_log.user_service
        assert api_log.api_url == api_call_log.api_url
        assert api_log.response_code == api_call_log.response_code
        assert api_log.retry == api_call_log.retry

    @staticmethod
    def check_outgoing_logs(api_call_logs: List[OutgoingAPICallLog]):
        api_logs = list(OutgoingAPICallLog.objects.order_by('created_at'))[-len(api_call_logs) :]

        for api_log, api_call_log in zip(api_logs, api_call_logs):
            assert api_log.service == api_call_log.service
            assert api_log.user_service == api_call_log.user_service
            assert api_log.api_url == api_call_log.api_url
            assert api_log.response_code == api_call_log.response_code
            assert api_log.retry == api_call_log.retry


class APIHelper(APITestCase):
    URL = ''

    def _set_client_credentials(self, auth_token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token}')

    def _post_request(self, url: Optional[str] = None, data: Optional[dict] = None, **kwargs) -> HttpResponse:
        if not url:
            url = self.URL
        return self.client.post(path=url, data=data, **kwargs)

    def _get_request(self, url: Optional[str] = None, **kwargs) -> HttpResponse:
        if not url:
            url = self.URL
        return self.client.get(path=url, **kwargs)

    def _change_parameters_in_object(self, obj, update_fields: dict):
        obj.__dict__.update(**update_fields)
        obj.save()

    def _check_response(
        self,
        response: HttpResponse,
        status_code: int,
        status_data: Optional[str] = None,
        code: Optional[str] = None,
        message: Optional[str] = None,
    ):
        assert response.status_code == status_code, (response.status_code, status_code)
        data = response.json()
        if status_data:
            assert data['status'] == status_data, (data['status'], status_data)
        if code:
            assert data['code'] == code, (data['code'], code)
        if message:
            assert data['message'] == message, (data['message'], message)
        return data


SIGN = (
    'VMdXaWC74CZju4ygmmGuzTdG3yGMyXAHDMLFjUKG/kgrNTAjKPfLhNiFvceFD2hd7cqjmRHH+Elm9V'
    'M/izzNJui7ri8BlY3cwIZtC31JRCqQSpDPMcqEIn2F1Rq6lGSvyKtU+f3ZxcmKRizPbo/LqQpzlVAmuj9WiZK'
    's2WDc5Ad1g30x6GQACJjFlkffPXDm8PJON3mCIPTge273r8f1ud4ZakJrArYb8XpsqOeFWqYyECxDwcUG'
    'th1hqKQ3Bumvog2M0Sf3suyXL7IoA8RDddixbLtYDKNddR3d1Cs8eDa00xhXW++1cduoIW6URZZ2AXh'
    'Pg/sdACWBWqTGa86i2w=='
)


def sign_mock(*args, **kwargs):
    return SIGN


class MockCacheValue(MagicMock):
    def __init__(self, *args: Any, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self.cache_storage = {}

    def rpush(self, key, value):
        if key in self.cache_storage:
            return self.cache_storage[key].append(value)
        self.cache_storage[key] = [value]

    def lrange(self, key, start, end):
        if key not in self.cache_storage:
            return []
        if end == -1:
            return self.cache_storage[key][start:]
        return self.cache_storage[key][start:end]

    def ltrim(self, key, start, end):
        self.cache_storage[key] = self.cache_storage[key][start:end]
        return True


INTERNAL_TEST_PRIVATE_KEY = '''
-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAMcSjXbWO6B7pbMPcqTzQrZmjvwqWYeEH6XNtlZ7xSjnG8+UKrxw
4rdP8VwsODHJNWd1trKStcZjfixFI5CHqnsCAwEAAQJAIc4Tub9thrYYkEyqQjqQ
9Jp743RpmaqlGSnSseL4uxYe+ZdVlmeC/Kf53jg/KESF1gpRte0EmGZDHIpuveNU
sQIhAPF4NEYXiuQ7pGn6Uj8RmZ+HMO0om9UwWUoaH1hqiSfZAiEA0w06menb6OcG
leSBcvXp7ho7i7ls/EuJWh9Q2T3qZHMCIALnQxmkptLftLZhgCOp/oLgiUIQvu7t
SeWOMtpJTaThAiAkpcNrPoSFKLioBonD4JfCVKPKW2RlWuh60b1EO9AbqQIhAMPR
2LryyIKuW+wfGDnCQZF/XgjVvrRtwSyIVvKLpedo
-----END RSA PRIVATE KEY-----
'''

INTERNAL_TEST_JWT_TOKEN = (
    'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MjE2NjM1MzMsInNlcnZpY2UiOiJhYmMifQ.W7DsYm0'
    '9G8ysUJxdhvKDFj_xYWG5i2eUJxira2SDO5MS3kprbZXDaAckshizquvWyo-cRwmGInd_ukw_c2r_Cg'
)

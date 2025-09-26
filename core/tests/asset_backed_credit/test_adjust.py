from decimal import ROUND_HALF_EVEN, Decimal
from unittest.mock import MagicMock, patch

import responses
from django.test import TestCase, override_settings

from exchange.asset_backed_credit.exceptions import ThirdPartyError, UserServiceIsNotInternallyCloseable
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.externals.providers import TARA, VENCY
from exchange.asset_backed_credit.externals.providers.tara import (
    TaraCheckUserBalance,
    TaraDischargeAccount,
    TaraGetTraceNumber,
)
from exchange.asset_backed_credit.externals.providers.vency import (
    VencyCancelOrderAPI,
    VencyGetOrderAPI,
    VencyRenewTokenAPI,
)
from exchange.asset_backed_credit.models import AssetToDebtMarginCall, Service, UserService
from exchange.asset_backed_credit.services.adjust import AdjustService
from exchange.asset_backed_credit.services.providers.dispatcher import TaraCreditAPIs
from exchange.base.models import PRICE_PRECISIONS, RIAL, Currencies, get_market_symbol
from tests.asset_backed_credit.helper import SIGN, ABCMixins, MockCacheValue, sign_mock

USDT_PRICE = Decimal(1_000_0)
BTC_PRICE = Decimal(1_000_000_0)


def mock_get_mark_price(src_currency: int, _):
    if src_currency == RIAL:
        return Decimal(1)
    elif src_currency == Currencies.usdt:
        return USDT_PRICE
    elif src_currency == Currencies.btc:
        return BTC_PRICE
    return None


def mock_get_last_trade_price(self):
    if self.src_currency == RIAL:
        return Decimal(1)
    elif self.src_currency == Currencies.usdt:
        return USDT_PRICE
    elif self.src_currency == Currencies.btc:
        return BTC_PRICE
    return None


def mock_get_price_range(src_currency: int, dst_currency: int):
    if src_currency == RIAL:
        return Decimal(1), Decimal(1)
    elif src_currency == Currencies.usdt:
        return USDT_PRICE, USDT_PRICE
    elif src_currency == Currencies.btc:
        return BTC_PRICE, BTC_PRICE
    return None


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
@patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
@patch('exchange.wallet.estimator.PriceEstimator.get_price_range', mock_get_price_range)
class TestAdjustService(ABCMixins, TestCase):
    def setUp(self) -> None:
        TARA.set_token('XXX')
        self.margin_call = self.create_margin_call(total_assets=Decimal(100_000_0), total_debt=Decimal(90_000_0))
        self.user = self.margin_call.user
        self.service = self.create_service()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_adjust_margin_call_discharge_user_service_ratio_ok_success(self, mock_restriction_task, *_):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        account_number = '1234'
        trace_number_data = '1234'
        reference_number_data = '123456'
        amount = Decimal(13_000_000)

        user_service = self.create_user_service(
            user=self.user,
            service=self.service,
            initial_debt=amount,
            current_debt=amount,
            account_number=account_number,
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number,
                'balance': str(amount),
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': account_number,
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', user_service).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number_data,
                    },
                ),
            ],
        )

        AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount
        assert user_service.current_debt == 0
        assert user_service.status == UserService.STATUS.closed

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.discharged
        assert self.margin_call.orders.count() == 0
        assert not self.margin_call.is_solved
        assert mock_restriction_task.called

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch.dict(
        'exchange.asset_backed_credit.services.providers.dispatcher.API_DISPATCHER',
        {
            Service.PROVIDERS.tara: {Service.TYPES.credit: TaraCreditAPIs},
            Service.PROVIDERS.wepod: {Service.TYPES.credit: TaraCreditAPIs},
        },
    )
    @patch(
        'exchange.asset_backed_credit.tasks.send_adjustment_notification',
        side_effect=MagicMock,
    )
    @patch('exchange.asset_backed_credit.services.liquidation.liquidate_margin_call', side_effect=MagicMock)
    def test_adjust_margin_call_discharge_multiple_user_services_ratio_near_liquidation_ratio_ok_success(self, *mocks):
        send_adjust_notifications_mock = mocks[1]
        liquidate_margin_call_mock = mocks[0]

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('0.6'))

        trace_number_data = '1234'
        reference_number_data = '123456'
        debt_1 = Decimal(100_000_0)
        debt_2 = Decimal(600_000_0)
        debt_3 = Decimal(600_000_0)
        amount = Decimal(50_000_0)

        user_service_1 = self.create_user_service(
            user=self.user,
            service=self.service,
            initial_debt=debt_1,
            current_debt=debt_1,
            account_number='us1-account-no',
        )

        service_2 = self.create_service(provider=Service.PROVIDERS.wepod)
        user_service_2 = self.create_user_service(
            user=self.user, service=service_2, initial_debt=debt_2, current_debt=debt_2, account_number='us2-account-no'
        )

        service_3 = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service_3 = self.create_user_service(
            user=self.user, service=service_3, initial_debt=debt_3, current_debt=debt_3, account_number='us3-account-no'
        )

        # for user_service_3
        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )
        responses.get(
            url=VencyGetOrderAPI.get_url(account_number='us3-account-no'),
            json={
                'orderId': '6789',
                'type': 'LENDING',
                'status': 'IN_PROGRESS',
                'uniqueIdentifier': 'us3-account-no',
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )
        responses.put(
            url=VencyCancelOrderAPI.get_url(account_number='us3-account-no'),
            status=200,
        )

        # for user_service_2
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': 'us2-account-no',
                'balance': str(amount),
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': 'us2-account-no',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', user_service_1).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number_data,
                    },
                ),
            ],
        )
        # for user_service_1
        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': 'us1-account-no',
                'balance': '0',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': 'us1-account-no',
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', user_service_3).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': '4567',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '0',
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': '0',
                        'sign': SIGN,
                        'traceNumber': '4567',
                    },
                ),
            ],
        )

        AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service_1.refresh_from_db()
        assert user_service_1.initial_debt == debt_1
        assert user_service_1.current_debt == 1_000_000
        assert user_service_1.status == UserService.STATUS.initiated

        user_service_2.refresh_from_db()
        assert user_service_2.initial_debt == debt_2
        assert user_service_2.current_debt == 5_500_000
        assert user_service_2.status == UserService.STATUS.initiated

        user_service_3.refresh_from_db()
        assert user_service_3.initial_debt == debt_3
        assert user_service_3.current_debt == 0
        assert user_service_3.status == UserService.STATUS.closed

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.discharged
        assert self.margin_call.orders.count() == 0

        send_adjust_notifications_mock.assert_called_once()
        liquidate_margin_call_mock.assert_not_called()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.adjust.report_exception')
    @patch(
        'exchange.asset_backed_credit.tasks.send_liquidation_notification',
        side_effect=MagicMock,
    )
    def test_adjust_margin_call_discharge_user_service_provider_third_party_error_ratio_not_ok_liquidate_success(
        self, *mocks
    ):
        send_liquidation_notifications_mock = mocks[0]
        report_exception_mock = mocks[1]
        tolerance = Decimal('0.03')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        account_number = '1234'
        trace_number_data = '1234'
        amount = Decimal(13_000_000)

        user_service = self.create_user_service(
            user=self.user,
            service=self.service,
            initial_debt=amount,
            current_debt=amount,
            account_number=account_number,
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number,
                'balance': str(amount),
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': account_number,
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', user_service).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': False,
                'data': '',
                'timestamp': '1701964345',
            },
            status=417,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number_data,
                    },
                ),
            ],
        )

        AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount
        assert user_service.current_debt == amount
        assert user_service.status == UserService.STATUS.initiated

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.liquidated
        assert self.margin_call.orders.count() == 2

        usdt_order = self.margin_call.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == (USDT_PRICE * (1 - tolerance)).quantize(
            PRICE_PRECISIONS[get_market_symbol(Currencies.usdt, Currencies.rls)], rounding=ROUND_HALF_EVEN
        )

        btc_order = self.margin_call.orders.get(src_currency=Currencies.btc)
        assert btc_order.amount == Decimal('1.23')
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        send_liquidation_notifications_mock.assert_called_once()
        report_exception_mock.assert_not_called()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.adjust.report_exception')
    @patch(
        'exchange.asset_backed_credit.tasks.send_liquidation_notification',
        side_effect=MagicMock,
    )
    def test_adjust_margin_call_discharge_user_service_provider_user_has_active_debt_error_liquidate_success(
        self, *mocks
    ):
        send_liquidation_notifications_mock = mocks[0]
        report_exception_mock = mocks[1]
        tolerance = Decimal('0.03')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        account_number = '1234'
        amount = Decimal(13_000_000)

        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            initial_debt=amount,
            current_debt=amount,
            account_number=account_number,
        )

        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )
        responses.get(
            url=VencyGetOrderAPI.get_url('1234'),
            json={
                'orderId': '6789',
                'type': 'LENDING',
                'status': 'VERIFIED',
                'uniqueIdentifier': '1234',
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )

        AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount
        assert user_service.current_debt == amount
        assert user_service.status == UserService.STATUS.initiated

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.liquidated
        assert self.margin_call.orders.count() == 2

        usdt_order = self.margin_call.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == (USDT_PRICE * (1 - tolerance)).quantize(
            PRICE_PRECISIONS[get_market_symbol(Currencies.usdt, Currencies.rls)], rounding=ROUND_HALF_EVEN
        )

        btc_order = self.margin_call.orders.get(src_currency=Currencies.btc)
        assert btc_order.amount == Decimal('1.23')
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        send_liquidation_notifications_mock.assert_called_once()
        report_exception_mock.assert_not_called()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch(
        'exchange.asset_backed_credit.tasks.send_adjustment_notification',
        side_effect=MagicMock,
    )
    @patch(
        'exchange.asset_backed_credit.tasks.send_liquidation_notification',
        side_effect=MagicMock,
    )
    def test_adjust_margin_call_discharge_user_service_ratio_not_ok_liquidate_success(self, *mocks):
        adjust_notifications_mock = mocks[1]
        liquidation_notifications_mock = mocks[0]

        tolerance = Decimal('0.03')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.13'))

        account_number = '1234'
        trace_number_data = '1234'
        reference_number_data = '123456'
        debt_1 = Decimal(700_000_0)
        debt_2 = Decimal(600_000_0)
        debt_3 = Decimal(25_000_0)
        amount = Decimal(25_000_0)

        user_service_1 = self.create_user_service(
            user=self.user,
            service=self.service,
            initial_debt=debt_1,
            current_debt=debt_1,
            account_number=account_number,
        )
        service_2 = self.create_service(provider=Service.PROVIDERS.wepod)
        user_service_2 = self.create_user_service(
            user=self.user, service=service_2, initial_debt=debt_2, current_debt=debt_2, account_number='1235'
        )
        service_3 = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service_3 = self.create_user_service(
            user=self.user, service=service_3, initial_debt=debt_3, current_debt=debt_3, account_number='6789'
        )

        responses.post(
            url=VencyRenewTokenAPI.url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'expires_in': 599,
                'scope': VencyRenewTokenAPI.SCOPES,
                'token_type': 'Bearer',
            },
            status=200,
            match=[
                responses.matchers.urlencoded_params_matcher(
                    {
                        'grant_type': 'client_credentials',
                        'client_id': VENCY.client_id,
                        'client_secret': VENCY.client_secret,
                        'scope': VencyRenewTokenAPI.SCOPES,
                    }
                ),
            ],
        )
        responses.get(
            url=VencyGetOrderAPI.get_url('6789'),
            json={
                'orderId': '1020102010',
                'type': 'LENDING',
                'status': 'IN_PROGRESS',
                'uniqueIdentifier': '6789',
                'createdAt': '2024-08-08T06:01:08.220457Z',
            },
            status=200,
        )
        responses.put(
            url=VencyCancelOrderAPI.get_url('6789'),
            status=200,
        )

        url = TaraCheckUserBalance.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'accountNumber': account_number,
                'balance': str(amount),
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'accountNumber': account_number,
                        'sign': SIGN,
                    },
                ),
            ],
        )
        url = TaraGetTraceNumber('decharge', user_service_1).url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'traceNumber': trace_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                    },
                ),
            ],
        )
        url = TaraDischargeAccount.url
        responses.post(
            url=url,
            json={
                'success': True,
                'data': '',
                'timestamp': '1701964345',
                'referenceNumber': reference_number_data,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'mobile': self.user.mobile,
                        'nationalCode': self.user.national_code,
                        'amount': str(amount),
                        'sign': SIGN,
                        'traceNumber': trace_number_data,
                    },
                ),
            ],
        )

        AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service_1.refresh_from_db()
        assert user_service_1.initial_debt == debt_1
        assert user_service_1.current_debt == 6_750_000
        assert user_service_1.status == UserService.STATUS.initiated

        user_service_2.refresh_from_db()
        assert user_service_2.initial_debt == debt_2
        assert user_service_2.current_debt == 6_000_000
        assert user_service_2.status == UserService.STATUS.initiated

        user_service_3.refresh_from_db()
        assert user_service_3.initial_debt == debt_3
        assert user_service_3.current_debt == 0
        assert user_service_3.status == UserService.STATUS.closed

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.liquidated
        assert self.margin_call.orders.count() == 2

        usdt_order = self.margin_call.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == (USDT_PRICE * (1 - tolerance)).quantize(
            PRICE_PRECISIONS[get_market_symbol(Currencies.usdt, Currencies.rls)], rounding=ROUND_HALF_EVEN
        )

        btc_order = self.margin_call.orders.get(src_currency=Currencies.btc)
        assert btc_order.amount == Decimal('1.13')
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        adjust_notifications_mock.assert_called_once()
        liquidation_notifications_mock.assert_called_once()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.adjust.report_exception')
    @patch(
        'exchange.asset_backed_credit.tasks.send_liquidation_notification',
        side_effect=MagicMock,
    )
    def test_adjust_margin_call_discharge_user_service_not_internally_closeable_error_liquidate_success(self, *mocks):
        send_liquidation_notifications_mock = mocks[0]
        report_exception_mock = mocks[1]
        tolerance = Decimal('0.03')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        account_number = '1234'
        amount = Decimal(13_000_000)

        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            initial_debt=amount,
            current_debt=amount,
            account_number=account_number,
        )

        with patch(
            'exchange.asset_backed_credit.services.adjust.close_user_service',
            side_effect=UserServiceIsNotInternallyCloseable(),
        ):
            AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount
        assert user_service.current_debt == amount
        assert user_service.status == UserService.STATUS.initiated

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.liquidated
        assert self.margin_call.orders.count() == 2

        usdt_order = self.margin_call.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == (USDT_PRICE * (1 - tolerance)).quantize(
            PRICE_PRECISIONS[get_market_symbol(Currencies.usdt, Currencies.rls)], rounding=ROUND_HALF_EVEN
        )

        btc_order = self.margin_call.orders.get(src_currency=Currencies.btc)
        assert btc_order.amount == Decimal('1.23')
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        send_liquidation_notifications_mock.assert_called_once()
        report_exception_mock.assert_not_called()

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    @patch('exchange.asset_backed_credit.services.adjust.report_exception')
    @patch(
        'exchange.asset_backed_credit.tasks.send_liquidation_notification',
        side_effect=MagicMock,
    )
    def test_adjust_margin_call_discharge_user_service_connection_error_liquidate_success(self, *mocks):
        send_liquidation_notifications_mock = mocks[0]
        report_exception_mock = mocks[1]
        tolerance = Decimal('0.03')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        account_number = '1234'
        amount = Decimal(13_000_000)

        service = self.create_service(provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan)
        user_service = self.create_user_service(
            user=self.user,
            service=service,
            initial_debt=amount,
            current_debt=amount,
            account_number=account_number,
        )

        with patch('exchange.asset_backed_credit.services.adjust.close_user_service', side_effect=ConnectionError()):
            AdjustService(margin_call_id=self.margin_call.id).execute()

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount
        assert user_service.current_debt == amount
        assert user_service.status == UserService.STATUS.initiated

        self.margin_call.refresh_from_db()
        assert self.margin_call.last_action == AssetToDebtMarginCall.ACTION.liquidated
        assert self.margin_call.orders.count() == 2

        usdt_order = self.margin_call.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == (USDT_PRICE * (1 - tolerance)).quantize(
            PRICE_PRECISIONS[get_market_symbol(Currencies.usdt, Currencies.rls)], rounding=ROUND_HALF_EVEN
        )

        btc_order = self.margin_call.orders.get(src_currency=Currencies.btc)
        assert btc_order.amount == Decimal('1.23')
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        send_liquidation_notifications_mock.assert_called_once()
        report_exception_mock.assert_called_once()

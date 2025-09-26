import copy
from unittest.mock import patch
from uuid import uuid4

from rest_framework import status

from exchange.accounts.models import User
from exchange.base.internal import idempotency
from exchange.base.internal.services import Services
from exchange.base.models import Currencies
from exchange.wallet.models import Transaction, Wallet, WalletBulkTransferRequest
from tests.base.utils import create_order
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class InternalWalletsBulkTransferTest(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/wallets/bulk-transfer'
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')

    def _request(self, data=None, headers=None):
        return self.client.post(self.URL, data=data or {}, headers=headers or {}, format='json')

    def _test_successful_bulk_wallets_transfer(self, data, headers=None):
        data.update({'userId': self.user.uid})
        response = self._request(data=data, headers=headers)
        assert response.status_code == status.HTTP_200_OK, response.json()
        result = response.json()

        wallet_bulk_transfer_log = WalletBulkTransferRequest.objects.first()
        assert wallet_bulk_transfer_log.pk == result['id']
        assert wallet_bulk_transfer_log.status == WalletBulkTransferRequest.STATUS.done
        assert wallet_bulk_transfer_log.user == self.user
        assert wallet_bulk_transfer_log.src_wallet_type == getattr(Wallet.WALLET_TYPE, data['data']['srcType'])
        assert wallet_bulk_transfer_log.dst_wallet_type == getattr(Wallet.WALLET_TYPE, data['data']['dstType'])
        assert wallet_bulk_transfer_log.rejection_reason == ''
        assert wallet_bulk_transfer_log.currency_amounts == {
            str(self.get_currency_int(currency_amount['currency'])): currency_amount['amount']
            for currency_amount in data['data']['transfers']
        }
        assert wallet_bulk_transfer_log.transactions.count() == 2 * len(data['data']['transfers'])

    def get_currency_int(self, currency_codename):
        return getattr(Currencies, currency_codename)

    def _test_unsuccessful_bulk_wallets_transfer(self, data, code, msg, status_code=None):
        initial_transactions = Transaction.objects.count()
        initial_balances = list(Wallet.objects.filter(user=self.user).order_by('type'))
        response = self._request(data=data)
        assert response.status_code == (
            status_code
            if status_code
            else status.HTTP_400_BAD_REQUEST
            if code == 'ParseError'
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        ), response.json()

        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert data['message'] == msg
        assert Transaction.objects.count() == initial_transactions
        assert list(Wallet.objects.filter(user=self.user).order_by('type')) == initial_balances

    @mock_internal_service_settings
    def test_wallets_bulk_transfer_credit_to_spot(self):
        usdt_credit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.credit)
        usdt_credit_wallet.create_transaction('manual', amount='30.6').commit()
        rls_credit_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.credit)
        rls_credit_wallet.create_transaction('manual', amount='10000').commit()

        self._test_successful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'credit',
                    'dstType': 'spot',
                    'transfers': [
                        {'currency': 'usdt', 'amount': '10.4'},
                        {'currency': 'rls', 'amount': '1234'},
                    ],
                },
            },
        )

    @mock_internal_service_settings
    def test_wallets_bulk_transfer_idempotency(self):
        usdt_credit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.credit)
        usdt_credit_wallet.create_transaction('manual', amount='30.6').commit()
        rls_credit_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.credit)
        rls_credit_wallet.create_transaction('manual', amount='10000').commit()

        data = {
            'userId': self.user.uid,
            'data': {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                    {'currency': 'rls', 'amount': '1234'},
                ],
            },
        }

        idempotency_key = str(uuid4())
        self._test_successful_bulk_wallets_transfer(
            data=data,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        self._test_successful_bulk_wallets_transfer(
            data=data,
            headers={
                idempotency.IDEMPOTENCY_HEADER: idempotency_key,
            },
        )
        assert WalletBulkTransferRequest.objects.all().count() == 1

    @mock_internal_service_settings
    def test_wallets_bulk_transfer_permission_denied(self):
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'spot',
                    'dstType': 'margin',
                    'transfers': [
                        {'currency': 'usdt', 'amount': '10.4'},
                    ],
                },
            },
            'PermissionDenied',
            'Service ABC is not allowed to transfer funds from wallet Spot',
            403,
        )

    @mock_internal_service_settings
    def test_wallets_bulk_transfer_credit_to_margin_invalid_coins(self):
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'credit',
                    'dstType': 'margin',
                    'transfers': [
                        {'currency': 'btc', 'amount': '10.4'},
                    ],
                },
            },
            'UnsupportedCoin',
            'Cannot transfer btc to margin wallet',
        )

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.views.check_bulk_transfer_permission', lambda *args: None)
    def test_wallets_bulk_transfer_for_amount_above_active_balance(self):
        create_order(self.user, Currencies.btc, Currencies.usdt, '0.001', '18900', sell=False, charge_ratio=2)
        # wallet.active_balance == $18.9
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'spot',
                    'dstType': 'credit',
                    'transfers': [
                        {'currency': 'usdt', 'amount': '19'},
                    ],
                },
            },
            'InsufficientBalance',
            'Amount cannot exceed active balance',
        )

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.views.check_bulk_transfer_permission', lambda *args: None)
    def test_wallets_transfer_credit_not_allowed_currencies(self):
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'spot',
                    'dstType': 'credit',
                    'transfers': [
                        {'currency': 'ltc', 'amount': '10'},
                    ],
                },
            },
            'UnsupportedCoin',
            'Cannot transfer ltc to credit wallet',
        )

        ltc_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.ltc)
        ltc_spot_wallet.create_transaction('manual', amount='30').commit()
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'spot',
                    'dstType': 'credit',
                    'transfers': [
                        {'currency': 'ltc', 'amount': '10'},
                    ],
                },
            },
            'UnsupportedCoin',
            'Cannot transfer ltc to credit wallet',
        )

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.views.check_bulk_transfer_permission', lambda *args: None)
    def test_wallets_bulk_transfer_atomic(self):
        usdt_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        usdt_spot_wallet.create_transaction('manual', amount='30.6').commit()

        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': self.user.uid,
                'data': {
                    'srcType': 'spot',
                    'dstType': 'credit',
                    'transfers': [
                        {'currency': 'usdt', 'amount': '10.4'},
                        {'currency': 'btc', 'amount': '0.001'},
                    ],
                },
            },
            'InsufficientBalance',
            'Amount cannot exceed active balance',
        )

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.views.check_bulk_transfer_permission', lambda *args: None)
    def test_wallets_bulk_transfer_user_not_found(self):
        data = {
            'userId': str(uuid4()),
            'data': {
                'srcType': 'spot',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
        }
        response = self._request(data=data)
        assert response.status_code == 404
        assert response.json()['error'] == 'NotFound'
        assert response.json()['message'] == 'User not found'

    @mock_internal_service_settings
    def test_wallets_bulk_transfer_invalid_uuid(self):
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'userId': 'invalid-uuid',
                'data': {
                    'srcType': 'spot',
                    'dstType': 'credit',
                    'transfers': [
                        {'currency': 'usdt', 'amount': '10.4'},
                    ],
                },
            },
            'ParseError',
            'Invalid monetary value: "invalid-uuid"',
        )

    @mock_internal_service_settings
    def test_wallets_bulk_transfer_without_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token("notification")}')
        response = self._request(self.URL)
        assert response.status_code == 404
        assert response.json() == {'detail': 'یافت نشد.'}

    @mock_internal_service_settings
    @patch('exchange.wallet.internal.views.check_bulk_transfer_permission', lambda *args: None)
    def test_wallets_bulk_transfer_wrong_inputs(self):
        data = {
            'userId': self.user.uid,
            'data': {
                'srcType': 'margin',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
        }

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['srcType'] = 'invalid-type'
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Invalid choices: "invalid-type"',
        )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['dstType'] = 'invalid-type'
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Invalid choices: "invalid-type"',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'data': 'invalid-dict'},
            'ParseError',
            'Input should be a dict: "invalid-dict"',
        )

        dirty_data = copy.deepcopy(data)
        del dirty_data['data']
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Missing wallet transfers value',
        )

        dirty_data = copy.deepcopy(data)
        del dirty_data['data']['srcType']
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Missing choices value',
        )

        dirty_data = copy.deepcopy(data)
        del dirty_data['data']['dstType']
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Missing choices value',
        )

        dirty_data = copy.deepcopy(data)
        for amount in ('-31', '0'):
            dirty_data['data']['transfers'][0]['amount'] = amount
            self._test_unsuccessful_bulk_wallets_transfer(
                dirty_data,
                'ParseError',
                'Only positive values are allowed for monetary values.',
            )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['transfers'][0]['amount'] = ''
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Missing monetary value',
        )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['transfers'][0]['amount'] = '12,000.12'
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Invalid monetary value: "12,000.12"',
        )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['transfers'][0]['currency'] = 'us'
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Invalid choices: "us"',
        )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['transfers'][0]['amount'] = '1E-10'
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'InvalidAmount',
            'Amount must be positive',
        )

        dirty_data = copy.deepcopy(data)
        for src in (125, 's'):
            dirty_data['data']['srcType'] = src
            self._test_unsuccessful_bulk_wallets_transfer(
                dirty_data,
                'ParseError',
                f'Invalid choices: "{src}"',
            )

        dirty_data = copy.deepcopy(data)
        for dst in (125, 's'):
            dirty_data['data']['dstType'] = dst
            self._test_unsuccessful_bulk_wallets_transfer(
                dirty_data,
                'ParseError',
                f'Invalid choices: "{dst}"',
            )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['srcType'] = dirty_data['data']['dstType']
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'SameDestination',
            'Dst wallet must be different from src wallet',
        )

        dirty_data = copy.deepcopy(data)
        dirty_data['data']['transfers'] = [{'currency': 'usdt', 'amount': '1'} for _ in range(11)]
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'List is too long, max len is 10',
        )

        dirty_data = copy.deepcopy(data)
        dirty_data['data'] = {}
        self._test_unsuccessful_bulk_wallets_transfer(
            dirty_data,
            'ParseError',
            'Missing wallet transfers value',
        )

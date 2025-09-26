from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.wallet.models import Transaction, Wallet, WalletBulkTransferRequest
from tests.base.utils import create_order


class WalletsBulkTransferTest(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_successful_bulk_wallets_transfer(self, data, expected_src_balances, expected_dst_balances):
        response = self.client.post('/wallets/bulk-transfer', data=data, format='json')
        assert response.status_code == status.HTTP_200_OK, response.json()
        result = response.json()
        assert result['status'] == 'ok', result
        assert 'result' in result
        for transfer in result['result']:
            currency = self.get_currency_int(transfer['dstWallet']['currency'])
            assert transfer['srcWallet']['id']
            assert transfer['srcWallet']['balance'] == expected_src_balances[currency]
            assert transfer['dstWallet']['id']
            assert transfer['dstWallet']['balance'] == expected_dst_balances[currency]
            for wallet_data in (transfer['srcWallet'], transfer['dstWallet']):
                wallet = Wallet.objects.get(user=self.user, currency=currency, id=wallet_data['id'])
                assert wallet.balance == Decimal(wallet_data['balance'])

        wallet_bulk_transfer_log = WalletBulkTransferRequest.objects.first()
        assert wallet_bulk_transfer_log.status == WalletBulkTransferRequest.STATUS.done
        assert wallet_bulk_transfer_log.user == self.user
        assert wallet_bulk_transfer_log.src_wallet_type == getattr(
            Wallet.WALLET_TYPE, result['result'][0]['srcWallet']['type']
        )
        assert wallet_bulk_transfer_log.dst_wallet_type == getattr(
            Wallet.WALLET_TYPE, result['result'][0]['dstWallet']['type']
        )
        assert wallet_bulk_transfer_log.rejection_reason == ''
        assert wallet_bulk_transfer_log.currency_amounts == {
            str(self.get_currency_int(currency_amount['currency'])): currency_amount['amount']
            for currency_amount in data['transfers']
        }
        assert wallet_bulk_transfer_log.transactions.count() == 2 * len(data['transfers'])

    def get_currency_int(self, currency_codename):
        return getattr(Currencies, currency_codename)

    def _test_unsuccessful_bulk_wallets_transfer(self, data, code, msg):
        initial_transactions = Transaction.objects.count()
        initial_balances = list(Wallet.objects.filter(user=self.user).order_by('type'))
        response = self.client.post('/wallets/bulk-transfer', data=data, format='json')
        assert response.status_code == (
            status.HTTP_400_BAD_REQUEST if code == 'ParseError' else status.HTTP_422_UNPROCESSABLE_ENTITY
        ), response.json()
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert data['message'] == msg
        assert Transaction.objects.count() == initial_transactions
        assert list(Wallet.objects.filter(user=self.user).order_by('type')) == initial_balances

    def test_wallets_bulk_transfer_margin_to_spot(self):
        usdt_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        usdt_spot_wallet.create_transaction('manual', amount='30.6').commit()
        rls_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        rls_spot_wallet.create_transaction('manual', amount='10000').commit()

        self._test_successful_bulk_wallets_transfer(
            {
                'srcType': 'margin',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                    {'currency': 'rls', 'amount': '1234'},
                ],
            },
            expected_src_balances={
                Currencies.usdt: '20.2',
                Currencies.rls: '8766',
            },
            expected_dst_balances={
                Currencies.usdt: '10.4',
                Currencies.rls: '1234',
            },
        )

    def test_wallets_bulk_transfer_spot_to_margin(self):
        usdt_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        usdt_spot_wallet.create_transaction('manual', amount='30.6').commit()
        rls_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        rls_spot_wallet.create_transaction('manual', amount='10000').commit()

        self._test_successful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'margin',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            expected_src_balances={
                Currencies.usdt: '20.2',
                Currencies.rls: '8766',
            },
            expected_dst_balances={
                Currencies.usdt: '10.4',
                Currencies.rls: '1234',
            },
        )

    def test_wallets_bulk_transfer_spot_to_margin_invalid_coins(self):
        btc_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        btc_spot_wallet.create_transaction('manual', amount='30.6').commit()

        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'margin',
                'transfers': [
                    {'currency': 'btc', 'amount': '10.4'},
                ],
            },
            'UnsupportedCoin',
            'Cannot transfer btc to margin wallet',
        )

    def test_wallets_bulk_transfer_spot_to_credit(self):
        usdt_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        usdt_spot_wallet.create_transaction('manual', amount='30.6').commit()
        btc_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        btc_spot_wallet.create_transaction('manual', amount='1.234').commit()

        self._test_successful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                    {'currency': 'btc', 'amount': '0.23'},
                ],
            },
            expected_src_balances={
                Currencies.usdt: '20.2',
                Currencies.btc: '1.004',
            },
            expected_dst_balances={
                Currencies.usdt: '10.4',
                Currencies.btc: '0.23',
            },
        )

    def test_wallets_bulk_transfer_margin_to_credit(self):
        usdt_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.margin)
        usdt_spot_wallet.create_transaction('manual', amount='30.6').commit()

        self._test_successful_bulk_wallets_transfer(
            {
                'srcType': 'margin',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            expected_src_balances={
                Currencies.usdt: '20.2',
            },
            expected_dst_balances={
                Currencies.usdt: '10.4',
            },
        )

    def test_wallets_bulk_transfer_credit_to_others(self):
        usdt_credit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.credit)
        usdt_credit_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'credit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'InvalidSrc',
            'credit wallet type is not allowed in srcType',
        )

    def test_wallets_bulk_transfer_fails_from_debit_to_others(self):
        usdt_debit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.debit)
        usdt_debit_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'debit',
                'dstType': 'spot',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'InvalidSrc',
            'debit wallet type is not allowed in srcType',
        )

    def test_wallets_bulk_transfer_fails_from_others_to_debit(self):
        usdt_debit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, Wallet.WALLET_TYPE.spot)
        usdt_debit_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'debit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                ],
            },
            'InvalidDst',
            'debit wallet type is not allowed in dstType',
        )

    def test_wallets_bulk_transfer_for_amount_above_active_balance(self):
        create_order(self.user, Currencies.btc, Currencies.usdt, '0.001', '18900', sell=False, charge_ratio=2)
        # wallet.active_balance == $18.9
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '19'},
                ],
            },
            'InsufficientBalance',
            'Amount cannot exceed active balance',
        )

    def test_wallets_transfer_credit_not_allowed_currencies(self):
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'ltc', 'amount': '10'},
                ],
            },
            'UnsupportedCoin',
            'Cannot transfer ltc to credit wallet',
        )

        ltc_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.ltc)
        ltc_spot_wallet.create_transaction('manual', amount='30').commit()
        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'ltc', 'amount': '10'},
                ],
            },
            'UnsupportedCoin',
            'Cannot transfer ltc to credit wallet',
        )

    def test_wallets_bulk_transfer_atomic(self):
        usdt_spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        usdt_spot_wallet.create_transaction('manual', amount='30.6').commit()

        self._test_unsuccessful_bulk_wallets_transfer(
            {
                'srcType': 'spot',
                'dstType': 'credit',
                'transfers': [
                    {'currency': 'usdt', 'amount': '10.4'},
                    {'currency': 'btc', 'amount': '0.001'},
                ],
            },
            'InsufficientBalance',
            'Amount cannot exceed active balance',
        )

    def test_wallets_bulk_transfer_wrong_inputs(self):
        data = {
            'srcType': 'spot',
            'dstType': 'credit',
            'transfers': [
                {'currency': 'usdt', 'amount': '10.4'},
            ],
        }
        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'srcType': 'invalid-type'},
            'ParseError',
            'Invalid choices: "invalid-type"',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'dstType': 'invalid-type'},
            'ParseError',
            'Invalid choices: "invalid-type"',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'transfers': 'invalid-list'},
            'ParseError',
            'transfers must be a list',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {'srcType': 'spot', 'dstType': 'credit'},
            'ParseError',
            'transfers is missing',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {'srcType': 'spot', 'transfers': [{'currency': 'usdt', 'amount': '10.4'}]},
            'ParseError',
            'Missing choices value',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {'dstType': 'spot', 'transfers': [{'currency': 'usdt', 'amount': '10.4'}]},
            'ParseError',
            'Missing choices value',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {'srcType': 'spot', 'dstType': 'credit', 'transfers': []},
            'ParseError',
            'transfers is empty',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            [1, 2, 3],
            'ParseError',
            'Input should be a dict: "[1, 2, 3]"',
        )

        for amount in ('-31', '0'):
            self._test_unsuccessful_bulk_wallets_transfer(
                {**data, 'transfers': [{'currency': 'usdt', 'amount': amount}]},
                'ParseError',
                'Only positive values are allowed for monetary values.',
            )

        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': ''}]},
            'ParseError',
            'Missing monetary value',
        )

        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': '12,000.12'}]},
            'ParseError',
            'Invalid monetary value: "12,000.12"',
        )

        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'transfers': [{'currency': 'us', 'amount': '10.4'}]},
            'ParseError',
            'Invalid choices: "us"',
        )
        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': '1E-10'}]},
            'InvalidAmount',
            'Amount must be positive',
        )

        for src in (125, 's'):
            self._test_unsuccessful_bulk_wallets_transfer(
                {**data, 'srcType': src}, 'ParseError', f'Invalid choices: "{src}"'
            )

        for dst in (125, 's'):
            self._test_unsuccessful_bulk_wallets_transfer(
                {**data, 'dstType': dst}, 'ParseError', f'Invalid choices: "{dst}"'
            )

        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'srcType': 'spot', 'dstType': 'spot'},
            'SameDestination',
            'Dst wallet must be different from src wallet',
        )

        self._test_unsuccessful_bulk_wallets_transfer(
            {**data, 'transfers': [{'currency': 'usdt', 'amount': '1'} for _ in range(21)]},
            'ParseError',
            'List is too long, max len is 20',
        )


class WalletsBulkTransfersListTest(APITestCase):
    URL = '/wallets/bulk-transfers/list'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)
        WalletBulkTransferRequest.objects.create(
            user=cls.user,
            status=WalletBulkTransferRequest.STATUS.new,
            src_wallet_type=Wallet.WALLET_TYPE.spot,
            dst_wallet_type=Wallet.WALLET_TYPE.credit,
            currency_amounts={
                Currencies.btc: '1.23',
                Currencies.eth: '13.23',
            },
        )
        WalletBulkTransferRequest.objects.create(
            user=cls.user,
            status=WalletBulkTransferRequest.STATUS.done,
            src_wallet_type=Wallet.WALLET_TYPE.margin,
            dst_wallet_type=Wallet.WALLET_TYPE.spot,
            currency_amounts={
                Currencies.btc: '1.23',
                Currencies.eth: '13.23',
            },
        )
        WalletBulkTransferRequest.objects.create(
            user=cls.user,
            status=WalletBulkTransferRequest.STATUS.rejected,
            rejection_reason='Invalid margin ration',
            src_wallet_type=Wallet.WALLET_TYPE.credit,
            dst_wallet_type=Wallet.WALLET_TYPE.margin,
            currency_amounts={
                Currencies.btc: '1.23',
                Currencies.eth: '13.23',
            },
        )

        # For another user
        WalletBulkTransferRequest.objects.create(
            user=User.objects.get(pk=203),
            status=WalletBulkTransferRequest.STATUS.rejected,
            rejection_reason='Invalid margin ration',
            src_wallet_type=Wallet.WALLET_TYPE.margin,
            dst_wallet_type=Wallet.WALLET_TYPE.credit,
            currency_amounts={
                Currencies.btc: '1.23',
                Currencies.eth: '13.23',
            },
        )

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_successful_bulk_wallets_transfer_list(self):
        response = self.client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK, response.json()
        result = response.json()
        assert result['status'] == 'ok', result
        assert result['hasNext'] is False
        assert 'result' in result
        assert len(result['result']) == 3
        assert result['result'][0]['id'] is not None
        assert result['result'][0]['rejectionReason'] == 'Invalid margin ration'
        assert result['result'][0]['status'] == 'rejected'
        assert result['result'][0]['srcType'] == 'credit'
        assert result['result'][0]['dstType'] == 'margin'
        assert result['result'][0]['transfers'] == [
            {
                'amount': '1.23',
                'currency': 'btc',
            },
            {
                'amount': '13.23',
                'currency': 'eth',
            },
        ]

        assert result['result'][1]['rejectionReason'] == ''
        assert result['result'][1]['status'] == 'done'

        assert result['result'][2]['rejectionReason'] == ''
        assert result['result'][2]['status'] == 'new'

    def test_successful_bulk_wallets_transfer_list_unauthenticated(self):
        self.client.credentials()
        response = self.client.get(self.URL)
        assert response.status_code == 401

    def test_successful_bulk_wallets_transfer_list_pagination(self):
        response = self.client.get(self.URL + '?pageSize=1')
        assert response.status_code == status.HTTP_200_OK, response.json()
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is True
        assert len(result['result']) == 1

    def test_successful_bulk_wallets_transfer_list_filtering(self):
        response = self.client.get(self.URL + '?srcType=spot')
        assert response.status_code == status.HTTP_200_OK, response.json()
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is False
        assert len(result['result']) == 1
        assert result['result'][0]['srcType'] == 'spot'

        response = self.client.get(self.URL + '?srcType=credit')
        assert response.json()['result'][0]['srcType'] == 'credit'

        response = self.client.get(self.URL + '?srcType=margin')
        assert response.json()['result'][0]['srcType'] == 'margin'

        response = self.client.get(self.URL + '?dstType=margin')
        assert response.json()['result'][0]['dstType'] == 'margin'

        response = self.client.get(self.URL + '?dstType=credit')
        assert response.json()['result'][0]['dstType'] == 'credit'

        response = self.client.get(self.URL + '?dstType=spot')
        assert response.json()['result'][0]['dstType'] == 'spot'

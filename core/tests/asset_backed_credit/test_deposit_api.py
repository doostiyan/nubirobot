from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Wallet
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.constants import ZERO
from exchange.base.models import Currencies, get_currency_codename
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins, APIHelper


class WalletServiceDepositTests(ABCMixins, APIHelper, TestCase):
    URL = '/asset-backed-credit/wallets/deposit'

    def setUp(self):
        self.user = User.objects.get(id=201)
        self._set_client_credentials(self.user.auth_token.key)

    def get_currency_int(self, currency_codename):
        return getattr(Currencies, currency_codename)

    def test_transfer_success_from_margin_to_collateral(self):
        usdt_margin_initial_balance = Decimal('50')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.margin, amount=usdt_margin_initial_balance
        )

        data = {
            "srcType": "margin",
            "dstType": "collateral",
            "transfers": [{"currency": "usdt", "amount": '2.12'}],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(response, status.HTTP_200_OK)

        result = response.json()
        assert result['status'] == 'ok', result
        assert 'result' in result
        for transfer in result['result']:
            currency = self.get_currency_int(transfer['dstWallet']['currency'])
            assert transfer['srcWallet']['id']
            assert transfer['srcWallet']['balance'] == '47.88'
            assert transfer['dstWallet']['id']
            assert transfer['dstWallet']['balance'] == '2.12'
            for wallet_data in (transfer['srcWallet'], transfer['dstWallet']):
                wallet = ExchangeWallet.objects.get(user=self.user, currency=currency, id=wallet_data['id'])
                assert wallet.balance == Decimal(wallet_data['balance'])

        assert WalletService.get_user_wallet(
            user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
        ).balance == Decimal(data['transfers'][0]['amount'])
        assert ExchangeWallet.get_user_wallet(
            user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.margin
        ).balance == usdt_margin_initial_balance - Decimal(data['transfers'][0]['amount'])

    def test_transfer_success_from_spot_to_collateral(self):
        usdt_spot_initial_amount = Decimal('50')
        btc_spot_initial_amount = Decimal('3.0021')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_spot_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=btc_spot_initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "usdt", "amount": '2.12'},
                {"currency": "btc", "amount": '1.01'},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(response, status.HTTP_200_OK)

        result = response.json()
        assert result['status'] == 'ok', result
        assert 'result' in result
        for transfer in result['result']:
            currency = self.get_currency_int(transfer['dstWallet']['currency'])
            assert transfer['srcWallet']['id']
            assert (
                transfer['srcWallet']['balance']
                == {
                    Currencies.usdt: '47.88',
                    Currencies.btc: '1.9921',
                }.get(currency)
            )
            assert transfer['dstWallet']['id']
            assert (
                transfer['dstWallet']['balance']
                == {
                    Currencies.usdt: '2.12',
                    Currencies.btc: '1.01',
                }.get(currency)
            )
            for wallet_data in (transfer['srcWallet'], transfer['dstWallet']):
                wallet = ExchangeWallet.objects.get(user=self.user, currency=currency, id=wallet_data['id'])
                assert wallet.balance == Decimal(wallet_data['balance'])

        assert WalletService.get_user_wallet(
            user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
        ).balance == Decimal(data['transfers'][0]['amount'])
        assert WalletService.get_user_wallet(
            user=self.user, currency=Currencies.btc, wallet_type=Wallet.WalletType.COLLATERAL
        ).balance == Decimal(data['transfers'][1]['amount'])
        assert ExchangeWallet.get_user_wallet(
            user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
        ).balance == usdt_spot_initial_amount - Decimal(data['transfers'][0]['amount'])
        assert ExchangeWallet.get_user_wallet(
            user=self.user, currency=Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot
        ).balance == btc_spot_initial_amount - Decimal(data['transfers'][1]['amount'])

    def test_transfer_success_with_multiple_coins_to_credit(self):
        amounts = [Decimal('50'), Decimal('3.0021'), Decimal('10'), Decimal('201.01')]
        self.charge_exchange_wallet(self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[0])
        self.charge_exchange_wallet(self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[1])
        self.charge_exchange_wallet(self.user, Currencies.eth, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[2])
        self.charge_exchange_wallet(self.user, Currencies.dai, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[3])

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "usdt", "amount": '2.12'},
                {"currency": "btc", "amount": '0.00000001'},
                {"currency": "eth", "amount": '3.0004'},
                {"currency": "dai", "amount": '13'},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(response, status.HTTP_200_OK)

        for i, item in enumerate(data['transfers']):
            assert WalletService.get_user_wallet(
                user=self.user, currency=getattr(Currencies, item['currency']), wallet_type=Wallet.WalletType.COLLATERAL
            ).balance == Decimal(item['amount'])
            assert ExchangeWallet.get_user_wallet(
                user=self.user, currency=getattr(Currencies, item['currency']), tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance == amounts[i] - Decimal(item['amount'])

    def test_transfer_success_from_margin_to_debit(self):
        usdt_initial_balance = Decimal('50')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.margin, amount=usdt_initial_balance
        )

        data = {
            "srcType": "margin",
            "dstType": "debit",
            "transfers": [{"currency": "usdt", "amount": '2.12'}],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(response, status.HTTP_200_OK)

        assert WalletService.get_user_wallet(
            user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.DEBIT
        ).balance == Decimal(data['transfers'][0]['amount'])
        assert ExchangeWallet.get_user_wallet(
            user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.margin
        ).balance == usdt_initial_balance - Decimal(data['transfers'][0]['amount'])

    def test_transfer_success_from_spot_to_debit(self):
        usdt_initial_balance = Decimal('50')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_initial_balance
        )

        data = {
            "srcType": "spot",
            "dstType": "debit",
            "transfers": [{"currency": "usdt", "amount": '2.12'}],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(response, status.HTTP_200_OK)

        result = response.json()
        assert result['status'] == 'ok', result
        assert 'result' in result
        for transfer in result['result']:
            currency = self.get_currency_int(transfer['dstWallet']['currency'])
            assert transfer['srcWallet']['id']
            assert transfer['srcWallet']['balance'] == '47.88'
            assert transfer['dstWallet']['id']
            assert transfer['dstWallet']['balance'] == '2.12'
            for wallet_data in (transfer['srcWallet'], transfer['dstWallet']):
                wallet = ExchangeWallet.objects.get(user=self.user, currency=currency, id=wallet_data['id'])
                assert wallet.balance == Decimal(wallet_data['balance'])

        assert WalletService.get_user_wallet(
            user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.DEBIT
        ).balance == Decimal(data['transfers'][0]['amount'])
        assert ExchangeWallet.get_user_wallet(
            user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
        ).balance == usdt_initial_balance - Decimal(data['transfers'][0]['amount'])

    def test_transfer_fails_from_credit_to_debit(self):
        usdt_initial_balance = Decimal('50')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.credit, amount=usdt_initial_balance
        )

        data = {
            "srcType": "credit",
            "dstType": "debit",
            "transfers": [{"currency": "usdt", "amount": '3'}],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='InvalidSrcType',
            message='Source wallet should be spot or margin wallets',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.DEBIT
            ).balance
            == ZERO
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == usdt_initial_balance
        )

    def test_transfer_success_with_multiple_coins_to_debit(self):
        amounts = [Decimal('50'), Decimal('3.0021'), Decimal('10'), Decimal('15'), Decimal('201.01')]
        self.charge_exchange_wallet(self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[0])
        self.charge_exchange_wallet(self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[1])
        self.charge_exchange_wallet(self.user, Currencies.eth, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[2])
        self.charge_exchange_wallet(self.user, Currencies.usdc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[3])
        self.charge_exchange_wallet(self.user, Currencies.dai, tp=ExchangeWallet.WALLET_TYPE.spot, amount=amounts[4])

        data = {
            "srcType": "spot",
            "dstType": "debit",
            "transfers": [
                {"currency": "usdt", "amount": '2.12'},
                {"currency": "btc", "amount": '0.00000001'},
                {"currency": "eth", "amount": '3.0004'},
                {"currency": "usdc", "amount": '13'},
                {"currency": "dai", "amount": '13'},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(response, status.HTTP_200_OK)

        for i, item in enumerate(data['transfers']):
            assert WalletService.get_user_wallet(
                user=self.user, currency=getattr(Currencies, item['currency']), wallet_type=Wallet.WalletType.DEBIT
            ).balance == Decimal(item['amount'])
            assert ExchangeWallet.get_user_wallet(
                user=self.user, currency=getattr(Currencies, item['currency']), tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance == amounts[i] - Decimal(item['amount'])

    def test_transfer_fails_when_destination_wallet_is_debit_and_currency_are_not_in_debit_active_currencies(self):
        initial_amount = Decimal('14.04')
        self.charge_exchange_wallet(
            self.user, Currencies.ltc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "debit",
            "transfers": [
                {"currency": "ltc", "amount": '2.12'},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='UnsupportedCoin',
            message='Cannot transfer ltc to debit wallet',
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.ltc, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == initial_amount
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.ltc, wallet_type=Wallet.WalletType.DEBIT
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_amount_is_zero(self):
        usdt_initial_amount = Decimal('50')
        btc_initial_amount = Decimal('3.000554')
        credit_usdt_initial_balance = Decimal('12.4')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=btc_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.credit, amount=credit_usdt_initial_balance
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "usdt", "amount": 0},
                {"currency": "btc", "amount": 0.001},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response, status.HTTP_422_UNPROCESSABLE_ENTITY, code='InvalidAmount', message='Amount can not be zero'
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_initial_amount
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == btc_initial_amount
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == credit_usdt_initial_balance
        )

    def test_transfer_fails_with_amount_less_than_zero(self):
        usdt_initial_amount = Decimal('50')
        btc_initial_amount = Decimal('3.000554')
        credit_usdt_initial_balance = Decimal('12.4')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=btc_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.credit, amount=credit_usdt_initial_balance
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "usdt", "amount": -5.00001},
                {"currency": "btc", "amount": 0.001},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='InvalidAmount',
            message='Amount can not be less than zero',
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_initial_amount
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == btc_initial_amount
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == credit_usdt_initial_balance
        )

    def test_transfer_fails_when_amount_is_more_than_user_balance(self):
        usdt_initial_amount = Decimal('50')
        btc_initial_amount = Decimal('3.000554')
        credit_usdt_initial_balance = Decimal('12.4')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=btc_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.credit, amount=credit_usdt_initial_balance
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "usdt", "amount": 51},
                {"currency": "btc", "amount": 0.001},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='InsufficientBalance',
            message='Amount cannot exceed active balance',
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_initial_amount
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == btc_initial_amount
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == credit_usdt_initial_balance
        )

    def test_transfer_fails_when_currency_is_invalid(self):
        usdt_initial_amount = Decimal('50')
        btc_initial_amount = Decimal('3.000554')
        credit_usdt_initial_balance = Decimal('12.4')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=btc_initial_amount
        )
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.credit, amount=credit_usdt_initial_balance
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "dummy_currency", "amount": 2},
                {"currency": "btc", "amount": 0.01},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='UnsupportedCoin',
            message='Currency dummy_currency is invalid',
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_initial_amount
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == btc_initial_amount
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == credit_usdt_initial_balance
        )

    def test_transfer_fails_when_destination_wallet_is_collateral_and_currency_not_in_abc_active_currencies(self):
        initial_amount = Decimal('3.0554')
        self.charge_exchange_wallet(
            self.user, Currencies.ltc, tp=ExchangeWallet.WALLET_TYPE.spot, amount=initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [
                {"currency": "ltc", "amount": 2},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='UnsupportedCoin',
            message='Cannot transfer ltc to credit wallet',
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.ltc, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == initial_amount
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.ltc, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_source_wallet_is_margin_and_currency_is_not_margin_currencies(self):
        data = {
            "srcType": "margin",
            "dstType": "collateral",
            "transfers": [
                {"currency": "dai", "amount": 2},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='UnsupportedCoin',
            message='Cannot transfer dai from margin wallet',
        )

        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.dai, tp=ExchangeWallet.WALLET_TYPE.margin
            )
            == None
        )
        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.dai, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_source_wallet_is_wrong(self):
        data = {
            "srcType": "dummy_wallet",
            "dstType": "collateral",
            "transfers": [
                {"currency": "usdt", "amount": 2},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='InvalidSrcType',
            message='Source wallet should be spot or margin wallets',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_destination_wallet_is_wrong(self):
        initial_amount = Decimal('60')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "dummy_wallet_type",
            "transfers": [
                {"currency": "usdt", "amount": 2},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='InvalidDstType',
            message='Destination wallet should be collateral or debit wallets',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == initial_amount
        )

    def test_transfer_fails_when_transfer_list_is_empty(self):
        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='transfers list should have at least 1 item after validation, not 0',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_transfer_list_is_none(self):
        data = {"srcType": "spot", "dstType": "collateral", "transfers": None}

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='transfers input should be a valid list',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )

    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_active_currencies')
    def test_transfer_fails_when_transfer_list_is_larger_than_max_size(self, mock_collateral_currencies):
        mock_collateral_currencies.return_value = Currencies
        usdt_spot_initial_amount = Decimal('500')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_spot_initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [{"currency": get_currency_codename(c), "amount": '1'} for c, _ in list(Currencies)[:20]],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_400_BAD_REQUEST,
            code='ParseError',
            message='transfers list should have at most 19 items after validation, not 20',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_spot_initial_amount
        )

    def test_transfer_fails_when_destination_wallet_is_in_external_wallet_type(self):
        data = {
            "srcType": "margin",
            "dstType": "spot",
            "transfers": [
                {"currency": "usdt", "amount": 2},
            ],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='InvalidDstType',
            message='Destination wallet should be collateral or debit wallets',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_no_authentication_credentials_is_sent(self):
        self.client = APIClient()
        usdt_spot_initial_amount = Decimal('500')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_spot_initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [{"currency": "usdt", "amount": '1'}],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_401_UNAUTHORIZED,
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_spot_initial_amount
        )

    def test_transfer_fails_when_both_dst_and_src_wallets_are_same(self):
        data = {
            "srcType": "debit",
            "dstType": "debit",
            "transfers": [{"currency": "usdt", "amount": '1'}],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='SameDestination',
            message='Dst wallet must be different from src wallet',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.DEBIT
            ).balance
            == ZERO
        )

    def test_transfer_fails_when_transfer_list_has_same_currencies(self):
        usdt_spot_initial_amount = Decimal('500')
        self.charge_exchange_wallet(
            self.user, Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot, amount=usdt_spot_initial_amount
        )

        data = {
            "srcType": "spot",
            "dstType": "collateral",
            "transfers": [{"currency": 'usdt', "amount": '1'} for _ in range(5)],
        }

        response = self._post_request(data=data, format='json')
        self._check_response(
            response,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            code='DuplicateCurrencies',
            message='Same currencies in the transfers set',
        )

        assert (
            WalletService.get_user_wallet(
                user=self.user, currency=Currencies.usdt, wallet_type=Wallet.WalletType.COLLATERAL
            ).balance
            == ZERO
        )
        assert (
            ExchangeWallet.get_user_wallet(
                user=self.user, currency=Currencies.usdt, tp=ExchangeWallet.WALLET_TYPE.spot
            ).balance
            == usdt_spot_initial_amount
        )

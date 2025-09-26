from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import ADDRESS_TYPE, Currencies, get_currency_codename
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.features.models import QueueItem
from exchange.wallet.models import AvailableDepositAddress, Wallet, WalletDepositAddress


class WalletGetAddressEndPointTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)
        cls.url = "/users/wallets/generate-address"

    def setUp(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    @classmethod
    def _verify_user_email(cls, user: User):
        VerificationProfile.objects.filter(id=user.get_verification_profile().id).update(email_confirmed=True)

    @classmethod
    def _make_user_eligible_for_deposit(cls, user: User):
        user.user_type = User.USER_TYPES.verified
        user.save()

    @classmethod
    def _enable_miner_feature_for_user(cls, user: User):
        req = QueueItem.objects.create(
            feature=QueueItem.FEATURES.miner,
            user=user,
        )
        req.enable_feature()

    @patch('exchange.wallet.models.Wallet.get_current_deposit_address')
    def test_generate_address_btc_success(self, mock_get_current_deposit_address):
        currency_name = get_currency_codename(Currencies.btc)
        network = CurrenciesNetworkName.BTC
        btc_dummy_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)

        mock_get_current_deposit_address.return_value = WalletDepositAddress(address=btc_dummy_address)

        data = {
            'currency': currency_name,
            'network': network,
            'addressType': 'default',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'ok')
        self.assertEqual(response_message['address'], btc_dummy_address)

    @patch('exchange.wallet.models.Wallet.get_current_deposit_address')
    def test_generate_address_eth_success(self, mock_get_current_deposit_address):
        currency_name = get_currency_codename(Currencies.yfi)
        network = CurrenciesNetworkName.ETH
        eth_dummy_address = '0x8ba1f109551bd432803012645ac136ddd64dba72'

        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)

        mock_get_current_deposit_address.return_value = WalletDepositAddress(address=eth_dummy_address)

        data = {
            'currency': currency_name,
            'network': network,
            'addressType': 'default',
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'ok')
        self.assertEqual(response_message['address'], eth_dummy_address)

    @patch('exchange.wallet.models.Wallet.get_current_deposit_address')
    def test_generate_address_one_success(self, mock_get_current_deposit_address):
        currency_name = get_currency_codename(Currencies.one)
        network = CurrenciesNetworkName.ONE
        one_eth_like_dummy_address = '0x8ba1f109551bd432803012645ac136ddd64dba72'
        one_atom_like_address = 'one13wslzz24r02r9qpszfj94sfkmhtymwnjyashyu'

        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)

        mock_get_current_deposit_address.return_value = WalletDepositAddress(address=one_eth_like_dummy_address)

        data = {
            'currency': currency_name,
            'network': network,
            'addressType': 'default',
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'ok')
        self.assertEqual(response_message['address'], one_atom_like_address)

    @override_settings(MINER_ENABLED=True)
    def test_generate_address_btc_miner_success(self):
        currency_name = get_currency_codename(Currencies.btc)
        network = CurrenciesNetworkName.BTC

        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)
        self._enable_miner_feature_for_user(self.user)

        btc_dummy_address = 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq'
        AvailableDepositAddress.objects.create(
            currency=Currencies.btc, address=btc_dummy_address, type=ADDRESS_TYPE.miner
        )
        data = {
            'currency': currency_name,
            'network': network,
            'addressType': 'default',
        }
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'ok')
        self.assertEqual(response_message['address'], btc_dummy_address)

    def test_generate_address_endpoint_unverified_email_failed(self):
        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'failed')
        self.assertEqual(response_message['code'], 'UnverifiedEmail')

    def test_generate_address_endpoint_user_level_too_low_failed(self):
        self._verify_user_email(self.user)
        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'failed')
        self.assertEqual(response_message['code'], 'CoinDepositLimitation')

    def test_generate_address_endpoint_empty_request_failed(self):
        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)
        response = self.client.post(self.url, data={})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'failed')
        self.assertEqual(response_message['code'], 'MissingWallet')

    def test_generate_address_endpoint_wallet_id_not_found_failed(self):
        nonexistent_wallet_pk = 20000
        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)
        response = self.client.post(self.url, data={'wallet': nonexistent_wallet_pk})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response_message = response.json()
        self.assertEqual(response_message['error'], 'NotFound')

    def test_generate_address_endpoint_invalid_currency_failed(self):
        invalid_currency = "INVALID_CURRENCY"
        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)
        response = self.client.post(self.url, data={'currency': invalid_currency})
        print(response, response.json())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'failed')
        self.assertEqual(response_message['code'], 'ParseError')

    def test_generate_address_endpoint_btc_legacy_address_failed(self):
        currency_name = get_currency_codename(Currencies.btc)
        network = CurrenciesNetworkName.BTC
        self._verify_user_email(self.user)
        self._make_user_eligible_for_deposit(self.user)
        data = {
            'currency': currency_name,
            'network': network,
            'addressType': 'legacy',
        }
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_message = response.json()
        self.assertEqual(response_message['status'], 'failed')
        self.assertEqual(response_message['code'], 'DepositNotAvailable!')

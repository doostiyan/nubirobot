from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet


class LightningInvoiceAPITest(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)
        cls.user.user_type = User.USER_TYPES.level1
        cls.user.save(update_fields=('user_type',))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _test_unsuccessful_ln_invoice_create(self, wallet, status_code, expected_response: dict = None):
        response = self.client.get('/users/wallets/invoice/generate', {'wallet': wallet.id})
        assert response.status_code == status_code
        if expected_response is not None:
            response_data = response.json()
            for key in expected_response.keys():
                assert expected_response[key] == response_data[key]

    def test_ln_invoice_create_wrong_wallet(self):
        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self._test_unsuccessful_ln_invoice_create(margin_wallet, status.HTTP_404_NOT_FOUND)

        other_user = User.objects.get(pk=202)
        other_user_wallet = Wallet.get_user_wallet(other_user, Currencies.rls)
        self._test_unsuccessful_ln_invoice_create(other_user_wallet, status.HTTP_404_NOT_FOUND)

        spot_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.spot)
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        self._test_unsuccessful_ln_invoice_create(spot_wallet, 400, dict(status='failed', code='UnverifiedEmail'))

    def _test_unsuccessful_ln_invoice_decode(self, wallet, status_code):
        response = self.client.get('/users/wallets/invoice/decode', {'wallet': wallet.id})
        assert response.status_code == status_code

    def test_ln_invoice_decode_wrong_wallet(self):
        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        self._test_unsuccessful_ln_invoice_decode(margin_wallet, status.HTTP_404_NOT_FOUND)

        other_user = User.objects.get(pk=202)
        other_user_wallet = Wallet.get_user_wallet(other_user, Currencies.rls)
        self._test_unsuccessful_ln_invoice_decode(other_user_wallet, status.HTTP_404_NOT_FOUND)

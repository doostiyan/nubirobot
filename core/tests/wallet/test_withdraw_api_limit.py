from datetime import timedelta

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, Tag, User, UserTag, VerificationProfile
from exchange.base.models import Currencies
from exchange.security.models import LoginAttempt
from exchange.wallet.models import Wallet, WithdrawRequest

from ..base.utils import create_withdraw_request


class WithdrawApiLimitTest(APITestCase):
    def setUp(self):
        self.level1_user = User.objects.create(username='level1_user', email="a@b.com",
                                               user_type=User.USER_TYPES.level1, mobile="09980000000")
        update_defaults = {
            'email_confirmed': True,
            'mobile_confirmed': True,
            'identity_confirmed': True,
            'bank_account_confirmed': True,
            'selfie_confirmed': True,
            'mobile_identity_confirmed': True,
            'identity_liveness_confirmed': True,
        }
        VerificationProfile.objects.update_or_create(user=self.level1_user, defaults=update_defaults)
        LoginAttempt.objects.create(user=self.level1_user, ip='31.56.129.161', is_successful=False)

        Token.objects.create(user=self.level1_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.level1_user.auth_token.key}')

        Wallet.create_user_wallets(self.level1_user)
        self.bank_account = BankAccount.objects.create(
            confirmed=1, user=self.level1_user, account_number='0217225661033', shaba_number='0217225661033')
        self.system_rial_account = BankAccount.get_generic_system_account()

        self.level2_user = User.objects.create(
            username='level2_user', email="level2@user.com", user_type=User.USER_TYPES.level2, mobile="09980000002"
        )
        VerificationProfile.objects.update_or_create(user=self.level2_user, defaults=update_defaults)
        Token.objects.create(user=self.level2_user)
        self.bank_account_2 = BankAccount.objects.create(
            confirmed=1, user=self.level2_user, account_number='0217225661034', shaba_number='0217225661034'
        )

    def test_new_request_limit_exceeded_different_currencies(self):
        [create_withdraw_request(self.level1_user, Currencies.usdt, 10, status=WithdrawRequest.STATUS.new)
         for _ in range(40)]
        rls_wallet = Wallet.get_user_wallet(self.level1_user, Currencies.rls)
        self._deposit_in_wallet_manually(rls_wallet, 400000)
        json_response = self.client.get(
            '/users/wallets/withdraw',
            {'wallet': rls_wallet.id, 'amount': 300000, 'address': str(self.bank_account.id)}).json()
        self.assertDictEqual(json_response,
                             {'status': 'failed', 'code': 'WithdrawLimitReached', 'message': 'msgWithdrawLimitReached'})

    def test_new_request_limit_exceeded_same_currency(self):
        wallet = Wallet.get_user_wallet(self.level1_user, Currencies.rls)
        [self._create_rial_withdraw(100000, wallet) for _ in range(41)]
        self._deposit_in_wallet_manually(wallet, 30000000)
        json_response = self.client.get(
            '/users/wallets/withdraw',
            {'wallet': wallet.id, 'amount': 3000000, 'address': str(self.bank_account.id)}).json()
        self.assertDictEqual(json_response,
                             {'status': 'failed', 'code': 'WithdrawLimitReached', 'message': 'msgWithdrawLimitReached'})

    def test_verified_request_limit_exceeded(self):
        withdraws = [
            create_withdraw_request(self.level1_user, Currencies.usdt, 10, status=WithdrawRequest.STATUS.verified)
            for _ in range(10)]
        wallet = withdraws[0].wallet
        self._deposit_in_wallet_manually(wallet, 300)
        json_response = self.client.get('/users/wallets/withdraw',
                                        {'wallet': wallet.id,
                                         'amount': 10, 'address': 'TDNVov3FR1Dtdr2jSzactpNN4oeuMqCaPN'}).json()
        self.assertDictEqual(json_response,
                             {'status': 'failed', 'code': 'WithdrawLimitReached', 'message': 'msgWithdrawLimitReached'})

    def test_new_request_limit_not_exceeded_few_withdraws(self):
        [create_withdraw_request(self.level1_user, Currencies.usdt, 10, status=WithdrawRequest.STATUS.new)
         for _ in range(20)]
        rls_wallet = Wallet.get_user_wallet(self.level1_user, Currencies.rls)
        self._deposit_in_wallet_manually(rls_wallet, 4000000)
        json_response = self.client.get(
            '/users/wallets/withdraw',
            {'wallet': rls_wallet.id, 'amount': 3000000, 'address': str(self.bank_account.id)}
        ).json()
        json_response['withdraw'].pop('createdAt')
        json_response['withdraw'].pop('id')
        self.assertDictEqual(json_response,
                             {'status': 'ok', 'withdraw': {'status': 'New', 'amount': '3000000', 'currency': 'rls',
                                                           'address': 'None: 0217225661033', 'tag': None,
                                                           'blockchain_url': None, 'wallet_id': rls_wallet.id,
                                                           'is_cancelable': True, 'network': 'FIAT_MONEY',
                                                           'invoice': None}})

    def test_withdraws_new_request_limit_not_exceeded_scattered_withdraws(self):
        now = timezone.now()
        [create_withdraw_request(self.level1_user, Currencies.usdt, 10, status=WithdrawRequest.STATUS.new,
                                 created_at=now - timedelta(minutes=10 * i))
         for i in range(40)]
        rls_wallet = Wallet.get_user_wallet(self.level1_user, Currencies.rls)
        self._deposit_in_wallet_manually(rls_wallet, 4000000)
        json_response = self.client.get(
            '/users/wallets/withdraw',
            {'wallet': rls_wallet.id, 'amount': 3000000, 'address': str(self.bank_account.id)}
        ).json()
        json_response['withdraw'].pop('createdAt')
        json_response['withdraw'].pop('id')
        self.assertDictEqual(
            json_response,
            {'status': 'ok', 'withdraw': {'address': 'None: 0217225661033', 'amount': '3000000',
                                          'blockchain_url': None, 'currency': 'rls', 'invoice': None,
                                          'is_cancelable': True, 'network': 'FIAT_MONEY',
                                          'status': 'New', 'tag': None, 'wallet_id': rls_wallet.id}})

    def test_verified_request_limit_not_exceeded_scattered_withdraws(self):
        now = timezone.now()
        withdraws = [
            create_withdraw_request(self.level1_user, Currencies.usdt, 2, status=WithdrawRequest.STATUS.verified,
                                    created_at=now - timedelta(hours=3 * i))
            for i in range(10)]
        wallet = withdraws[0].wallet
        self._deposit_in_wallet_manually(wallet, 1000)
        json_response = self.client.get('/users/wallets/withdraw',
                                        {'wallet': wallet.id, 'amount': 100,
                                         'address': 'TDNVov3FR1Dtdr2jSzactpNN4oeuMqCaPN'}).json()
        json_response['withdraw'].pop('createdAt')
        json_response['withdraw'].pop('id')
        self.assertDictEqual(json_response,
                             {'status': 'ok',
                              'withdraw': {'status': 'New', 'amount': '100', 'currency': 'usdt',
                                           'address': 'TDNVov3FR1Dtdr2jSzactpNN4oeuMqCaPN', 'tag': None,
                                           'blockchain_url': None, 'is_cancelable': True,
                                           'network': 'TRX', 'invoice': None, 'wallet_id': wallet.id}})

    def test_verified_request_limit_not_exceeded_few_withdraws(self):
        now = timezone.now()
        withdraws = [
            create_withdraw_request(self.level1_user, Currencies.usdt, 2, status=WithdrawRequest.STATUS.verified,
                                    created_at=now - timedelta(hours=3 * i))
            for i in range(9)]
        wallet = withdraws[0].wallet
        self._deposit_in_wallet_manually(wallet, 1000)
        json_response = self.client.get('/users/wallets/withdraw',
                                        {'wallet': wallet.id,
                                         'amount': 100, 'address': 'TDNVov3FR1Dtdr2jSzactpNN4oeuMqCaPN'}).json()
        json_response['withdraw'].pop('createdAt')
        json_response['withdraw'].pop('id')
        self.assertDictEqual(json_response,
                             {'status': 'ok',
                              'withdraw': {'status': 'New', 'amount': '100', 'currency': 'usdt',
                                           'address': 'TDNVov3FR1Dtdr2jSzactpNN4oeuMqCaPN', 'tag': None,
                                           'blockchain_url': None, 'wallet_id': wallet.id,
                                           'is_cancelable': True, 'network': 'TRX', 'invoice': None}})

    def _create_rial_withdraw(self, amount, wallet, fee=None, status: str = WithdrawRequest.STATUS.new):
        tr1 = wallet.create_transaction(tp='manual', amount=amount)
        tr1.commit()
        wallet.refresh_from_db()
        return WithdrawRequest.objects.create(
            wallet=wallet,
            status=status,
            target_account=self.system_rial_account,
            amount=amount,
            fee=fee,
        )

    def _deposit_in_wallet_manually(self, wallet, amount):
        transaction = wallet.create_transaction(tp='manual', amount=amount)
        transaction.commit()
        wallet.refresh_from_db()

    def test_withdraw_request_limit_exceeded_over_shaba_limit(self):
        # Since level 2 user has lower daily rial withdraw limit, level 3 is used
        User.objects.filter(pk=self.level2_user.pk).update(user_type=User.USER_TYPES.verified)
        create_withdraw_request(self.level2_user, Currencies.rls, 500000000, status=WithdrawRequest.STATUS.accepted)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.level2_user.auth_token.key}')
        rls_wallet = Wallet.get_user_wallet(self.level2_user, Currencies.rls)
        rls_wallet.balance = 100000000000
        rls_wallet.save()
        WithdrawRequest.objects.create(
            wallet=rls_wallet,
            amount=300_000_000_0,
            target_account=self.bank_account_2,
            status=WithdrawRequest.STATUS.verified,
        )
        json_response = self.client.get(
            '/users/wallets/withdraw',
            {'wallet': rls_wallet.id, 'amount': 2000000001, 'address': str(self.bank_account_2.id)},
        ).json()
        expected_result = {
            'status': 'failed',
            'code': 'ShabaWithdrawCannotProceed',
            'message': 'Shaba withdraw cannot proceed. Daily Shaba withdraw limit Exceeded.',
        }
        self.assertDictEqual(json_response, expected_result)

        over_shaba_limit_tag = Tag.objects.create(name='برداشت بیشتر از محدودیت شبا')
        UserTag.objects.create(user=self.level2_user, tag=over_shaba_limit_tag)

        json_response = self.client.get(
            '/users/wallets/withdraw',
            {'wallet': rls_wallet.id, 'amount': 2000000001, 'address': str(self.bank_account_2.id)},
        ).json()
        json_response['withdraw'].pop('createdAt')
        json_response['withdraw'].pop('id')
        self.assertDictEqual(json_response,
                             {'status': 'ok', 'withdraw': {'status': 'New', 'amount': '2000000001', 'currency': 'rls',
                                                           'address': 'None: 0217225661034', 'tag': None,
                                                           'blockchain_url': None, 'wallet_id': rls_wallet.id,
                                                           'is_cancelable': True, 'network': 'FIAT_MONEY',
                                                           'invoice': None}})

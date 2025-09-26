import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from exchange.accounts.models import User, UserRestriction, UserSms, VerificationProfile
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Currencies, Settings
from exchange.base.serializers import serialize_currency
from exchange.gift.models import CardDesign, GiftBatchRequest, GiftCard, GiftPackage
from exchange.gift.serializers import serialize_gift_package
from exchange.wallet.models import Wallet, WithdrawRequest
from exchange.wallet.withdraw import process_withdraws


@override_settings(IS_PROD=True)
class CreateGiftBatchRequestTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )
        self.user.mobile = '989121234567'
        self.user.save()
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)

    def test_creation(self):
        response = self.client.post('/gift/create-gift-batch', data={
            'number': 12,
            'total_amount': Decimal('1'),
            'gift_type': 'physical',
        }).json()
        assert response['status'] == 'ok'
        gift_batch = GiftBatchRequest.objects.filter(user=self.user).first()
        assert gift_batch is not None
        assert gift_batch.number == 12
        assert gift_batch.total_amount == Decimal('1')
        assert gift_batch.gift_type == 0

        # backward compatible password value
        assert gift_batch.password == '1111'

    def test_creation_with_password(self):
        response = self.client.post(
            '/gift/create-gift-batch',
            data={
                'number': 12,
                'total_amount': Decimal('1'),
                'gift_type': 'physical',
                'password': '12345',
            },
        ).json()
        assert response['status'] == 'ok'
        gift_batch = GiftBatchRequest.objects.filter(user=self.user).first()
        assert gift_batch is not None
        assert gift_batch.number == 12
        assert gift_batch.total_amount == Decimal('1')
        assert gift_batch.gift_type == 0
        assert gift_batch.password == '12345'

    def test_creation_with_just_number_and_password(self):
        response = self.client.post(
            '/gift/create-gift-batch',
            data={
                'number': 12,
                'password': '12345',
            },
        ).json()
        assert response['status'] == 'ok'
        gift_batch = GiftBatchRequest.objects.filter(user=self.user).first()
        assert gift_batch is not None
        assert gift_batch.number == 12
        assert not gift_batch.total_amount
        assert not gift_batch.gift_type
        assert gift_batch.password == '12345'

    def test_without_email_confirmed_creation(self):
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        response = self.client.post('/gift/create-gift-batch', data={
            'number': 12,
            'total_amount': Decimal('1'),
            'gift_type': 'physical',
        })
        assert response.status_code == 400
        response = response.json()
        assert response['status'] == 'failed'
        assert response['code'] == 'UnverifiedEmail'


class RedeemLandingTest(TestCase):
    def setUp(self):
        self.gifter = User.objects.get(pk=200)
        self.giftee = User.objects.get(pk=201)
        self.design, _ = CardDesign.objects.get_or_create(title='Grand')
        self.client = Client()
        self.redeem_code = 'a' * 32
        self.gift_card = GiftCard.objects.create(
            sender=self.gifter,
            currency=Currencies.btc,
            amount=Decimal('0.1'),
            initial_withdraw=None,
            gift_type=GiftCard.GIFT_TYPES.digital,
            gift_sentence='this is a gift',
            receiver=self.giftee,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password('1372'),
            redeem_code=self.redeem_code,
            redeem_type=GiftCard.REDEEM_TYPE.internal,
            otp_enabled=True,
            card_design=self.design
        )
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )

    def test_invalid_redeem_codes(self):
        response = self.client.get(f'/gift/{"a" * 33}').json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidRedeemCode'
        response = self.client.get(f'/gift/{"b" * 32}')
        assert response.status_code == 404
        assert response.json()['error'] == 'NotFound'

    def test_valid_redeem_code(self):
        assert cache.get(f'gift_otp_{self.gift_card.id}') is None
        response = self.client.get(f'/gift/{self.redeem_code}').json()
        assert response['redeem_code'] ==  self.redeem_code
        assert response['card_design'] ==  self.gift_card.card_design.title
        assert response['currency'] ==  serialize_currency(self.gift_card.currency)
        assert Decimal(response['amount']) ==  self.gift_card.amount
        assert response['mobile_provided'] ==  True
        assert response['sentence'] ==  self.gift_card.gift_sentence
        assert response['redeem_type'] ==  self.gift_card.get_redeem_type_display()
        assert not cache.get(f'gift_otp_{self.gift_card.id}') is None
        user_sms = UserSms.objects.get(
            tp=UserSms.TYPES.gift,
            to=self.gift_card.mobile,
        )
        assert not user_sms is None
        assert user_sms.text == cache.get(f'gift_otp_{self.gift_card.id}')


class RedeemLoggedInUserGiftCardTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.sender = User.objects.get(pk=200)
        self.sender.mobile ='989121234567'
        self.sender.save()
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )
        self.url = '/gift/redeem'
        self.password = '1372'
        self.otp = 'aaaa'
        self.redeem_code = 'a' * 32
        self.user_btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.user_btc_wallet.balance = 1
        self.user_btc_wallet.save()
        self.user_btc_wallet.get_current_deposit_address(create=True)
        self.sys_btc_wallet = Wallet.get_user_wallet(
            User.objects.get(username='system-gift@nobitex.ir'),
            Currencies.btc,
        )
        amount = Decimal('0.1')
        initial_withdraw = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_btc_wallet,
            amount=amount,
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            status=WithdrawRequest.STATUS.done,
            target_address=self.user_btc_wallet.get_current_deposit_address().address
        )
        self.sys_btc_wallet.create_transaction(tp='manual', amount='1').commit()
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)
        self.gift_card = GiftCard.objects.create(
            sender=self.sender,
            currency=Currencies.btc,
            amount=amount,
            initial_withdraw=initial_withdraw,
            gift_type=GiftCard.GIFT_TYPES.digital,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code,
            redeem_type=GiftCard.REDEEM_TYPE.internal,
        )
        cache.set(f'gift_otp_{self.gift_card.id}', self.otp)

    def get_request_body(self):
        return {
            'redeem_code': self.redeem_code,
            'password': self.password,
            'otp': self.otp,
        }

    @override_settings(IS_PROD=True)
    def test_otp(self):
        request_body = self.get_request_body()
        request_body['otp'] = '12121212'
        response = self.client.post(self.url, data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidOTP'

    @override_settings(IS_PROD=True)
    def test_redeemed(self):
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.redeemed
        self.gift_card.save(update_fields=['gift_status', ])
        response = self.client.post(self.url, data=self.get_request_body()).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'AlreadyRedeemedOrCanceled'

    @override_settings(IS_PROD=True)
    def test_canceled(self):
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.canceled
        self.gift_card.save(update_fields=['gift_status'])
        response = self.client.post(self.url, data=self.get_request_body()).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'CardIsCanceled'

    @override_settings(IS_PROD=True)
    def test_password(self):
        request_body = self.get_request_body()
        request_body['password'] = '12121212'
        response = self.client.post(self.url, data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidPassword'

    def test_success(self):
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.verified
        self.gift_card.save(update_fields=['gift_status'])
        response = self.client.post(self.url, data=self.get_request_body()).json()
        assert response['status'] == 'ok'
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)
        assert self.sys_btc_wallet.balance == Decimal('.9')


class CreateGiftCardTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )
        self.user.user_type = User.USER_TYPES.level1
        self.user.mobile = '09121112123'
        self.user.save(update_fields=['user_type', 'mobile', ])
        vp, _ = VerificationProfile.objects.get_or_create(user=self.user)
        vp.mobile_confirmed = True
        vp.save(update_fields=['mobile_confirmed', ])
        self.user_bitcoin_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.user_bitcoin_wallet.create_transaction(tp='manual', amount='.1').commit()
        self.user_rls_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.user_rls_wallet.create_transaction(tp='manual', amount='1000000').commit()
        self.sys_btc_wallet = Wallet.get_user_wallet(
            User.objects.get(username='system-gift@nobitex.ir'),
            Currencies.btc,
        )
        self.card_design, _ = CardDesign.objects.get_or_create(title='default')
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)

    def create_gift_card_params(self):
        return {
            'amount': '.012',
            'currency': 'btc',
            'mobile': '989366946395',
            'email': 'user12@gmail.com',
            'gift_type': 'digital',
            'gift_sentence': 'test gift sentence',
            'otp_enabled': 'false',
            'receiver_address': 'Solar system, Milkey way, Earth.',
            'receiver_postal_code': '1464733313',
            'receiver_full_name': 'testuser testian',
            'card_design': 'default',
            'redeem_date': (datetime.datetime.today() + datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'redeem_type': 'internal',
            'password': 'verysecurepassword',
        }

    def test_physical_gift_required_parameters(self):
        request_body = self.create_gift_card_params()
        request_body['gift_type'] = 'physical'
        del request_body['receiver_address']
        response = self.client.post('/gift/create-gift', data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ValidationError'
        request_body = self.create_gift_card_params()
        request_body['gift_type'] = 'physical'
        del request_body['receiver_postal_code']
        response = self.client.post('/gift/create-gift', data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ValidationError'

    def test_required_parameters(self):
        for required_keys in [
            'amount',
            'currency',
            'gift_type',
            'redeem_type',
        ]:
            request_body = self.create_gift_card_params()
            del request_body[required_keys]
            response = self.client.post('/gift/create-gift', data=request_body).json()
            assert response['status'] == 'failed'
            assert response['code'] == 'ParseError'

    def test_withdraw_condition(self):
        UserRestriction.objects.filter(
            user=self.user,
        ).delete()
        UserRestriction.objects.create(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequest,
        )
        response = self.client.post('/gift/create-gift', data=self.create_gift_card_params()).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'WithdrawUnavailable'

        UserRestriction.objects.filter(
            user=self.user,
        ).delete()
        UserRestriction.objects.create(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
        )
        response = self.client.post('/gift/create-gift', data=self.create_gift_card_params()).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'WithdrawUnavailable'

        UserRestriction.objects.filter(
            user=self.user,
        ).delete()
        UserRestriction.objects.create(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestRial,
        )
        request_body = self.create_gift_card_params()
        request_body['currency'] = 'rls'
        request_body['amount'] = '1000000'
        response = self.client.post('/gift/create-gift', data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'WithdrawUnavailable'

    def test_wallet_balance(self):
        request_body = self.create_gift_card_params()
        request_body['amount'] = '0.10001'
        response = self.client.post('/gift/create-gift', data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InsufficientBalance'

        request_body = self.create_gift_card_params()
        request_body['currency'] = 'rls'
        request_body['amount'] = '1020000'
        response = self.client.post('/gift/create-gift', data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InsufficientBalance'

    @pytest.mark.skip('In progress: Should find proccess_withdraws considerations.')
    def test_successful_creation(self):
        self.user_bitcoin_wallet = Wallet.objects.get(pk=self.user_bitcoin_wallet.pk)
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)
        assert self.user_bitcoin_wallet.balance == Decimal('0.1')
        assert self.sys_btc_wallet.balance == Decimal('0')
        Settings.set('withdraw_enabled', 'yes')
        response = self.client.post('/gift/create-gift', data=self.create_gift_card_params()).json()
        assert response['status'] == 'ok'
        process_withdraws()
        self.user_bitcoin_wallet = Wallet.objects.get(pk=self.user_bitcoin_wallet.pk)
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)
        assert self.sys_btc_wallet.balance == Decimal('0.012')
        assert self.user_bitcoin_wallet.balance == Decimal('0.088')


def mocked_lnd_request():
    return mock.Mock(side_effect={
        'https://tlnurlapi.nobitex.ir/addgifts': {'gifts': {'lnurl': 'lnurltest123456321', 'key': 'test_key'}}
    })


class PublicRedeemLightningGiftCardTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.sender = User.objects.get(pk=200)
        self.sender.mobile ='989121234567'
        self.sender.save()
        self.client = Client()
        self.url = '/gift/redeem-lightning'
        self.password = '1372'
        self.otp = 'aaaa'
        self.redeem_code = 'a' * 32
        self.user_btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.user_btc_wallet.balance = 1
        self.user_btc_wallet.save()
        self.user_btc_wallet.get_current_deposit_address(create=True)
        self.sys_btc_wallet = Wallet.get_user_wallet(
            User.objects.get(username='system-gift@nobitex.ir'),
            Currencies.btc,
        )
        amount = Decimal('0.1')
        initial_withdraw = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_btc_wallet,
            amount=amount,
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            status=WithdrawRequest.STATUS.done,
            target_address=self.user_btc_wallet.get_current_deposit_address().address
        )
        self.sys_btc_wallet.create_transaction(tp='manual', amount='1').commit()
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)

        self.gift_card = GiftCard.objects.create(
            sender=self.sender,
            currency=Currencies.btc,
            amount=Decimal('0.1'),
            initial_withdraw=initial_withdraw,
            gift_type=GiftCard.GIFT_TYPES.digital,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code,
            redeem_type=GiftCard.REDEEM_TYPE.lightning,
        )
        cache.set(f'gift_otp_{self.gift_card.id}', self.otp)

    def get_request_body(self):
        return {
            'redeem_code': self.redeem_code,
            'password': self.password,
            'otp': self.otp,
        }

    @override_settings(IS_PROD=True)
    def test_otp(self):
        request_body = self.get_request_body()
        request_body['otp'] = 'z' * 8
        response = self.client.post(self.url, data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidOTP'

    def test_password(self):
        request_body = self.get_request_body()
        request_body['password'] = '12121212'
        response = self.client.post(self.url, data=request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidPassword'

    @mock.patch('exchange.gift.models.GiftCard.set_lnurl', side_effect=mocked_lnd_request)
    def test_success(self, mock_post):
        response = self.client.post(self.url, data=self.get_request_body()).json()
        assert response['status'] == 'ok'
        self.gift_card = GiftCard.objects.get(pk=self.gift_card.pk)
        assert response['lnUrl'] == self.gift_card.lnurl

    def test_verified_gift_cost(self):
        self.gift_card.gift_batch = GiftBatchRequest.objects.create(user=self.user)
        self.gift_card.gift_type = GiftCard.GIFT_TYPES.physical
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.verified
        self.gift_card.save()
        assert self.gift_card.cost == settings.GIFT_CARD_PHYSICAL_PRINT_FEE + settings.GIFT_CARD_PHYSICAL_POSTAL_FEE

        initial_withdraw = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_btc_wallet,
            amount=Decimal('0.1'),
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            status=WithdrawRequest.STATUS.done,
            target_address=self.user_btc_wallet.get_current_deposit_address().address
        )
        self.gift_card2 = GiftCard.objects.create(
            sender=self.sender,
            currency=Currencies.btc,
            amount=Decimal('0.1'),
            initial_withdraw=initial_withdraw,
            gift_type=GiftCard.GIFT_TYPES.digital,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code='b' * 32,
            redeem_type=GiftCard.REDEEM_TYPE.lightning,
            gift_batch=self.gift_card.gift_batch,
        )
        self.gift_card2.gift_type = GiftCard.GIFT_TYPES.physical
        self.gift_card2.gift_status = GiftCard.GIFT_STATUS.verified
        self.gift_card2.save()
        assert self.gift_card.cost == settings.GIFT_CARD_PHYSICAL_PRINT_FEE

        self.gift_card.gift_status = GiftCard.GIFT_STATUS.printed
        self.gift_card.save()
        assert self.gift_card.cost == settings.GIFT_CARD_PHYSICAL_PRINT_FEE
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.confirmed
        self.gift_card.save()
        assert self.gift_card.cost == settings.GIFT_CARD_PHYSICAL_PRINT_FEE
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.redeemed
        self.gift_card.save()
        assert self.gift_card.cost == settings.GIFT_CARD_PHYSICAL_FEE
        self.gift_card.gift_status = GiftCard.GIFT_STATUS.verified
        self.gift_card.gift_batch = None
        self.gift_card.save()
        assert self.gift_card.cost == settings.GIFT_CARD_PHYSICAL_FEE


class ResendGiftOtpTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client()
        self.url = '/gift/resend-gift-otp'
        self.password = '1372'
        self.redeem_code = 'a' * 32
        self.request_body = {'redeem_code': self.redeem_code}
        self.gift_card = GiftCard.objects.create(
            sender=User.objects.get(pk=200),
            currency=Currencies.btc,
            amount=Decimal('0.1'),
            initial_withdraw=None,
            gift_type=GiftCard.GIFT_TYPES.digital,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code,
            redeem_type=GiftCard.REDEEM_TYPE.lightning,
        )
        self.opt_key = f'gift_otp_{self.gift_card.id}'

    def test_success(self):
        assert cache.get(self.opt_key) is None
        response  = self.client.post(self.url, data=self.request_body).json()
        assert response['status'] == 'ok'
        assert cache.get(self.opt_key) == UserSms.objects.filter(to=self.gift_card.mobile).last().text

    def test_too_many_requests(self):
        for _ in range(8):
            assert self.client.post(self.url, data=self.request_body).json()['status'] == 'ok'
        response  = self.client.post(self.url, data=self.request_body).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'TooManyRequests'


class UserGiftCardsList(TestCase):
    def setUp(self):
        self.url = '/gift/user-gifts'
        self.user = User.objects.get(pk=201)
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )
        self.other_user = User.objects.get(pk=200)
        self.package_type = GiftPackage.objects.create(
            name='test-package',
            price=10_000,
            stock=0,
            weight=10,
            width=10,
            height=10,
            depth=10,
            can_batch_request=True,
        )
        self.card_design, _ = CardDesign.objects.get_or_create(title='default')
        self.sent_gifts = [
            GiftCard(
                sender=self.user,
                currency=Currencies.btc,
                amount=Decimal('0.1'),
                initial_withdraw=None,
                gift_type=GiftCard.GIFT_TYPES.digital,
                gift_sentence='this is a gift',
                receiver=self.other_user,
                package_type=self.package_type,
                address='Solar system, Milkey way, Earth.',
                postal_code='12344123',
                full_name='giftee recipient 0',
                mobile='09122231232',
                password=make_password('randomstring'),
                redeem_code='as2d12d12d',
                redeem_type=GiftCard.REDEEM_TYPE.lightning,
                gift_status=GiftCard.GIFT_STATUS.verified,
                card_design=self.card_design,
            ),
            GiftCard(
                sender=self.user,
                currency=Currencies.rls,
                amount=Decimal('1000'),
                initial_withdraw=None,
                gift_type=GiftCard.GIFT_TYPES.digital,
                gift_sentence='this is a gift',
                package_type=self.package_type,
                receiver=self.other_user,
                full_name='giftee recipient 1',
                mobile='09122231232',
                password=make_password('1234'),
                redeem_code='aaaaaaaaaaaa',
                redeem_type=GiftCard.REDEEM_TYPE.internal,
                card_design=self.card_design,
            ),
        ]
        self.received_gifts = [
            GiftCard(
                sender=self.other_user,
                currency=Currencies.eth,
                amount=Decimal('0.1'),
                initial_withdraw=None,
                gift_type=GiftCard.GIFT_TYPES.digital,
                package_type=self.package_type,
                gift_sentence='this is a gift',
                receiver=self.user,
                full_name='main user',
                mobile='0912223122',
                password=make_password('pass'),
                redeem_code='bbbbbbbbbbbb',
                redeem_type=GiftCard.REDEEM_TYPE.internal,
                gift_status=GiftCard.GIFT_STATUS.verified,
                card_design=self.card_design,
            ),
        ]
        for gc in self.received_gifts:
            gc.save()
        for gc in self.sent_gifts:
            gc.save()

    def test_api(self):
        response = self.client.get(self.url).json()
        assert response['status'] == 'ok'
        assert len(response['sent_gift_cards']) == 1
        assert len(response['received_gift_cards']) == 1
        card0 = response['sent_gift_cards'][0]
        assert card0['full_name'] == 'giftee recipient 0'
        assert card0['address'] == 'Solar system, Milkey way, Earth.'
        assert card0['mobile'] == '09122231232'
        assert card0['postal_code'] == '12344123'
        assert card0['gift_sentence'] == 'this is a gift'
        assert card0['amount'] == '0.1'
        assert card0['sender']['username'] == 'user1@example.com'
        assert card0['receiver']['username'] == 'gateway@internal.com'
        assert card0['currency'] == 'btc'
        assert card0['gift_type'] == 'Digital'
        assert card0['gift_status'] == 'Verified'
        assert card0['card_design'] == self.card_design.title
        assert card0['redeem_date'] is None
        assert card0['package_type'] == serialize_gift_package(self.package_type)


class GiftPackagesList(TestCase):
    def setUp(self):
        self.url = '/gift/packages'
        self.user = User.objects.get(pk=201)
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )
        self.package = GiftPackage.objects.create(
            name='test-package',
            price=10_000,
            stock=0,
            weight=10,
            width=10,
            height=10,
            depth=10,
            can_batch_request=True,
        )

    def test_api(self):
        response = self.client.get(self.url).json()
        assert response['status'] == 'ok'
        assert len(response['giftPackages']) == 1
        package = response['giftPackages'][0]
        assert package == {
            'id': self.package.id,
            'name': self.package.name,
            'isInStock': False,
            'weight': self.package.weight,
            'width': self.package.width,
            'height': self.package.height,
            'depth': self.package.depth,
            'canBatchRequest': self.package.can_batch_request,
            'images': []
        }

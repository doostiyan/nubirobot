import datetime
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase, Client

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Currencies
from exchange.gift.crons import VerifyGifts
from exchange.gift.models import GiftCard
from exchange.wallet.models import Wallet, WithdrawRequest


class TestVerifyGiftsCron(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.sender = User.objects.get(pk=200)
        self.sender.save()
        self.client = Client(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )
        self.password = '1381'
        self.otp = '1324'
        self.redeem_code_verified = '0' * 32
        self.redeem_code_closed = '1' * 32
        self.redeem_code_physical = '2' * 32
        self.user_btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.user_rial_wallet = Wallet.get_user_wallet(user=self.user, currency=Currencies.rls)
        self.user_rial_wallet.balance = Decimal('10_000_000')
        self.user_rial_wallet.save()
        self.user_btc_wallet.balance = 1
        self.user_btc_wallet.save()
        self.user_btc_wallet.get_current_deposit_address(create=True)
        self.sys_btc_wallet = Wallet.get_user_wallet(
            User.objects.get(username='system-gift@nobitex.ir'),
            Currencies.btc,
        )
        self.gift_rial_wallet = Wallet.get_user_wallet(
            User.get_gift_system_user(),
            Currencies.rls,
        )
        self.gift_rial_wallet.balance = Decimal('10_000_000')
        self.gift_rial_wallet.save()
        self.gift_rial_wallet.refresh_from_db()
        amount = Decimal('0.01')
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
        initial_withdraw_closed = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_btc_wallet,
            amount=amount,
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            status=WithdrawRequest.STATUS.new,
            target_address=self.user_btc_wallet.get_current_deposit_address().address
        )

        initial_withdraw_physical_closed = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_btc_wallet,
            amount=amount,
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            status=WithdrawRequest.STATUS.new,
            target_address=self.user_btc_wallet.get_current_deposit_address().address
        )

        self.sys_btc_wallet.create_transaction(tp='manual', amount='1').commit()
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)
        self.gift_card_verified = GiftCard.objects.create(
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
            redeem_code=self.redeem_code_verified,
            redeem_type=GiftCard.REDEEM_TYPE.internal,
            created_at=ir_now() - datetime.timedelta(minutes=4)
        )
        self.physical_gift_closed = GiftCard.objects.create(
            sender=self.sender,
            currency=Currencies.btc,
            amount=amount,
            initial_withdraw=initial_withdraw_physical_closed,
            gift_type=GiftCard.GIFT_TYPES.physical,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code_physical,
            redeem_type=GiftCard.REDEEM_TYPE.internal,
            created_at=ir_now() - datetime.timedelta(minutes=4)
        )
        self.gift_card_closed = GiftCard.objects.create(
            sender=self.sender,
            currency=Currencies.btc,
            amount=amount,
            initial_withdraw=initial_withdraw_closed,
            gift_type=GiftCard.GIFT_TYPES.physical,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code_closed,
            redeem_type=GiftCard.REDEEM_TYPE.internal,
            created_at=ir_now() - datetime.timedelta(minutes=4)
        )

    def test_verified_gifts(self):
        VerifyGifts().run()
        self.gift_card_verified.refresh_from_db()
        assert self.gift_card_verified.gift_status == GiftCard.GIFT_STATUS.verified

    def test_closed_gifts(self):
        VerifyGifts().run()
        self.gift_card_closed.refresh_from_db()
        assert self.gift_card_closed.gift_status == GiftCard.GIFT_STATUS.closed

    def test_closed_physical_gifts(self):
        VerifyGifts().run()
        self.physical_gift_closed.refresh_from_db()
        assert self.physical_gift_closed.gift_status == GiftCard.GIFT_STATUS.closed

    def test_reverted_physical_transaction(self):
        VerifyGifts().run()
        assert self.user_rial_wallet.balance == Decimal('10_000_000')

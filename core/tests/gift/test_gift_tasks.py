from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Currencies
from exchange.gift.models import GiftBatchRequest, GiftCard
from exchange.gift.tasks import cancel_batch_request_gifts
from exchange.wallet.models import WithdrawRequest, Wallet
from exchange.wallet.withdraw_process import ProcessingWithdrawMethod


class TestCancelBatchRequestGiftsTask(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.withdraw_processor = ProcessingWithdrawMethod(currency=Currencies.btc)
        self.cancelable_gift_batch = GiftBatchRequest.objects.create(
            user=self.user,
            number=1,
            currency=Currencies.btc,
            gift_type=GiftCard.GIFT_TYPES.physical,
        )
        self.uncancellable_gift_batch = GiftBatchRequest.objects.create(
            user=self.user,
            number=1,
            currency=Currencies.btc,
        )
        self.password = 'testpass123'
        self.redeem_code = 't' * 32
        self.user_btc_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        self.user_rial_wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        self.user_btc_wallet.balance = 1
        self.user_rial_wallet.balance = Decimal('1_000_000')
        self.user_btc_wallet.save()
        self.user_rial_wallet.save()
        self.user_btc_wallet.get_current_deposit_address(create=True)
        self.sys_btc_wallet = Wallet.get_user_wallet(
            User.objects.get(username='system-gift@nobitex.ir'),
            Currencies.btc,
        )
        self.sys_rial_wallet = Wallet.get_user_wallet(
            User.objects.get(username='system-gift@nobitex.ir'),
            Currencies.rls,
        )
        self.sys_rial_wallet.balance = Decimal('1_360_000')
        self.sys_rial_wallet.save()
        amount = Decimal('0.1')
        self.initial_withdraw = WithdrawRequest.objects.create(
            tp=WithdrawRequest.TYPE.internal,
            wallet=self.user_btc_wallet,
            amount=amount,
            explanations=f'User-{self.user.id} withdraw for requested gift card.',
            target_account=None,
            network=CURRENCY_INFO[Currencies.btc]['default_network'],
            target_address=str(self.user_btc_wallet.get_current_deposit_address())
        )
        self.initial_withdraw.do_verify()
        self.initial_withdraw.create_transaction()
        self.sys_btc_wallet.create_transaction(tp='manual', amount='1').commit()
        self.sys_btc_wallet = Wallet.objects.get(pk=self.sys_btc_wallet.pk)

    def test_cancelable_batch_gifts(self):
        self.cancelable_gift_card = GiftCard.objects.create(
            sender=self.user,
            currency=Currencies.btc,
            amount=Decimal('0.1'),
            initial_withdraw=self.initial_withdraw,
            gift_type=GiftCard.GIFT_TYPES.physical,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code,
            redeem_type=GiftCard.REDEEM_TYPE.lightning,
        )

        self.cancelable_gift_card.gift_batch = self.cancelable_gift_batch
        self.cancelable_gift_card.gift_status = GiftCard.GIFT_STATUS.verified
        self.cancelable_gift_card.save()
        self.withdraw_processor.process_withdraws(
            withdraw_requests=[self.cancelable_gift_card.initial_withdraw],
            status=WithdrawRequest.STATUS.verified,
        )
        cancel_batch_request_gifts(self.cancelable_gift_batch.id)
        self.cancelable_gift_card.refresh_from_db()
        self.cancelable_gift_batch.refresh_from_db()
        assert self.cancelable_gift_card.gift_status == GiftCard.GIFT_STATUS.canceled
        assert self.cancelable_gift_batch.status == GiftBatchRequest.BATCH_STATUS.canceled
        self.user_rial_wallet.refresh_from_db()
        assert self.user_rial_wallet.balance == Decimal('1_360_000')
        assert self.user_btc_wallet.balance == Decimal('1')

    def test_uncancellable_batch_gifts(self):
        self.uncancellable_gift_card = GiftCard.objects.create(
            sender=self.user,
            currency=Currencies.btc,
            amount=Decimal('0.1'),
            initial_withdraw=self.initial_withdraw,
            gift_type=GiftCard.GIFT_TYPES.physical,
            gift_sentence='this is a gift',
            receiver=self.user,
            full_name='giftee recipient',
            mobile='09122231232',
            password=make_password(self.password),
            redeem_code=self.redeem_code,
            redeem_type=GiftCard.REDEEM_TYPE.lightning,
        )

        self.uncancellable_gift_card.gift_batch = self.uncancellable_gift_batch
        self.withdraw_processor.process_withdraws(
            withdraw_requests=[self.uncancellable_gift_card.initial_withdraw],
            status=WithdrawRequest.STATUS.verified,
        )
        cancel_batch_request_gifts(self.cancelable_gift_batch.id)
        self.uncancellable_gift_card.refresh_from_db()
        self.uncancellable_gift_batch.refresh_from_db()
        assert self.uncancellable_gift_batch.status == GiftBatchRequest.BATCH_STATUS.new
        assert self.uncancellable_gift_card.gift_status == GiftCard.GIFT_STATUS.new
        self.user_rial_wallet.refresh_from_db()
        assert self.user_rial_wallet.balance == Decimal('1_000_000')
        self.user_btc_wallet.refresh_from_db()
        assert self.user_btc_wallet.balance == Decimal('0.9')

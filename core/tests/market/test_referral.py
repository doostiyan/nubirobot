from datetime import timedelta
from decimal import Decimal
from typing import List

from django.core.cache import cache
from django.test import TestCase, override_settings

from exchange.accounts.models import ReferralProgram, User, UserReferral
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market, OrderMatching, ReferralFee
from exchange.market.referral import calculate_referral_fees
from exchange.matcher.matcher import Matcher
from exchange.wallet.models import Transaction, Wallet

from ..base.utils import create_order, do_matching_round


class ReferralTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)
        cls.user3 = User.objects.get(pk=203)
        cls.user4 = User.objects.get(pk=204)
        cls.program10 = ReferralProgram.create(cls.user1, 10)[0]
        cls.program15 = ReferralProgram.create(cls.user1, 15)[0]
        cls.program30 = ReferralProgram.create(cls.user1, 30)[0]

    def setUp(self):
        # Charge referral fee wallet
        fee_wallet_rls = Wallet.get_fee_collector_wallet(Currencies.rls)
        charge_fee = fee_wallet_rls.create_transaction(tp='referral', amount=Decimal('1_000_000_0'))
        charge_fee.commit()
        Settings.set_dict('referral_fee_restrictions', {})

    def _set_up_referral(self):
        UserReferral.objects.create(
            parent=self.user1,
            child=self.user2,
            referral_share=30,
            child_referral_share=10,
            referral_program=self.program10,
        )
        UserReferral.objects.create(
            parent=self.user1,
            child=self.user3,
            referral_share=35,
            child_referral_share=15,
            referral_program=self.program15,
        )
        UserReferral.objects.create(
            parent=self.user1,
            child=self.user4,
            referral_share=30,
            child_referral_share=0,
            referral_program=self.program30,
        )

    @staticmethod
    def _create_orders(users: List[User], dst: int):
        price = Decimal('184.7e7') if dst == Currencies.rls else Decimal('184.7e3')
        create_order(users[0], Currencies.btc, dst, Decimal('0.412'), price, sell=True)
        create_order(users[1], Currencies.btc, dst, Decimal('0.412'), price, sell=False)

    def _create_trade(self, users: List[User], dst=Currencies.rls):
        market = Market.objects.get(src_currency=Currencies.btc, dst_currency=dst)
        self._create_orders(users, dst)
        if dst == Currencies.usdt:
            Matcher.initialize_globals()
        do_matching_round(market)
        return OrderMatching.objects.order_by('-created_at').last()

    def _verify_referral_fee(
        self, user: User, referred_user: User, amount: Decimal, program: ReferralProgram, trade: OrderMatching
    ):
        referral_fee = ReferralFee.objects.filter(user=user, referred_user=referred_user).order_by('created_at').first()
        assert referral_fee
        assert referral_fee.referral_program == program
        assert referral_fee.matching == trade
        assert not referral_fee.is_calculated
        assert referral_fee.amount == amount
        return referral_fee

    def test_create_referral_program(self):
        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        r1, error = ReferralProgram.create(user1, 0)
        assert not error
        assert r1.referral_code
        assert r1.user == user1
        assert r1.friend_share == 0
        assert r1.user_share == 30
        r2, error = ReferralProgram.create(user1, 20)
        assert not error
        assert r2.referral_code
        assert r2.user == user1
        assert r2.friend_share == 20
        assert r2.user_share == 10
        r3, error = ReferralProgram.create(user2, 0)
        assert not error
        assert r3.referral_code
        assert r3.user == user2
        assert r3.friend_share == 0
        assert r3.user_share == 30
        # check uniqueness
        assert r1.referral_code != r2.referral_code != r3.referral_code
        assert r1.referral_code != r3.referral_code

    def test_referral_calculation(self):
        self._set_up_referral()

        # Trade
        last_trade = self._create_trade([self.user2, self.user3])
        user2_total_fee = last_trade.get_sell_fee_amount()
        user3_total_fee = last_trade.get_buy_fee_amount() * last_trade.matched_price
        assert user2_total_fee == Decimal('190_241_0')
        assert user3_total_fee == Decimal('190_241_0')
        user2_referral_fee = (user2_total_fee * Decimal('0.3')).quantize(Decimal('1'))
        user3_referral_fee = (user3_total_fee * Decimal('0.35')).quantize(Decimal('1'))
        user2_child_referral_fee = (user2_total_fee * Decimal('0.1')).quantize(Decimal('1'))
        user3_child_referral_fee = (user3_total_fee * Decimal('0.15')).quantize(Decimal('1'))

        # Check ReferralFee
        fee_u2 = self._verify_referral_fee(self.user1, self.user2, Decimal('57_072_3'), self.program10, last_trade)
        fee_u3 = self._verify_referral_fee(self.user1, self.user3, Decimal('66_584_4'), self.program15, last_trade)
        self._verify_referral_fee(self.user2, self.user2, Decimal('19_024_1'), self.program10, last_trade)
        self._verify_referral_fee(self.user3, self.user3, Decimal('28_536_2'), self.program15, last_trade)

        # Check calculation
        calculate_referral_fees()
        fee_u2.refresh_from_db()
        fee_u3.refresh_from_db()
        assert fee_u2.matching == fee_u3.matching == last_trade
        assert fee_u2.is_calculated == fee_u3.is_calculated == True
        assert fee_u2.amount == user2_referral_fee
        assert fee_u3.amount == user3_referral_fee
        assert not ReferralFee.objects.filter(is_calculated=False).exists()

        # Check transfer destination transaction
        user1_wallet = Wallet.get_user_wallet(self.user1, Currencies.rls)
        referral_transactions = Transaction.objects.filter(
            description__startswith='Charge for Referral Fee:',
            created_at__gte=last_trade.created_at,
        )
        assert len(referral_transactions) == 3
        referral_transactions = referral_transactions.filter(wallet=user1_wallet)
        assert len(referral_transactions) == 1
        referral_transaction = referral_transactions.get()
        assert referral_transaction.tp == Transaction.TYPE.referral
        assert referral_transaction.amount == Decimal('123_656_7')
        assert referral_transaction.ref_module == Transaction.REF_MODULES['TransferDst']
        assert referral_transaction.ref_id == min(fee_u2.pk, fee_u3.pk)

        # Check transfer source transaction
        system_fee_wallet = Wallet.get_fee_collector_wallet(Currencies.rls)
        src_transactions = Transaction.objects.filter(
            wallet=system_fee_wallet,
            tp=Transaction.TYPE.referral,
            created_at__gte=last_trade.created_at,
        )
        assert len(src_transactions) == 1
        src_transaction = src_transactions.get()
        assert src_transaction.amount == Decimal('-171_217_0')
        assert src_transaction.ref_module is None
        assert src_transaction.ref_id is None

        # Check referral reports
        stats10 = ReferralFee.get_referral_program_stats(self.program10)
        stats15 = ReferralFee.get_referral_program_stats(self.program15)
        assert self.program10.get_referred_users_count() == 0
        assert self.program15.get_referred_users_count() == 0
        assert stats10['trades'] == 1
        assert stats15['trades'] == 1
        assert stats10['friendsTrades'] == 1
        assert stats15['friendsTrades'] == 1
        assert stats10['profit'] == user2_referral_fee
        assert stats15['profit'] == user3_referral_fee
        assert stats10['friendsProfit'] == user2_child_referral_fee
        assert stats15['friendsProfit'] == user3_child_referral_fee

    @override_settings(ASYNC_TRADE_COMMIT=True)
    def test_bulk_create_referral(self):
        self._set_up_referral()
        trade = self._create_trade([self.user2, self.user3])
        assert not ReferralFee.objects.exists()
        MarketManager.create_bulk_referral_fee([trade])
        self._verify_referral_fee(self.user1, self.user2, Decimal('57_072_3'), self.program10, trade)
        self._verify_referral_fee(self.user1, self.user3, Decimal('66_584_4'), self.program15, trade)
        self._verify_referral_fee(self.user2, self.user2, Decimal('19_024_1'), self.program10, trade)
        self._verify_referral_fee(self.user3, self.user3, Decimal('28_536_2'), self.program15, trade)
        assert ReferralFee.objects.count() == 4

        # Check calculation
        calculate_referral_fees()
        assert not ReferralFee.objects.filter(is_calculated=False).exists()

    @override_settings(ASYNC_TRADE_COMMIT=True)
    def test_bulk_create_zero_share_referral(self):
        self._set_up_referral()
        trade = self._create_trade([self.user2, self.user4])
        assert not ReferralFee.objects.exists()
        MarketManager.create_bulk_referral_fee([trade])
        self._verify_referral_fee(self.user1, self.user2, Decimal('57_072_3'), self.program10, trade)
        self._verify_referral_fee(self.user1, self.user4, Decimal('57_072_3'), self.program30, trade)
        self._verify_referral_fee(self.user2, self.user2, Decimal('19_024_1'), self.program10, trade)
        assert ReferralFee.objects.count() == 3

        # Check calculation
        calculate_referral_fees()
        assert not ReferralFee.objects.filter(is_calculated=False).exists()

    @override_settings(ASYNC_TRADE_COMMIT=True)
    def test_bulk_create_usdt_referral(self):
        self._set_up_referral()
        tether_market = Market.get_for(Currencies.usdt, Currencies.rls)
        cache.set(f'market_{tether_market.id}_last_price', Decimal('10000'))
        trade = self._create_trade(users=[self.user2, self.user3], dst=Currencies.usdt)

        assert not ReferralFee.objects.exists()
        MarketManager.create_bulk_referral_fee([trade])
        self._verify_referral_fee(self.user1, self.user2, Decimal('22_828_9'), self.program10, trade)
        self._verify_referral_fee(self.user1, self.user3, Decimal('34_623_9'), self.program15, trade)
        self._verify_referral_fee(self.user2, self.user2, Decimal('7_609_6'), self.program10, trade)
        self._verify_referral_fee(self.user3, self.user3, Decimal('14_838_8'), self.program15, trade)
        assert ReferralFee.objects.count() == 4

        # Check calculation
        calculate_referral_fees()
        assert ReferralFee.objects.filter(is_calculated=False).count() == 1
        cache.clear()

    @override_settings(ASYNC_TRADE_COMMIT=True)
    def test_bulk_create_usdt_referral_with_expired_referral_success(self):
        # given->
        Settings.set_cached_json(
            'referral_fee_restrictions', {'parent_share_eligible_months': 9, 'child_share_eligible_months': 6}
        )

        self._set_up_referral()

        referral1 = UserReferral.objects.filter(parent=self.user1, child=self.user2).first()
        referral1.created_at = ir_now() - timedelta(days=10 * 30)
        referral1.save(update_fields=['created_at'])

        referral2 = UserReferral.objects.filter(parent=self.user1, child=self.user3).first()
        referral2.created_at = ir_now() - timedelta(days=7 * 30)
        referral2.save(update_fields=['created_at'])

        tether_market = Market.get_for(Currencies.usdt, Currencies.rls)
        cache.set(f'market_{tether_market.id}_last_price', Decimal('10000'))
        trade = self._create_trade(users=[self.user2, self.user3], dst=Currencies.usdt)

        assert not ReferralFee.objects.exists()

        # when->
        MarketManager.create_bulk_referral_fee([trade])

        # then->
        self._verify_referral_fee(self.user1, self.user3, Decimal('34_623_9'), self.program15, trade)
        assert ReferralFee.objects.count() == 1

        calculate_referral_fees()
        assert ReferralFee.objects.filter(is_calculated=False).count() == 0
        cache.clear()

import datetime
import json
import os
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Type
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.test import Client, TestCase

from exchange.accounts.models import UploadedFile, User, UserRestriction
from exchange.base.calendar import ir_now, ir_today
from exchange.base.models import RIAL, Currencies, Settings
from exchange.market.models import Market, Order, OrderMatching
from exchange.promotions.crons import DiscountUpdateCron
from exchange.promotions.discount import get_active_user_discount
from exchange.promotions.models import Discount, DiscountTransactionLog, UserDiscount, UserDiscountBatch
from exchange.promotions.tasks import task_create_user_discount
from exchange.wallet.models import Transaction, Wallet
from exchange.web_engage.utils import generate_key


class TestDiscount(TestCase):
    MAX_SYSTEM_FEE_WALLET = 100000000

    def setUp(self):
        # set system_fee_wallet
        self.system_fee_wallet = Wallet.get_fee_collector_wallet(RIAL)
        self.system_fee_wallet.balance = TestDiscount.MAX_SYSTEM_FEE_WALLET
        self.system_fee_wallet.save(update_fields=['balance'])
        self.system_fee_wallet.refresh_from_db()

        self.users = [User.objects.get(pk=pk) for pk in list(range(201, 205)) + [1000]]

        self.market_btc_usdt = Market.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            is_active=True,
        )

        self.market_btc_rls = Market.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            is_active=True,
        )

        cache.set('orderbook_BTCIRT_best_buy', Decimal('600_000_000_0'))
        cache.set('orderbook_USDTIRT_best_buy', Decimal('36_000_0'))

        self.date_time_now_ir = ir_now().replace(hour=12, minute=0, second=0, microsecond=0)

        self.done_order = [
            Order.objects.create(
                user=self.users[0],
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                amount=Decimal('1'),
                price=Decimal('610_000_000_0'),
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.market,
                status=Order.STATUS.done,
                created_at=self.date_time_now_ir - datetime.timedelta(days=1),
                trade_type=Order.TRADE_TYPES.spot,
            )
            for _ in range(6)
        ]
        self.done_order.append(
            Order.objects.create(
                user=self.users[0],
                src_currency=Currencies.btc,
                dst_currency=Currencies.rls,
                amount=Decimal('1'),
                price=Decimal('610_000_000_0'),
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.market,
                status=Order.STATUS.done,
                created_at=self.date_time_now_ir - datetime.timedelta(days=1),
                trade_type=Order.TRADE_TYPES.margin,
            )
        )

        order_matching_data = {
            'numbers': 7,
            'market': [self.market_btc_rls, self.market_btc_rls, self.market_btc_usdt, self.market_btc_usdt,
                       self.market_btc_rls, self.market_btc_usdt, self.market_btc_usdt],
            'sell_order': [self.done_order[i] for i in range(7)],
            'buy_order': [self.done_order[i] for i in range(7)],
            'seller': [self.users[i] for i in [0, 0, 2, 0, 0, 3, 0]],
            'buyer': [self.users[i] for i in [1, 2, 0, 2, 3, 0, 3]],
            'is_seller_maker': [False for _ in range(7)],
            'matched_amount': [Decimal(i) for i in
                               ['0.002', '0.0002', '0.0001', '0.0001', '0.0001', '0.001', '0.0001']],
            'matched_price': [Decimal(i) for i in ['610_000_000_0', '610_000_000_0', '17_049.48', '17_049.48',
                                                   '610_000_000_0', '17_049.48', '17_049.48']],
            'created_at': [-10 for _ in range(7)],
            'sell_fee_amount': [Decimal(i) for i in ['10_000_0', '1_000_0', '0.00255742', '0.00009985', '10_000_0',
                                                     '0.00009985', '0.00255742']],
            'buy_fee_amount': [Decimal(i) for i in ['0.000001', '0.0000001', '0.00009985', '0.00255742', '0.000001',
                                                    '0.00255742', '0.00009985']]
        }
        self.order_matchings = self._make_order_matching(order_matching_data, self.date_time_now_ir)

        discount_data = {
            Discount.STATUS.inactive: {
                'times': 2,
                'currency': [Currencies.btc, None],
                'start_date': [-10, -8],
                'end_date': [10, 3, 6],
                'created_at': [-10, -8],
                'amount_rls': [5000, 5000],
                'budget': [2000000, 2000000],
                'budget_remain': [10000, 10000],
                'percent': [100, 60],
                'trade_types': [Order.TRADE_TYPES.spot],
            },
            Discount.STATUS.active: {
                'times': 7,
                'currency': [None, Currencies.btc, Currencies.usdt, Currencies.btc, Currencies.btc, Currencies.btc,
                             Currencies.usdt],
                'start_date': [-10, -6, -5, -4, -3, -2, -1],
                'end_date': [1, -2, -3, -1, 0, 5, 6],
                'created_at': [-11, -6, -5, -4, -3, -2, -1],
                'amount_rls': [200000] + [100000 for _ in range(6)],
                'budget': [100000000 for _ in range(7)],
                'budget_remain': [200000 for _ in range(6)] + [100000],
                'percent': [25] + [100 for _ in range(6)],
                'trade_types': [Order.TRADE_TYPES.spot, Order.TRADE_TYPES.margin],
            },
            Discount.STATUS.finished: {
                'times': 2,
                'currency': [Currencies.btc, None],
                'start_date': [-100, -50],
                'end_date': [0, 1],
                'created_at': [-100, -100],
                'amount_rls': [10000, 100000],
                'budget': [200000, 20000000],
                'budget_remain': [0, 100000],
                'percent': [100, 60],
                'trade_types': [Order.TRADE_TYPES.spot],
            }
        }
        self.discount = self._make_discount(discount_data, self.date_time_now_ir)

        self.user_discount_data = {
            'numbers': 11,
            'user': [self.users[i] for i in [0, 1, 0, 1, 2, 0, 1, 2, 3, 2, 3]],
            'discount': [self.discount[i] for i in [0, 10, 4, 4, 4, 6, 6, 6, 9, 7, 2]],
            'amount_rls': [self.discount[i].amount_rls for i in [0, 10, 4, 4, 4, 6, 6, 6, 9, 7, 2]],
            'activation_date': [-6, -5, -4, -3, -2, -1, -6, -5, -6, -5, -2],
            'end_date': [-2, -2, -3, -2, -2, 0, -1, -2, -2, 2, 10],
            'created_at': [-6, -5, -4, -3, -2, -1, -6, -5, -6, -5, -2]
        }
        self.user_discounts = self._make_user_discount(self.user_discount_data, self.date_time_now_ir)

        # For APIs
        self.client = Client(HTTP_USER_AGENT='Mozilla/5.0', HTTP_AUTHORIZATION='Token user201token')
        self.webengage_token = generate_key()
        Settings.set("webengage_journey_api_key", self.webengage_token)
        self.client_webengage = Client(REMOTE_ADDR="54.82.121.36", HTTP_AUTHORIZATION=f'Token {self.webengage_token}')

        # set webengage id
        webengage_ids = ['9a12a59c-2d5e-4e87-aed3-ad429cec5274', 'd3d5bead-2ffd-4f8d-b55f-3d5bee91c74a',
                         '45f90342-2138-451d-bea4-2560fe15843f', '383e65b7-afc4-4da1-921c-6a707e924cac',
                         '74bc3635-3fe0-49a5-9f3b-f198277708e6']
        for i, user in enumerate(self.users):
            user.webengage_cuid = uuid.UUID(webengage_ids[i])
            user.save(update_fields=['webengage_cuid'])
            user.refresh_from_db()

    def _make_user_discount(self, user_discount_data: Dict[str, List[Any]],
                            source_date: datetime) -> List[Type[UserDiscount]]:
        user_discount = []

        for i in range(user_discount_data['numbers']):
            user_discount.append(
                UserDiscount.objects.create(
                    user=user_discount_data['user'][i],
                    discount=user_discount_data['discount'][i],
                    amount_rls=user_discount_data['amount_rls'][i],
                    activation_date=source_date.date() + \
                                    datetime.timedelta(days=user_discount_data['activation_date'][i]),
                    end_date=source_date.date() + datetime.timedelta(days=user_discount_data['end_date'][i]),
                    created_at=source_date + datetime.timedelta(days=user_discount_data['created_at'][i]))
            )
        return user_discount

    def _make_order_matching(self, order_matching_data: Dict[str, List[Any]],
                             source_date: datetime) -> List[Type[OrderMatching]]:
        order_matching = []

        for i in range(order_matching_data['numbers']):
            order_matching.append(
                OrderMatching.objects.create(
                    market=order_matching_data['market'][i],
                    sell_order=order_matching_data['sell_order'][i],
                    buy_order=order_matching_data['buy_order'][i],
                    seller=order_matching_data['seller'][i],
                    buyer=order_matching_data['buyer'][i],
                    is_seller_maker=order_matching_data['is_seller_maker'][i],
                    matched_amount=order_matching_data['matched_amount'][i],
                    matched_price=order_matching_data['matched_price'][i],
                    created_at=source_date + datetime.timedelta(minutes=order_matching_data['created_at'][i]),
                    sell_fee_amount=order_matching_data['sell_fee_amount'][i],
                    buy_fee_amount=order_matching_data['buy_fee_amount'][i])
            )
        return order_matching

    def _make_discount(self, discount_data: Dict[int, Dict[str, Any]], source_date: datetime) -> List[Discount]:
        discounts: List[Discount] = []
        j = 0
        for status_type, data in discount_data.items():
            if 'times' in data:
                for i in range(data['times']):
                    discounts.append(
                        Discount.objects.create(
                            name='test' + str(j),
                            description='test' + str(j) + '...',
                            status=status_type,
                            webengage_campaign_id=uuid.uuid4(),
                            currency=data['currency'][i],
                            start_date=source_date.date() + datetime.timedelta(days=data['start_date'][i]),
                            end_date=source_date.date() + datetime.timedelta(days=data['end_date'][i]),
                            created_at=source_date + datetime.timedelta(days=data['created_at'][i]),
                            amount_rls=data['amount_rls'][i],
                            budget=data['budget'][i],
                            budget_remain=data['budget_remain'][i],
                            percent=data['percent'][i],
                            trade_types=data['trade_types'] if 'trade_types' in data else None,
                        )
                    )
                    j += 1

        return discounts

    @patch('django.utils.timezone.now')
    def test_discount_cron(self, mock_ir_now):
        dt = self.date_time_now_ir + datetime.timedelta(minutes=30)
        mock_ir_now.return_value = dt
        # check before executing cron functions
        # 1 --> check for calculate_user_discount
        query_wallet = Q(currency=Currencies.rls, user_id__in=[201, 202, 203, 204], type=Wallet.WALLET_TYPE.spot)

        for wallet in Wallet.objects.filter(query_wallet):
            assert wallet.balance == Decimal('0')
        assert Transaction.objects.all().count() == 0

        # 2 --> check check_finished_discount
        assert Discount.objects.filter(status=Discount.STATUS.active).count() == 7
        assert Discount.objects.filter(status=Discount.STATUS.finished).count() == 2

        # cron functions
        DiscountUpdateCron().run()

        # 1 --> check user wallet
        assert list(Wallet.objects.filter(query_wallet).order_by(
            'user_id').values_list('balance', flat=True)) == [100000, 6100, 2451, 1542]

        # 1 --> check user transactions
        query_trans = Q(tp=Transaction.TYPE.discount, ref_module=Transaction.REF_MODULES['DiscountDst'],
                        wallet_id__in=Wallet.objects.filter(query_wallet).values_list('id', flat=True))
        assert list(Transaction.objects.filter(query_trans).order_by('wallet__user_id') \
                    .values_list('amount', flat=True)) == [100000, 6100, 2451, 1542]
        query_trans = Q(tp=Transaction.TYPE.discount, ref_module=Transaction.REF_MODULES['DiscountDst'])
        assert Transaction.objects.filter(query_trans).count() == 4

        # 1 --> check system wallet and transactions
        assert Wallet.get_fee_collector_wallet(RIAL).balance == (TestDiscount.MAX_SYSTEM_FEE_WALLET - 110093)
        query_trans = Q(tp=Transaction.TYPE.discount, wallet_id=self.system_fee_wallet.id)
        assert Transaction.objects.filter(query_trans).count() == 4
        query_trans = Q(tp=Transaction.TYPE.discount)
        assert Transaction.objects.filter(query_trans).count() == 8

        # 1 --> check discount transaction log
        query_discount_trans = Q(user_discount_id__in=[self.user_discounts[i].id for i in [5, 6, 9, 10]])
        assert list(DiscountTransactionLog.objects.filter(query_discount_trans).order_by('user_discount__user_id') \
                    .values_list('amount', flat=True)) == [100000, 6100, 2451, 1542]

        # 1 --> check user_discount
        user_discount_query = Q(user_id__in=[201, 202, 203, 204], discount_id__in=[self.discount[i].id for i in [6, 7]])
        assert list(UserDiscount.objects.filter(user_discount_query).order_by('user_id', 'discount_id').values_list(
            'amount_rls', flat=True)) == [0, 0, 0, 97549]

        # 2 --> check number of active discounts
        assert Discount.objects.filter(status=Discount.STATUS.active).count() == 4
        assert Discount.objects.filter(status=Discount.STATUS.finished).count() == 5
        assert Discount.objects.filter(status=Discount.STATUS.finished,
                                       id__in=[self.discount[i].id for i in [3, 4, 5]]).count() == 3
        # 2 --> check user discount
        assert list(UserDiscount.objects.filter(discount_id__in=[self.discount[i].id for i in [3, 4, 5]]).values_list(
            'end_date', flat=True)) == [self.user_discounts[i].end_date for i in [2, 3, 4]]

        # 3 --> check budget_remain
        assert Discount.objects.get(id=self.discount[6].id).budget_remain == 393900
        assert Discount.objects.get(id=self.discount[9].id).budget_remain == 10000

    @patch('django.utils.timezone.now')
    def test_discount_apis(self, mock_ir_now):
        dt = self.date_time_now_ir + datetime.timedelta(minutes=30)
        mock_ir_now.return_value = dt
        # 1. check History
        response = self.client.post('/promotions/discount/discount-history', data={}).json()
        assert 'status' in response and response['status'] == 'ok'
        assert 'hasNext' in response and response['hasNext'] is False
        assert 'discounts' in response and len(response['discounts']) == 1
        assert [x['isActive'] for x in response['discounts']] == [False]

        # cron functions
        DiscountUpdateCron().run()

        # 2. get active user_discount
        response = self.client.get('/promotions/discount/active', data={}).json()
        assert 'status' in response and response['status'] == 'ok'
        assert (
            'discount' in response
            and response['discount']['remainAmount'] == '0'
            and response['discount']['tradeTypes'] == [1, 2]
        )

        user_wid_1 = self.users[0].get_webengage_id()
        user_wid_2 = self.users[1].get_webengage_id()
        discount_wid = self.discount[8].webengage_campaign_id

        UserDiscount.objects.filter(id=response['discount']['id']) \
            .update(end_date=self.date_time_now_ir - datetime.timedelta(days=1))

        # 3. create user_discount
        response = self.client_webengage.post('/promotions/discount/webengage/private_create',
                                              data={'userId': user_wid_1, 'discountId': discount_wid}).json()
        assert 'status' in response and response['status'] == 'ok'
        # exists user_discount
        response = self.client_webengage.post('/promotions/discount/webengage/private_create',
                                              data={'userId': user_wid_1, 'discountId': discount_wid}).json()

        assert 'status' in response and response['status'] == 'failed'
        # no budget_remain
        response = self.client_webengage.post('/promotions/discount/webengage/private_create',
                                              data={'userId': user_wid_2, 'discountId': discount_wid}).json()
        assert 'status' in response and response['status'] == 'failed'

        # 4. check user_discount
        response = self.client_webengage.post('/promotions/discount/webengage/private_check_user_discount',
                                              data={'userId': user_wid_1, 'discountId': discount_wid}).json()
        assert 'status' in response and response['status'] == 'failed'

        # deactive user discount
        # 1. check History
        response = self.client.post('/promotions/discount/discount-history', data={}).json()
        assert 'status' in response and response['status'] == 'ok'
        assert 'discounts' in response and len(response['discounts']) == 2
        assert [x['isActive'] for x in response['discounts']] == [False, False]

        # 2. get active user_discount
        response = self.client.get('/promotions/discount/active', data={}).json()
        assert 'status' in response and response['status'] == 'ok'
        assert 'discount' in response and response['discount']['remainAmount'] == '100000'

        # 5. get transaction list with user_discount
        user_discount_id = DiscountTransactionLog.objects.filter(
            user_discount__user_id=self.users[0].id).first().user_discount_id
        response = self.client.post('/promotions/discount/transactions-history',
                                    data={'userDiscountId': user_discount_id}).json()
        assert 'status' in response and response['status'] == 'ok'
        assert 'transactions' in response and len(response['transactions']) == 1

        response = self.client.post('/promotions/discount/transactions-history', data={'userDiscountId': -1}).json()
        assert 'status' in response and response['status'] == 'failed'

        # 6. check transaction
        response = self.client.get('/users/transactions-history', data={}).json()
        assert 'transactions' in response and len(response['transactions']) == 1
        assert Decimal(response['transactions'][0]['amount']) == 100000
        assert getattr(Transaction.TYPE, response['transactions'][0]['tp']) == Transaction.TYPE.discount

        # 7. check transaction details
        trans_log = DiscountTransactionLog.objects.filter(user_discount__user=self.users[0]).first()
        response = self.client.post('/promotions/discount/trades-history',
                                    data={'transactionLogId': trans_log.id}).json()
        assert 'trades' in response and len(response['trades']) == 7

        response = self.client.post('/promotions/discount/trades-history', data={'transactionLogId': -1}).json()
        assert 'status' in response and response['status'] == 'ok'
        assert 'trades' in response and len(response['trades']) == 0

        user_discount = get_active_user_discount(self.users[0].id, ir_today())
        user_discount.end_date = self.date_time_now_ir - datetime.timedelta(days=1)
        user_discount.save(update_fields=['end_date'])
        # 2.check user_discount
        response = self.client.get('/promotions/discount/active', data={}).json()
        assert 'status' in response and response['status'] == 'failed'
        assert 'message' in response and response['message'] == 'There is no active discount existed for this user.'

    def test_discount_task(self):
        # deactive user discount
        user_discount = get_active_user_discount(self.users[0].id, ir_today())
        user_discount.end_date = self.date_time_now_ir - datetime.timedelta(days=1)
        user_discount.save(update_fields=['end_date'])

        # active status
        discount = Discount.objects.create(
            name='test task',
            description='test tast...',
            status=Discount.STATUS.active,
            start_date=self.date_time_now_ir + datetime.timedelta(days=5),
            end_date=self.date_time_now_ir + datetime.timedelta(days=10),
            created_at=self.date_time_now_ir + datetime.timedelta(days=5),
            amount_rls=10000,
            budget=0,
            budget_remain=0,
            percent=100,
        )
        # add restriction to user
        UserRestriction.objects.create(user=self.users[4], restriction=UserRestriction.RESTRICTION.WithdrawRequestRial)

        # make UploadedFile
        uploaded_file = UploadedFile.objects.create(filename=uuid.uuid4(), user=self.users[3],
                                                    tp=UploadedFile.TYPES.discount)
        user_discount_batch_file = SimpleUploadedFile(name='user_discount_batch_data.csv', content=open(
            'tests/promotions/user_discount_batch_data.csv', 'rb').read(), content_type='text/csv')
        with open(uploaded_file.disk_path, 'wb+') as destination:
            for chunk in user_discount_batch_file.chunks():
                destination.write(chunk)
        self.addCleanup(os.remove, uploaded_file.disk_path)

        # make a UserDiscountBatch
        user_discount_batch = UserDiscountBatch.objects.create(file=uploaded_file, discount=discount)
        user_discount_batch_file.seek(0)
        task_create_user_discount(user_discount_batch.id,
                                  [l.decode().strip() for l in user_discount_batch_file.readlines()])
        user_discount_batch = UserDiscountBatch.objects.get(id=user_discount_batch.id)

        detail = json.loads(user_discount_batch.details)
        error_detail = {
            '111111': 'invalid_uuid_error',
            '383e65b7-afc4-4da1-921c-6a707e924cac': 'active_discount_exist_error',
            '74bc3635-3fe0-49a5-9f3b-f198277708e6': 'user_restriction_error',
            '07702f18-7108-4b5c-af90-54b520b2e968': 'webengage_id_error',
            '45f90342-2138-451d-bea4-2560fe15843f': 'discount_budget_limit',
            '9a12a59c-2d5e-4e87-aed3-ad429cec5274': 'discount_budget_limit',
            'd3d5bead-2ffd-4f8d-b55f-3d5bee91c74a': 'discount_budget_limit',
        }
        for key, err in detail.items():
            assert error_detail[key] == err

    @patch('django.utils.timezone.now')
    def test_not_enough_budget_in_system_wallet(self, mock_ir_now):
        dt = self.date_time_now_ir + datetime.timedelta(minutes=30)
        mock_ir_now.return_value = dt
        self.system_fee_wallet.balance = 0
        self.system_fee_wallet.save(update_fields=['balance'])
        self.system_fee_wallet.refresh_from_db()

        assert Transaction.objects.filter(wallet_id=self.system_fee_wallet.id).count() == 0

        with pytest.raises(AttributeError):
            # cron functions
            DiscountUpdateCron().run()

        assert Transaction.objects.filter(wallet_id=self.system_fee_wallet.id).count() == 0

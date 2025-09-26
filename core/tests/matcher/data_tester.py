import csv
import os
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.test import TestCase, override_settings
from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Market, Order, OrderMatching
from exchange.matcher.matcher import Matcher
from tests.base.utils import create_order


class DataTester(TestCase):

    data_path = os.path.join(settings.BASE_DIR, 'tests/matcher/data_tests/data_files')

    @override_settings(DISABLE_ORDER_PRICE_GUARD=True)
    @override_settings(ALLOW_SMALL_ORDERS=True)
    @transaction.atomic
    def run_test(self, test_category=None, test_name=None):
        test_category = test_category or self.test_category
        test_name = test_name or self.test_name
        print('Running matcher test', test_category, test_name)

        user1 = User.objects.get(pk=201)
        user2 = User.objects.get(pk=202)
        eth, rls = Currencies.eth, Currencies.rls
        market = Market.objects.get(src_currency=eth, dst_currency=rls)
        orders = {}
        try:
            for data_name, data_info in self.run_test_data(test_category, test_name).items():
                orders[data_name] = {'id': create_order(
                    user1 if data_info['user'] == 'user_201' else user2,
                    eth,
                    rls,
                    data_info['amount'],
                    data_info['price'],
                    data_info['sell'],
                    data_info['is_market']
                ).id}
        except Exception as error:
            print(f'{data_name}: {error}')
            raise error
        Matcher(market).do_matching_round()
        for order in orders:
            orders[order]['obj'] = Order.objects.get(pk=orders[order]['id'])
        try:
            validations = self.run_test_validations(test_category, test_name)
            for test, test_op in validations['order'].items():
                if test_op.get('op', 'Equal') == 'Equal':
                    real_value = getattr(orders[test_op['operands'][1]['obj']]['obj'], test_op['operands'][1]['attr'])
                    expected_value = test_op['operands'][2]['value']
                    self.assertEqual(real_value, expected_value, f'Failed: {test_op}')
            for test, test_detail in validations['order_matching'].items():
                order_matching = OrderMatching.objects.filter(
                    sell_order=orders[test_detail['sell_order']]['obj'],
                    buy_order=orders[test_detail['buy_order']]['obj'],
                ).first()
                if not order_matching:
                    raise AssertionError(
                        f'OrderMatching Not Exists;'
                        f'sell_order:{test_detail["sell_order"]}, buy_order:{test_detail["buy_order"]}'
                    )
                self.assertEqual(order_matching.is_seller_maker, eval(test_detail['is_seller_maker']))
                self.assertEqual(order_matching.matched_price, Decimal(test_detail['matched_price']))
                self.assertEqual(order_matching.matched_amount, Decimal(test_detail['matched_amount']))

        except AssertionError as error:
            print(f'*** {test_category}.{test_name}; {test}: {error} ***')
            raise error
        transaction.set_rollback(True)

    def run_test_data(self, test_category=None, test_name=None):
        data = {}
        try:
            with open(os.path.join(self.data_path, test_category, test_name, 'data/order.csv')) as file:
                orders = csv.reader(file)
                header = next(orders, [])
                for order in orders:
                    data[order[0]] = {
                        'user': order[1],
                        'price': Decimal(order[2]),
                        'amount': Decimal(order[3]),
                        'sell': eval(order[4]),
                        'is_market': eval(order[5]) if 'is_market' in header else False
                    }
        except FileNotFoundError:
            print(f'*** Test Data File Not Found ***')
        return data

    def run_test_validations(self, test_category=None, test_name=None):
        validations = {'order': {}, 'order_matching': {}}
        path = os.path.join(self.data_path, test_category, test_name, 'validations')
        if os.path.exists(f'{path}/order.csv'):
            with open(f'{path}/order.csv') as file:
                operations = csv.reader(file)
                header = next(operations, [])
                for operation in operations:
                    validations['order'][operation[0]] = {
                        'operation': operation[1],
                        'operands': {
                            1: {
                                'obj': operation[2],
                                'attr': operation[3]
                            },
                            2: {
                                'value': eval(operation[4])
                            }
                        }
                    }

        if os.path.exists(f'{path}/order_matching.csv'):
            with open(f'{path}/order_matching.csv') as file:
                order_matchings = csv.reader(file)
                header = next(order_matchings, [])
                for order_matching in order_matchings:
                    validations['order_matching'][order_matching[0]] = {
                        'sell_order': order_matching[1],
                        'buy_order': order_matching[2],
                        'is_seller_maker': order_matching[3],
                        'matched_price': order_matching[4],
                        'matched_amount': order_matching[5],
                    }

        return validations

import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase, override_settings

from exchange.accounts.models import User
from exchange.base.models import Currencies, Settings


class MarginCalculatorAPITest(APITestCase):

    pools: list

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.user.base_fee_usdt = Decimal('0.08')
        cls.user.save(update_fields=('base_fee_usdt',))
        Settings.set(f'position_fee_rate_{Currencies.btc}', Decimal('0.0005'))
        Settings.set(f'position_fee_rate_{Currencies.usdt}', Decimal('0.0005'))

    def _test_successful_calculator(self, mode: str, data: dict, expected_result: dict, use_auth: bool = False):
        headers = {'HTTP_AUTHORIZATION': f'Token {self.user.auth_token.key}'} if use_auth else {}
        response = self.client.post(f'/margin/calculator/{mode}', data, **headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.pop('status') == 'ok'
        assert data == expected_result

    def _test_unsuccessful_calculator(self, mode: str, data: dict, code: str):
        response = self.client.post(f'/margin/calculator/{mode}', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST if code == 'ParseError' else status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code

    def _test_successful_pnl_calculator(
        self,
        side: str,
        symbol: str,
        entry_price: str,
        exit_price: str,
        amount: str,
        result_pnl: str,
        result_pnl_percent: str,
        leverage: Optional[str] = None,
        extension_days: Optional[int] = None,
        use_auth: bool = False,
    ):
        data = {'side': side, 'symbol': symbol, 'entryPrice': entry_price, 'exitPrice': exit_price, 'amount': amount}
        if leverage:
            data['leverage'] = leverage
        if extension_days is not None:
            data['extensionDays'] = extension_days
        self._test_successful_calculator(
            mode='pnl',
            data=data,
            expected_result={'PNL': result_pnl, 'PNLPercent': result_pnl_percent},
            use_auth=use_auth,
        )

    def test_calculator_pnl_sell_close_at_same_price(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', exit_price='21300', amount='0.01')
        self._test_successful_pnl_calculator(**data, result_pnl='-0.55', result_pnl_percent='-0.3')
        self._test_successful_pnl_calculator(**data, result_pnl='-0.34', result_pnl_percent='-0.2', use_auth=True)
        User.objects.filter(pk=self.user.pk).update(base_fee_usdt=0)  # no trade fee
        self._test_successful_pnl_calculator(**data, result_pnl='0', result_pnl_percent='0', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='-0.55', result_pnl_percent='-0.3', extension_days=5)
        data['amount'] = '0.1'
        self._test_successful_pnl_calculator(**data, result_pnl='-5.54', result_pnl_percent='-0.3')

    def test_calculator_pnl_buy_close_at_same_price(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', exit_price='21200', amount='0.01')
        self._test_successful_pnl_calculator(**data, result_pnl='-0.55', result_pnl_percent='-0.5')
        self._test_successful_pnl_calculator(**data, result_pnl='-0.34', result_pnl_percent='-0.3', use_auth=True)
        User.objects.filter(pk=self.user.pk).update(base_fee_usdt=0)  # no trade fee
        self._test_successful_pnl_calculator(**data, result_pnl='0', result_pnl_percent='0', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='-0.55', result_pnl_percent='-0.5', extension_days=5)
        data['amount'] = '0.1'
        self._test_successful_pnl_calculator(**data, result_pnl='-5.51', result_pnl_percent='-0.5')

    def test_calculator_pnl_sell_close_at_better_price(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', exit_price='20700', amount='0.01')
        self._test_successful_pnl_calculator(**data, result_pnl='5.4', result_pnl_percent='2.5')
        self._test_successful_pnl_calculator(**data, result_pnl='5.61', result_pnl_percent='2.6', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='5.13', result_pnl_percent='2.4', extension_days=5)
        self._test_successful_pnl_calculator(**data, result_pnl='3.76', result_pnl_percent='1.8', extension_days=30)
        self._test_successful_pnl_calculator(
            **data, result_pnl='5.32', result_pnl_percent='2.5', extension_days=5, use_auth=True
        )
        data['amount'] = '0.1'
        self._test_successful_pnl_calculator(**data, result_pnl='53.99', result_pnl_percent='2.5')

    def test_calculator_pnl_buy_close_at_better_price(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', exit_price='21800', amount='0.01')
        self._test_successful_pnl_calculator(**data, result_pnl='5.38', result_pnl_percent='5.1')
        self._test_successful_pnl_calculator(**data, result_pnl='5.59', result_pnl_percent='5.3', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='5.11', result_pnl_percent='4.8', extension_days=5)
        self._test_successful_pnl_calculator(**data, result_pnl='3.75', result_pnl_percent='3.5', extension_days=30)
        self._test_successful_pnl_calculator(
            **data, result_pnl='5.31', result_pnl_percent='5', extension_days=5, use_auth=True
        )
        data['amount'] = '0.1'
        self._test_successful_pnl_calculator(**data, result_pnl='53.79', result_pnl_percent='5.1')

    def test_calculator_pnl_sell_close_at_worse_price(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', exit_price='22400', amount='0.01')
        self._test_successful_pnl_calculator(**data, result_pnl='-11.57', result_pnl_percent='-5.4')
        self._test_successful_pnl_calculator(**data, result_pnl='-11.35', result_pnl_percent='-5.3', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='-11.57', result_pnl_percent='-5.4', extension_days=10)
        data['amount'] = '0.1'
        self._test_successful_pnl_calculator(**data, result_pnl='-115.68', result_pnl_percent='-5.4')

    def test_calculator_pnl_buy_close_at_worse_price(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', exit_price='20100', amount='0.01')
        self._test_successful_pnl_calculator(**data, result_pnl='-11.52', result_pnl_percent='-10.9')
        self._test_successful_pnl_calculator(**data, result_pnl='-11.32', result_pnl_percent='-10.7', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='-11.52', result_pnl_percent='-10.9', extension_days=10)
        data['amount'] = '0.1'
        self._test_successful_pnl_calculator(**data, result_pnl='-115.22', result_pnl_percent='-10.9')

    def test_calculator_pnl_sell_leverage(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', exit_price='20700', amount='0.01', leverage='2')
        self._test_successful_pnl_calculator(**data, result_pnl='5.4', result_pnl_percent='5.1')
        self._test_successful_pnl_calculator(**data, result_pnl='5.61', result_pnl_percent='5.3', use_auth=True)
        self._test_successful_pnl_calculator(**data, result_pnl='5.13', result_pnl_percent='4.8', extension_days=5)
        data['leverage'] = '3'
        self._test_successful_pnl_calculator(**data, result_pnl='5.4', result_pnl_percent='7.6')
        data['leverage'] = '4'
        self._test_successful_pnl_calculator(**data, result_pnl='5.4', result_pnl_percent='10.1')
        data['leverage'] = '5'
        self._test_successful_pnl_calculator(**data, result_pnl='5.4', result_pnl_percent='12.7')

    def _test_successful_exit_price_calculator(
        self,
        side: str,
        symbol: str,
        entry_price: str,
        pnl_percent: int,
        result_exit_price: str,
        leverage: Optional[str] = None,
        extension_days: Optional[int] = None,
        use_auth: bool = False,
    ):
        data = {'side': side, 'symbol': symbol, 'entryPrice': entry_price, 'PNLPercent': pnl_percent}
        if leverage:
            data['leverage'] = leverage
        if extension_days is not None:
            data['extensionDays'] = extension_days
        self._test_successful_calculator(
            mode='exit-price', data=data, expected_result={'exitPrice': result_exit_price}, use_auth=use_auth,
        )

    def test_calculator_exit_price_sell_with_profit(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', pnl_percent=5)
        self._test_successful_exit_price_calculator(**data, result_exit_price='20170.3')
        self._test_successful_exit_price_calculator(**data, result_exit_price='20191.04', use_auth=True)
        self._test_successful_exit_price_calculator(**data, result_exit_price='20113.15', extension_days=5)
        self._test_successful_exit_price_calculator(**data, result_exit_price='19703.18', extension_days=30)
        data['pnl_percent'] = 50  # equal to 5% pnl on 30th day
        self._test_successful_exit_price_calculator(**data, result_exit_price='10501.07')
        data['pnl_percent'] = 100
        self._test_successful_exit_price_calculator(**data, result_exit_price='-242.53')
        User.objects.filter(pk=self.user.pk).update(base_fee_usdt=0)  # no trade fee
        self._test_successful_exit_price_calculator(**data, result_exit_price='-215.15', use_auth=True)

    def test_calculator_exit_price_buy_with_profit(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', pnl_percent=5)
        self._test_successful_exit_price_calculator(**data, result_exit_price='21791.98')
        self._test_successful_exit_price_calculator(**data, result_exit_price='21770.17', use_auth=True)
        self._test_successful_exit_price_calculator(**data, result_exit_price='21820.53', extension_days=5)
        self._test_successful_exit_price_calculator(**data, result_exit_price='22025.34', extension_days=30)
        data['pnl_percent'] = 50  # equal to 5% pnl on 30th day
        self._test_successful_exit_price_calculator(**data, result_exit_price='26622.71')
        data['pnl_percent'] = 100
        self._test_successful_exit_price_calculator(**data, result_exit_price='31990.19')
        User.objects.filter(pk=self.user.pk).update(base_fee_usdt=0)  # no trade fee
        self._test_successful_exit_price_calculator(**data, result_exit_price='31907.07', use_auth=True)

    def test_calculator_exit_price_sell_with_zero_profit(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', pnl_percent=0)
        self._test_successful_exit_price_calculator(**data, result_exit_price='21244.66')
        self._test_successful_exit_price_calculator(**data, result_exit_price='21265.93', use_auth=True)
        User.objects.filter(pk=self.user.pk).update(base_fee_usdt=0)  # no trade fee
        self._test_successful_exit_price_calculator(**data, result_exit_price='21300', use_auth=True)
        self._test_successful_exit_price_calculator(**data, result_exit_price='21244.66', extension_days=5)

    def test_calculator_exit_price_buy_with_zero_profit(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', pnl_percent=0)
        self._test_successful_exit_price_calculator(**data, result_exit_price='21255.23')
        self._test_successful_exit_price_calculator(**data, result_exit_price='21233.96', use_auth=True)
        User.objects.filter(pk=self.user.pk).update(base_fee_usdt=0)  # no trade fee
        self._test_successful_exit_price_calculator(**data, result_exit_price='21200', use_auth=True)
        self._test_successful_exit_price_calculator(**data, result_exit_price='21255.23', extension_days=5)

    def test_calculator_exit_price_sell_with_loss(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', pnl_percent=-5)
        self._test_successful_exit_price_calculator(**data, result_exit_price='22308.27')
        self._test_successful_exit_price_calculator(**data, result_exit_price='22330.08', use_auth=True)
        self._test_successful_exit_price_calculator(**data, result_exit_price='22308.27', extension_days=5)
        data['pnl_percent'] = -82  # near liquidation
        self._test_successful_exit_price_calculator(**data, result_exit_price='38687.95')
        self._test_successful_exit_price_calculator(**data, result_exit_price='38717.96', use_auth=True)

    def test_calculator_exit_price_buy_with_loss(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', pnl_percent=-5)
        self._test_successful_exit_price_calculator(**data, result_exit_price='20723.85')
        self._test_successful_exit_price_calculator(**data, result_exit_price='20703.11', use_auth=True)
        self._test_successful_exit_price_calculator(**data, result_exit_price='20723.85', extension_days=5)
        data['pnl_percent'] = -82  # near liquidation
        self._test_successful_exit_price_calculator(**data, result_exit_price='12540.58')
        self._test_successful_exit_price_calculator(**data, result_exit_price='12528.04', use_auth=True)

    def test_calculator_exit_price_sell_leverage(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', leverage='2')
        self._test_successful_exit_price_calculator(**data, pnl_percent=5, result_exit_price='20707.48')
        self._test_successful_exit_price_calculator(**data, pnl_percent=5, result_exit_price='20728.49', use_auth=True)
        self._test_successful_exit_price_calculator(
            **data, pnl_percent=5, result_exit_price='20678.9', extension_days=5
        )
        self._test_successful_exit_price_calculator(**data, pnl_percent=-5, result_exit_price='21776.46')
        data['leverage'] = '3'
        self._test_successful_exit_price_calculator(**data, pnl_percent=5, result_exit_price='20886.54')
        self._test_successful_exit_price_calculator(**data, pnl_percent=-5, result_exit_price='21599.19')
        data['leverage'] = '4'
        self._test_successful_exit_price_calculator(**data, pnl_percent=5, result_exit_price='20976.07')
        self._test_successful_exit_price_calculator(**data, pnl_percent=-5, result_exit_price='21510.56')
        data['leverage'] = '5'
        self._test_successful_exit_price_calculator(**data, pnl_percent=5, result_exit_price='21029.78')
        self._test_successful_exit_price_calculator(**data, pnl_percent=-5, result_exit_price='21457.38')

    def _test_successful_liquidation_price_calculator(
        self,
        side: str,
        symbol: str,
        entry_price: str,
        amount: str,
        result_liquidation_price: str,
        leverage: Optional[str] = None,
        added_collateral: Optional[str] = None,
        extension_days: Optional[int] = None,
        use_auth: bool = False,
    ):
        data = {'side': side, 'symbol': symbol, 'entryPrice': entry_price, 'amount': amount}
        if leverage:
            data['leverage'] = leverage
        if extension_days is not None:
            data['extensionDays'] = extension_days
        if added_collateral is not None:
            data['addedCollateral'] = added_collateral
        self._test_successful_calculator(
            mode='liquidation-price',
            data=data,
            expected_result={'liquidationPrice': result_liquidation_price},
            use_auth=use_auth,
        )

    def test_calculator_liquidation_price_sell_initial_collateral(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', amount='0.01')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='38651.79')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='38680.81', use_auth=True)
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='38597.31', extension_days=5
        )
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='38324.94', extension_days=30
        )
        data['amount'] = '0.1'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='38651.79')
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='38603.44', extension_days=5
        )

    def test_calculator_liquidation_price_buy_initial_collateral(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', amount='0.01')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='12736.56')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='12730.18', use_auth=True)
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='12796.64', extension_days=5
        )
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='13097.03', extension_days=30
        )
        data['amount'] = '0.1'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='12736.56')
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='12789.88', extension_days=5
        )

    def test_calculator_liquidation_price_sell_added_collateral(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', amount='0.01', added_collateral='50')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='43191.33')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='43222.63', use_auth=True)
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='42864.49', extension_days=30
        )
        data['added_collateral'] = '100'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='47730.88')

    def test_calculator_liquidation_price_buy_added_collateral(self):
        data = dict(side='buy', symbol='BTCUSDT', leverage=2, entry_price='21200', amount='0.01', added_collateral='50')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='7730.05')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='7726.18', use_auth=True)
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='8090.52', extension_days=30
        )
        data['added_collateral'] = '100'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='2723.54')

    def test_calculator_liquidation_price_sell_leverage(self):
        data = dict(side='sell', symbol='BTCUSDT', entry_price='21300', amount='0.01', leverage='2')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='28982.56')
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='29006.74', use_auth=True)
        self._test_successful_liquidation_price_calculator(
            **data, result_liquidation_price='28655.71', extension_days=30
        )
        data['leverage'] = '3'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='25759.48')
        data['leverage'] = '4'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='24147.94')
        data['leverage'] = '5'
        self._test_successful_liquidation_price_calculator(**data, result_liquidation_price='23181.02')

    def test_calculator_invalid_data(self):
        data = {
            'symbol': 'BTCUSDT',
            'entryPrice': '21300',
            'exitPrice': '21300',
            'amount': '0.01',
            'PNLPercent': -5,
            'extensionDays': 5,
            'addedCollateral': '50',
        }
        self._test_unsuccessful_calculator('pnl', {**data, 'symbol': 'rls-btc'}, 'InvalidSymbol')
        self._test_unsuccessful_calculator('exit-price', {**data, 'symbol': 'rls-btc'}, 'InvalidSymbol')
        self._test_unsuccessful_calculator('liquidation-price', {**data, 'symbol': ''}, 'InvalidSymbol')

        self._test_unsuccessful_calculator('pnl', {**data, 'side': 'both'}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'side': True}, 'ParseError')
        self._test_unsuccessful_calculator('liquidation-price', {**data, 'side': 1}, 'ParseError')

        self._test_unsuccessful_calculator('pnl', {**data, 'entryPrice': ''}, 'ParseError')
        self._test_unsuccessful_calculator('pnl', {**data, 'entryPrice': '-50'}, 'ParseError')
        self._test_unsuccessful_calculator('pnl', {**data, 'exitPrice': ''}, 'ParseError')
        self._test_unsuccessful_calculator('pnl', {**data, 'exitPrice': '-30'}, 'ParseError')
        self._test_unsuccessful_calculator('pnl', {**data, 'amount': ''}, 'ParseError')
        self._test_unsuccessful_calculator('pnl', {**data, 'amount': '-1E-4'}, 'ParseError')

        self._test_unsuccessful_calculator('exit-price', {**data, 'entryPrice': ''}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'entryPrice': '5A'}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'PNLPercent': ''}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'PNLPercent': 2.3}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'PNLPercent': -150}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'PNLPercent': 250}, 'ParseError')

        self._test_unsuccessful_calculator('liquidation-price', {**data, 'entryPrice': '40$'}, 'ParseError')
        self._test_unsuccessful_calculator('liquidation-price', {**data, 'amount': ''}, 'ParseError')
        self._test_unsuccessful_calculator('liquidation-price', {**data, 'amount': '-2.3'}, 'ParseError')
        self._test_unsuccessful_calculator('liquidation-price', {**data, 'addedCollateral': '-100'}, 'ParseError')

        self._test_unsuccessful_calculator('pnl', {**data, 'extensionDays': '50'}, 'ParseError')
        self._test_unsuccessful_calculator('exit-price', {**data, 'extensionDays': '-4'}, 'ParseError')
        self._test_unsuccessful_calculator('liquidation-price', {**data, 'extensionDays': '2.3'}, 'ParseError')

    def test_non_existing_calculator_mode(self):
        response = self.client.post('/margin/calculator/fee', {})
        assert response.status_code == status.HTTP_404_NOT_FOUND

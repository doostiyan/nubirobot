from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from tests.base.utils import create_trade


class TradesListTest(APITestCase):
    def setUp(self) -> None:
        self.list_url = '/market/trades/list'
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')

    @classmethod
    def setUpTestData(cls):
        cls.user1 = User.objects.get(pk=201)
        cls.user2 = User.objects.get(pk=202)
        conf = {'fee_rate': '0.003'}
        cls.trades = [
            create_trade(cls.user1, cls.user2, Currencies.bch, Currencies.usdt, amount='1.7', price='257.9', **conf),
            create_trade(cls.user2, cls.user1, Currencies.bch, Currencies.usdt, amount='3', price='515.8', **conf),
            create_trade(cls.user2, cls.user1, Currencies.btc, Currencies.usdt, amount='0.3', price='18000', **conf),
            create_trade(cls.user1, cls.user2, Currencies.btc, Currencies.usdt, amount='1', price='60000', **conf)
        ]

    def create_sample_xrp_usdt_trades(self):
        user1_trades = []
        for amount, price, side in [
            ('0.1', '1000', 'buy'),
            ('0.3', '1002', 'buy'),
            ('0.21', '1010', 'sell'),
            ('1.4', '993', 'buy'),
            ('2', '980', 'sell'),
            ('0.2', '1005', 'buy'),
        ]:
            if side == 'buy':
                buyer = self.user1
                seller = self.user2
            else:
                seller = self.user1
                buyer = self.user2
            user1_trades.append(create_trade(
                seller=seller,
                buyer=buyer,
                src_currency=Currencies.xrp,
                dst_currency=Currencies.usdt,
                amount=amount,
                price=price,
                fee_rate='0.003',
            ))
        user1_trades.reverse()
        return user1_trades

    def test_list_all_1(self):
        response = self.client.post('/market/trades/list', data={'srcCurrency': 'bch', 'dstCurrency': 'usdt'})
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        trades = data.get('trades')
        assert len(trades) == 2
        for trade in trades:
            assert trade['srcCurrency'] == 'BitcoinCash'
            assert trade['dstCurrency'] == 'Tether'
            assert trade['market'] == 'BCH-USDT'
        assert trades[0]['type'] == 'buy'
        assert trades[0]['total'] == '1547.4'
        assert trades[0]['fee'] == '0.009'
        assert trades[1]['type'] == 'sell'
        assert trades[1]['total'] == '438.43'
        assert trades[1]['fee'] == '1.31529'
        assert not data['hasNext']

        response = self.client.post('/market/trades/list', data={'srcCurrency': 'btc', 'dstCurrency': 'usdt'})
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        trades = data.get('trades')
        assert len(trades) == 2
        for trade in trades:
            assert trade['srcCurrency'] == 'Bitcoin'
            assert trade['dstCurrency'] == 'Tether'
            assert trade['market'] == 'BTC-USDT'
        assert trades[0]['type'] == 'sell'
        assert trades[0]['total'] == '60000'
        assert trades[0]['fee'] == '180'
        assert trades[1]['type'] == 'buy'
        assert trades[1]['total'] == '5400'
        assert trades[1]['fee'] == '0.0009'
        assert not data['hasNext']

        # check trade_order
        data = self.client.post('/market/trades/list', data={'srcCurrency': 'btc', 'dstCurrency': 'usdt',
                                    'tradeOrder': 'asc'}).json()
        assert data['status'] == 'ok'
        res = ['buy', 'sell']
        for i, trade in enumerate(data.get('trades')):
            assert trade['type'] == res[i]

    def test_list_all_2(self):
        # first page
        response = self.client.post(self.list_url)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['trades']) == 4

        # last page
        response = self.client.post(self.list_url, data={'page': 4, 'pageSize': 1})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is False
        assert len(result['trades']) == 1
        assert result['trades'][0]['id'] == self.trades[0].pk

        # out of index page
        response = self.client.post(self.list_url, data={'page': 2})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['trades']) == 0

        # page size
        response = self.client.post(self.list_url, data={'page': 2, 'pageSize': 2})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['trades']) == 2
        assert result['trades'][0]['id'] == self.trades[1].pk
        assert result['trades'][1]['id'] == self.trades[0].pk

    def test_list_all_checking_order_ids(self):
        trades = self.create_sample_xrp_usdt_trades()
        response = self.client.post('/market/trades/list', data={'srcCurrency': 'xrp', 'dstCurrency': 'usdt'})
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        fetched_trades = data.get('trades')
        assert len(fetched_trades) == 6
        for trade, fetched_trade in zip(trades, fetched_trades):
            assert trade.id == fetched_trade['id']
            order_id = trade.sell_order.id if trade.seller == self.user1 else trade.buy_order.id
            assert order_id == fetched_trade['orderId']

    def test_filter_by_from_id(self):
        trades = self.create_sample_xrp_usdt_trades()
        from_id = trades[-3].id
        trades = trades[:-2]
        response = self.client.post('/market/trades/list',
            data={'srcCurrency': 'xrp', 'dstCurrency': 'usdt', 'fromId': from_id})
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        fetched_trades = data.get('trades')
        assert len(fetched_trades) == 4
        for trade, fetched_trade in zip(trades, fetched_trades):
            assert trade.id == fetched_trade['id']

    def test_filter_by_market(self):
        response = self.client.post(self.list_url, data={'srcCurrency': 'btc', 'dstCurrency': 'usdt'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['trades']) == 2
        assert result['trades'][0]['id'] == self.trades[3].pk
        assert result['trades'][1]['id'] == self.trades[2].pk

    def test_filter_by_trade_type(self):
        response = self.client.post(self.list_url, data={'tradeType': 'sell'})
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['trades']) == 2
        assert result['trades'][0]['id'] == self.trades[3].pk
        assert result['trades'][1]['id'] == self.trades[0].pk
        assert result['trades'][1]['type'] == 'sell'

        response = self.client.post(self.list_url, data={'tradeType': 'buy'})
        assert response.status_code == 200
        result2 = response.json()
        assert result2['status'] == 'ok'
        assert len(result2['trades']) == 2
        assert result2['trades'][0]['id'] == self.trades[2].pk
        assert result2['trades'][1]['id'] == self.trades[1].pk
        assert result2['trades'][1]['type'] == 'buy'

    @override_settings(LOAD_LEVEL=4)
    def test_download_csv(self):
        response = self.client.post(f'{self.list_url}?download=true')
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert len(str(response.content).split(r'\n')) == 6


class RoundedDecimalFieldInPositionTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.trade = create_trade(self.user1, self.user2, amount=Decimal('0.01'), price=Decimal('2.7e9'))

    def test_sell_fee_amount_rounding(self):
        self.trade.sell_fee_amount = Decimal('12.12345678925')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.sell_fee_amount == Decimal('12.1234567892')
        self.trade.sell_fee_amount = Decimal('12.12345678915')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.sell_fee_amount == Decimal('12.1234567892')
        self.trade.sell_fee_amount = Decimal('12.12345678911')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.sell_fee_amount == Decimal('12.1234567891')
        self.trade.sell_fee_amount = Decimal('12.12345678916')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.sell_fee_amount == Decimal('12.1234567892')

    def test_buy_fee_amount_rounding(self):
        self.trade.buy_fee_amount = Decimal('12.12345678925')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.buy_fee_amount == Decimal('12.1234567892')
        self.trade.buy_fee_amount = Decimal('12.12345678915')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.buy_fee_amount == Decimal('12.1234567892')
        self.trade.buy_fee_amount = Decimal('12.12345678911')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.buy_fee_amount == Decimal('12.1234567891')
        self.trade.buy_fee_amount = Decimal('12.12345678916')
        self.trade.save()
        self.trade.refresh_from_db()
        assert self.trade.buy_fee_amount == Decimal('12.1234567892')

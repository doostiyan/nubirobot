from decimal import Decimal

from django.core.cache import cache
from django.test import Client, TestCase
from rest_framework import status

from exchange.accounts.models import User, Notification, UserSms
from exchange.base.serializers import serialize
from exchange.market.models import Market
from exchange.pricealert.models import PriceAlert


class PriceAlertModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)

    @staticmethod
    def get_market_with_value(symbol, value):
        market = Market.by_symbol(symbol)
        cache.set(f'market_{market.id}_last_price', value)
        return market

    def test_price_alert(self):
        market = Market.by_symbol('BTCUSDT')
        cache_key = 'market_{}_last_price'.format(market.id)
        alert = PriceAlert(
            user=self.user,
            market=market,
            tp=PriceAlert.TYPES.price,
            param_direction=True,
            param_value=Decimal('33900'),
            cooldown=-1,
        )
        assert alert.is_one_time
        cache.set(cache_key, Decimal('33880'))
        assert not alert.is_active()
        cache.set(cache_key, Decimal('33905.1'))
        assert alert.is_active()
        cache.set(cache_key, Decimal('33875'))
        assert not alert.is_active()
        # Test direction:'-'
        alert.param_value = Decimal('33500')
        alert.param_direction = False
        assert not alert.is_active()
        cache.set(cache_key, Decimal('33490'))
        assert alert.is_active()

    def test_price_alert_price_message_usdt(self):
        alert = PriceAlert(
            market=self.get_market_with_value('BTCUSDT', Decimal('33905.1')),
            tp=PriceAlert.TYPES.price,
            param_direction=True,
            param_value=Decimal('33900'),
        )
        assert alert.get_text() == 'قیمت در بازار BTCUSDT به بیش از 33900 رسید. قیمت فعلی: 33905.1'

    def test_price_alert_price_message_irt(self):
        alert = PriceAlert(
            market=self.get_market_with_value('BTCIRT', Decimal('33880')),
            tp=PriceAlert.TYPES.price,
            param_direction=False,
            param_value=Decimal('33900'),
        )
        assert alert.get_text() == 'قیمت در بازار BTCIRT به کمتر از 3390 رسید. قیمت فعلی: 3388'

    def test_price_alert_periodic_message_usdt(self):
        alert = PriceAlert(
            market=self.get_market_with_value('BTCUSDT', Decimal('33905.1')),
            tp=PriceAlert.TYPES.periodic,
        )
        assert alert.get_text() == 'قیمت در بازار BTCUSDT: 33905.1'

    def test_price_alert_periodic_message_irt(self):
        alert = PriceAlert(
            market=self.get_market_with_value('BTCIRT', Decimal('33880')),
            tp=PriceAlert.TYPES.periodic,
        )
        assert alert.get_text() == 'قیمت در بازار BTCIRT: 3388'

    def test_price_alert_send_onetime(self):
        market = self.get_market_with_value('BTCIRT', 2000)
        alert = PriceAlert.objects.create(
            user_id=201, market_id=market.id, tp=1, param_direction=True, param_value=1000, channel=1, cooldown=-1
        )
        alert.send_notification()
        assert alert.pk is None

    def test_price_alert_send_multi_time(self):
        market = self.get_market_with_value('BTCIRT', 2000)
        alert = PriceAlert.objects.create(
            user_id=201, market_id=market.id, tp=1, param_direction=True, param_value=1000, channel=1
        )
        alert.send_notification()
        assert alert.last_alert

    def test_price_alert_send_channel(self):
        market = self.get_market_with_value('BTCIRT', 2000)
        User.objects.filter(pk=201).update(mobile='09000000000')
        for channel in range(1, 8):
            alert = PriceAlert.objects.create(
                user_id=201, market_id=market.id, tp=1, param_direction=False, param_value=3000, channel=channel
            )
            alert.send_notification()
            sms = UserSms.objects.filter(user=alert.user, tp=UserSms.TYPES.price_alert, text=alert.get_text())
            assert sms.exists() == ('SMS' in alert.get_channel_display())
            notification = Notification.objects.filter(user=alert.user, message=alert.get_text())
            assert notification.exists() == ('Notif' in alert.get_channel_display())
            sms.delete() and notification.delete()


class PriceAlertViewTest(TestCase):
    url = '/v2/price-alerts'

    def setUp(self):
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    @staticmethod
    def get_channel(sms=False, email=False, notif=False):
        channels = [('sms', sms), ('email', email), ('notif', notif)]
        return '/'.join([k for k, v in channels if v])

    @staticmethod
    def assert_api_error(data, code):
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert data['message']

    def test_price_alert_api_unauthorized_access(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION='')
        data = response.json()
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert data['detail']

    def test_price_alert_list(self):
        for i in range(4):  # User alerts
            PriceAlert.objects.create(user_id=201, market_id=1, tp=1, param_direction=True, param_value=1000)
        for user_id in range(202, 205):  # Other users alert
            PriceAlert.objects.create(user_id=user_id, market_id=1, tp=1, param_direction=True, param_value=1000)
        response = self.client.get(self.url)
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['alerts']) == 4

    def test_price_alert_serialization(self):
        alert = PriceAlert.objects.create(
            user_id=201,
            market_id=Market.by_symbol('BTCIRT').id,
            tp=PriceAlert.TYPES.price,
            param_direction=True,
            param_value=1000,
            channel=getattr(PriceAlert.CHANNELS, self.get_channel(sms=True, email=True)),
            description='test',
        )
        response = self.client.get(self.url)
        data = response.json()
        assert data['status'] == 'ok'
        assert data['alerts']
        assert data['alerts'][0]['id'] == alert.id
        assert data['alerts'][0]['market'] == 'BTCIRT'
        assert data['alerts'][0]['type'] == 'Price'
        assert data['alerts'][0]['direction'] == '+'
        assert Decimal(data['alerts'][0]['price']) == 1000
        assert data['alerts'][0]['channel'] == 'SMS/Email'
        assert data['alerts'][0]['description'] == 'test'
        assert data['alerts'][0]['createdAt']

    def test_price_alert_form_invalid_market(self):
        response = self.client.post(self.url, {'market': 1})
        self.assert_api_error(response.json(), 'InvalidSymbol')

    def test_price_alert_form_invalid_tp(self):
        response = self.client.post(self.url, {'market': 'BTCIRT', 'tp': 1})
        self.assert_api_error(response.json(), 'ParseError')

    def test_price_alert_form_invalid_channel(self):
        response = self.client.post(self.url, {'market': 'BTCIRT', 'channel': 3})
        self.assert_api_error(response.json(), 'ParseError')

    def test_price_alert_form_blank_fields(self):
        response = self.client.post(self.url, {'market': 'BTCIRT'})
        self.assert_api_error(response.json(), 'ValidationError')

    def test_price_alert_creation(self):
        alert_data = {
            'market': 'BTCIRT',
            'tp': 'price',
            'direction': '-',
            'price': 50_000_0,
            'channel': self.get_channel(email=True, notif=True),
        }
        response = self.client.post(self.url, alert_data)
        data = response.json()
        assert data['status'] == 'ok'
        assert data['alert']
        assert data['alert']['market'] == 'BTCIRT'
        assert data['alert']['type'] == 'Price'
        assert data['alert']['direction'] == '-'
        assert data['alert']['price'] == '500000'
        assert data['alert']['channel'] == 'Email/Notif'
        assert data['alert']['description'] is None
        assert data['alert']['createdAt']
        assert not data['alert']['lastAlert']

    def test_price_alert_update(self):
        alert = PriceAlert.objects.create(
            user_id=201, market_id=1, tp=1, param_direction=True, param_value=1000, channel=1
        )
        alert_data = serialize(alert)
        assert alert_data['direction'] == '+'
        assert alert_data['description'] is None
        alert_data['direction'] = '-'
        alert_data['description'] = 'test'
        alert_data['pk'] = alert_data['id']
        alert_data['tp'] = alert_data['type'].lower()
        alert_data['channel'] = alert_data['channel'].lower()
        alert_data.pop('lastAlert')
        response = self.client.post(self.url, alert_data)
        data = response.json()
        assert data['status'] == 'ok'
        assert data['alert']
        assert data['alert']['id'] == alert.id
        assert data['alert']['direction'] == '-'
        assert data['alert']['description'] == 'test'

    def test_price_alert_update_not_owned_alarm(self):
        alert = PriceAlert.objects.create(
            user_id=202, market_id=1, tp=1, param_direction=True, param_value=1000, channel=1
        )
        alert_data = {
            'pk': alert.pk,
            'market': 'BTCIRT',
            'tp': 'price',
            'direction': '-',
            'price': 1000,
            'channel': self.get_channel(notif=True),
        }
        response = self.client.post(self.url, alert_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()['detail']

    def test_price_alert_update_not_existing_alarm(self):
        alert_data = {
            'pk': 100,
            'market': 'BTCIRT',
            'tp': 'price',
            'direction': '-',
            'price': 1000,
            'channel': self.get_channel(notif=True),
        }
        response = self.client.post(self.url, alert_data)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()['detail']

    def test_price_alert_delete_blank_items(self):
        response = self.client.delete(self.url)
        self.assert_api_error(response.json(), 'ValidationError')

    def test_price_alert_delete(self):
        for i in range(4):
            PriceAlert.objects.create(id=i, user_id=201, market_id=1, tp=1, param_direction=True, param_value=1000)
        response = self.client.delete(f'{self.url}?delete_item=1,3')
        data = response.json()
        assert data['status'] == 'ok'
        assert PriceAlert.objects.count() == 2
        assert not PriceAlert.objects.filter(pk__in=(1, 3)).exists()

    def test_price_alert_price_precision_error(self):
        alert_data = {
            'market': 'BTCIRT',
            'tp': 'price',
            'direction': '-',
            'price': 5.5555555555555558e17,
            'channel': self.get_channel(email=True, notif=True),
        }
        response = self.client.post(self.url, alert_data)
        self.assert_api_error(response.json(), 'ParseError')

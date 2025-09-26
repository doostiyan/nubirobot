import time
from unittest import mock

import requests
from django.test import TestCase

from exchange.xchange.marketmaker.client import Client


class MarketMakerClientTests(TestCase):
    @mock.patch.object(time, 'time', lambda: 1705776237.000)
    def test_sign_post_request_with_data(self):
        request = requests.Request(
            method=Client.Method.POST.value,
            url='https://test.test/url',
            json={
                'quoteId': 'qid_0001',
                'clientId': 'clid_00000001',
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'referenceCurrency': 'usdt',
                'side': 'buy',
                'referenceCurrencyAmount': 10,
            },
            headers=Client.HEADERS,
        )
        Client.API_SECRET = 'secret'
        session = requests.Session()
        signed_request = Client.sign(session, request)
        assert signed_request.headers['mm-sign'] == 'cisavRXYvHXd1SPdy9iT/Q10C8xLIzstuGbe+IrPhrk='
        assert signed_request.url == 'https://test.test/url?timestamp=1705776237000'

    @mock.patch.object(time, 'time', lambda: 1705776237.000)
    def test_sign_post_request_without_data(self):
        request = requests.Request(
            method=Client.Method.POST.value,
            url='https://test.test/url',
            json={},
            headers=Client.HEADERS,
        )
        Client.API_SECRET = 'secret'
        session = requests.Session()
        signed_request = Client.sign(session, request)
        assert signed_request.headers['mm-sign'] == '/T/9d3AApxdeGoG80ArpvgZBw7QySUPExAfJB9OrSwc='
        assert signed_request.url == 'https://test.test/url?timestamp=1705776237000'

    @mock.patch.object(time, 'time', lambda: 1705776237.000)
    def test_sign_get_request_with_query(self):
        request = requests.Request(
            method=Client.Method.GET.value,
            url='https://test.test/url?clientId=CLIENTID',
            json={},
            headers=Client.HEADERS,
        )
        Client.API_SECRET = 'secret'
        session = requests.Session()
        signed_request = Client.sign(session, request)
        assert signed_request.headers['mm-sign'] == 'TVgNLX17fypF4JFy10qDGhXItv39184bHUsp72Irygw='
        assert signed_request.url == 'https://test.test/url?clientId=CLIENTID&timestamp=1705776237000'

    @mock.patch.object(time, 'time', lambda: 1705776237.000)
    def test_sign_get_request_without_query(self):
        request = requests.Request(
            method=Client.Method.GET.value,
            url='https://test.test/url',
            json={},
            headers=Client.HEADERS,
        )
        Client.API_SECRET = 'secret'
        session = requests.Session()
        signed_request = Client.sign(session, request)
        assert signed_request.headers['mm-sign'] == '/T/9d3AApxdeGoG80ArpvgZBw7QySUPExAfJB9OrSwc='
        assert signed_request.url == 'https://test.test/url?timestamp=1705776237000'

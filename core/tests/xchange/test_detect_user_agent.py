from django.test import RequestFactory, TestCase

from exchange.xchange.helpers import detect_user_agent
from exchange.xchange.models import ExchangeTrade


class DetectUserAgentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rf = RequestFactory()

    def test_android_lite(self):
        req = self.rf.get('/', HTTP_USER_AGENT='Android/1.0', HTTP_X_APP_MODE='lite')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.android_lite

    def test_android_pro_case_insensitive(self):
        req = self.rf.get('/', HTTP_USER_AGENT='android/9', HTTP_X_APP_MODE='PRO')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.android_pro

    def test_android_default_when_no_mode(self):
        req = self.rf.get('/', HTTP_USER_AGENT='Android/11')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.android

    def test_iosapp(self):
        req = self.rf.get('/', HTTP_USER_AGENT='iOSApp/7.3')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.ios

    def test_api_clients(self):
        api_agents = ['python-requests', 'restsharp', 'guzzlehttp', 'python', 'axios']
        for agent in api_agents:
            with self.subTest(agent=agent):
                req = self.rf.get('/', HTTP_USER_AGENT=f'{agent}/2.0')
                assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.api

    def test_mozilla(self):
        req = self.rf.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.mozilla

    def test_firefox(self):
        req = self.rf.get(
            '/', HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0'
        )
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.firefox

    def test_opera(self):
        req = self.rf.get(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/99.0.4844.84 Safari/537.36 OPR/85.0.4341.18',
        )
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.opera

    def test_chrome(self):
        req = self.rf.get(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36',
        )
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.chrome

    def test_safari(self):
        req = self.rf.get(
            '/', HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
        )
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.safari

    def test_samsung_internet(self):
        req = self.rf.get(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 (Linux; Android 12; SAMSUNG SM-G991B) AppleWebKit/537.36 Chrome/103.0.5060.129 Mobile Safari/537.36 SamsungBrowser/19.0',
        )
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.samsung_internet

    def test_edge(self):
        req = self.rf.get(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0',
        )
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.edge

    def test_unknown_category(self):
        req = self.rf.get('/', HTTP_USER_AGENT='WeirdBrowser/0.1')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.unknown

    def test_no_user_agent_header(self):
        req = self.rf.get('/')
        assert detect_user_agent(req) == ExchangeTrade.USER_AGENT.unknown

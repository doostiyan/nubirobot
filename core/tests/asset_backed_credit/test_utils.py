from django.test import RequestFactory, TestCase

from exchange.asset_backed_credit.utils import extract_version, is_supported_version, is_user_agent_android


class TestUtils(TestCase):
    def test_is_supported_version(self):
        assert is_supported_version('1.0.0', min_version='1.0.0')
        assert is_supported_version('1.0.0', min_version='1.0.0', max_version='2.0.0')
        assert is_supported_version('7.0.3', max_version='7.0.3')

        assert not is_supported_version('7.0.4', max_version='7.0.3')
        assert not is_supported_version('4.5.6', min_version='4.5.7', max_version='7.8.9')

    def test_get_version_from_user_agent(self):
        assert extract_version('Android/7.0.3-testnet-dev') == '7.0.3'
        assert extract_version('Android/7.0.3-master') == '7.0.3'
        assert extract_version('Android/7.0.3') == '7.0.3'
        assert extract_version('Android/7.0.3-testnet') == '7.0.3'
        assert extract_version('Android/7.0.2 (SM-N986B)') == '7.0.2'

    def test_is_user_agent_android(self):
        factory = RequestFactory()

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Linux; Android 11)'
        assert not is_user_agent_android(request)

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7.0.3-testnet'
        assert is_user_agent_android(request)

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7.0.2 (SM-N986B)'
        assert is_user_agent_android(request)

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7.0.2 (SM-N986B)'
        assert is_user_agent_android(request, min_version='7.0.2')

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7.0.2 (SM-N986B)'
        assert not is_user_agent_android(request, min_version='7.0.3')

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7.0.2 (SM-N986B)'
        assert is_user_agent_android(request, max_version='7.0.2')

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7.0.2 (SM-N986B)'
        assert not is_user_agent_android(request, max_version='7.0.1')

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Android/7 (SM-N986B)'
        assert not is_user_agent_android(request, min_version='6.0.0')

        request = factory.get('/')
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Linux; Android 11)'
        assert not is_user_agent_android(request, min_version='7.0.0')

        request = factory.get('/')
        assert not is_user_agent_android(request)

        request = factory.get('/')
        request.META[
            'HTTP_USER_AGENT'
        ] = 'Mozilla/5.0 (Linux; Android 11; SM-A107F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/136.0.7103.60 Mobile Safari/537.36'
        assert not is_user_agent_android(request)

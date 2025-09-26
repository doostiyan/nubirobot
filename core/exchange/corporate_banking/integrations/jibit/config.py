from django.conf import settings

from exchange.base.models import Settings

JIBIT_ACCESS_TOKEN_SETTINGS_KEY = 'cobank_jibit_access_token'
JIBIT_REFRESH_TOKEN_SETTINGS_KEY = 'cobank_jibit_refresh_token'


def get_base_url():
    return (
        'https://wiremock-core-testnet.c62.darkube.app/jibit-cobank/{}'
        if settings.IS_TESTNET and Settings.get_value('cobank_qa_test_server', 'yes')
        else 'https://napi.jibit.ir/cobank/{}'
    )

from exchange.base.apimanager import APIManager


def test_api_manager():
    assert APIManager.get_cache_key('test', endpoint='a') == 'apicall_test_a'
    assert APIManager.get_calls_count('test', endpoint='a') == 0
    APIManager.log_call('test', endpoint='a')
    assert APIManager.get_calls_count('test', endpoint='a') == 1
    APIManager.log_call('test', endpoint='beta', n=10)
    assert APIManager.get_calls_count('test', endpoint='a') == 1
    assert APIManager.get_calls_count('test', endpoint='beta') == 10
    assert not APIManager.log_call('test', endpoint='beta', limit=10)
    assert APIManager.get_calls_count('test', endpoint='beta') == 10
    assert APIManager.log_call('test', endpoint='beta', limit=20)
    assert APIManager.get_calls_count('test', endpoint='beta') == 11
    APIManager.reset_calls_count('test', endpoint='beta')
    assert APIManager.get_calls_count('test', endpoint='beta') == 0

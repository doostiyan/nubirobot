import pytest


@pytest.fixture
def tx_hash():
    return '779f2698c3af0ec141d1257c76dfc9a0b21d3098b35e0fa4bbaead30001566ed'


@pytest.fixture
def block_head_mock_response():
    return {'blocks': 879337, 'chain': 'main', 'headers': 879337}


@pytest.fixture
def tx_details_mock_response_tx_hash_1():
    return {'blockNumber': 879307, 'fee': 1115,
            'hash': '779f2698c3af0ec141d1257c76dfc9a0b21d3098b35e0fa4bbaead30001566ed',
            'inputs': [
                {'coin': {'address': '1M3Tiu6PLrHkHmyEux8rkXB3bWS1mY6sXR', 'coinbase': False,
                          'height': 879306,
                          'type': None, 'value': 108000}
                 }], 'outputs': [
            {'address': 'bc1qzupzvgw5zsh4pzxj5zgytcftynqlklw4wn6422',
             'scriptPubKey': {'reqSigs': None, 'type': 'witness_v0_keyhash'}, 'value': 106104},
            {'address': '1AKArMmoZwBSE9QA2aKY3Uv2DjVTvd9JcP',
             'scriptPubKey': {'reqSigs': None, 'type': 'pubkeyhash'}, 'value': 781}],
            'time': 1736911668,
            'witnessHash': '779f2698c3af0ec141d1257c76dfc9a0b21d3098b35e0fa4bbaead30001566ed'}
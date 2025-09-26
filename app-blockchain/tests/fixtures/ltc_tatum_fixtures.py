import pytest


@pytest.fixture
def tx_hash():
    return 'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef'


@pytest.fixture
def tx_hash_aggregation():
    return '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026'


@pytest.fixture
def block_head_mock_response():
    return {'blocks': 2822029, 'chain': 'main', 'headers': 2822029}


@pytest.fixture
def tx_details_mock_response_tx_hash():
    return {'blockNumber': 2707106, 'fee': '0.000037',
            'hash': 'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
            'inputs': [
                {'coin': {'address': 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw', 'coinbase': False,
                          'height': 2707105, 'reqSigs': None,
                          'script': '76a914b96758481720ca64e02538df543b75880dabc44b88ac',
                          'type': None, 'value': '600.11160078'}, }], 'outputs': [
            {'address': 'MKJ3hKvF75dA47PyFceqK8P1jpsFqJzLYJ',
             'script': 'a9147cfd7e9a8fa7894e2e0fa04253a6dd96f7de053287',
             'scriptPubKey': {'reqSigs': 1, 'type': 'scripthash'}, 'value': '0.01390822'},
            {'address': 'ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju',
             'script': '001411cb684376102fa1542a4bd3474e5e4edb233fa7',
             'scriptPubKey': {'reqSigs': 1, 'type': 'witness_v0_keyhash'}, 'value': '0.02941137'},
            {'address': 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw',
             'script': '76a914b96758481720ca64e02538df543b75880dabc44b88ac',
             'scriptPubKey': {'reqSigs': 1, 'type': 'pubkeyhash'}, 'value': '600.06824419'}],
            'time': 1719010699}


@pytest.fixture
def tx_details_mock_response_tx_hash_aggregation():
    return {'blockNumber': 2707106, 'fee': '0.0000336',
            'hash': '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
            'inputs': [
                {'coin': {'address': 'MRnv1iF722SUsrFZxmZSg1Ey7Vhghy8Gz6', 'coinbase': False,
                          'height': 2707018, 'reqSigs': None,
                          'script': 'a914c443e60fdb7090820bfbd9934254468656f842cd87',
                          'type': None,
                          'value': '0.04944048'}}, {
                    'coin': {'address': 'MRSXyMETyqz1zrAvNjhHNsspDz1vGjZv6f',
                             'coinbase': False,
                             'height': 2706537, 'reqSigs': None,
                             'script': 'a914c0692e46f1320af7d0ccb205961c6e5a1a674d2287',
                             'type': None, 'value': '0.00059312'}}], 'outputs': [
            {'address': 'Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV',
             'script': '76a914b5050584153d964c70bb658d613638a65879c44888ac',
             'scriptPubKey': {'reqSigs': 1, 'type': 'pubkeyhash'}, 'value': '0.05'}],
            'time': 1719010699}
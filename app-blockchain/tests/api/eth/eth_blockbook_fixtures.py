import pytest


@pytest.fixture
def token_tx_details_mock_response() -> dict:
    return {'txid': '0x7d621745c41f9a31649683da8a59f01005f48b77f841ef181ea6c49a5f9887a5', 'vin': [
        {'addresses': ['0xE718C3A32474C8448D529837a4cb31b89BC228ab']}], 'vout': [
        {'addresses': ['0xdAC17F958D2ee523a2206206994597C13D831ec7']}],
            'blockHash': '0xd2379883e02f316822576b31b952ac11d60d69199e774e8ae54dfba09c75cc91',
            'blockHeight': 20750598, 'confirmations': 3215, 'blockTime': 1726338059, 'value': '0',
            'fees': '156721351494046', 'tokenTransfers': [
            {'from': '0xE718C3A32474C8448D529837a4cb31b89BC228ab', 'to': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
             'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'value': '1067017891'}],
            'ethereumSpecific': {'status': 1,
                                 'data': '0xa9059cbb000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec7000000000000000000000000000000000000000000000000000000003f9966a3'}}


@pytest.fixture
def tx_details_mock_response() -> dict:
    return {'txid': '0x3a39bc06b8b44cb7f59f2291cafb8693c28c51e2aa4196856f46cc0eaafea287', 'vin': [
        {'addresses': ['0xd84B7DfA43dbEb0e2f4e9dAABb0326fa0dEd5e3b'], 'isAddress': True}], 'vout': [
        {'value': '41332982043186680', 'addresses': ['0x9C89C3289bcAf3c06318A2b03584956c7349C3f9'],
         'isAddress': True}], 'blockHash': '0xf2634a31942550c0d5f2befa4421adb471cd696f62d6b320b0227ee2b1e142f6',
            'blockHeight': 20753635, 'confirmations': 171, 'blockTime': 1726374635,
            'value': '41332982043186680', 'fees': '26556924765000',
            'ethereumSpecific': {'status': 1, 'data': '0x'}}


@pytest.fixture
def block_txs_mock_response() -> dict:
    return {'hash': '0xf02b43c8a3d86dcaa2e8cddf86aa3cf8b7d6cfddd5a7c1caaa85e7683168eb64',
            'height': 20753638, 'confirmations': 149, 'txs': [
            {'txid': '0x0874f11f3f5d2cdd9640e9812c2179d3666a0ff3e4338e571e28c6c59ee27f80',
             'vin': [{'addresses': ['0x9FC3da866e7DF3a1c57adE1a97c9f00a70f010c8'], 'isAddress': True}], 'vout': [
                {'value': '16519211539722639', 'addresses': ['0x388C818CA8B9251b393131C08a736A67ccB19297'],
                 'isAddress': True}], 'blockHash': '0xf02b43c8a3d86dcaa2e8cddf86aa3cf8b7d6cfddd5a7c1caaa85e7683168eb64',
             'blockHeight': 20753638, 'confirmations': 148, 'blockTime': 1726374671, 'value': '16519211539722639',
             'fees': '31178737683250',
             'ethereumSpecific': {'status': 1, 'data': '0x'}}]}


@pytest.fixture
def token_txs_mock_response() -> dict:
    return {'address': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'txs': 210715113,
            'transactions': [
                {'txid': '0x37719d67ffd9e9e114ebb70be9889d9806ab6e4e098a2b25d5b9cc3f758ae436', 'vin': [
                    {'addresses': ['0xC1aA38477597803dA4F26111a1656522E8c4C844'],
                     'isAddress': True}], 'vout': [
                    {'value': '0', 'addresses': ['0xdAC17F958D2ee523a2206206994597C13D831ec7'],
                     'isAddress': True}],
                 'blockHash': '0xdbc4abe205d29623d16e3ba0fbb6089f31a111054e32ae59b0ca1c480e7a9966',
                 'blockHeight': 20752954, 'confirmations': 721, 'blockTime': 1726366415,
                 'fees': '55074914411920', 'tokenTransfers': [
                    {'from': '0xC1aA38477597803dA4F26111a1656522E8c4C844',
                     'to': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
                     'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'value': '1500000000'}],
                 'ethereumSpecific': {'status': 1,
                                      'data': '0xa9059cbb000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec70000000000000000000000000000000000000000000000000000000059682f00'}}
            ], 'tokens': [
            {'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7', 'balance': '533256985377'}]}


@pytest.fixture
def address_txs_mock_response() -> dict:
    return {'address': '0xd84B7DfA43dbEb0e2f4e9dAABb0326fa0dEd5e3b',
            'transactions': [
                {'txid': '0x3a39bc06b8b44cb7f59f2291cafb8693c28c51e2aa4196856f46cc0eaafea287', 'vin': [
                    {'addresses': ['0xd84B7DfA43dbEb0e2f4e9dAABb0326fa0dEd5e3b'],
                     'isAddress': True}], 'vout': [
                    {'value': '41332982043186680',
                     'addresses': ['0x9C89C3289bcAf3c06318A2b03584956c7349C3f9'], 'isAddress': True}],
                 'blockHash': '0xf2634a31942550c0d5f2befa4421adb471cd696f62d6b320b0227ee2b1e142f6',
                 'blockHeight': 20753635, 'confirmations': 12, 'blockTime': 1726374635,
                 'value': '41332982043186680', 'fees': '26556924765000',
                 'ethereumSpecific': {'status': 1, 'data': '0x'}},
                {'txid': '0xc8eff0af35ac4cdb662cb134cc226c8f0f04af8598655cb01e3e52cd929b41a7', 'vin': [
                    {'addresses': ['0xd84B7DfA43dbEb0e2f4e9dAABb0326fa0dEd5e3b'],
                     'isAddress': True}], 'vout': [
                    {'value': '61929458768865380',
                     'addresses': ['0x3254D5CAD483E329c475d4e13bF2343C578eEa42'], 'isAddress': True}],
                 'blockHash': '0xd2c29e2f20ded269544119588898b5343b67a81c0e86ad6f82f93f6acdc59188',
                 'blockHeight': 20753599, 'confirmations': 48, 'blockTime': 1726374179,
                 'value': '61929458768865380', 'fees': '28871966781000',
                 'ethereumSpecific': {'status': 1, 'data': '0x', }}]}


@pytest.fixture
def address_txs_weth_tx_mock_response() -> dict:
    return {'address': '0xDb9f32E57A580889fa77De0BC294f81C486076e9',
            'transactions': [{'txid': '0x2e7fdd1119226e0375ab51a0995c6c2352d642620457e3d075834398fdd79c37', 'vin': [
                {'addresses': ['0x6b125E0Cd4feADA1aE0b9A8c8f902a5278E99A23'],
                 'isAddress': True}], 'vout': [
                {'addresses': ['0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'],
                 'isAddress': True}],
                              'blockHash': '0x69a15e4d5c7dadadc4186d21ac8dd91f9cd5df3481db142732b43e23854a96c4',
                              'blockHeight': 22466562, 'confirmations': 7301, 'blockTime': 1747045139, 'value': '0',
                              'fees': '345906707264766', 'tokenTransfers': [
                    {
                        'type': 'ERC20', 'standard': 'ERC20',
                        'from': '0x6b125E0Cd4feADA1aE0b9A8c8f902a5278E99A23',
                        'to': '0xDb9f32E57A580889fa77De0BC294f81C486076e9',
                        'contract': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
                        'value': '100000000000000000'}
                ],
                              'ethereumSpecific': {
                                  'status': 1,
                                  'data': '0xa9059cbb000000000000000000000000db9f32e57a580889fa77de0bc294f81c486076e90'
                                          '00000000000000000000000000000000000000000000000016345785d8a0000'}}]}


@pytest.fixture
def block_head_mock_response() -> dict:
    return {'blockbook': {'inSync': True, 'bestHeight': 20753638},
            'backend': {'difficulty': '0'}}

import pytest


@pytest.fixture
def block_head() -> dict:
    return {
        'items': [
            {'height': 36885294},
            {'height': 36885293},
            {'height': 36885292},
            {'height': 36885291},
            {'height': 36885290},
            {'height': 36885289},
            {'height': 36885288},
            {'height': 36885287},
            {'height': 36885286},
            {'height': 36885285},
            {'height': 36885284},
            {'height': 36885283},
            {'height': 36885282},
            {'height': 36885281},
            {'height': 36885280},
            {'height': 36885279},
            {'height': 36885278},
            {'height': 36885277},
            {'height': 36885276},
            {'height': 36885275},
            {'height': 36885274},
            {'height': 36885273},
            {'height': 36885272},
            {'height': 36885271},
            {'height': 36885270},
            {'height': 36885269},
            {'height': 36885268},
            {'height': 36885267},
            {'height': 36885266},
            {'height': 36885265},
            {'height': 36885264},
            {'height': 36885263},
            {'height': 36885262},
            {'height': 36885261},
            {'height': 36885260},
            {'height': 36885259},
            {'height': 36885258},
            {'height': 36885257},
            {'height': 36885256},
            {'height': 36885255},
            {'height': 36885254},
            {'height': 36885253},
            {'height': 36885252},
            {'height': 36885251},
            {'height': 36885250},
            {'height': 36885249},
            {'height': 36885248},
            {'height': 36885247},
            {'height': 36885246},
            {'height': 36885245},
        ],
    }


@pytest.fixture
def block_addresses() -> dict:
    return {
        36655532: {
            "items": [
                {
                    'timestamp': '2025-01-27T08:12:28.000000Z',
                    'fee': {'value': '6062800000000000'},
                    'transaction_types': ['contract_call'],
                    'status': 'ok',
                    'confirmations': 225239,
                    'exchange_rate': None,
                    'to': {'hash': '0x2cA6571Daa15ce734Bbd0Bf27D5C9D16787fc33f'},
                    'result': 'success',
                    'hash': '0x032ddcc8c83af3c6cd38f6c4708a86b79c069db3390fc852c94793ac8a773600',
                    'from': {'hash': '0x82f4789515D514138E647653cBC1F73feA0B0945'},
                    'block_number': 36655532,
                    'raw_input': '0x9d00c9fd64000d7c0f00e8cdfbe4419507017f38b73b70e8',
                    'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '12344062500000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x2cA6571Daa15ce734Bbd0Bf27D5C9D16787fc33f',

                 },
                 'result': 'success',
                 'hash': '0xa95b3e471cdfb971cdf53529d2442c1a4fcf5447e6de7d064c4767173c6c8005',
                 'from': {
                     'hash': '0xA941989652AD057cC4155b7A11145f8629b4B9cF',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x833bf6c000000000000000000000000000000000000000',
                 'value': '0'
                 },
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '1050000000000000'},
                 'transaction_types': ['coin_transfer'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x1e429358DB3949c20fd49a0212F5CEc7a731a500',

                 },
                 'result': 'success',
                 'hash': '0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553',
                 'from': {
                     'hash': '0x3727cfCBD85390Bb11B3fF421878123AdB866be8',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x',
                 'value': '187197483771850000000000'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '1367010000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x2cA6571Daa15ce734Bbd0Bf27D5C9D16787fc33f',

                 },
                 'result': 'success',
                 'hash': '0xd2a513c47e9985bcd8507f0c593c51b9aca9fefc7f6c3e68725320730c4aa9ab',
                 'from': {
                     'hash': '0x486aC9352F2001d1f43B9c02622Aa26099b86609',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x9d00c9fd64000d7c0f00ec76684d5a5805e85beeeda5de0e42d8cf17',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '1367010000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x2cA6571Daa15ce734Bbd0Bf27D5C9D16787fc33f',

                 },
                 'result': 'success',
                 'hash': '0x229be970f85a1c52d63907d8551a235f715ef652d19d707afff32ee9b05d8563',
                 'from': {
                     'hash': '0x6b5aA7e68FEe9b1829D8939182855F743F946C3C',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x9d00c9fd64000d7c0f00ec2c1b7f7f5a2858e48b9e8',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '6559575000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                 },
                 'result': 'success',
                 'hash': '0x29b76b1c2a5559a8a7c2ffab7fa4de2b48885b9ac52e10829275d31c9bd04c78',
                 'from': {
                     'hash': '0xF3Ab7061F6c2b630C85e29eBFe762E0259333333',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x0dbe671f',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '1658425000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0xD6D433DE0fCeA8693C7dE4a1a8c0C0401931aDc8',

                 },
                 'result': 'success',
                 'hash': '0xe333bec5e4448a9c450e5260c3d712f6acd72d0e51acbd5624cd6c218d447a3d',
                 'from': {
                     'hash': '0x4Cf46A2bD39133C8cA1E41bd4548EB3A07000000',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x7577109d00000000000000000000000000000000000',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '583725000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'error',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                 },
                 'result': 'execution reverted',
                 'hash': '0xefde56b34f2181fe22f9a8ecefee31e79076ddbb772c3dcd64f30b048d05bbaf',
                 'from': {
                     'hash': '0x71C43C8653dc879e69D1C80757AFdB4Ff5555555',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x0dbe671f',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '5221650000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x3501dfc6Cb9C3923D705edab64ee5377dfAA28Bb',

                 },
                 'result': 'success',
                 'hash': '0xe28ed59892687bfbd42a3845005dfeff2ff2d47bbab631453e08ff6a83691c4d',
                 'from': {
                     'hash': '0xE642d3fd3Db84e193237eC9468acAc5974e0abf9',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x7577109d0000000000000000000000000000',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '583725000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'error',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                 },
                 'result': 'execution reverted',
                 'hash': '0x8e5593cc6bba214770ce2358a603b8318377b705e4ee0a6e2c217f3270ef897e',
                 'from': {
                     'hash': '0xE2Cbb26fB6EBb050191aaa040b75959Fe6888888',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x0dbe671f',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '1658425000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0xD6D433DE0fCeA8693C7dE4a1a8c0C0401931aDc8',

                 },
                 'result': 'success',
                 'hash': '0x580a2c9f96d1862d2bd4d9eb43b7d8a49a8008ffbd0ce4b5513f01c0a6842944',
                 'from': {
                     'hash': '0x488887d02591DBb334867F04e560D83150111111',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x7577109d000000000000000000000000000000',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '5221650000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x3501dfc6Cb9C3923D705edab64ee5377dfAA28Bb',

                 },
                 'result': 'success',
                 'hash': '0x5b6304551b27044416f6883317acf4ffb661677c27792ac3d21e75de2b84371a',
                 'from': {
                     'hash': '0x45B0A38BA66387A6B729afc88cbbB4a90288c044',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x7577109d0000000000000000000000000000',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '7801125000000000'},
                 'transaction_types': ['contract_call',
                                       'token_transfer'],
                 'status': 'ok',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0xC8f55c5aA2C752eE285Bd872855C749f4ee6239B',

                 },
                 'result': 'success',
                 'hash': '0xcd65d6222491aaf68664c15dad797d3af61bdd89d87ba40131fd3b55452c855e',
                 'from': {
                     'hash': '0xe2Ec688D7B2C88185E89d7C32230E5a9D16611Bd',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x8e33aba5000000000000000000000000e2ec688d',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '583725000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'error',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                 },
                 'result': 'execution reverted',
                 'hash': '0x68fa9f180e4db12ccf903c37928ecb0b4b3148e028b77d131552cb32cad93933',
                 'from': {
                     'hash': '0x7Ac6d25FD5E437cB7c57Aee77aC2d0A6Cb85936C',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x0dbe671f',
                 'value': '0'},
                {'timestamp': '2025-01-27T08:12:28.000000Z',
                 'fee': {'type': 'actual',
                         'value': '583725000000000'},
                 'transaction_types': ['contract_call'],
                 'status': 'error',
                 'confirmations': 225239,
                 'exchange_rate': None,
                 'to': {
                     'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                 },
                 'result': 'execution reverted',
                 'hash': '0x3219c2551fe28168e9bae3dea7700a54125f5bb5a3360eff1222e89fb17a3528',
                 'from': {
                     'hash': '0xF3B713D68e4f8Eb8E717753bb1e3c3c994111111',

                 },
                 'block_number': 36655532,
                 'raw_input': '0x0dbe671f',
                 'value': '0'}]
            ,
        },
        36655533: {
            'items': [{'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '13427812500000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'ok',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0x2cA6571Daa15ce734Bbd0Bf27D5C9D16787fc33f',

                       },
                       'result': 'success',
                       'hash': '0x8e1e7671389f3ab9452941f9d9899abf5416758aed17b13ba812a539c4de25a3',
                       'from': {
                           'hash': '0x94Fa877f03AA7cDeA7681dF7cd07E136B2608604',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x833bf6c000000000000000000000000',
                       'value': '0'},
                      {'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '11446687500000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'ok',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0x2cA6571Daa15ce734Bbd0Bf27D5C9D16787fc33f',

                       },
                       'result': 'success',
                       'hash': '0x3a71a1240a5d791459bc3d96d50210ee4702a32ab204d5db28046b3dcc265a45',
                       'from': {
                           'hash': '0xDA2636b373C2Ce00cbE54ccc238C9a73A6df2f7B',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x833bf6c000000000000000000000000000000000',
                       'value': '0'},
                      {'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '6559575000000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'ok',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                       },
                       'result': 'success',
                       'hash': '0x099e9e989649f2e57310f5ff30eee9922898e51151c688697a4812605d027a92',
                       'from': {
                           'hash': '0x1967F7997982fA30E478423bb456FA0ED6222222',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x0dbe671f',
                       'value': '0'},
                      {'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '1658425000000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'ok',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0xD6D433DE0fCeA8693C7dE4a1a8c0C0401931aDc8',

                       },
                       'result': 'success',
                       'hash': '0x92576c46233054a178b72735a650d032dab6490fbe3e3c9d79f3a87bf1fe47b4',
                       'from': {
                           'hash': '0x937cB0b5AaBf09252F56376f73ad893b98666666',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x7577109d0000000000000000000000000',
                       'value': '0'},
                      {'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '5221650000000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'ok',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0x3501dfc6Cb9C3923D705edab64ee5377dfAA28Bb',

                       },
                       'result': 'success',
                       'hash': '0x85b230b8d8ce5a623b37d4aaf3e0060d2e55f059fc50b95fc959b2502d716fc6',
                       'from': {
                           'hash': '0x04d582F0E3340a9c73BAf0AFE86989dc2036397b',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x7577109d000000000000000000000000000',
                       'value': '0'},
                      {'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '583725000000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'error',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                       },
                       'result': 'execution reverted',
                       'hash': '0xbdc28c821aa13eb03224410a344ff49d9f8052d60cf8bb79ad9af000a75c7ab7',
                       'from': {
                           'hash': '0xF3Ab7061F6c2b630C85e29eBFe762E0259333333',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x0dbe671f',
                       'value': '0'},
                      {'timestamp': '2025-01-27T08:12:31.000000Z',
                       'fee': {'type': 'actual',
                               'value': '583725000000000'},
                       'transaction_types': ['contract_call'],
                       'status': 'error',
                       'confirmations': 230482,
                       'exchange_rate': None,
                       'to': {
                           'hash': '0x4758878dD3ee11Afc8Ff96A329a4462A60508A9A',

                       },
                       'result': 'execution reverted',
                       'hash': '0x2e3782d054aacf8d8487ec0c00011e3132b57c28d8eea1b895821c645867afc8',
                       'from': {
                           'hash': '0x71C43C8653dc879e69D1C80757AFdB4Ff5555555',

                       },
                       'block_number': 36655533,
                       'raw_input': '0x0dbe671f',
                       'value': '0'}]
        }
    }


@pytest.fixture
def address_transactions() -> dict:
    return {
        "items": [
            {
                "timestamp": "2025-02-01T15:18:59.000000Z",
                "fee": {
                    "value": "1050000000000000"
                },
                "transaction_types": [
                    "coin_transfer"
                ],
                "status": "ok",
                "confirmations": 1301,
                "to": {
                    "hash": "0x1013c6e6923A2BaD089C2E509697F421ab2Fcf46",
                },
                "result": "success",
                "hash": "0x3ee7e779a5f9ac9bafa738a761944c2406d89ae0b51dccb9707cdab6737ccf1f",
                "from": {
                    "hash": "0x1e429358DB3949c20fd49a0212F5CEc7a731a500",
                },
                "block_number": 36892962,
                "raw_input": "0x",
                "value": "43350400000000000000",
            }
        ],
    }


@pytest.fixture
def transactions_details() -> dict:
    return {
        "0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553": {
            "timestamp": "2025-01-27T08:12:28.000000Z",
            "fee": {
                "value": "1050000000000000"
            },
            "transaction_types": [
                "coin_transfer"
            ],
            "status": "ok",
            "confirmations": 266280,
            "to": {
                "hash": "0x1e429358DB3949c20fd49a0212F5CEc7a731a500",
            },
            "result": "success",
            "hash": "0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553",
            "from": {
                "hash": "0x3727cfCBD85390Bb11B3fF421878123AdB866be8",
            },
            "block_number": 36655532,
            "raw_input": "0x",
            "value": "187197483771850000000000",
        }
    }


DATA_TYPES_MAPPER: dict = {
    'actions': list,
    'authorization_list': list,
    'base_fee_per_gas': str,
    'block_number': int,
    'confirmation_duration': list,
    'confirmations': int,
    'created_contract': type(None),
    'decoded_input': dict,
    'exchange_rate': type(None),
    'fee': dict,
    'from': dict,
    'gas_limit': str,
    'gas_price': str,
    'gas_used': str,
    'has_error_in_internal_transactions': bool,
    'hash': str,
    'max_fee_per_gas': str,
    'max_priority_fee_per_gas': str,
    'method': str,
    'nonce': int,
    'position': int,
    'priority_fee': str,
    'raw_input': str,
    'result': str,
    'revert_reason': type(None),
    'status': str,
    'timestamp': str,
    'to': dict,
    'token_transfers': type(None),
    'token_transfers_overflow': type(None),
    'transaction_tag': type(None),
    'transaction_types': list,
    'tx_burnt_fee': str,
    'type': int,
    'value': str
}

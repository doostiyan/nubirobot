import pytest
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.sol.bitquery_sol import BitQuerySolApi
from exchange.blockchain.api.sol.sol_explorer_interface import SolExplorerInterface
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestBitQuerySolApiCalls(TestCase):
    api = BitQuerySolApi
    block_heights = [(215481260, 215481265)]

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert isinstance(get_block_head_response, dict)
        assert {'data'}.issubset(set(get_block_head_response.keys()))
        assert isinstance(get_block_head_response.get('data').get('solana').get('blocks')[0].get('height'), str)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for from_block, to_block in self.block_heights:
            get_block_txs_response = self.api.get_batch_block_txs(from_block, to_block)
            assert isinstance(get_block_txs_response, dict)
            assert isinstance(get_block_txs_response.get('data'), dict)
            assert isinstance(get_block_txs_response.get('data').get('solana'), dict)
            assert isinstance(get_block_txs_response.get('data').get('solana').get('transfers'), list)
            keys2check = [('transaction', dict), ('sender', dict), ('receiver', dict), ('currency', dict),
                          ('amount', float), ('instruction', dict)]
            keys2check2 = [('program', 'id', str), ('program', 'parsed', bool), ('externalProgram', 'id', str),
                           ('program', 'name', str), ('externalProgram', 'parsed', bool), ('action', 'name', str),
                           ('externalProgram', 'name', str), ('externalAction', 'name', str)]
            keys2check3 = [('sender', 'address', str), ('receiver', 'address', str), ('transaction', 'signature', str),
                           ('currency', 'symbol', str)]
            for tx in get_block_txs_response.get('data').get('solana').get('transfers'):
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                for key1, key2, value in keys2check2:
                    assert isinstance(tx.get('instruction').get(key1).get(key2), value)
                for key1, key2, value in keys2check3:
                    assert isinstance(tx.get(key1).get(key2), value)


class TestBitQuerySolFromExplorer(TestFromExplorer):
    api = BitQuerySolApi
    symbol = 'SOL'
    currencies = Currencies.sol
    explorerInterface = SolExplorerInterface

    @classmethod
    def test_get_block_txs(cls):
        APIS_CONF['SOL']['get_blocks_addresses'] = 'bitquery_sol_explorer_interface'
        block_txs_mock_responses = [
            {'data': {'solana': {'blocks': [{'height': '215532408'}]}}},
            {'data': {'solana': {'transfers': [
                {
                    'transaction': {
                        'signature': '2hzFA2GosGptDyKnwUSXRZTHC1XnPR1ufTemsQJQLxsMqQkvbSs'
                                     'Q4TWJn3xSxmNEEBuvggPSE8pouuHawMA1fxm',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'action': {'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'externalAction': {'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': '34rjofDpCG5MUkDLpmW1ZxCjrLPHZpDrV5ejC4jjGXvMYGJvTuPH'
                                     'vZaT1r4QkDsSqseVU3Fxyz1TP6jVbQpVutyi',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {
                        'address': 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {'externalProgram': {
                        'id': '11111111111111111111111111111111',
                        'parsed': True,
                        'name': 'system'},
                        'action': {'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'externalAction': {'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': '37o6NW4zAFSLbjd9cH6Px65sQ9bfkkQ1aYhX25jnzRgLvxJjYsJhempH'
                                     'MRc44Uc1Q53HqfSkfuAmZmcpFRGVjKDR',
                        'success': True, 'error': ''
                    },
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49'},
                    'currency': {'symbol': 'SOL'}, 'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True, 'name': 'system'
                        },
                        'action': {'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'externalAction': {'name': 'transfer'}}},
                {
                    'transaction': {
                        'signature': '3Re5eVCQ39qX7LaikEGEtkWwA15e47dwJ2ufw6JcJnw'
                                     'DL7Bcymy4W81nuLKBfFWsSZkZ6BS19WZxtZxQJrDAbKFt',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'action': {
                            'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'externalAction': {
                            'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': '4QyzsQBPD4cS3EsRiR5WsBRDHt1Y8YunNh5HGYZEXSCJzaSk'
                                     '5B3VsjYfdRQ9yYgCSmB7mRoHo6n213qxHR977VWo',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'action': {'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'externalAction': {'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': '4TaEkLUNLYavV5FZumHzNsQVSeHg3NFh8hmpQcXphnXo485g5rNYFa'
                                     'xbm96La9osTiuZKh8q5q8AUjBEPTrXcgzp',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'action': {
                            'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'externalAction': {
                            'name': 'transfer'}}},
                {
                    'transaction': {
                        'signature': '4pBAQ7Lp4yF7RKJbWg1bw8bnYJ65UyK2BPXc2EKMHryT2LMzRJn'
                                     'tk813yjHvdok8KVYCveNBdiU2yruyDBvGcjTw',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'action': {'name': 'transfer'},
                        'program': {'id': '11111111111111111111111111111111', 'parsed': True,
                                    'name': 'system'},
                        'externalAction': {'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': '5FVphpscGNDB8A3totKMafMwxWAXKoect3yJGh5AStDNTrRqXqL1Gr'
                                     'R7J2fh3m2MXxQnBy9FxppaAHgwrFzNvDh9',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'action': {
                            'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'externalAction': {
                            'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': 'LVFPUKnHNm817FRjZXdCVZk1AAAHRVMX2ERyhBV16Eft9u8fLf'
                                     'vuhqo6g7UwXYbQuZn4oNobXXctNCv9uSptbfM',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'action': {'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'
                        },
                        'externalAction': {'name': 'transfer'}
                    }
                },
                {
                    'transaction': {
                        'signature': 'Z71KLUykUxCEznVjNN8uD4cuqMsjXQgfs3mvHHxNyssGB1yb'
                                     'nwWC2xEierDvYBPXZ7JC4fkhn4h5zxrTE4n3Vbk',
                        'success': True, 'error': ''},
                    'block': {'height': 215532408},
                    'sender': {
                        'address': '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
                    'receiver': {'address': 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49'},
                    'currency': {'symbol': 'SOL'},
                    'amount': 5e-03,
                    'instruction': {
                        'externalProgram': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'action': {
                            'name': 'transfer'},
                        'program': {
                            'id': '11111111111111111111111111111111',
                            'parsed': True,
                            'name': 'system'},
                        'externalAction': {'name': 'transfer'}
                    }
                }]}}}
        ]
        expected_txs_addresses = {
            'input_addresses': {'9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa'},
            'output_addresses': {'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY',
                                 'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49'},
        }
        expected_txs_info = {
            'outgoing_txs': {
                '9bPRsbBTnL4Lm5yPQ9bcSbcri7byVhVS8JewgwGW17wa': {
                    Currencies.sol: [
                        {
                            'contract_address': None,
                            'tx_hash': '2hzFA2GosGptDyKnwUSXRZTHC1XnPR1ufTemsQJQLxsMqQ'
                                       'kvbSsQ4TWJn3xSxmNEEBuvggPSE8pouuHawMA1fxm',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '34rjofDpCG5MUkDLpmW1ZxCjrLPHZpDrV5ejC4jjGXvMYGJvTu'
                                       'PHvZaT1r4QkDsSqseVU3Fxyz1TP6jVbQpVutyi',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '37o6NW4zAFSLbjd9cH6Px65sQ9bfkkQ1aYhX25jnzRgLvxJ'
                                       'jYsJhempHMRc44Uc1Q53HqfSkfuAmZmcpFRGVjKDR',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '3Re5eVCQ39qX7LaikEGEtkWwA15e47dwJ2ufw6JcJnwDL7B'
                                       'cymy4W81nuLKBfFWsSZkZ6BS19WZxtZxQJrDAbKFt',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '4QyzsQBPD4cS3EsRiR5WsBRDHt1Y8YunNh5HGYZEXSCJzaSk5'
                                       'B3VsjYfdRQ9yYgCSmB7mRoHo6n213qxHR977VWo',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '4TaEkLUNLYavV5FZumHzNsQVSeHg3NFh8hmpQcXphnXo485g5'
                                       'rNYFaxbm96La9osTiuZKh8q5q8AUjBEPTrXcgzp',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '4pBAQ7Lp4yF7RKJbWg1bw8bnYJ65UyK2BPXc2EKMHryT2LMzRJ'
                                       'ntk813yjHvdok8KVYCveNBdiU2yruyDBvGcjTw',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '5FVphpscGNDB8A3totKMafMwxWAXKoect3yJGh5AStDNTrRqXqL1'
                                       'GrR7J2fh3m2MXxQnBy9FxppaAHgwrFzNvDh9',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': 'LVFPUKnHNm817FRjZXdCVZk1AAAHRVMX2ERyhBV16Eft9u8fLfvuh'
                                       'qo6g7UwXYbQuZn4oNobXXctNCv9uSptbfM',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': 'Z71KLUykUxCEznVjNN8uD4cuqMsjXQgfs3mvHHxNyssGB1ybnwWC2x'
                                       'EierDvYBPXZ7JC4fkhn4h5zxrTE4n3Vbk',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408
                        }
                    ]
                },
            },
            'incoming_txs': {
                'ADaUMid9yfUytqMBgopwjb2DTLSokTSzL1zt6iGPaS49': {
                    Currencies.sol: [
                        {
                            'contract_address': None,
                            'tx_hash': '2hzFA2GosGptDyKnwUSXRZTHC1XnPR1ufTemsQJQLxsM'
                                       'qQkvbSsQ4TWJn3xSxmNEEBuvggPSE8pouuHawMA1fxm',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '34rjofDpCG5MUkDLpmW1ZxCjrLPHZpDrV5ejC4jjGXvMY'
                                       'GJvTuPHvZaT1r4QkDsSqseVU3Fxyz1TP6jVbQpVutyi',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '37o6NW4zAFSLbjd9cH6Px65sQ9bfkkQ1aYhX25jnzRgLvxJ'
                                       'jYsJhempHMRc44Uc1Q53HqfSkfuAmZmcpFRGVjKDR',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': '5FVphpscGNDB8A3totKMafMwxWAXKoect3yJGh5AStDNTrR'
                                       'qXqL1GrR7J2fh3m2MXxQnBy9FxppaAHgwrFzNvDh9',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                        {
                            'contract_address': None,
                            'tx_hash': 'Z71KLUykUxCEznVjNN8uD4cuqMsjXQgfs3mvHHxNyssGB1yb'
                                       'nwWC2xEierDvYBPXZ7JC4fkhn4h5zxrTE4n3Vbk',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408},
                    ]
                },
                'Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY': {
                    Currencies.sol: [
                        {
                            'contract_address': None,
                            'tx_hash': '3Re5eVCQ39qX7LaikEGEtkWwA15e47dwJ2ufw6JcJnwDL7Bc'
                                       'ymy4W81nuLKBfFWsSZkZ6BS19WZxtZxQJrDAbKFt',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408
                        },
                        {
                            'contract_address': None,
                            'tx_hash': '4QyzsQBPD4cS3EsRiR5WsBRDHt1Y8YunNh5HGYZEXSCJzaSk'
                                       '5B3VsjYfdRQ9yYgCSmB7mRoHo6n213qxHR977VWo',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408
                        },
                        {
                            'contract_address': None,
                            'tx_hash': '4TaEkLUNLYavV5FZumHzNsQVSeHg3NFh8hmpQcXphnXo485g5r'
                                       'NYFaxbm96La9osTiuZKh8q5q8AUjBEPTrXcgzp',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408
                        },
                        {
                            'contract_address': None,
                            'tx_hash': '4pBAQ7Lp4yF7RKJbWg1bw8bnYJ65UyK2BPXc2EKMHryT2LMzRJn'
                                       'tk813yjHvdok8KVYCveNBdiU2yruyDBvGcjTw',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408
                        },
                        {
                            'contract_address': None,
                            'tx_hash': 'LVFPUKnHNm817FRjZXdCVZk1AAAHRVMX2ERyhBV16Eft9u8fLfvu'
                                       'hqo6g7UwXYbQuZn4oNobXXctNCv9uSptbfM',
                            'value': Decimal('0.005'), 'symbol': 'SOL', 'block_height': 215532408
                        }
                    ]
                },
            }
        }
        cls.get_block_txs(block_txs_mock_responses, expected_txs_addresses, expected_txs_info)

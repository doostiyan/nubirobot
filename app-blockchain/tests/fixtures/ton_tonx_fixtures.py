import pytest


@pytest.fixture
def tx_hash_successful_in_msg():
    return 'AnyidRmybKx3I3oYbvMEGHTrawIsMvklxBVk3dBGApU='


@pytest.fixture
def tx_hash_successful_out_msg():
    return 'lljO7TqOjNQxigdp/OWM/Tto8iZAhhTu/LpcukcqVkQ='


@pytest.fixture
def tx_details_tx_hash_in_msg_mock_response():
    return {'id': 1, 'jsonrpc': '2.0', 'result': [
        {'account': '0:A32D52CED80A23FE4FE90BA94593EF686DE03F9FBDAA069E642826A95234B982',
         'account_friendly': 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs',
         'block_ref': {'seqno': 49859297, 'shard': 'A000000000000000', 'workchain': 0},
         'description': {'aborted': False,
                         'action': {'action_list_hash': 'lqKW0iTyhcZ77pPDD4owkVfw2qNdxbh+QQt4YwoJz8c=',
                                    'msgs_created': 0, 'no_funds': False, 'result_code': 0, 'skipped_actions': 0,
                                    'spec_actions': 0, 'status_change': 'unchanged', 'success': True, 'tot_actions': 0,
                                    'valid': True}, 'bounce': {'type': ''},
                         'compute_ph': {'account_activated': False, 'exit_code': 0, 'mode': 0,
                                        'msg_state_used': False, 'success': True, 'type': 'vm', },
                         'credit_ph': {'credit': '1436400000', 'due_fees_collected': ''}, 'destroyed': False,
                         'storage_ph': {'status_change': 'unchanged'}, 'type': 'ord'},
         'end_status': 'active', 'hash': 'AnyidRmybKx3I3oYbvMEGHTrawIsMvklxBVk3dBGApU=',
         'in_msg': {'bounce': False, 'bounced': False, 'created_at': '1740225324', 'created_lt': '54245386000002',
                    'destination': '0:A32D52CED80A23FE4FE90BA94593EF686DE03F9FBDAA069E642826A95234B982',
                    'destination_friendly': 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs', 'fwd_fee': '266669',
                    'hash': 'gp+pXSHXd4wDcjljr65bhZlrAuEo2jlqx08PRaoK5GI=', 'ihr_disabled': True,
                    'message_content': {'body': 'te6cckEBAQEADwAAGgAAAAAxMjMxNDI5NzjSYp6p', 'decoded': None,
                                        'hash': '02NYdrMHu0jZZ1+zmsqomc8BGPf74BlAbKnkoxB5y9U='}, 'opcode': '0x00000000',
                    'source': '0:17846940D60757F9EA81E8295EA615237474B17CD8F432DF5F9C2C3CCE5D57B6',
                    'source_friendly': 'EQAXhGlA1gdX-eqB6ClephUjdHSxfNj0Mt9fnCw8zl1Xtp94', 'value': '1436400000'},
         'lt': 54245389000001, 'now': 1740225332, 'orig_status': 'active', 'out_msgs': {'out_msgs': None},
         'total_fees': 40002, 'trace_id': None}]}


@pytest.fixture
def tx_details_tx_hash_out_msg_mock_response():
    return {'id': 1, 'jsonrpc': '2.0', 'result': [
        {'account': '0:BE0E12287E3B91D1996ACC51C85E7A6EBBB5320CA7DF997CD1442AC3E880B961',
         'account_friendly': 'EQC-DhIofjuR0ZlqzFHIXnpuu7UyDKffmXzRRCrD6IC5Ycwx',
         'block_ref': {'seqno': 49918136, 'shard': 'A000000000000000', 'workchain': 0},
         'description': {'aborted': False,
                         'action': {'action_list_hash': 'p+RMP48wSuJa579YqziZgtrWA8Ttpe8fIMJHRehkO2U=',
                                    'msgs_created': 1, 'no_funds': False, 'result_code': 0, 'skipped_actions': 0,
                                    'spec_actions': 0, 'status_change': 'unchanged', 'success': True, 'tot_actions': 1,
                                    'valid': True}, 'bounce': {'type': ''},
                         'compute_ph': {'account_activated': False, 'exit_code': 0, 'mode': 0,
                                        'msg_state_used': False, 'success': True, 'type': 'vm', }, 'credit_first': True,
                         'credit_ph': {'credit': '12103379298761900287', 'due_fees_collected': ''}, 'destroyed': False,
                         'storage_ph': {'status_change': 'unchanged'}, 'type': 'ord'},
         'end_status': 'active', 'hash': 'lljO7TqOjNQxigdp/OWM/Tto8iZAhhTu/LpcukcqVkQ=',
         'in_msg': {'bounce': False, 'bounced': False, 'created_at': '0', 'created_lt': '0',
                    'destination': '0:BE0E12287E3B91D1996ACC51C85E7A6EBBB5320CA7DF997CD1442AC3E880B961',
                    'destination_friendly': 'EQC-DhIofjuR0ZlqzFHIXnpuu7UyDKffmXzRRCrD6IC5Ycwx', 'fwd_fee': '0',
                    'hash': 'G8kfmlgNckh0v+MJLFTKfQa2s3V5NROwtySHjkeeva4=', 'ihr_disabled': False, 'message_content': {
                 'body': 'te6cckEBAwEAmAABnA1YW5jmGc9ljrYZZb/aMRQZbB8Nas/R6vOMoX18p0qwEFUuGvKqExxYMSNsYeM42KxuM8bjrB8d2CIDQDtRaAEpqaMXZ7w5FgAAANgAAwEBamIAUZapZ2wFEf8n9IXUosn3tDbwH8/e1QNPMhQTVKkaXMEoCd88qAAAAAAAAAAAAAAAAAABAgAaAAAAADYyNjczNzI4MexRI3c=',
                 'decoded': None, 'hash': 'I2YF4lUTFJOneAtzRXRxONM1O0mORzlqfDA7VShSE2Y='}, 'opcode': '0x0d585b98',
                    'source': '', 'source_friendly': '', 'value': '0'}, 'lt': 54310931000001, 'now': 1740388489,
         'orig_status': 'active', 'out_msgs': {'out_msgs': [
            {'bounce': True, 'bounced': False, 'created_at': '1740388489', 'created_lt': '54310931000002',
             'destination': '0:A32D52CED80A23FE4FE90BA94593EF686DE03F9FBDAA069E642826A95234B982',
             'destination_friendly': 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs', 'fwd_fee': '321070',
             'hash': 'fLaOobNCF5bvdITXBR0HjKC9Ta2SfTK160eFhFjX96c=', 'ihr_disabled': True, 'ihr_fee': '0',
             'message_content': {'body': 'te6cckEBAQEADwAAGgAAAAA2MjY3MzcyODHtaMGJ', 'decoded': None,
                                 'hash': 'ivmsjMWnZXFNxbJcwoHNZCwEaMcz8nnKEWGzrcy0MxI='}, 'opcode': '0x00000000',
             'source': '0:BE0E12287E3B91D1996ACC51C85E7A6EBBB5320CA7DF997CD1442AC3E880B961',
             'source_friendly': 'EQC-DhIofjuR0ZlqzFHIXnpuu7UyDKffmXzRRCrD6IC5Ycwx', 'value': '5300000000'}]},
         'total_fees': 2174980, 'trace_id': None}]}

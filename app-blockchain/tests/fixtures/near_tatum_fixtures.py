import pytest


@pytest.fixture
def tx_hash_successful():
    return 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx'


@pytest.fixture
def tx_hash_failed():
    return '7EzTx2oZzwV1G7pynayHZKPJcTaN6Ra37UiaGEDD2QxE'


@pytest.fixture
def tx_details_tx_hash_successful_mock_response():
    return {'jsonrpc': '2.0', 'result': {'final_execution_status': 'FINAL',
                                         'status': {'SuccessValue': ''},
                                         'transaction': {
                                             'actions': [{'Transfer': {
                                                 'deposit': '999000000000000000000000'}}],
                                             'hash': 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx',
                                             'receiver_id': 'e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1',
                                             'signature': 'ed25519:5TQUqcwj5GLjAZxejX5NQNN8PyNpb73nsGxvRbcMrwERhrJMUGkcYTRsNdUwVP43ASR12U87aFm71nHN7on7t6LD',
                                             'signer_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'}},
            'id': 'dontcare'}


@pytest.fixture
def tx_details_tx_hash_failed_mock_response():
    return {'jsonrpc': '2.0', 'result': {'final_execution_status': 'FINAL',
                                         'status': {
                                             'SuccessValue': 'IjEwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAi'},
                                         'transaction': {'actions': [{'FunctionCall': {
                                             'args': 'eyJhbW91bnQiOiIxMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwIiwibXNnIjoie1wiZm9yY2VcIjowLFwiYWN0aW9uc1wiOlt7XCJwb29sX2lkXCI6NCxcInRva2VuX2luXCI6XCJ3cmFwLm5lYXJcIixcInRva2VuX291dFwiOlwiZGFjMTdmOTU4ZDJlZTUyM2EyMjA2MjA2OTk0NTk3YzEzZDgzMWVjNy5mYWN0b3J5LmJyaWRnZS5uZWFyXCIsXCJhbW91bnRfaW5cIjpcIjEwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDBcIixcIm1pbl9hbW91bnRfb3V0XCI6XCIwXCJ9LHtcInBvb2xfaWRcIjo0MTc5LFwidG9rZW5faW5cIjpcImRhYzE3Zjk1OGQyZWU1MjNhMjIwNjIwNjk5NDU5N2MxM2Q4MzFlYzcuZmFjdG9yeS5icmlkZ2UubmVhclwiLFwidG9rZW5fb3V0XCI6XCIxNzIwODYyOGY4NGY1ZDZhZDMzZjBkYTNiYmJlYjI3ZmZjYjM5OGVhYzUwMWEzMWJkNmFkMjAxMWUzNjEzM2ExXCIsXCJtaW5fYW1vdW50X291dFwiOlwiMTExNDA5OFwifV19IiwicmVjZWl2ZXJfaWQiOiJ2Mi5yZWYtZmluYW5jZS5uZWFyIn0=',
                                             'deposit': '1', 'gas': 180000000000000,
                                             'method_name': 'ft_transfer_call'}}],
                                             'hash': '7EzTx2oZzwV1G7pynayHZKPJcTaN6Ra37UiaGEDD2QxE',
                                             'nonce': 79540996000038,
                                             'public_key': 'ed25519:5xzZbJ17bcfaXrASdvxHFbwJAiiN4H2GnhC68rzeD43V',
                                             'receiver_id': 'wrap.near',
                                             'signature': 'ed25519:61vAPJtaXdF1J4EPajuGqDR4N6Kib4rcb6p2UtgmGmizsJSFnUf1jxVrq1TF7w4PqBJkGSYhqJk2akeKdEGPtvf4',
                                             'signer_id': '49c6c71594ad38c52e4292e1141b36064bf08d0fe2ddb13333a2fed13b9dec8c'},
                                         },
            'id': 'dontcare'}

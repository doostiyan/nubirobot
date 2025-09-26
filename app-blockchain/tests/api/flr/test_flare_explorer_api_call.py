import pytest
from exchange.blockchain.api.flr.flare_explorer import FlareExplorerApi
from exchange.blockchain.tests.fixtures.flare_fixtures import DATA_TYPES_MAPPER


def validate_general_response(response: dict) -> None:
    assert isinstance(response, dict)
    assert response.get('items')
    assert isinstance(response.get('items'), list)


# GET BLOCK HEAD API #

@pytest.mark.slow
def test__flareexplorer_flare__get_block_head__api_call__successful() -> None:
    get_block_head_response = FlareExplorerApi.get_block_head()

    validate_general_response(response=get_block_head_response)
    assert len(get_block_head_response.get('items')) == 50
    assert all([{'base_fee_per_gas', 'burnt_fees', 'burnt_fees_percentage', 'difficulty', 'gas_limit',
                 'gas_target_percentage', 'gas_used', 'gas_used_percentage', 'hash', 'height', 'miner',
                 'nonce', 'parent_hash', 'priority_fee', 'rewards', 'size', 'timestamp', 'total_difficulty',
                 'transaction_count', 'transaction_fees', 'type', 'uncles_hashes',
                 'withdrawals_count'}.issubset(block_data) for block_data in get_block_head_response.get('items')])
    assert isinstance(get_block_head_response.get('items')[0]['height'], int)


# GET BLOCK ADDRESSES API #

@pytest.mark.slow
def test__flareexplorer_flare__get_block_addresses__api_call__successful() -> None:
    get_block_addresses_response = FlareExplorerApi.get_block_txs(block_height=36655532)

    validate_general_response(response=get_block_addresses_response)
    assert len(get_block_addresses_response.get('items')) == 15
    assert all(
        [set(DATA_TYPES_MAPPER.keys()).issubset(set(block_data.keys()))
         for block_data in get_block_addresses_response.get('items')])
    for block_data in get_block_addresses_response.get('items'):
        for k, v in block_data.items():
            if DATA_TYPES_MAPPER.get(k) and v:
                assert isinstance(v, DATA_TYPES_MAPPER[k])


# GET TX DETAILS API #

@pytest.mark.slow
def test__sonicscan_sonic__get_transactions_details__api_call__successful() -> None:
    get_tx_details_response: dict = FlareExplorerApi.get_tx_details(
        tx_hash="0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553")

    assert isinstance(get_tx_details_response, dict)
    keys_to_value_types_mapper: dict = {
        'actions': list,
        'authorization_list': list,
        'base_fee_per_gas': str,
        'block_number': int,
        'confirmation_duration': list,
        'confirmations': int,
        'fee': dict,
        'transaction_types': list,
        'gas_limit': str,
        'status': str,
        'method': type(None),
        'type': int,
        'has_error_in_internal_transactions': bool,
        'exchange_rate': type(None),
        'to': dict,
        'tx_buntu_fee': type(None),
        'max_fee_per_gas': type(None),
        'result': str,
        'hash': str,
        'gas_price': str,
        'priority_fee': type(None),
        'from': dict,
        'token_transfers': list,
        'gas_used': str,
        'created_contract': type(None),
        'position': int,
        'nonce': int,
        'decoded_input': type(None),
        'token_transfers_overflow': bool,
        'raw_input': str,
        'value': str,
        'transaction_leg': type(None),
        'max_priority_fee_per_gas': type(None),
        'revert_reason': type(None),
    }
    for key, expected_type in keys_to_value_types_mapper.items():
        assert isinstance(get_tx_details_response.get(key), expected_type), f"Type mismatch for key: {key}"


# GET ADDRESS TXS API #

@pytest.mark.slow
def test__flareexplorer_flare__get_address_transactions__api_call__successful() -> None:
    get_address_txs_response = FlareExplorerApi.get_address_txs(address="0x1e429358DB3949c20fd49a0212F5CEc7a731a500")

    validate_general_response(response=get_address_txs_response)
    assert len(get_address_txs_response.get('items')) == 50
    required_fields: set = {
        'actions',
        'authorization_list',
        'base_fee_per_gas',
        'block_number',
        'confirmation_duration',
        'confirmations',
        'created_contract',
        'decoded_input',
        'exchange_rate',
        'fee',
        'from',
        'gas_limit',
        'gas_price',
        'gas_used',
        'has_error_in_internal_transactions',
        'hash',
        'max_fee_per_gas',
        'max_priority_fee_per_gas',
        'method',
        'nonce',
        'position',
        'priority_fee',
        'raw_input',
        'result',
        'revert_reason',
        'status',
        'timestamp',
        'to',
        'token_transfers',
        'token_transfers_overflow',
        'transaction_tag',
        'transaction_types',
        'tx_burnt_fee',
        'type',
        'value',
    }

    assert all(
        required_fields.issubset(x.keys()) and all(
            isinstance(x[key], DATA_TYPES_MAPPER[key]) if x[key] else True for key in required_fields)
        for x in get_address_txs_response['items']
    )

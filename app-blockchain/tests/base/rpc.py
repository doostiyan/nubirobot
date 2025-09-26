import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from pytz import utc

"""
This is a module for performing RPC common structured tests and for validating test results. 
Lots of providers with rpc api request and response have commons structure so we want to make the process reusable. 
"""


def validate_mocked_block_txs_response(data: dict, tx: dict, block_number: int, block_data: dict, symbol: str) -> None:
    assert data['tx_hash'] == tx['hash'], \
        f"Transaction hash does not match for outgoing_txs in block {block_number}"
    assert float(data['value']) * pow(10, 18) == float(
        int(block_data['result']['transactions'][0]['value'], 16)), \
        f"Value does not match for outgoing_txs in block {block_number}"
    assert data['contract_address'] is None, \
        f"Contract address does not match for outgoing_txs in block {block_number}"
    assert data['block_height'] == block_number, \
        f"Block height does not match for outgoing_txs in block {block_number}"
    assert data['symbol'] == symbol, \
        f"Symbol does not match for outgoing_txs in block {block_number}"


def validate_rpc_general_response(response) -> None:
    assert isinstance(response, dict)
    assert response.get('result')


def validate_rpc_block_head_response(block_head_response) -> None:
    validate_rpc_general_response(response=block_head_response)
    assert isinstance(block_head_response.get('result'), str)
    assert block_head_response.get('result').startswith('0x')


def validate_rpc_block_txs_response(block_txs_response, should_exist_keys: set) -> None:
    assert isinstance(block_txs_response, dict)
    assert block_txs_response.get('result')
    assert isinstance(block_txs_response.get('result'), dict)
    assert should_exist_keys.issubset(block_txs_response['result'].keys())
    assert all([isinstance(value, str) if key not in ["transactions", "uncles"] else isinstance(value, list)
                for key, value in block_txs_response['result'].items()])


def validate_rpc_tx_receipt_response(tx_receipt_response, should_exist_keys: set,
                                     nullable_keys: Optional[set] = None) -> None:
    if not nullable_keys:
        nullable_keys = set()
    validate_rpc_general_response(response=tx_receipt_response)
    assert isinstance(tx_receipt_response.get('result'), dict)
    assert should_exist_keys.issubset(tx_receipt_response['result'].keys())
    for key, value in tx_receipt_response['result'].items():
        if not value and key in nullable_keys:
            continue
        if key in ["logs"]:
            assert isinstance(value, list)
        else:
            assert isinstance(value, str)


def validate_rpc_tx_detail_response(tx_detail_response, expected_types: dict) -> None:
    validate_rpc_general_response(response=tx_detail_response)
    result = tx_detail_response.get('result')
    assert isinstance(result, dict)

    for value, expected_type in expected_types.items():
        assert isinstance(result[value], expected_type) or (result[value] is None and expected_type is Optional[None])


def validate_rpc_address_txs_response(address_txs_response, expected_types: dict) -> None:
    validate_rpc_general_response(response=address_txs_response)
    result = address_txs_response.get('result')
    assert isinstance(result, list)

    for tx in result:
        for value, expected_type in expected_types.items():
            assert isinstance(tx[value], expected_type) or (tx[value] is None and expected_type is Optional[None])


def do_mocked_block_head_response_test(api, explorer_interface_class, block_head) -> None:
    """
    Using common fixtures (defined in conftest.py file) we want to make general request to get provider
    block head using Api and ExplorerInterfaceClass passed for each provider
    """
    explorer_interface_obj = explorer_interface_class()
    explorer_interface_obj.block_head_apis = [api]
    explorer_interface_obj.block_txs_apis = [api]

    with patch.object(target=api, attribute='request', return_value=block_head):
        parsed_response = explorer_interface_obj.get_block_head()

        assert isinstance(parsed_response, int)
        assert parsed_response == 4646786


def do_mocked_block_txs_response_test(api, explorer_interface_class, block_addresses, symbol: str,
                                      currency: int) -> None:
    """
    Using common fixtures (defined in conftest.py file) we want to make general request to get provider
    block txs using Api and ExplorerInterfaceClass passed for each provider
    """
    explorer_interface_obj = explorer_interface_class()
    explorer_interface_obj.block_txs_apis = [api]

    def mock_request(*args, **kwargs) -> dict:
        hex_height = kwargs.get('height')
        return block_addresses.get(int(hex_height, 16))

    with patch.object(target=api, attribute='request', side_effect=mock_request):
        for block_number, block_data in block_addresses.items():
            txs_addresses, txs_info, latest_block_processed = explorer_interface_obj.get_latest_block(
                after_block_number=block_number - 1,  # inclusive after
                to_block_number=block_number,
                include_info=True,
                include_inputs=True,
            )

            expected_input_addresses = {block_data['result']['transactions'][0]['from']}
            expected_output_addresses = {block_data['result']['transactions'][0]['to']}
            assert txs_addresses['input_addresses'] == expected_input_addresses, \
                f"Input addresses do not match for block {block_number}"
            assert txs_addresses['output_addresses'] == expected_output_addresses, \
                f"Output addresses do not match for block {block_number}"

            tx = block_data['result']['transactions'][0]

            outgoing_key = block_data['result']['transactions'][0]['from']
            assert outgoing_key in txs_info['outgoing_txs'], \
                f"Outgoing key {outgoing_key} not found in txs_info['outgoing_txs']"
            validate_mocked_block_txs_response(
                data=txs_info['outgoing_txs'][outgoing_key][currency][0],
                tx=tx,
                block_number=block_number,
                block_data=block_data,
                symbol=symbol,
            )

            incoming_key = block_data['result']['transactions'][0]['to']
            assert incoming_key in txs_info['incoming_txs'], \
                f"Incoming key {incoming_key} not found in txs_info['incoming_txs']"
            incoming_data = txs_info['incoming_txs'][incoming_key][currency][0]
            validate_mocked_block_txs_response(
                data=incoming_data,
                tx=tx,
                block_number=block_number,
                block_data=block_data,
                symbol=symbol,
            )

            assert latest_block_processed == block_number


def do_tx_detail_test(explorer_interface_obj, symbol: str, currency: int) -> None:
    tx_hash: str = "0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83"
    tx_details: dict = explorer_interface_obj.get_tx_details(tx_hash=tx_hash)

    assert isinstance(tx_details, dict)
    assert tx_details['hash'] == tx_hash
    assert tx_details['success'] is True
    assert tx_details['block'] == 3700579
    assert tx_details['fees'] is None
    assert tx_details['date'] is None
    assert tx_details['memo'] is None
    assert tx_details['confirmations'] == 946207
    assert tx_details['raw'] is None
    assert tx_details['inputs'] == list()
    assert tx_details['outputs'] == list()
    assert isinstance(tx_details["transfers"], list)
    assert len(tx_details["transfers"]) == 1
    tx = tx_details["transfers"][0]
    assert tx.get("from") == '0xf310b07583a5515d25384a82df027124d54aaf26'
    assert tx.get("to") == '0x0b31836b57cb2f5af83f4eb6560cc1b4eb655123'
    assert tx.get("type") == 'MainCoin'
    assert tx.get("symbol") == symbol
    assert tx.get("currency") == currency
    assert tx.get("value") == Decimal('0.002072500000000000')
    assert tx.get("is_valid") is True
    assert tx.get("token") is None
    assert tx.get("memo") is None


def do_mocked_tx_detail_response_test(api, explorer_interface_class, block_head, transaction_receipt,
                                      transactions_details, symbol: str, currency: int) -> None:
    """
    Using common fixtures (defined in conftest.py file) we want to make general request to get provider tx detail using
    Api and ExplorerInterfaceClass passed for each provider
    """
    explorer_interface_obj = explorer_interface_class()
    explorer_interface_obj.tx_details_apis = [api]

    def mock_tx_detail_request(*args, **kwargs) -> dict:
        return transactions_details.get(args[0])

    def mock_tx_receipt_request(*args, **kwargs) -> dict:
        return transaction_receipt.get(args[0])

    with patch.object(target=api, attribute='get_tx_details', side_effect=mock_tx_detail_request):
        with patch.object(target=api, attribute='get_block_head', return_value=block_head):
            with patch.object(target=api, attribute='get_tx_receipt', side_effect=mock_tx_receipt_request):
                do_tx_detail_test(
                    explorer_interface_obj=explorer_interface_obj,
                    symbol=symbol,
                    currency=currency,
                )


def do_mocked_address_txs_response_test(api, explorer_interface_class, block_head, address_transactions,
                                        currency: int) -> None:
    """
    Using common fixtures (defined in conftest.py file) we want to make general request to get provider
    address txs using Api and ExplorerInterfaceClass passed for each provider
    """
    explorer_interface_obj = explorer_interface_class()
    explorer_interface_obj.address_txs_apis = [api]
    address: str = "0xf310b07583a5515d25384a82df027124d54aaf26"

    with patch.object(target=api, attribute='get_address_txs', return_value=address_transactions):
        with patch.object(target=api, attribute='get_block_head', return_value=block_head):
            address_txs = explorer_interface_obj.get_txs(address=address)

            assert isinstance(address_txs, list)
            assert len(address_txs) == 1

            output_data: dict = address_txs[0][currency]
            expected_data: dict = address_transactions['result'][0]

            assert int(float(output_data['amount']) * pow(10, 18)) == int(expected_data['value'])
            assert output_data['address'] == expected_data['from']
            assert output_data['block'] == int(expected_data['blockNumber'])
            assert output_data['confirmations'] == int(expected_data['confirmations'])
            assert output_data['date'] == datetime.datetime(year=2025, month=1, day=14, hour=2, minute=15, second=57,
                                                            tzinfo=utc)
            assert output_data['direction'] == "outgoing"
            assert output_data['from_address'] == expected_data['from']
            assert output_data['hash'] == expected_data['hash']
            assert output_data['memo'] is None
            assert output_data['raw'] is None
            assert output_data['to_address'] == expected_data['to']

from unittest.mock import patch

from exchange.base.parsers import parse_currency
from exchange.blockchain.api.sonic.sonic_explorer_interface import SonicExplorerInterface
from exchange.blockchain.api.sonic.sonic_publicnode import SonicPublicNodeWeb3API
from exchange.blockchain.models import Currencies
from exchange.blockchain.tests.base.rpc import do_tx_detail_test
from exchange.blockchain.tests.fixtures.publicnode_fixtures import (block_addresses, block_head,  # noqa: F401
                                                                    transactions_details, tx_receipt)

# GET BLOCK HEAD API #


def test__publicnode_sonic__get_block_head__from_explorer_interface__successful(block_head: int) -> None:  # noqa: F811
    api = SonicPublicNodeWeb3API
    sonic_explorer_interface = SonicExplorerInterface()
    sonic_explorer_interface.block_head_apis = [api]
    sonic_explorer_interface.block_txs_apis = [api]

    with patch.object(target=api, attribute='get_block_head', return_value=block_head):
        parsed_response = sonic_explorer_interface.get_block_head()

        assert isinstance(parsed_response, int)
        assert parsed_response == 4646786


# GET BLOCK ADDRESSES API #

def test__publicnode_sonic__get_multiple_block_addresses__from_explorer_interface__successful(
        block_addresses) -> None:  # noqa: F811
    api = SonicPublicNodeWeb3API
    sonic_explorer_interface = SonicExplorerInterface()
    sonic_explorer_interface.block_txs_apis = [api]

    def mock_request(*args, **kwargs) -> dict:
        return block_addresses.get(args[0])

    with patch.object(target=api, attribute='get_block_txs', side_effect=mock_request):
        for block_number, block_data in block_addresses.items():
            txs_addresses, txs_info, latest_block_processed = sonic_explorer_interface.get_latest_block(
                after_block_number=block_number - 1,  # inclusive after
                to_block_number=block_number,
                include_info=True,
                include_inputs=True,
            )

            block_tx = block_data['transactions'][0]

            expected_input_addresses = {block_tx['from']}
            expected_output_addresses = {block_tx['to']}
            assert txs_addresses['input_addresses'] == expected_input_addresses, \
                f"Input addresses do not match for block {block_number}"
            assert txs_addresses['output_addresses'] == expected_output_addresses, \
                f"Output addresses do not match for block {block_number}"

            validate_block_txs_data(
                tx_data=txs_info['outgoing_txs'][block_tx['from']][parse_currency('s')][0],
                expected_data=block_data["transactions"][0],
                block_number=block_number,
            )

            validate_block_txs_data(
                tx_data=txs_info['incoming_txs'][block_tx['to']][parse_currency('s')][0],
                expected_data=block_data["transactions"][0],
                block_number=block_number,
            )

            assert latest_block_processed == block_number


def validate_block_txs_data(tx_data: dict, expected_data: dict, block_number: int) -> None:
    assert tx_data['tx_hash'] == f"0x{expected_data['hash'].hex()}", \
        f"Transaction hash does not match for tx in block {block_number}"
    assert float(tx_data['value']) * pow(10, 18) == float(expected_data['value']), \
        f"Value does not match for tx in block {block_number}"
    assert tx_data['contract_address'] is None, \
        f"Contract address does not match for tx in block {block_number}"
    assert tx_data['block_height'] == block_number, \
        f"Block height does not match for tx in block {block_number}"
    assert tx_data['symbol'] == 'S', \
        f"Symbol does not match for tx in block {block_number}"


# GET TXs DETAILS API #

def test__publicnode_sonic__get_transactions_details__from_explorer_interface__successful(
        transactions_details: dict, block_head: dict, tx_receipt: dict) -> None:  # noqa: F811
    api = SonicPublicNodeWeb3API
    sonic_explorer_interface = SonicExplorerInterface()
    sonic_explorer_interface.tx_details_apis = [api]

    def mock_request(*args, **kwargs) -> dict:
        return transactions_details.get(args[0])

    with patch.object(target=api, attribute='get_tx_details', side_effect=mock_request):
        with patch.object(target=api, attribute='get_block_head', return_value=block_head):
            with patch.object(target=api, attribute='get_tx_receipt', return_value=tx_receipt):
                do_tx_detail_test(
                    explorer_interface_obj=sonic_explorer_interface,
                    symbol='S',
                    currency=Currencies.s,
                )

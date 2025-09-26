from decimal import Decimal
from unittest.mock import patch

from exchange.base.parsers import parse_currency, parse_iso_date
from exchange.blockchain.api.flr.flare_explorer import FlareExplorerApi
from exchange.blockchain.api.flr.flare_explorer_interface import FlareExplorerInterface
from exchange.blockchain.tests.fixtures.flare_fixtures import (address_transactions, block_addresses, block_head,
                                                               transactions_details)

# GET BLOCK HEAD API #


def test__flareexplorer_flare__get_block_head__from_explorer_interface__successful(block_head) -> None:  # noqa: F811
    api = FlareExplorerApi
    flare_explorer_interface = FlareExplorerInterface()
    flare_explorer_interface.block_head_apis = [api]
    flare_explorer_interface.block_txs_apis = [api]

    with patch.object(target=api, attribute='request', return_value=block_head):
        parsed_response = flare_explorer_interface.get_block_head()

        assert isinstance(parsed_response, int)
        assert parsed_response == 36885294


# GET BLOCK ADDRESSES API #

def test__flareexplorer_flare__get_multiple_block_addresses__from_explorer_interface__successful(
        block_addresses) -> None:  # noqa: F811
    api = FlareExplorerApi
    flare_explorer_interface = FlareExplorerInterface()
    flare_explorer_interface.block_txs_apis = [api]

    def mock_request(*args, **kwargs) -> dict:
        return block_addresses.get(kwargs.get('height'))

    with patch.object(target=api, attribute='request', side_effect=mock_request):
        for block_number, block_data in block_addresses.items():
            txs_addresses, txs_info, latest_block_processed = flare_explorer_interface.get_latest_block(
                after_block_number=block_number - 1,  # inclusive after block
                to_block_number=block_number,
                include_info=True,
                include_inputs=True,
            )

            if block_number == 36655532:
                assert txs_addresses['input_addresses'] == {'0x3727cfCBD85390Bb11B3fF421878123AdB866be8'}, \
                    f"Input addresses do not match for block {block_number}"
                assert txs_addresses['output_addresses'] == {'0x1e429358DB3949c20fd49a0212F5CEc7a731a500'}, \
                    f"Output addresses do not match for block {block_number}"

                tx = block_data['items'][2]
                outgoing_key = '0x3727cfCBD85390Bb11B3fF421878123AdB866be8'
                assert outgoing_key in txs_info['outgoing_txs'], \
                    f"Outgoing key {outgoing_key} not found in txs_info['outgoing_txs']"
                outgoing_data = txs_info['outgoing_txs'][outgoing_key][parse_currency('flr')][0]
                assert outgoing_data['tx_hash'] == tx['hash'], \
                    f"Transaction hash does not match for outgoing_txs in block {block_number}"
                assert str(int(outgoing_data['value'] * pow(10, 18))) == tx['value'], \
                    f"Value does not match for outgoing_txs in block {block_number}"
                assert outgoing_data['contract_address'] is None, \
                    f"Contract address does not match for outgoing_txs in block {block_number}"
                assert outgoing_data['block_height'] == block_number, \
                    f"Block height does not match for outgoing_txs in block {block_number}"
                assert outgoing_data['symbol'] == 'FLR', \
                    f"Symbol does not match for outgoing_txs in block {block_number}"

                incoming_key = '0x1e429358DB3949c20fd49a0212F5CEc7a731a500'
                assert incoming_key in txs_info['incoming_txs'], \
                    f"Incoming key {incoming_key} not found in txs_info['incoming_txs']"
                incoming_data = txs_info['incoming_txs'][incoming_key][parse_currency('flr')][0]
                assert incoming_data['tx_hash'] == tx['hash'], \
                    f"Transaction hash does not match for incoming_txs in block {block_number}"
                assert str(int(incoming_data['value'] * pow(10, 18))) == tx['value'], \
                    f"Value does not match for incoming_txs in block {block_number}"
                assert incoming_data['contract_address'] is None, \
                    f"Contract address does not match for incoming_txs in block {block_number}"
                assert incoming_data['block_height'] == block_number, \
                    f"Block height does not match for incoming_txs in block {block_number}"
                assert incoming_data['symbol'] == 'FLR', \
                    f"Symbol does not match for incoming_txs in block {block_number}"

            elif block_number == 36655533:
                assert txs_addresses['input_addresses'] == set()
                assert txs_addresses['output_addresses'] == set()
                assert len(txs_info['outgoing_txs']) == 0
                assert len(txs_info['incoming_txs']) == 0

            assert latest_block_processed == block_number


# GET TXs DETAILS API #

def test__sonicscan_sonic__get_transactions_details__from_explorer_interface__successful(
        transactions_details, block_head) -> None:  # noqa: F811
    api = FlareExplorerApi
    flare_explorer_interface = FlareExplorerInterface()
    flare_explorer_interface.tx_details_apis = [api]

    def mock_request(*args, **kwargs) -> dict:
        return transactions_details.get(kwargs.get('tx_hash'))

    with patch.object(target=api, attribute='request', side_effect=mock_request):
        with patch.object(target=api, attribute='get_block_head', return_value=block_head):
            tx_hash: str = "0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553"
            tx_details: dict = flare_explorer_interface.get_tx_details(tx_hash=tx_hash)

            assert isinstance(tx_details, dict), "tx_details is not a dictionary"

            assert tx_details[
                       "hash"] == "0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553", "Hash does not match"
            assert tx_details["success"] is True, "Success status does not match"
            assert tx_details["block"] == 36655532, "Block number does not match"
            assert tx_details["date"] == parse_iso_date(s="2025-01-27T08:12:28.000000Z"), "Date does not match"
            assert tx_details["fees"] == Decimal('0.00105000000000000'), "Fees do not match"
            assert tx_details["memo"] is None, "Memo is not None"
            assert tx_details["confirmations"] == 266280, "Confirmations do not match"
            assert tx_details["raw"] is None, "Raw is not None"
            assert isinstance(tx_details["inputs"], list), "Inputs is not a list"
            assert len(tx_details["inputs"]) == 0, "Inputs list is not empty"
            assert isinstance(tx_details["outputs"], list), "Outputs is not a list"
            assert len(tx_details["outputs"]) == 0, "Outputs list is not empty"

            assert isinstance(tx_details["transfers"], list), "Transfers is not a list"
            assert len(tx_details["transfers"]) == 1, "Transfers list length does not match"

            transfer = tx_details["transfers"][0]
            assert isinstance(transfer, dict), "Transfer is not a dictionary"
            assert transfer["currency"] == 123, "Currency does not match"
            assert transfer["from"] == "0x3727cfCBD85390Bb11B3fF421878123AdB866be8", "From address does not match"
            assert transfer["is_valid"] is True, "Is_valid status does not match"
            assert transfer["memo"] is None, "Memo in transfer is not None"
            assert transfer["symbol"] == "FLR", "Symbol does not match"
            assert transfer["to"] == "0x1e429358DB3949c20fd49a0212F5CEc7a731a500", "To address does not match"
            assert transfer["value"] == Decimal('187197.48377185000000000'), "Value does not match"
            assert transfer["token"] is None, "Token is not None"


# GET ADDRESS TRANSACTIONS API #

def test__flarescan_flare__get_address_transactions__from_explorer_interface__successful(
        address_transactions: dict, block_head) -> None:
    api = FlareExplorerApi
    flare_explorer_interface = FlareExplorerInterface()
    flare_explorer_interface.address_txs_apis = [api]
    address: str = "0x1e429358DB3949c20fd49a0212F5CEc7a731a500"

    with patch.object(target=api, attribute='get_address_txs', return_value=address_transactions):
        with patch.object(target=api, attribute='get_block_head', return_value=block_head):
            address_txs = flare_explorer_interface.get_txs(address=address)

            assert isinstance(address_txs, list)
            assert len(address_txs) == 1

            output_data: dict = address_txs[0][parse_currency('flr')]
            expected_data: dict = address_transactions['items'][0]

            assert int(float(output_data['amount']) * pow(10, 18)) == int(expected_data['value'])
            assert output_data['address'] == expected_data['from']['hash']
            assert output_data['block'] == int(expected_data['block_number'])
            assert output_data['confirmations'] == int(expected_data['confirmations'])
            assert output_data['date'] == parse_iso_date(s=expected_data['timestamp'])
            assert output_data['direction'] == "outgoing"
            assert output_data['from_address'] == expected_data['from']['hash']
            assert output_data['hash'] == expected_data['hash']
            assert output_data['memo'] is None
            assert output_data['raw'] is None
            assert output_data['to_address'] == expected_data['to']['hash']

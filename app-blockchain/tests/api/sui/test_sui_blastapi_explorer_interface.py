import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from exchange.base.models import Currencies

# from exchange.blockchain.api.sui.sui_blastapi import BlastApiSuiApi # noqa: ERA001
# from exchange.blockchain.api.sui.sui_explorer_interface import RpcSuiExplorerInterface # noqa: ERA001
from exchange.blockchain.tests.fixtures.sui_blastapi_fixtures import (
    ADDRESS_TXS_CHECKPOINT_VALUE,
    BLOCK_HEAD_FIXTURE_VALUE,
    address_transactions,
    batch_tx_details,
    block_addresses,
    block_head,
    tx_details,
)

pytestmark = pytest.mark.skip(reason='Skipping all tests in this file temporarily')


def test_blastapi_sui_get_block_head_from_api_interface_successful(block_head) -> None:
    api = BlastApiSuiApi# noqa: F821
    sui_explorer_interface = RpcSuiExplorerInterface()# noqa: F821
    sui_explorer_interface.block_head_apis = [api]

    with patch.object(api, 'request', return_value=block_head):
        assert sui_explorer_interface.get_block_head() == BLOCK_HEAD_FIXTURE_VALUE


def test_blastapi_sui_get_block_txs_from_api_interface_successful(
        block_addresses, batch_tx_details) -> None:
    api = BlastApiSuiApi# noqa: F821
    sui_explorer_interface = RpcSuiExplorerInterface()# noqa: F821
    sui_explorer_interface.block_head_apis = [api]
    sui_explorer_interface.block_txs_apis = [api]

    with patch.object(api, attribute='request', return_value=block_addresses), \
            patch.object(api, attribute='get_tx_details_batch', return_value=batch_tx_details):
        to_block_number: int = 115765230
        block_txs = sui_explorer_interface.get_latest_block(
            after_block_number=115765229,  # inclusive after
            to_block_number=115765230,
            include_info=True,
            include_inputs=True,
        )

        assert isinstance(block_txs, tuple)

        addresses_info, txs_info, block_number = block_txs

        assert isinstance(addresses_info, dict)
        assert addresses_info['input_addresses'] == {
            '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'}
        assert addresses_info['output_addresses'] == {
            '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'}

        assert isinstance(txs_info, dict)
        assert 'incoming_txs' in txs_info
        assert 'outgoing_txs' in txs_info

        outgoing_txs = txs_info['outgoing_txs']
        assert '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384' in outgoing_txs

        outgoing_tx = outgoing_txs['0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384']
        assert Currencies.sui in outgoing_tx
        assert isinstance(outgoing_tx[Currencies.sui], list)
        assert len(outgoing_tx[Currencies.sui]) == 1

        out_tx_data = outgoing_tx[Currencies.sui][0]
        assert out_tx_data['tx_hash'] == '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt'
        assert out_tx_data['block_height'] == BLOCK_HEAD_FIXTURE_VALUE
        assert out_tx_data['symbol'] == 'SUI'
        assert out_tx_data['contract_address'] is None
        assert out_tx_data['value'] == Decimal('500.000000000')

        incoming_txs = txs_info['incoming_txs']
        assert '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33' in incoming_txs

        incoming_tx = incoming_txs['0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33']
        assert Currencies.sui in incoming_tx
        assert isinstance(incoming_tx[Currencies.sui], list)
        assert len(incoming_tx[Currencies.sui]) == 1

        in_tx_data = incoming_tx[Currencies.sui][0]
        assert in_tx_data['tx_hash'] == '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt'
        assert in_tx_data['block_height'] == BLOCK_HEAD_FIXTURE_VALUE
        assert in_tx_data['symbol'] == 'SUI'
        assert in_tx_data['contract_address'] is None
        assert in_tx_data['value'] == Decimal('500.000000000')

        assert block_number == to_block_number


def test__blastapi_sui__get_transactions_details__from_explorer_interface__successful(
        tx_details: dict, block_head: dict) -> None:
    api = BlastApiSuiApi# noqa: F821
    sui_explorer_interface = RpcSuiExplorerInterface()# noqa: F821
    sui_explorer_interface.block_head_apis = [api]
    sui_explorer_interface.tx_details_apis = [api]

    with patch.object(target=api, attribute='get_tx_details', return_value=tx_details), \
            patch.object(target=api, attribute='get_block_head', return_value=block_head):
        tx_detail = sui_explorer_interface.get_tx_details(tx_hash='4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt')
        assert isinstance(tx_detail, dict)

        assert tx_detail['hash'] == '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt'
        assert tx_detail['success'] is True
        assert tx_detail['block'] == BLOCK_HEAD_FIXTURE_VALUE

        assert isinstance(tx_detail['date'], datetime.datetime)
        assert tx_detail['date'].tzinfo is not None

        assert tx_detail['fees'] is None
        assert tx_detail['memo'] is None
        assert tx_detail['confirmations'] == 0
        assert tx_detail['raw'] is None

        assert isinstance(tx_detail['inputs'], list)
        assert len(tx_detail['inputs']) == 0

        assert isinstance(tx_detail['outputs'], list)
        assert len(tx_detail['outputs']) == 0

        assert isinstance(tx_detail['transfers'], list)
        assert len(tx_detail['transfers']) == 1

        transfer = tx_detail['transfers'][0]
        assert transfer['type'] == 'MainCoin'
        assert transfer['symbol'] == 'SUI'
        assert transfer['currency'] == Currencies.sui
        assert transfer['from'] == '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'
        assert transfer['to'] == '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'
        assert transfer['value'] == Decimal('500.000000000')
        assert transfer['is_valid'] is True
        assert transfer['token'] is None
        assert transfer['memo'] is None


def test__blastapi_sui__get_address_txs__from_explorer_interface__successful(block_head: dict,
                                                                             address_transactions: dict) -> None:
    api = BlastApiSuiApi # noqa: F821
    sui_explorer_interface = RpcSuiExplorerInterface() # noqa: F821
    sui_explorer_interface.address_txs_apis = [api]

    expected_confirmation: int = 23239131

    with patch.object(target=api, attribute='get_address_txs', return_value=address_transactions), \
            patch.object(target=api, attribute='get_block_head', return_value=block_head):
        address_txs = sui_explorer_interface.get_txs(
            address='0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'
        )

        assert isinstance(address_txs, list)
        assert len(address_txs) == 1

        tx_entry = address_txs[0]
        assert isinstance(tx_entry, dict)
        assert Currencies.sui in tx_entry

        tx_data = tx_entry[Currencies.sui]
        assert isinstance(tx_data, dict)

        assert tx_data['amount'] == Decimal('500.000000000')
        assert tx_data['from_address'] == '0xceadf149873caa7f8bfc95cd0c2aaa5cc14ee53a4b71d1616b75b64d9e6f6384'
        assert tx_data['to_address'] == '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'
        assert tx_data['hash'] == '9H7LgfoSC5NrduQijjw6DBFdHxyEgKPHr3eYAgFK5GcM'
        assert tx_data['block'] == ADDRESS_TXS_CHECKPOINT_VALUE

        assert isinstance(tx_data['date'], datetime.datetime)
        assert tx_data['date'].tzinfo is not None  # Ensure timezone info exists

        assert tx_data['memo'] is None
        assert tx_data['confirmations'] == expected_confirmation
        assert tx_data['address'] == '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'
        assert tx_data['direction'] == 'incoming'
        assert tx_data['raw'] is None

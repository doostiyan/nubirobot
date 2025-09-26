from exchange.blockchain.api.sonic.sonic_explorer_interface import SonicExplorerInterface
from exchange.blockchain.api.sonic.sonic_scan import SonicScanApi
from exchange.blockchain.models import Currencies
from exchange.blockchain.tests.base.rpc import (do_mocked_address_txs_response_test, do_mocked_block_head_response_test,
                                                do_mocked_block_txs_response_test, do_mocked_tx_detail_response_test)
from exchange.blockchain.tests.fixtures.rpc_fixtures import (block_addresses, block_head,  # noqa: F401
                                                             transaction_receipt, transactions_details)

# GET BLOCK HEAD API #


def test__sonicscan_sonic__get_block_head__from_explorer_interface__successful(rpc_block_head) -> None:
    do_mocked_block_head_response_test(
        api=SonicScanApi,
        explorer_interface_class=SonicExplorerInterface,
        block_head=rpc_block_head,
    )


# GET BLOCK ADDRESSES API #

def test__sonicscan_sonic__get_multiple_block_addresses__from_explorer_interface__successful(
        rpc_block_addresses) -> None:  # noqa: F811
    do_mocked_block_txs_response_test(
        api=SonicScanApi,
        explorer_interface_class=SonicExplorerInterface,
        block_addresses=rpc_block_addresses,
        symbol='S',
        currency=Currencies.s,
    )


# GET TXs DETAILS API #

def test__sonicscan_sonic__get_transactions_details__from_explorer_interface__successful(
        rpc_block_head,
        rpc_transaction_receipt,
        rpc_transactions_details,
) -> None:  # noqa: F811
    do_mocked_tx_detail_response_test(
        api=SonicScanApi,
        explorer_interface_class=SonicExplorerInterface,
        block_head=rpc_block_head,
        transaction_receipt=rpc_transaction_receipt,
        transactions_details=rpc_transactions_details,
        symbol='S',
        currency=Currencies.s,
    )


# GET ADDRESS TRANSACTIONS API #

def test__sonicscan_sonic__get_address_transactions__from_explorer_interface__successful(
        rpc_block_head, rpc_address_transactions) -> None:  # noqa: F811
    do_mocked_address_txs_response_test(
        api=SonicScanApi,
        explorer_interface_class=SonicExplorerInterface,
        block_head=rpc_block_head,
        address_transactions=rpc_address_transactions,
        currency=Currencies.s,
    )

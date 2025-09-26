from exchange.blockchain.api.flr.flare_explorer_interface import FlareExplorerInterface
from exchange.blockchain.api.flr.flare_routescan import FlareRoutescanApi
from exchange.blockchain.models import Currencies
from exchange.blockchain.tests.base.rpc import (do_mocked_address_txs_response_test, do_mocked_block_head_response_test,
                                                do_mocked_block_txs_response_test, do_mocked_tx_detail_response_test)

# BLOCK HEAD API #


def test__flare_routescan__get_block_head__from_explorer_interface__successful(rpc_block_head) -> None:
    do_mocked_block_head_response_test(
        api=FlareRoutescanApi,
        explorer_interface_class=FlareExplorerInterface,
        block_head=rpc_block_head,
    )


# BLOCK ADDRESSES API #

def test__ankr_flare__get_multiple_block_addresses__from_explorer_interface__successful(rpc_block_addresses) -> None:
    do_mocked_block_txs_response_test(
        api=FlareRoutescanApi,
        explorer_interface_class=FlareExplorerInterface,
        block_addresses=rpc_block_addresses,
        symbol='FLR',
        currency=Currencies.flr,
    )


# TX DETAIL API #

def test__ankr_flare__get_transaction_details__from_explorer_interface__successful(rpc_block_head,
                                                                                   rpc_transaction_receipt,
                                                                                   rpc_transactions_details) -> None:
    do_mocked_tx_detail_response_test(
        api=FlareRoutescanApi,
        explorer_interface_class=FlareExplorerInterface,
        block_head=rpc_block_head,
        transaction_receipt=rpc_transaction_receipt,
        transactions_details=rpc_transactions_details,
        symbol='FLR',
        currency=Currencies.flr,
    )


# ADDRESS TRANSACTIONS API #

def test__ankr_flare__get_address_transactions__from_explorer_interface__successful(rpc_block_head,
                                                                                    rpc_address_transactions) -> None:  # noqa: F811
    do_mocked_address_txs_response_test(
        api=FlareRoutescanApi,
        explorer_interface_class=FlareExplorerInterface,
        block_head=rpc_block_head,
        address_transactions=rpc_address_transactions,
        currency=Currencies.flr,
    )

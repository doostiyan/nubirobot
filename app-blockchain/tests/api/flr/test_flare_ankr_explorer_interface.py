from exchange.blockchain.api.flr.flare_ankr import FlareAnkrApi
from exchange.blockchain.api.flr.flare_explorer_interface import FlareExplorerInterface
from exchange.blockchain.models import Currencies
from exchange.blockchain.tests.base.rpc import (do_mocked_block_head_response_test, do_mocked_block_txs_response_test,
                                                do_mocked_tx_detail_response_test)

# GET BLOCK HEAD API #


def test__ankr_flare__get_block_head__from_explorer_interface__successful(
        rpc_block_head,
) -> None:
    do_mocked_block_head_response_test(
        api=FlareAnkrApi,
        explorer_interface_class=FlareExplorerInterface,
        block_head=rpc_block_head,
    )


# GET BLOCK ADDRESSES API #

def test__ankr_flare__get_multiple_block_addresses__from_explorer_interface__successful(rpc_block_addresses) -> None:
    do_mocked_block_txs_response_test(
        api=FlareAnkrApi,
        explorer_interface_class=FlareExplorerInterface,
        block_addresses=rpc_block_addresses,
        symbol='FLR',
        currency=Currencies.flr,
    )


# GET TXs DETAILS API #

def test__ankr_flare__get_transactions_details__from_explorer_interface__successful(rpc_block_head,
                                                                                    rpc_transaction_receipt,
                                                                                    rpc_transactions_details) -> None:  # noqa: F811
    do_mocked_tx_detail_response_test(
        api=FlareAnkrApi,
        explorer_interface_class=FlareExplorerInterface,
        block_head=rpc_block_head,
        transaction_receipt=rpc_transaction_receipt,
        transactions_details=rpc_transactions_details,
        symbol='FLR',
        currency=Currencies.flr,
    )

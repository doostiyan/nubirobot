from decimal import Decimal
from unittest.mock import patch

from exchange.base.parsers import parse_currency, parse_iso_date, parse_utc_timestamp, parse_utc_timestamp_ms
from exchange.blockchain.api.bsc.bsc_explorer_interface import BscExplorerInterface
from exchange.blockchain.api.bsc.bsc_oklink import OkLinkBscApi
from exchange.blockchain.contracts_conf import CONTRACT_INFO
from exchange.blockchain.models import Currencies
from exchange.blockchain.tests.base.rpc import do_mocked_block_head_response_test
from exchange.blockchain.tests.fixtures.bsc_oklink_fixtures import (
    block_head,
    bsc_babydoge_transaction,
    bsc_native_transaction,
    bsc_usdt_transaction,
)

# GET BLOCK HEAD API #

def test__oklink_bsc__get_block_head__from_explorer_interface__successful(
        block_head: dict,
) -> None:
    do_mocked_block_head_response_test(
        api=OkLinkBscApi,
        explorer_interface_class=BscExplorerInterface,
        block_head=block_head,
    )


# GET ADDRESS TRANSACTIONS API #

def test__oklink_bsc__get_address_transactions__from_explorer_interface__successful(
        block_head: dict,
        bsc_native_transaction: dict,
) -> None:
    api = OkLinkBscApi
    bsc_explorer_interface = BscExplorerInterface()
    bsc_explorer_interface.address_txs_apis = [api]
    bsc_explorer_interface.block_head_apis = [api]
    address: str = '0x18dd8c2f3ebef1948a07ece5c72f4ea43f2e6cd9'

    with patch.object(target=api, attribute='get_address_txs', return_value=bsc_native_transaction), \
         patch.object(target=api, attribute='get_block_head', return_value=block_head):
        address_txs = bsc_explorer_interface.get_txs(address=address)

        assert isinstance(address_txs, list)
        assert len(address_txs) == 1

        output_data: dict = address_txs[0][parse_currency('bnb')]
        expected_data: dict = bsc_native_transaction['data'][0]['transactionLists'][0]

        assert output_data['amount'] == Decimal('0.000425117490378252')
        assert output_data['address'] == expected_data['to']
        assert output_data['block'] == int(expected_data['height'])
        assert output_data['date'] == parse_utc_timestamp_ms(s=expected_data['transactionTime'])
        assert output_data['direction'] == 'incoming'
        assert output_data['from_address'] == expected_data['from']
        assert output_data['hash'] == expected_data['txId']
        assert output_data['memo'] is None
        assert output_data['raw'] is None
        assert output_data['to_address'] == expected_data['to']


def test__oklink_bsc__get_token_transactions__from_explorer_interface__when_scale_token__successful(
        block_head: dict,
        bsc_babydoge_transaction: dict,
) -> None:
    api = OkLinkBscApi
    bsc_explorer_interface = BscExplorerInterface()
    bsc_explorer_interface.token_txs_apis = [api]
    bsc_explorer_interface.block_head_apis = [api]
    address: str = '0x7d403942336a95fd31cbbf24ff7ad82529519861'

    with patch.object(target=api, attribute='get_token_txs', return_value=bsc_babydoge_transaction), \
         patch.object(target=api, attribute='get_block_head', return_value=block_head):
        address_txs = bsc_explorer_interface.get_token_txs(
            address=address,
            contract_info=CONTRACT_INFO.get('BSC').get('mainnet').get(parse_currency('1b_babydoge')),
        )

        assert isinstance(address_txs, list)
        assert len(address_txs) == 1

        output_data: dict = address_txs[0][parse_currency('1b_babydoge')]
        expected_data: dict = bsc_babydoge_transaction['data'][0]['transactionLists'][0]

        assert output_data['amount'] == Decimal('0.047400000000000000')
        assert output_data['address'] == expected_data['to']
        assert output_data['block'] == int(expected_data['height'])
        assert output_data['date'] == parse_utc_timestamp_ms(s=expected_data['transactionTime'])
        assert output_data['direction'] == 'incoming'
        assert output_data['from_address'] == expected_data['from']
        assert output_data['hash'] == expected_data['txId']
        assert output_data['memo'] is None
        assert output_data['raw'] is None
        assert output_data['to_address'] == expected_data['to']


def test__oklink_bsc__get_token_transactions__from_explorer_interface__when_non_scale_token__successful(
        block_head: dict,
        bsc_usdt_transaction: dict,
) -> None:
    api = OkLinkBscApi
    bsc_explorer_interface = BscExplorerInterface()
    bsc_explorer_interface.token_txs_apis = [api]
    bsc_explorer_interface.block_head_apis = [api]
    address: str = '0xC195143bC42909274c1bC1696989876D53d74Aba'

    with patch.object(target=api, attribute='get_token_txs', return_value=bsc_usdt_transaction), \
         patch.object(target=api, attribute='get_block_head', return_value=block_head):
        address_txs = bsc_explorer_interface.get_token_txs(
            address=address,
            contract_info=CONTRACT_INFO.get('BSC').get('mainnet').get(parse_currency('usdt')),
        )

        assert isinstance(address_txs, list)
        assert len(address_txs) == 1

        output_data: dict = address_txs[0][parse_currency('usdt')]
        expected_data: dict = bsc_usdt_transaction['data'][0]['transactionLists'][0]

        assert output_data['amount'] == Decimal('2.27')
        assert output_data['address'].casefold() == expected_data['to'].casefold()
        assert output_data['block'] == int(expected_data['height'])
        assert output_data['date'] == parse_utc_timestamp_ms(s=expected_data['transactionTime'])
        assert output_data['direction'] == 'incoming'
        assert output_data['from_address'] == expected_data['from']
        assert output_data['hash'] == expected_data['txId']
        assert output_data['memo'] is None
        assert output_data['raw'] is None
        assert output_data['to_address'] == expected_data['to']

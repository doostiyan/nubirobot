from decimal import Decimal

import pytest

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from ..dtos.block_info import BlockInfoDTO
from ..services import BlockExplorerService
from ..utils.exceptions import BlockInfoNotFoundException


@pytest.mark.service
@pytest.mark.django_db
def test_get_latest_block_info_dto_service(mocker):
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_latest_block_addresses',
                 return_value=(
                     {
                         'input_addresses': set(),
                         'output_addresses': {'DUBV52DpEf7GziCrM6QpK6sbDish9Wegyr',
                                              'DTebbWq8fnZZJnw5tLfPyb1P3yM5g5bxJD',
                                              'DKY6Fj3wU5znaRtwXX7wm5eJRQ2H8bfMv2'}
                     },
                     {
                         'outgoing_txs': {

                         },
                         'incoming_txs': {
                             'DTebbWq8fnZZJnw5tLfPyb1P3yM5g5bxJD': {
                                 18: [{'tx_hash': '86a2ea84b35a96572621970e20ad95c7a3ee624fd2f91778fbfad82d1e33cf39',
                                       'value': Decimal('518188.00000000')}]},
                             'DKY6Fj3wU5znaRtwXX7wm5eJRQ2H8bfMv2': {
                                 18: [{'tx_hash': 'be936f855858103437805e4268e2fc746467d96e2942fece27dbd9bcf3447a7b',
                                       'value': Decimal('625825.00000000')}]},
                             'DUBV52DpEf7GziCrM6QpK6sbDish9Wegyr': {
                                 18: [{'tx_hash': 'a9ed4380d5a6f8270bd3dab5a62e6a381db3c3d7ea30374968f545cfd592bf21',
                                       'value': Decimal('513713.00000000')}]},
                         }
                     },
                     60
                 ))
    service_response = BlockExplorerService.get_latest_block_info_dto(
        network='DOGE',
        after_block_number=50,
        to_block_number=60,
        include_inputs=True,
        include_info=True,
    )
    latest_block_info_dto = BlockInfoDTO(
        latest_processed_block=60,
        transactions=[
            TransferTx(
                success=True,
                confirmations=None,
                from_address='',
                to_address='DTebbWq8fnZZJnw5tLfPyb1P3yM5g5bxJD',
                tx_hash='86a2ea84b35a96572621970e20ad95c7a3ee624fd2f91778fbfad82d1e33cf39',
                symbol='DOGE',
                value=Decimal('518188.00000000'),
                index=0,
                memo=''
            ),
            TransferTx(
                success=True,
                confirmations=None,
                from_address='',
                to_address='DKY6Fj3wU5znaRtwXX7wm5eJRQ2H8bfMv2',
                tx_hash='be936f855858103437805e4268e2fc746467d96e2942fece27dbd9bcf3447a7b',
                symbol='DOGE',
                value=Decimal('625825.00000000'),
                index=0,
                memo=''
            ),
            TransferTx(
                success=True,
                confirmations=None,
                from_address='',
                to_address='DUBV52DpEf7GziCrM6QpK6sbDish9Wegyr',
                tx_hash='a9ed4380d5a6f8270bd3dab5a62e6a381db3c3d7ea30374968f545cfd592bf21',
                symbol='DOGE',
                value=Decimal('513713.00000000'),
                index=0,
                memo=''
            ),
        ]
    )
    assert service_response == latest_block_info_dto


@pytest.mark.service
@pytest.mark.django_db
def test_get_latest_block_info_dto_service_with_none_block_info_data_should_raise_not_found_exception(mocker):
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_latest_block_addresses',
                 return_value=(set(), None, 0))
    pytest.raises(BlockInfoNotFoundException,
                  BlockExplorerService.get_latest_block_info_dto,
                  network='BTC',
                  after_block_number=50,
                  to_block_number=60,
                  include_inputs=True,
                  include_info=True)

import datetime
from decimal import Decimal

import pytest
from pytest_mock import MockerFixture

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.transactions.utils.exceptions import TransactionNotFoundException


@pytest.mark.service
@pytest.mark.django_db
def test_get_transaction_details_dto_service(mocker: MockerFixture) -> None:
    mocker.patch(
        'exchange.blockchain.explorer_original.BlockchainExplorer.get_transactions_details',
        return_value={
            '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38': {
                'hash': '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
                'success': True,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {
                        'type': 'MainCoin',
                        'symbol': 'ADA',
                        'currency': 21,
                        'to': (
                            'addr1qy2ujrvjfmj9tme79q2dkyte8928mmtp0ppy9czztt88uuz0wep2023z0nydf2m'
                            'gfkxll7hs4fet7uxdr9vh8ufg95ys5j93xz'
                        ),
                        'from': (
                            'addr1qxgmxp4mv4fac3s9zq52h2esjwy9dyqdrwv9zsdr2l8lqrnrty3259xt6uhdeuh'
                            'g4jm2up5wk6vchc57wzn3hqt2scyqvqygq9'
                        ),
                        'is_valid': True,
                        'token': None,
                        'value': Decimal('9.382732')
                    }
                ],
                'block': 6828440,
                'confirmations': 166477,
                'fees': Decimal('0.176237'),
                'date': datetime.datetime(2022, 2, 1, 16, 15, 2, tzinfo=datetime.timezone.utc)
            }
        }
    )
    service_response = TransactionExplorerService.get_transaction_details_from_default_provider_dtos(
        network='ADA',
        tx_hashes=['8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38']
    )
    transaction_details_dto = [
        TransferTx(
            success=True,
            tx_hash='8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
            block_hash=None,
            block_height=6828440,
            from_address=(
                'addr1qxgmxp4mv4fac3s9zq52h2esjwy9dyqdrwv9zsdr2l8lqrnrty3259xt6uhdeuh'
                'g4jm2up5wk6vchc57wzn3hqt2scyqvqygq9'
            ),
            to_address=(
                'addr1qy2ujrvjfmj9tme79q2dkyte8928mmtp0ppy9czztt88uuz0wep2023z0nydf2m'
                'gfkxll7hs4fet7uxdr9vh8ufg95ys5j93xz'
            ),
            confirmations=166477,
            date=datetime.datetime(2022, 2, 1, 16, 15, 2, tzinfo=datetime.timezone.utc),
            token=None,
            memo=None,
            value=Decimal('9.382732'),
            symbol='ADA',
            tx_fee=Decimal('0.176237'),
        )
    ]
    assert service_response == transaction_details_dto


@pytest.mark.service
@pytest.mark.django_db
def test_get_transaction_details_dtos_service(mocker):
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_transactions_details',
                 return_value={
                     '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38': {
                         'hash': '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
                         'success': True,
                         'inputs': [],
                         'outputs': [],
                         'transfers': [
                             {'type': 'MainCoin',
                              'symbol': 'ADA',
                              'currency': 21,
                              'to': 'addr1qy2ujrvjfmj9tme79q2dkyte8928mmtp0ppy9czztt88uuz0wep2023z0nydf2mgfkxll7hs4fet7'
                                    'uxdr9vh8ufg95ys5j93xz',
                              'value': Decimal('57.333792'),
                              'is_valid': True,
                              'token': None,
                              'from': 'addr1qxgmxp4mv4fac3s9zq52h2esjwy9dyqdrwv9zsdr2l8lqrnrty3259xt6uhdeuhg4jm2up5wk6v'
                                      'chc57wzn3hqt2scyqvqygq9'}
                         ],
                         'block': 6828440,
                         'confirmations': 166477,
                         'fees': Decimal('0.176237'),
                         'date': datetime.datetime(2022, 2, 1, 16, 15, 2, tzinfo=datetime.timezone.utc)
                     },
                     'b051c2a9cb4804be11d428758229886d369d6a358e2bbfecec4811a0538d0559': {
                         'hash': 'b051c2a9cb4804be11d428758229886d369d6a358e2bbfecec4811a0538d0559',
                         'success': True,
                         'inputs': [],
                         'outputs': [],
                         'transfers': [
                             {'type': 'MainCoin',
                              'symbol': 'ADA',
                              'currency': 21,
                              'to': 'addr1qxpp867zyjz93zu0j34vpmcxk3y6w0hymumnf6ntp5fhch64rwzekldc8w0k86c78sxuj67qjg3c'
                                    'vpzuk2p97fxzp3ysuzauup',
                              'value': Decimal('16.955756000000000000'),
                              'is_valid': True,
                              'token': None,
                              'from': 'addr1zxn9efv2f6w82hagxqtn62ju4m293tqvw0uhmdl64ch8uw6j2c79gy9l76sdg0xwhd7r0c0kna'
                                      '0tycz4y5s6mlenh8pq6s3z70'}
                         ],
                         'block': 9011709,
                         'confirmations': None,
                         'fees': Decimal('0.176237000000000000'),
                         'date': datetime.datetime(2022, 2, 1, 16, 15, 2, tzinfo=datetime.timezone.utc)
                     },
                 })
    service_response = TransactionExplorerService.get_transaction_details_from_default_provider_dtos(
        network='ADA',
        tx_hashes=['8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
                   'b051c2a9cb4804be11d428758229886d369d6a358e2bbfecec4811a0538d0559'], )
    transaction_details_dtos = [
        TransferTx(
            tx_hash='8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38',
            success=True,
            from_address='addr1qxgmxp4mv4fac3s9zq52h2esjwy9dyqdrwv9zsdr2l8lqrnrty3259xt6uhdeuhg4jm2up5wk6vchc57wzn3hqt2scyqvqygq9',
            to_address='addr1qy2ujrvjfmj9tme79q2dkyte8928mmtp0ppy9czztt88uuz0wep2023z0nydf2mgfkxll7hs4fet7uxdr9vh8ufg95ys5j93xz',
            value=Decimal('57.333792'),
            symbol='ADA',
            confirmations=166477,
            block_height=6828440,
            block_hash=None,
            date=datetime.datetime(2022, 2, 1, 16, 15, 2, tzinfo=datetime.timezone.utc),
            memo=None,
            tx_fee=Decimal('0.176237'),
            token=None,
        ),
        TransferTx(
            tx_hash='b051c2a9cb4804be11d428758229886d369d6a358e2bbfecec4811a0538d0559',
            success=True,
            from_address='addr1zxn9efv2f6w82hagxqtn62ju4m293tqvw0uhmdl64ch8uw6j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6s3z70',
            to_address='addr1qxpp867zyjz93zu0j34vpmcxk3y6w0hymumnf6ntp5fhch64rwzekldc8w0k86c78sxuj67qjg3cvpzuk2p97fxzp3ysuzauup',
            value=Decimal('16.955756000000000000'),
            symbol='ADA',
            confirmations=None,
            block_height=9011709,
            block_hash=None,
            date=datetime.datetime(2022, 2, 1, 16, 15, 2, tzinfo=datetime.timezone.utc),
            memo=None,
            tx_fee=Decimal('0.176237000000000000'),
            token=None,
        )
    ]
    assert service_response == transaction_details_dtos


@pytest.mark.service
@pytest.mark.django_db
def test_get_transaction_details_dtos_service_with_none_transaction_data_should_raise_not_found_exception(mocker):
    mocker.patch('exchange.blockchain.explorer_original.BlockchainExplorer.get_transactions_details',
                 return_value=None)

    service_response = TransactionExplorerService.get_transaction_details_from_default_provider_dtos(
        network='TON', tx_hashes=['a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0',
                                  '38b1afabbc0b905d0cf84bfc93ab690ee8f3e62543273b9d0705a8e4d9f138d2'])
    assert service_response == []


@pytest.mark.service
@pytest.mark.django_db
def test_get_transaction_details_dto_service_with_none_transaction_data_should_return_empty_list(
        mocker: MockerFixture) -> None:
    mocker.patch(
        'exchange.blockchain.explorer_original.BlockchainExplorer.get_transactions_details',
        return_value=None
    )
    service_response = TransactionExplorerService.get_transaction_details_from_default_provider_dtos(
        network='TON',
        tx_hashes=['a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0']
    )
    assert service_response == []

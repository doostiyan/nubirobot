import datetime
from decimal import Decimal

import pytest
import pytz
from django.conf import settings
from django.test.client import Client
from django.urls import reverse
from pytest_mock import MockerFixture
from rest_framework import status

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.transactions.tests.fixtures.view_fixtures import (
    batch_tx_detail_url_dynamic,
    batch_tx_detail_url_static,
    valid_batch_tx_detail_payload,
    valid_transfer,
)
from exchange.explorer.transactions.utils.exceptions import TransactionNotFoundException
from exchange.explorer.utils.test import APIKeyMock

from .fixtures.request_fixtures import api_key_fixture, auth_headers, non_localhost_ip

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404


@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize(
    ('network', 'tx_hash'),
    [
        ('ADA', '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38'),  # UTXO
        ('ETH', '0x881cebc3cf96900cdda47051b9841bd51730b1bdb247dc470871ad91548bd12f'),  # ETH
    ],
)
def test_get_transaction_details_api_for_all_networks_and_currencies(
        network: str, tx_hash: str, client: Client, mocker: MockerFixture
) -> None:
    url = reverse(
        'transactions:transaction_details',
        kwargs={'network': network, 'tx_hash': tx_hash},
    )

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == HTTP_OK


@pytest.mark.view
@pytest.mark.django_db
def test__get_transaction_details_api__with_invalid_tx_hash__should_return_empty_value__successful(
        client: Client, mocker: MockerFixture
) -> None:
    url = reverse(
        'transactions:transaction_details',
        kwargs={'network': 'BTC', 'tx_hash': 'INVALID_TX_HASH'},
    )
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == HTTP_NOT_FOUND


@pytest.mark.view
@pytest.mark.django_db
def test_get_transaction_details_api_with_invalid_network_should_return_400(
        client: Client, mocker: MockerFixture
) -> None:
    url = reverse(
        'transactions:transaction_details',
        kwargs={
            'network': 'INVALID_NETWORK',
            'tx_hash': 'a1bacbfccf58327990c37ce349d2d798ffba8aad7ef7d37069bf0ef827d974d0',
        },
    )
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == HTTP_BAD_REQUEST


@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize(
    ('network', 'tx_hash', 'address', 'currency'),
    [
        (
                'TON',
                'd7ff7b0e9da6048b2c9aa103bc396f1eebe96b6cf076971f4a47f6c066af810e',
                'UQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5guWp',
                'DOGS',
        ),
    ],
)
def test_get_confirmed_transaction_details_api(
        network: str,
        tx_hash: str,
        address: str,
        currency: str,
        client: Client,
        mocker: MockerFixture,
) -> None:
    url = reverse(
        'transactions:confirmed_transaction_details',
        kwargs={'network': network, 'tx_hash': tx_hash},
    )

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )

    mock_response = [
        TransferTx(
            tx_hash='d7ff7b0e9da6048b2c9aa103bc396f1eebe96b6cf076971f4a47f6c066af810e',
            success=True,
            from_address='EQCW9JCezZp01q0g5vSCbDnEjytQqD-9sL3yghMduOcN_w24',
            to_address='',
            value=Decimal('-42910.000000000'),
            symbol='DOGS',
            confirmations=591,
            block_height=0,
            block_hash=None,
            date=datetime.datetime(2025, 2, 2, 6, 3, 21, tzinfo=pytz.UTC),
            memo='1258333387',
            tx_fee=None,
            token=None,
            index=0,
        )
    ]

    mocker.patch(
        'exchange.explorer.wallets.services.WalletExplorerService.get_wallet_transactions_dto_around_tx',
        return_value=mock_response,
    )

    mocker.patch(
        'exchange.explorer.wallets.services.WalletExplorerService.is_nobitex_deposit_wallet',
        return_value=True,
    )

    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, {'address': address, 'currency': currency}, **headers)
    expected_result = [
        {
            'block_hash': None,
            'block_height': 0,
            'confirmations': 591,
            'date': '2025-02-02T06:03:21Z',
            'from_address': 'EQCW9JCezZp01q0g5vSCbDnEjytQqD-9sL3yghMduOcN_w24',
            'memo': '1258333387',
            'success': True,
            'symbol': 'DOGS',
            'to_address': '',
            'token': None,
            'tx_fee': None,
            'tx_hash': 'd7ff7b0e9da6048b2c9aa103bc396f1eebe96b6cf076971f4a47f6c066af810e',
            'value': '-42910.000000000',
        }
    ]
    assert response.status_code == HTTP_OK
    assert response.json() == expected_result


@pytest.mark.view
@pytest.mark.django_db
@pytest.mark.parametrize(
    ('network', 'tx_hash'),
    [
        ('ADA', '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38'),  # Upper Case
        ('ada', '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38'),  # Lower Case
    ],
)
def test_get_transaction_details_api_for_all_networks_and_currencies(
        network: str, tx_hash: str, client: Client, mocker: MockerFixture
) -> None:
    url = reverse(
        'transactions:transaction_details',
        kwargs={'network': network, 'tx_hash': tx_hash},
    )

    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )
    headers = {settings.API_KEY_CUSTOM_HEADER: 'key'}
    response = client.get(url, **headers)
    assert response.status_code == HTTP_OK


def mock_transaction_service(
        mocker: MockerFixture,
        valid_transfer: TransferTx,
):
    mocker.patch.object(
        TransactionExplorerService,
        'get_transaction_details_based_on_provider_name_and_url',
        return_value=[valid_transfer],
    )


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_dynamic_provider__successful(
        client: Client,
        mocker: MockerFixture,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_dynamic: str,
        valid_batch_tx_detail_payload: dict,
        valid_transfer: TransferTx,
):
    mock_transaction_service(mocker=mocker, valid_transfer=valid_transfer)
    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert 'transactions' in data
    assert len(data['transactions']) == 1

    result_tx = data['transactions'][0]
    assert result_tx['tx_hash'] == valid_transfer.tx_hash
    assert result_tx['success'] == valid_transfer.success
    assert result_tx['from_address'] == valid_transfer.from_address
    assert result_tx['to_address'] == valid_transfer.to_address
    assert result_tx['value'] == str(valid_transfer.value)
    assert result_tx['symbol'] == valid_transfer.symbol
    assert result_tx['confirmations'] == valid_transfer.confirmations
    assert result_tx['block_height'] == valid_transfer.block_height
    assert result_tx['block_hash'] == valid_transfer.block_hash
    assert result_tx['date'] == valid_transfer.date.isoformat().replace('+00:00', 'Z')
    assert result_tx['memo'] == valid_transfer.memo
    assert result_tx['tx_fee'] == valid_transfer.tx_fee
    assert result_tx['token'] == valid_transfer.token


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_static_provider__successful(
        client: Client,
        mocker: MockerFixture,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_static: str,
        valid_batch_tx_detail_payload: dict,
        valid_transfer: TransferTx,
):
    mock_transaction_service(mocker=mocker, valid_transfer=valid_transfer)
    response = client.post(
        path=batch_tx_detail_url_static,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert 'transactions' in data
    assert len(data['transactions']) == 1

    result_tx = data['transactions'][0]
    assert result_tx['tx_hash'] == valid_transfer.tx_hash
    assert result_tx['success'] == valid_transfer.success
    assert result_tx['from_address'] == valid_transfer.from_address
    assert result_tx['to_address'] == valid_transfer.to_address
    assert result_tx['value'] == str(valid_transfer.value)
    assert result_tx['symbol'] == valid_transfer.symbol
    assert result_tx['confirmations'] == valid_transfer.confirmations
    assert result_tx['block_height'] == valid_transfer.block_height
    assert result_tx['block_hash'] == valid_transfer.block_hash
    assert result_tx['date'] == valid_transfer.date.isoformat().replace('+00:00', 'Z')
    assert result_tx['memo'] == valid_transfer.memo
    assert result_tx['tx_fee'] == valid_transfer.tx_fee
    assert result_tx['token'] == valid_transfer.token


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_dynamic_provider__failed(
        client: Client,
        mocker: MockerFixture,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_dynamic: str,
        valid_batch_tx_detail_payload: dict,
        valid_transfer: TransferTx,
):
    # Mock the service to raise TransactionNotFoundException for dynamic provider
    mocker.patch.object(
        TransactionExplorerService,
        'get_transaction_details_from_dynamic_provider_dtos',
        side_effect=TransactionNotFoundException,
    )

    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {'code': HTTP_NOT_FOUND, 'detail': '', 'message_code': 'transaction_not_found'}


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_static_provider__failed(
        client: Client,
        mocker: MockerFixture,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_static: str,
        valid_batch_tx_detail_payload: dict,
        valid_transfer: TransferTx,
):
    # Mock the service to return empty list for static provider
    mocker.patch.object(
        TransactionExplorerService,
        'get_transaction_details_from_default_provider_dtos',
        return_value=[],
    )

    response = client.post(
        path=batch_tx_detail_url_static,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert 'transactions' in data
    assert len(data['transactions']) == 0


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_invalid_payload_and_missing_tx_hashes__failed(
        client: Client,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_dynamic: str,
):
    invalid_payload = {}
    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=invalid_payload,
        content_type='application/json',
        **auth_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'tx_hashes' in response.json().get('detail')


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_invalid_payload_and_empty_tx_hashes__failed(
        client: Client,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_dynamic: str,
):
    invalid_payload = {'tx_hashes': []}
    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=invalid_payload,
        content_type='application/json',
        **auth_headers)

    assert response.status_code == HTTP_BAD_REQUEST
    assert 'tx_hashes' in response.json().get('detail')


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_missing_api_key__failed(
        client: Client,
        batch_tx_detail_url_dynamic: str,
        valid_batch_tx_detail_payload: dict,
        non_localhost_ip: dict,
):
    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **non_localhost_ip,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_expired_api_key__failed(
        client: Client,
        mocker: MockerFixture,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_dynamic: str,
        valid_batch_tx_detail_payload: dict,
        non_localhost_ip: dict,
):
    api_key = APIKeyMock(rate='1/min', has_expired=True, revoked=False)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )

    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **non_localhost_ip,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.view
@pytest.mark.django_db
def test__batch_transaction_details_view__when_revoked_api_key__failed(
        client: Client,
        mocker: MockerFixture,
        api_key_fixture: str,
        auth_headers: dict,
        batch_tx_detail_url_dynamic: str,
        valid_batch_tx_detail_payload: dict,
        non_localhost_ip: dict,
):
    api_key = APIKeyMock(rate='1/min', has_expired=False, revoked=True)
    mocker.patch(
        'exchange.explorer.authentication.models.UserAPIKeyManager.get_from_key',
        return_value=api_key,
    )

    response = client.post(
        path=batch_tx_detail_url_dynamic,
        data=valid_batch_tx_detail_payload,
        content_type='application/json',
        **non_localhost_ip,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN

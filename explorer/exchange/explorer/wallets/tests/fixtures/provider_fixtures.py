import pytest

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.explorer.networkproviders.dtos.provider import ProviderData


@pytest.fixture
def provider_data():
    explorer_interface_key = 'ExplorerInterface'

    APIS_CLASSES[explorer_interface_key] = ExplorerInterface

    ExplorerInterface.address_txs_apis = [GeneralApi]
    ExplorerInterface.token_txs_apis = [GeneralApi]

    ExplorerInterface.min_valid_tx_amount = 0.01

    return ProviderData(provider_name='test_provider', interface_name=explorer_interface_key)

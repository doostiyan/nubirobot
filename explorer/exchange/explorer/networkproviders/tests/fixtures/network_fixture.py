import pytest

from exchange.explorer.networkproviders.models import Network


@pytest.fixture
def eth_network() -> Network:
    network = Network.objects.filter(name='ETH').get()
    network.use_db = True
    network.save()
    return network


@pytest.fixture
def btc_network() -> Network:
    network = Network.objects.filter(name='BTC').get()
    network.use_db = True
    network.save()
    return network


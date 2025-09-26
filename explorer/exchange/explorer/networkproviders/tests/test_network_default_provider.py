import threading

import pytest

from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService, NetworkService


@pytest.mark.django_db
def test__update_or_create_default_provider__when_race_condition__successful(django_cache):
    operation = Operation.BLOCK_TXS
    network_name = 'BTC'
    network_id = NetworkService.get_network_by_name(network_name=network_name).id

    thread1 = threading.Thread(target=NetworkDefaultProviderService.update_or_create_default_provider,
                               args=(1, operation, network_id))
    thread2 = threading.Thread(target=NetworkDefaultProviderService.update_or_create_default_provider,
                               args=(2, operation, network_id))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    final_db_record = (
        NetworkDefaultProviderService
        .get_default_provider_by_network_name_and_operation(network_name=network_name, operation=operation)
    )

    redis_data = django_cache.get(f'{network_name}_{operation}', None)
    assert redis_data.provider_name == final_db_record.provider.name

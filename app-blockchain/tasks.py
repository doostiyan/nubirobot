from celery import shared_task

from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.validators import validate_crypto_address_v2


@shared_task(name='generate_addresses', max_retries=1)
def task_generate_addresses(addresses_info_list, currency):
    from exchange.wallet.models import AvailableDepositAddress

    for address_info in addresses_info_list:
        address = address_info['address']
        if validate_crypto_address_v2(address=address, currency=currency):
            try:
                AvailableDepositAddress.objects.get(currency=currency, address=address)
            except AvailableDepositAddress.DoesNotExist:
                AvailableDepositAddress.objects.create(
                    currency=currency,
                    address=address,
                    description=address_info['description'],
                    type=address_info['address_type'],
                    salt=address_info.get('salt'),
                )


@shared_task(name='es-log', max_retries=1)
def log_provider_request_task(message: str, log_data: dict):
    try:
        logger.info(msg=message, extra=log_data)
    except Exception:
        logger.exception('Cannot log into ES')

from abc import ABC

from django.conf import settings

from exchange.base.logging import report_event
from exchange.blockchain.abstractـexplorer import AbstractBlockchainExplorer

from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.service_based import ServiceBasedExplorer


class BlockchainExplorer(AbstractBlockchainExplorer, ABC):
    @classmethod
    def get_wallet_ata(cls, address, currency):
        return cls._get_value_from_service_base(
            'get_ata',
            address=address,
            currency=currency,
        )

    @classmethod
    def _get_value_from_service_base(cls, method_name: str, **kwargs):
        method_names = [
            'get_ata',
        ]
        if method_name not in method_names:
            raise TypeError(f"You should set method_name between this list: {method_name}")
        try:
            method = getattr(ServiceBasedExplorer, method_name)
            return method(**kwargs)
        except Exception as e:
            logger.warning(f'An exception occurred within the service-base layer: {e}')
            if settings.BLOCKCHAIN_SERVER:
                report_event(f'An exception occurred within the service-base layer')

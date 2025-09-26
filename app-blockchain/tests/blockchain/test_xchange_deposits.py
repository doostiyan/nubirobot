from unittest import TestCase

from exchange.base.models import Currencies
from exchange.blockchain.inspector import BlockchainInspector, Bep20BlockchainInspector
from exchange.blockchain.models import BaseBlockchainInspector
from exchange.blockchain.tests.base.utils import Fake


class XChangeDepositTest(TestCase):
    fixtures = ['system', 'test_data']
    address_list = ['0x8894e0a0c962cb723c1976a4421c95949be2d4e3', '0x429B4b7e4d5084Ae9670d504619Eb54371a7D18B']

    def no_test_calling_near_currency_get_balance(self):
        currency = Currencies.near
        near_class = BlockchainInspector.CURRENCY_CLASSES[currency]
        near_class.__bases__ = (
            Fake.imitate(Bep20BlockchainInspector), BaseBlockchainInspector
        )

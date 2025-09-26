from decimal import Decimal

import pytest
from django.core.cache import cache
from django.test import TestCase

from exchange.base.models import Currencies
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.wallet.models import AvailableHotWalletAddress
from exchange.wallet.withdraw_commons import get_hot_wallet_addresses
from exchange.wallet.withdraw_diff import to_done_tagged_withdraws


class GrabbingAddressesTest(TestCase):
    """
        This test is for get_hot_wallet_addresses to make sure it -as an important agent in diff hot wallet process-
        is doing its job properly
    """
    address1 = '0xc7b76846De3DB54DB45c8b5deBCabfF4b0834F78'
    address2 = '0xBFE5655De088210b772346a3EA0ca249cC18A820'

    def test_output_check(self):
        """
            In this test we can make sure:
            1.get_hot_wallet_addresses returns the same output when network is passed or currency passed (with the same
            network as its default network)
            2.get_hot_wallet_addresses will return addresses all lower (by default) and won't touch addresses when
            keep_case parameter passed as True
            3.output of get_hot_wallet_addresses is of 'set' type (and obviously with no duplicates)
        """
        AvailableHotWalletAddress.objects.create(
            currency=Currencies.eth, network=CurrenciesNetworkName.ETH, address=self.address1, active=True
        )
        AvailableHotWalletAddress.objects.create(
            currency=Currencies.eth, network=CurrenciesNetworkName.ETH, address=self.address2, active=True
        )
        AvailableHotWalletAddress.objects.create(
            currency=Currencies.eth, network=CurrenciesNetworkName.ETH, address=self.address2, active=True
        )  # This is duplicate in purpose
        # when keep_case parameter passed as True, and we expect the function to do not touch the addresses case
        cache.set('hot_address_on_ETH', None, 24 * 60 * 60)
        eth_addresses_by_currency_with_keep_case = get_hot_wallet_addresses(currency=Currencies.eth, keep_case=True)
        eth_addresses_by_network_with_keep_case = get_hot_wallet_addresses(network_symbol=CurrenciesNetworkName.ETH,
                                                                           keep_case=True)
        assert eth_addresses_by_network_with_keep_case == eth_addresses_by_currency_with_keep_case == {self.address1,
                                                                                                       self.address2}
        # when keep_case parameter is False (by default) outputs are all lower
        eth_addresses_by_currency = get_hot_wallet_addresses(currency=Currencies.eth)
        eth_addresses_by_network = get_hot_wallet_addresses(network_symbol=CurrenciesNetworkName.ETH)
        assert eth_addresses_by_network == eth_addresses_by_currency == {self.address1.lower(), self.address2.lower()}

    def test_cached_data(self):
        """
            This test ensures us get_hot_wallet_addresses function cache addresses which it is got from database
            (so the next time it can be just read from cache instead of make a db call)
        """
        cache.set('hot_address_on_ETH', None, 24 * 60 * 60)
        AvailableHotWalletAddress.objects.create(
            currency=Currencies.eth, network=CurrenciesNetworkName.ETH, address=self.address1, active=True
        )
        address = get_hot_wallet_addresses(network_symbol=CurrenciesNetworkName.ETH)
        assert len(address) == 1
        assert cache.get('hot_address_on_ETH') == list(address)[0]  # because address is a set and the other side is str


class DiffHotWalletTest(TestCase):
    """
        This test is for main 'diff hot wallet' process to make sure it is doing its job in the right way.
        Note 1: This test works only for tag needed currencies. just one address in one currency(stellar)
        to have a fast test, but this can work for a bunch of other addresses in other currencies(tag needed)
        Note 2: The whole diff_hot_wallet process goal is 1- done withdrawrequest xor 2- alert about unauthorized
        withdraw in network (you can refer to diff hot wallet main doc/string doc) for now we just have the test
        for second scenario(to alert when needed)
    """
    address = 'GAQQXWTSEQ62TQXIJVL5PAUIIXQVCDP5KDHXGR6W64YPQBAV2GRVCDDU'

    @pytest.mark.slow
    def test_getting_errors(self):
        """
            This test will ensure us to_done_tagged_withdraws alerts when a withdraw in network has not its matched
            withdrawrequest(s) in database.
        """
        AvailableHotWalletAddress.objects.create(currency=Currencies.xlm,
                                                 network=CurrenciesNetworkName.XLM,
                                                 address=self.address)
        txs = BlockchainExplorer.get_wallet_withdraws(self.address, Currencies.xml, CurrenciesNetworkName.XLM)
        txs = list(filter(lambda tx: tx.value < Decimal('0'), txs))  # because deposits dont matter
        txs = list(map(lambda tx: tx.hash, txs))
        assert set(to_done_tagged_withdraws([Currencies.xlm], return_failed_hashes=True)) == set(txs)

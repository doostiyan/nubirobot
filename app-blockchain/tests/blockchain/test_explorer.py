from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

from exchange.blockchain.api.general.dtos import Balance
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser


class TestExplorer(TestCase):
    def test_get_balances(self):
        ResponseParser.symbol = 'Test'
        ResponseParser.currency = 0
        addresses = ['address1', 'address2', 'address3', 'address4', 'address5']
        expected_balances = [{0: {'symbol': 'Test', 'amount': 1000, 'address': 'address1'}},
                             {0: {'symbol': 'Test', 'amount': 2000, 'address': 'address2'}},
                             {0: {'symbol': 'Test', 'amount': 3000, 'address': 'address3'}},
                             {0: {'symbol': 'Test', 'amount': 4000, 'address': 'address4'}},
                             {0: {'symbol': 'Test', 'amount': 5000, 'address': 'address5'}}]

        # _____SUPPORT_GET_BALANCE_BATCH:True and GET_BALANCES_MAX_ADDRESS_NUM:1000______

        GeneralApi.SUPPORT_GET_BALANCE_BATCH = True
        GeneralApi.BALANCES_NOT_INCLUDE_ADDRESS = True
        GeneralApi.get_balances = Mock(side_effect=[{'not important response'}])
        ResponseParser.parse_balances_response = Mock(side_effect=[
            [Balance(balance=Decimal(1000)),
             Balance(balance=Decimal(2000)), Balance(balance=Decimal(3000)), Balance(balance=Decimal(4000)),
             Balance(
                 balance=Decimal(5000))]])
        ExplorerInterface.balance_apis.append(GeneralApi)
        balances = ExplorerInterface.get_api().get_balances(addresses)
        assert balances == expected_balances

        # _____SUPPORT_GET_BALANCE_BATCH:True and GET_BALANCES_MAX_ADDRESS_NUM:3________

        GeneralApi.SUPPORT_GET_BALANCE_BATCH = True
        GeneralApi.BALANCES_NOT_INCLUDE_ADDRESS = True
        GeneralApi.GET_BALANCES_MAX_ADDRESS_NUM = 3
        GeneralApi.get_balances = Mock(side_effect=[{'not important response'}, {'not important response'}])
        ResponseParser.parse_balances_response = Mock(
            side_effect=[
                [Balance(balance=Decimal(1000)), Balance(balance=Decimal(2000)), Balance(balance=Decimal(3000))],
                [Balance(balance=Decimal(4000)), Balance(balance=Decimal(5000))]])
        balances = ExplorerInterface.get_api().get_balances(addresses)
        assert balances == expected_balances

        # _____SUPPORT_GET_BALANCE_BATCH:False______

        GeneralApi.SUPPORT_GET_BALANCE_BATCH = False
        GeneralApi.get_balance = Mock(side_effect=[{'this'}, {'is'}, {'not'}, {'important'}, {'response'}])
        ResponseParser.parse_balance_response = Mock(side_effect=[1000, 2000, 3000, 4000, 5000])
        ExplorerInterface.balance_apis.append(GeneralApi)
        balances = ExplorerInterface.get_api().get_balances(addresses)
        assert balances == expected_balances

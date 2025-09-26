import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.apt.aptos_explorer_interface import AptosExplorerInterface
from exchange.blockchain.api.apt.aptoslabs_graphql import GraphQlAptosApi
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.utils import BlockchainUtilsMixin


@pytest.mark.slow
class TestGraphQlAptosApiCalls(TestCase):
    api = GraphQlAptosApi
    # address 0x21ddba785f3ae9c6f03664ab07e9ad83595a0fa5ca556cec2b9d9e7100db0f07 return time limit error
    addresses = ['0x187e9c0ebae099ea0b9b228012c25f7c3436ba4ae26b65f15391e4cd476ce784',
                 '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                 '0x8077f27cf9ef625b5d6a1d8cd3be823b68e64aa401e37912280b7a7e443bef19']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert self.check_general_response(get_block_head_response, {'data'})
        assert self.check_general_response(get_block_head_response.get('data'), {'processor_status'})
        assert isinstance(get_block_head_response.get('data').get('processor_status'), list)
        assert self.check_general_response(get_block_head_response.get('data').get('processor_status')[0],
                                           {'processor', 'last_success_version'})
        assert isinstance(get_block_head_response.get('data').get('processor_status')[0].get('last_success_version'),
                          int)

    def test_get_address_txs_api(self):
        data_keys = {'coin_activities', 'processor_status'}
        transaction_keys = {'activity_type', 'event_account_address', 'amount', 'transaction_version', 'block_height',
                            'coin_type', 'entry_function_id_str', 'is_gas_fee', 'is_transaction_success',
                            'owner_address', 'transaction_timestamp'}
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response, {'data'})
            assert self.check_general_response(get_address_txs_response.get('data'), data_keys)
            assert isinstance(get_address_txs_response.get('data').get('processor_status'), list)
            assert self.check_general_response(get_address_txs_response.get('data').get('processor_status')[0],
                                               {'processor', 'last_success_version'})
            assert isinstance(
                get_address_txs_response.get('data').get('processor_status')[0].get('last_success_version'),
                int)
            assert isinstance(get_address_txs_response.get('data').get('coin_activities'), list)
            for transaction in get_address_txs_response.get('data').get('coin_activities'):
                assert self.check_general_response(transaction, transaction_keys)

    def test_get_block_txs_api(self):
        transaction_keys = {'activity_type', 'event_account_address', 'amount', 'transaction_version', 'block_height',
                            'coin_type', 'entry_function_id_str', 'is_gas_fee', 'is_transaction_success',
                            'owner_address', 'transaction_timestamp'}
        get_block_txs_response = self.api.get_batch_block_txs(33255487, 33255495)
        if len(get_block_txs_response) != 0:
            for transaction in get_block_txs_response:
                assert self.check_general_response(transaction, transaction_keys)


class TestGraphQlAptosFromExplorer(TestCase):
    api = GraphQlAptosApi
    # second address has no valid transaction because the amount of it is less than min_tx_value_amount
    addresses = ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                 '0x2cf72a01b9e852938b1ba67b19027798377e15bd09d6524df864a5fb5d199da4']

    @pytest.mark.slow
    def test_get_address_txs(self):
        # The line below is temporary because explorer interface of aptos is not merged yet
        APIS_CONF['APT']['get_txs'] = 'aptos_explorer_interface'
        address_txs_mock_responses = [{'data': {'coin_activities': [{'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 22378860,
                                                                     'transaction_version': 96722562,
                                                                     'block_height': 36903096,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-03-04T10:34:35'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20000000,
                                                                     'transaction_version': 96722533,
                                                                     'block_height': 36903085,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-03-04T10:34:32'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20883123,
                                                                     'transaction_version': 96722393,
                                                                     'block_height': 36903035,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-03-04T10:34:19'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1000000, 'transaction_version': 96722269,
                                                                     'block_height': 36902986,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-03-04T10:34:04'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 601145923,
                                                                     'transaction_version': 89256425,
                                                                     'block_height': 33631200,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-17T19:59:51'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20000000,
                                                                     'transaction_version': 89256408,
                                                                     'block_height': 33631192,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-17T19:59:48'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 425040792,
                                                                     'transaction_version': 89256344,
                                                                     'block_height': 33631164,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-17T19:59:37'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1000000, 'transaction_version': 89256267,
                                                                     'block_height': 33631128,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-17T19:59:21'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 645593200,
                                                                     'transaction_version': 87091054,
                                                                     'block_height': 32707532,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T22:52:10'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20000000,
                                                                     'transaction_version': 87090984,
                                                                     'block_height': 32707501,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T22:51:58'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 832708364,
                                                                     'transaction_version': 87090909,
                                                                     'block_height': 32707468,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T22:51:47'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1000000, 'transaction_version': 87090854,
                                                                     'block_height': 32707445,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T22:51:39'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1539543033,
                                                                     'transaction_version': 86965547,
                                                                     'block_height': 32652834,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T17:13:16'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20000000,
                                                                     'transaction_version': 86965514,
                                                                     'block_height': 32652821,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T17:13:12'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1469490236,
                                                                     'transaction_version': 86965438,
                                                                     'block_height': 32652789,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T17:13:00'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1000000, 'transaction_version': 86965337,
                                                                     'block_height': 32652746,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2023-02-13T17:12:46'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 2438096476,
                                                                     'transaction_version': 47747669,
                                                                     'block_height': 16355359,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-12-10T10:20:08'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20000000,
                                                                     'transaction_version': 47747641,
                                                                     'block_height': 16355348,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-12-10T10:20:05'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1982029930,
                                                                     'transaction_version': 47747536,
                                                                     'block_height': 16355309,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-12-10T10:19:54'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1000000, 'transaction_version': 47747397,
                                                                     'block_height': 16355253,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-12-10T10:19:36'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 3643139320,
                                                                     'transaction_version': 34509081,
                                                                     'block_height': 10950893,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-11-19T11:35:49'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 20000000,
                                                                     'transaction_version': 34509043,
                                                                     'block_height': 10950878,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-11-19T11:35:45'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 3446811892,
                                                                     'transaction_version': 34508956,
                                                                     'block_height': 10950840,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-11-19T11:35:32'},
                                                                    {'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 1000000, 'transaction_version': 34508849,
                                                                     'block_height': 10950793,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-11-19T11:35:14'},
                                                                    {'activity_type': '0x1::coin::WithdrawEvent',
                                                                     'event_account_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'amount': 3005288022,
                                                                     'transaction_version': 29948061,
                                                                     'block_height': 9137250,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
                                                                     'transaction_timestamp': '2022-11-12T18:16:40'}],
                                                'processor_status': [{'last_success_version': 259914863,
                                                                      'processor': 'coin_processor'}]}},
                                      {'data': {'coin_activities': [{'activity_type': '0x1::coin::DepositEvent',
                                                                     'event_account_address': '0x2cf72a01b9e852938b1ba67b19027798377e15bd09d6524df864a5fb5d199da4',
                                                                     'amount': 2000000, 'transaction_version': 43637502,
                                                                     'block_height': 14667156,
                                                                     'coin_type': '0x1::aptos_coin::AptosCoin',
                                                                     'entry_function_id_str': '0x1::aptos_account::transfer',
                                                                     'is_gas_fee': False,
                                                                     'is_transaction_success': True,
                                                                     'owner_address': '0x2cf72a01b9e852938b1ba67b19027798377e15bd09d6524df864a5fb5d199da4',
                                                                     'transaction_timestamp': '2022-12-03T19:32:38'}],
                                                'processor_status': [
                                                    {'last_success_version': 58722262, 'processor': 'coin_processor'}]}}
                                      ]
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        AptosExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            [{'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '96722562',
              'block': 96722562,
              'timestamp': datetime.datetime(2023, 3, 4, 10, 34, 35, tzinfo=UTC), 'value': Decimal(
                    '-0.22378860'), 'confirmations': 163192301, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '96722533',
              'block': 96722533, 'timestamp': datetime.datetime(2023, 3, 4, 10, 34, 32, tzinfo=UTC), 'value': Decimal(
                 '-0.20000000'), 'confirmations': 163192330, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': [], 'hash': '96722393', 'block': 96722393,
              'timestamp': datetime.datetime(2023, 3, 4, 10, 34, 19, tzinfo=UTC), 'value': Decimal(
                 '0.20883123'), 'confirmations': 163192470, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '89256425',
              'block': 89256425, 'timestamp': datetime.datetime(2023, 2, 17, 19, 59, 51, tzinfo=UTC), 'value': Decimal(
                 '-6.01145923'), 'confirmations': 170658438, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '89256408',
              'block': 89256408, 'timestamp': datetime.datetime(2023, 2, 17, 19, 59, 48, tzinfo=UTC), 'value': Decimal(
                 '-0.20000000'), 'confirmations': 170658455, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': [], 'hash': '89256344', 'block': 89256344,
              'timestamp': datetime.datetime(2023, 2, 17, 19, 59, 37, tzinfo=UTC), 'value': Decimal(
                 '4.25040792'), 'confirmations': 170658519, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '87091054',
              'block': 87091054, 'timestamp': datetime.datetime(2023, 2, 13, 22, 52, 10, tzinfo=UTC), 'value': Decimal(
                 '-6.45593200'), 'confirmations': 172823809, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '87090984',
              'block': 87090984, 'timestamp': datetime.datetime(2023, 2, 13, 22, 51, 58, tzinfo=UTC), 'value': Decimal(
                 '-0.20000000'), 'confirmations': 172823879, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': [], 'hash': '87090909', 'block': 87090909,
              'timestamp': datetime.datetime(2023, 2, 13, 22, 51, 47, tzinfo=UTC), 'value': Decimal(
                 '8.32708364'), 'confirmations': 172823954, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '86965547',
              'block': 86965547, 'timestamp': datetime.datetime(2023, 2, 13, 17, 13, 16, tzinfo=UTC), 'value': Decimal(
                 '-15.39543033'), 'confirmations': 172949316, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '86965514',
              'block': 86965514, 'timestamp': datetime.datetime(2023, 2, 13, 17, 13, 12, tzinfo=UTC), 'value': Decimal(
                 '-0.20000000'), 'confirmations': 172949349, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': [], 'hash': '86965438', 'block': 86965438,
              'timestamp': datetime.datetime(2023, 2, 13, 17, 13, tzinfo=UTC), 'value': Decimal(
                 '14.69490236'), 'confirmations': 172949425, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '47747669',
              'block': 47747669, 'timestamp': datetime.datetime(2022, 12, 10, 10, 20, 8, tzinfo=UTC), 'value': Decimal(
                 '-24.38096476'), 'confirmations': 212167194, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '47747641',
              'block': 47747641, 'timestamp': datetime.datetime(2022, 12, 10, 10, 20, 5, tzinfo=UTC), 'value': Decimal(
                 '-0.20000000'), 'confirmations': 212167222, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': [], 'hash': '47747536', 'block': 47747536,
              'timestamp': datetime.datetime(2022, 12, 10, 10, 19, 54, tzinfo=UTC), 'value': Decimal(
                 '19.82029930'), 'confirmations': 212167327, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '34509081',
              'block': 34509081, 'timestamp': datetime.datetime(2022, 11, 19, 11, 35, 49, tzinfo=UTC), 'value': Decimal(
                 '-36.43139320'), 'confirmations': 225405782, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '34509043',
              'block': 34509043, 'timestamp': datetime.datetime(2022, 11, 19, 11, 35, 45, tzinfo=UTC), 'value': Decimal(
                 '-0.20000000'), 'confirmations': 225405820, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': [], 'hash': '34508956', 'block': 34508956,
              'timestamp': datetime.datetime(2022, 11, 19, 11, 35, 32, tzinfo=UTC), 'value': Decimal(
                 '34.46811892'), 'confirmations': 225405907, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None},
             {'contract_address': None, 'address': '0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b',
              'from_address': ['0xc0f3774ae4bd6ed534b110b7a792e415a007849d94bb132a41e9aca76c5b259b'],
              'hash': '29948061',
              'block': 29948061, 'timestamp': datetime.datetime(2022, 11, 12, 18, 16, 40, tzinfo=UTC), 'value': Decimal(
                 '-30.05288022'), 'confirmations': 229966802, 'is_double_spend': False, 'details': {}, 'tag': None,
              'huge': False, 'invoice': None}]

            , []
        ]
        for address, expected_address_txs in zip(self.addresses, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.apt, 'APT')
            assert len(expected_address_txs) == len(address_txs.get(Currencies.apt))
            if len(expected_address_txs) != 0:
                for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.apt)):
                    assert address_tx.confirmations >= expected_address_tx.get('confirmations')
                    address_tx.confirmations = expected_address_tx.get('confirmations')
                    assert address_tx.__dict__ == expected_address_tx

    @pytest.mark.slow
    def test_get_block_txs(self):
        cache.delete('latest_block_height_processed_apt')
        block_txs_mock_responses = [
            {'data': {'processor_status': [{'last_success_version': 259943716, 'processor': 'coin_processor'}]}},
            {'data': {'coin_activities': [
                {'activity_type': '0x1::coin::WithdrawEvent', 'amount': 3142650, 'transaction_version': 259948380,
                 'block_height': 91579833, 'coin_type': '0x1::aptos_coin::AptosCoin',
                 'entry_function_id_str': '0x1::aptos_account::transfer', 'is_gas_fee': False,
                 'is_transaction_success': True,
                 'owner_address': '0x834d639b10d20dcb894728aa4b9b572b2ea2d97073b10eacb111f338b20ea5d7',
                 'transaction_timestamp': '2023-09-12T14:17:53'},
                {'activity_type': '0x1::coin::DepositEvent', 'amount': 3142650, 'transaction_version': 259948380,
                 'block_height': 91579833, 'coin_type': '0x1::aptos_coin::AptosCoin',
                 'entry_function_id_str': '0x1::aptos_account::transfer', 'is_gas_fee': False,
                 'is_transaction_success': True,
                 'owner_address': '0xe3f495c6ffbcc03b7d3a12ca601df7da744dd733dd4b083d88990752d60a919f',
                 'transaction_timestamp': '2023-09-12T14:17:53'}]}}]
        self.api.request = Mock(side_effect=block_txs_mock_responses)
        settings.USE_TESTNET_BLOCKCHAINS = False
        AptosExplorerInterface.block_txs_apis[0] = self.api
        expected_txs_addresses = {
            'output_addresses': {'0xe3f495c6ffbcc03b7d3a12ca601df7da744dd733dd4b083d88990752d60a919f'},
            'input_addresses': {'0x834d639b10d20dcb894728aa4b9b572b2ea2d97073b10eacb111f338b20ea5d7'}}
        expected_txs_info = {
            'outgoing_txs': {
                '0x834d639b10d20dcb894728aa4b9b572b2ea2d97073b10eacb111f338b20ea5d7':
                    {Currencies.apt: [{'contract_address': None,
                                       'tx_hash': '259948380',
                                       'value': Decimal('0.03142650'),
                                       'block_height': 259948380, 'symbol':'APT'
                                       }]}
            },
            'incoming_txs': {
                '0xe3f495c6ffbcc03b7d3a12ca601df7da744dd733dd4b083d88990752d60a919f':
                    {Currencies.apt: [{'contract_address': None,
                                       'tx_hash': '259948380',
                                       'value': Decimal('0.03142650'),
                                       'block_height': 259948380, 'symbol':'APT'
                                       }]}
            }
        }
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('APT', None, None, True, True)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)

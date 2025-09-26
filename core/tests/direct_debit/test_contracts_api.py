import copy
from datetime import timedelta
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import get_earliest_time, get_latest_time, ir_now
from exchange.base.serializers import serialize
from exchange.direct_debit.models import DirectDebitContract
from tests.direct_debit.helper import DirectDebitMixins


class ContractsApiTests(DirectDebitMixins, APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.request_feature(self.user, 'done')

    def test_contract_list_output_keys(self):
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.waiting_for_confirm)
        contract = DirectDebitContract.objects.filter(user=self.user).first()
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK, (response.status_code, status.HTTP_200_OK)
        data = response.json()
        status_data = 'ok'
        assert data['status'] == status_data, (data['status'], status_data)
        assert len(data['contracts']) == 1, data['contracts']
        self._assert_contract_value(data['contracts'][0], contract)

    def test_contract_list_for_contracts_with_all_statuses(self):
        for contract_status in DirectDebitContract.STATUS:
            self.create_contract(user=self.user, status=contract_status[0])
        contracts = sorted(DirectDebitContract.objects.filter(user=self.user), key=lambda c: c.pk)
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert (
            len(data['contracts']) == len(DirectDebitContract.STATUS) - 2
        )  # waiting_for_updates and failed_update are excluded
        sorted_responses = sorted(data['contracts'], key=lambda contract: contract['id'])
        for response, contract in zip(sorted_responses, contracts):
            if contract.status != DirectDebitContract.STATUS.waiting_for_update:
                self._assert_contract_value(response, contract)

    def test_contract_list_with_direct_deposits_for_one_contract(self):
        nw = ir_now()
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        self.create_contract(user=self.user2, status=DirectDebitContract.STATUS.active)
        contract1 = DirectDebitContract.objects.filter(user=self.user).first()
        contract2 = DirectDebitContract.objects.filter(user=self.user2).first()

        # No direct deposits
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == 1
        self._assert_contract_value(data['contracts'][0], contract1, trx_count=0, trx_amount=Decimal(0))

        # User2 deposits
        self.create_deposit(user=self.user2, amount=Decimal(50_000_0), contract=contract2)
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == 1
        self._assert_contract_value(data['contracts'][0], contract1, trx_count=0, trx_amount=Decimal(0))

        # Only one deposit for today
        deposit1 = self.create_deposit(user=self.user, amount=Decimal(60_000_0), contract=contract1)
        deposit1.created_at = nw - timedelta(days=2)
        deposit1.save(update_fields={'created_at'})

        deposit2 = self.create_deposit(user=self.user, amount=Decimal(70_000_0), contract=contract1)
        deposit2.created_at = nw + timedelta(days=1)
        deposit2.deposited_at = nw - timedelta(days=1)
        deposit2.save(update_fields={'created_at', 'deposited_at'})

        deposit3 = self.create_deposit(user=self.user, amount=Decimal(80_000_0), contract=contract1)
        deposit3.deposited_at = nw + timedelta(days=1)
        deposit3.save(update_fields={'deposited_at'})

        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == 1
        self._assert_contract_value(data['contracts'][0], contract1, trx_count=1, trx_amount=Decimal(60_000_0))

        # Multiple deposits for today
        deposit4 = self.create_deposit(user=self.user, amount=Decimal(90_000_0), contract=contract1)
        deposit4.deposited_at = get_latest_time(nw)
        deposit4.save(update_fields={'deposited_at'})

        deposit5 = self.create_deposit(user=self.user, amount=Decimal(100_000_0), contract=contract1)
        deposit5.deposited_at = get_earliest_time(nw)
        deposit5.save(update_fields={'deposited_at'})

        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == 1
        self._assert_contract_value(data['contracts'][0], contract1, trx_count=3, trx_amount=Decimal(250_000_0))

    def test_contract_list_with_direct_deposits_for_multiple_contracts(self):
        nw = ir_now()
        for _ in range(3):
            self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        contracts = sorted(DirectDebitContract.objects.filter(user=self.user), key=lambda c: c.pk)

        self.create_deposit(
            user=self.user,
            amount=Decimal(100_000_0),
            contract=contracts[1],
            deposited_at=get_latest_time(nw),
        )

        self.create_deposit(
            user=self.user,
            amount=Decimal(110_000_0),
            contract=contracts[2],
            deposited_at=get_earliest_time(nw),
        )

        self.create_deposit(
            user=self.user,
            amount=Decimal(120_000_0),
            contract=contracts[2],
            deposited_at=nw,
        )

        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == len(contracts)
        response_contracts = sorted(data['contracts'], key=lambda c: c['id'])
        trx_counts = [0, 1, 2]
        trx_amounts = [Decimal(0), Decimal(100_000_0), Decimal(230_000_0)]
        for idx, contract in enumerate(contracts):
            self._assert_contract_value(
                response_contracts[idx],
                contract,
                trx_count=trx_counts[idx],
                trx_amount=trx_amounts[idx],
            )

    def test_contract_list_with_direct_deposits_for_multiple_contracts_include_updated_contracts(self):
        nw = ir_now()

        # contract without update ---
        contract1 = self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        self.create_deposit(
            user=self.user,
            amount=Decimal(100_000_0),
            contract=contract1,
            deposited_at=get_latest_time(nw),
        )
        # ---------------------------------

        # this contract has updated one time ---
        contract2 = self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        self.create_deposit(
            user=self.user,
            amount=Decimal(110_000_0),
            contract=contract2,
            deposited_at=get_earliest_time(nw),
        )

        old_contract2 = copy.deepcopy(contract2)
        old_contract2.id = None
        old_contract2.status = DirectDebitContract.STATUS.replaced
        old_contract2.save()
        self.create_deposit(
            user=self.user,
            amount=Decimal(100_000_0),
            contract=old_contract2,
            deposited_at=nw,
        )
        # ---------------------------------

        # this contract has updated more ---
        contract3 = self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        self.create_deposit(
            user=self.user,
            amount=Decimal(130_000_0),
            contract=contract3,
            deposited_at=nw,
        )

        old_contract3_1 = copy.deepcopy(contract3)
        old_contract3_1.id = None
        old_contract3_1.status = DirectDebitContract.STATUS.replaced
        old_contract3_1.save()
        self.create_deposit(
            user=self.user,
            amount=Decimal(100_000_0),
            contract=old_contract3_1,
            deposited_at=nw,
        )

        old_contract3_2 = copy.deepcopy(contract3)
        old_contract3_2.id = None
        old_contract3_2.status = DirectDebitContract.STATUS.replaced
        old_contract3_2.save()
        self.create_deposit(
            user=self.user,
            amount=Decimal(110_000_0),
            contract=old_contract3_2,
            deposited_at=nw,
        )
        # ---------------------------------

        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == 6  # 3 active and 3 replaced

        active_contracts = [_contract for _contract in data['contracts'] if _contract['status'] == 'Active']
        replaced_contracts = [_contract for _contract in data['contracts'] if _contract['status'] == 'Replaced']
        assert len(active_contracts) == 3
        assert len(replaced_contracts) == 3

        response_contracts = sorted(active_contracts, key=lambda c: c['id'])
        contracts = sorted(
            DirectDebitContract.objects.filter(
                user=self.user,
                status=DirectDebitContract.STATUS.active,
            ),
            key=lambda c: c.pk,
        )
        self._assert_contract_value(response_contracts[0], contracts[0], trx_count=1, trx_amount=Decimal(100_000_0))

        self._assert_contract_value(response_contracts[1], contracts[1], trx_count=2, trx_amount=Decimal(210_000_0))

        self._assert_contract_value(response_contracts[2], contracts[2], trx_count=3, trx_amount=Decimal(340_000_0))

    def test_contract_list_with_no_contract(self):
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert len(data['contracts']) == 0

    def test_user_cant_see_other_contracts(self):
        self.create_contract(user=self.user2, status=DirectDebitContract.STATUS.waiting_for_confirm)
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK, (response.status_code, status.HTTP_200_OK)
        data = response.json()
        status_data = 'ok'
        assert data['status'] == status_data, (data['status'], status_data)
        assert len(data['contracts']) == 0, data['contracts']

    def test_required_user_authentication_for_api(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token wrong_token'
        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'توکن غیر مجاز'}

    def test_contract_list_with_status_filter(self):
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.replaced)
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.waiting_for_confirm)

        response = self.client.get(path='/direct-debit/contracts?status=Active')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 1
        assert data['contracts'][0]['status'] == 'Active'

        response = self.client.get(path='/direct-debit/contracts?status=Active,Replaced')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 2
        assert {contract['status'] for contract in data['contracts']} == {'Active', 'Replaced'}

        response = self.client.get(path='/direct-debit/contracts?status=Invalid')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 3

        response = self.client.get(path='/direct-debit/contracts?status=Active,Invalid')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 1
        assert data['contracts'][0]['status'] == 'Active'

    def test_list_with_status_filter_in_lower_case(self):
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.initializing)
        response = self.client.get(path='/direct-debit/contracts?status=initializing')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 1
        assert data['contracts'][0]['status'] == 'Initializing'

    def test_contract_list_pagination(self):
        for _ in range(15):
            self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)

        response = self.client.get(path='/direct-debit/contracts?page=1&pageSize=10')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 10
        assert data['has_next'] is True

        response = self.client.get(path='/direct-debit/contracts?page=2&pageSize=10')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 5
        assert data['has_next'] is False

        response = self.client.get(path='/direct-debit/contracts?pageSize=10')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 10
        assert data['has_next'] is True

        response = self.client.get(path='/direct-debit/contracts?page=1')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data['contracts']) == 15
        assert data['has_next'] is False

    def test_contract_list_ordering(self):
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.replaced)
        self.create_contract(user=self.user, status=DirectDebitContract.STATUS.active)

        response = self.client.get(path='/direct-debit/contracts')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        contracts = data['contracts']

        assert len(contracts) == 3
        assert contracts[0]['status'] == 'Active'
        assert contracts[1]['status'] == 'Active'
        assert contracts[2]['status'] == 'Replaced'

    def _assert_contract_value(
        self,
        response: dict,
        contract: DirectDebitContract,
        trx_count: int = 0,
        trx_amount: Decimal = Decimal(0),
    ):
        required_keys = [
            'id',
            'status',
            'createdAt',
            'contractCode',
            'startedAt',
            'expiresAt',
            'dailyMaxTransactionCount',
            'dailyMaxTransactionAmount',
            'bank',
            'todayTransactionCount',
            'todayTransactionAmount',
        ]
        for key in required_keys:
            assert key in response
            if key == 'bank':
                assert 'bankName' in response[key]
                assert 'bankID' in response[key]

        assert response['id'] == contract.id
        assert response['dailyMaxTransactionCount'] == contract.daily_max_transaction_count
        assert response['dailyMaxTransactionAmount'] == serialize(contract.bank.daily_max_transaction_amount)
        assert response['maxTransactionAmount'] == serialize(contract.max_transaction_amount)
        assert response['status'] == contract.get_status_display()
        assert response['createdAt'] == serialize(contract.created_at)
        assert response['startedAt'] == serialize(contract.started_at)
        assert response['expiresAt'] == serialize(contract.expires_at)
        assert response['bank'] == serialize(contract.bank, opts={'bank_name_only': True})
        assert response['todayTransactionCount'] == trx_count
        assert response['todayTransactionAmount'] == serialize(trx_amount)

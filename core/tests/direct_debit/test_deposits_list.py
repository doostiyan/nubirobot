from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.direct_debit.models import DirectDeposit
from tests.direct_debit.helper import DirectDebitMixins


class DirectDepositAPITest(APITestCase, DirectDebitMixins):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.request_feature(self.user, 'done')
        self.contract = self.create_contract(user=self.user)
        self.contract.trace_id = 'cdklcdke-b7jk-5hg-997c-b991acdac3b6'
        self.contract.contract_id = 'kr7JBZLrkMNZ'
        self.contract.save()

    def _test_deposit(self, deposit, expected_deposit):
        assert deposit['status'] == expected_deposit['status']
        assert deposit['amount'] == expected_deposit['amount']
        assert deposit['fee'] == expected_deposit['fee']

    def test_deposit_list_none(self):
        data = self.client.get('/users/wallets/deposits/list').json()
        assert not data.get('deposits')

    def test_deposit_list(self):
        deposit = self.create_deposit(user=self.user, contract=self.contract)
        deposit.status = DirectDeposit.STATUS.succeed
        deposit.save()
        data = self.client.get('/users/wallets/deposits/list').json()
        expected_deposit = {
            'status': 'Succeed',
            'amount': '100000000',
            'fee': '50000',
        }
        deposit = data.get('deposits')[0]

        self._test_deposit(deposit, expected_deposit)

        deposit2 = self.create_deposit(user=self.user)
        deposit2.status = DirectDeposit.STATUS.succeed
        deposit2.save()

        data = self.client.get('/users/wallets/deposits/list').json()
        assert len(data.get('deposits')) == 2

    def test_only_visible_statuses_are_returned(self):
        visible_statuses = DirectDeposit.USER_VISIBLE_STATUES
        all_statuses = [_status for _status in DirectDeposit.STATUS._identifier_map.values()]

        deposits = []
        for _status in all_statuses:
            deposit = self.create_deposit(user=self.user, contract=self.contract, status=_status)
            deposits.append(deposit)

        response = self.client.get('/users/wallets/deposits/list')
        data = response.json()

        assert response.status_code == status.HTTP_200_OK

        returned_statuses = [deposit['status'] for deposit in data.get('deposits', [])]
        status_label_mapping = dict(DirectDeposit.STATUS)
        expected_statuses = [status_label_mapping[_status] for _status in visible_statuses]
        self.assertCountEqual(returned_statuses, expected_statuses)

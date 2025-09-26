import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.serializers import serialize
from exchange.direct_debit.models import DirectDebitContract
from tests.base.utils import check_response
from tests.direct_debit.helper import DirectDebitMixins


class ChangeContractStatusTests(DirectDebitMixins, TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.save()

        self.user2 = User.objects.get(id=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.url = '/direct-debit/contracts/{}'
        self.request_feature(self.user, 'done')
        self.api_url = f'{self.base_url}/v1/payman/status/change'
        cache.set('direct_debit_access_token', 'test_direct_debit_access_token')

    def _send_request(self, pk: int, status: str = ''):
        data = {
            'newStatus': status,
        }
        url = self.url.format(pk)
        return self.client.post(url, data=data)

    def test_contract_change_status_invalid_params(self):
        response = self._send_request(1)
        check_response(response, 400, 'failed', 'ParseError', 'Missing string value')

    def test_contract_change_status_not_found_contract(self):
        response = self._send_request(1, 'active')
        assert response.status_code == 404

    def test_contract_change_status_not_acceptable_status(self):
        contract = self.create_contract(self.user)
        assert contract.status == DirectDebitContract.STATUS.active

        response = self._send_request(contract.id, 'waiting')  # invalid status
        check_response(
            response,
            400,
            'failed',
            'NewStatusValidationError',
            'The new_status is not valid!',
        )

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.active

    def test_contract_change_status_is_cancelled(self):
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.cancelled)
        assert contract.status == DirectDebitContract.STATUS.cancelled

        response = self._send_request(contract.id, 'deactive')
        check_response(
            response,
            422,
            'failed',
            'InvalidStatusError',
            'Current contract status is not changeable',
        )

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.cancelled

    @responses.activate
    def test_contract_change_status_successful(self):
        new_status = 'deactive'
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.active)
        assert contract.status == DirectDebitContract.STATUS.active

        responses.post(self.api_url, json={'payman_id': contract.contract_id, 'status': new_status})
        response = self._send_request(contract.id, new_status)
        contract.refresh_from_db()
        check_response(
            response,
            200,
            'ok',
            special_key='contract',
            special_value=serialize(contract),
        )
        assert contract.status == DirectDebitContract.STATUS.deactive

    def test_change_contract_status_user_eligibility(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

        new_status = 'deactive'
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.active)
        assert contract.status == DirectDebitContract.STATUS.active

        response = self._send_request(contract.id, new_status)
        assert response.status_code == 400
        assert response.json() == {
            'code': 'UserLevelRestriction',
            'message': 'User level does not meet the requirements',
            'status': 'failed',
        }

    @responses.activate
    def test_contract_change_status_disabled_bank(self):
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.active)
        assert contract.status == DirectDebitContract.STATUS.active

        # active --> cancelled --- should be ok - bank is active
        assert contract.bank.is_active is True
        responses.post(self.api_url, json={'payman_id': contract.contract_id, 'status': 'cancelled'})
        response = self._send_request(contract.id, 'cancelled')
        contract.refresh_from_db()
        check_response(
            response,
            200,
            'ok',
            special_key='contract',
            special_value=serialize(contract),
        )
        assert contract.status == DirectDebitContract.STATUS.cancelled

        # active --> cancelled --- should be ok - bank is not active
        contract.status = contract.STATUS.active
        contract.save()
        contract.bank.is_active = False
        contract.bank.save()
        assert contract.status == DirectDebitContract.STATUS.active
        assert contract.bank.is_active is False
        responses.post(self.api_url, json={'payman_id': contract.contract_id, 'status': 'cancelled'})
        response = self._send_request(contract.id, 'cancelled')
        print(response.json())
        contract.refresh_from_db()
        check_response(
            response,
            200,
            'ok',
            special_key='contract',
            special_value=serialize(contract),
        )
        assert contract.status == DirectDebitContract.STATUS.cancelled

        contract.status = DirectDebitContract.STATUS.active
        contract.save()

        # deactive --> active --- should raise error
        assert contract.bank.is_active is False
        response = self._send_request(contract.id, 'deactive')
        check_response(
            response=response,
            status_code=422,
            status_data='failed',
            code='DeactivatedBankError',
            message='The bank is not active',
        )
        assert contract.status == DirectDebitContract.STATUS.active

        contract.status = DirectDebitContract.STATUS.deactive
        contract.save()

        # deactive --> active --- should raise error
        response = self._send_request(contract.id, 'active')
        check_response(
            response=response,
            status_code=422,
            status_data='failed',
            code='DeactivatedBankError',
            message='The bank is not active',
        )
        assert contract.status == DirectDebitContract.STATUS.deactive

    def test_contract_change_status_to_same_status(self):
        new_status = 'deactive'
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.deactive)
        assert contract.status == DirectDebitContract.STATUS.deactive

        response = self._send_request(contract.id, new_status)
        check_response(
            response,
            400,
            'failed',
            'ValueError',
            'Cannot change contract status to the same status.',
        )

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.deactive

    def test_contract_change_status_integrity_error(self):
        new_status = 'active'
        bank = self.create_bank()
        self.create_contract(self.user, bank=bank, status=DirectDebitContract.STATUS.active)
        contract = self.create_contract(self.user, bank=bank, status=DirectDebitContract.STATUS.deactive)
        assert contract.status == DirectDebitContract.STATUS.deactive

        response = self._send_request(contract.id, new_status)
        check_response(
            response,
            400,
            'failed',
            'ContractIntegrityError',
            'The user has an active contract with this bank',
        )

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.deactive

    @responses.activate
    def test_contract_change_status_faraboom_failed(self):
        new_status = 'deactive'
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.active)
        assert contract.status == DirectDebitContract.STATUS.active

        responses.post(
            self.api_url,
            json={
                'error': 'وضعیت قابل تغییر نمی باشد',
                'code': '2016',
                'errors': [
                    {
                        'error': 'وضعیت قابل تغییر نمی باشد',
                        'code': '2016',
                    },
                ],
            },
            status=400,
        )
        response = self._send_request(contract.id, new_status)
        check_response(
            response,
            400,
            'failed',
            'StatusUnchangedError',
            'The third-party could not change the status',
        )

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.active

    @responses.activate
    def test_contract_change_status_faraboom_failed_with_other_error_code(self):
        new_status = 'deactive'
        contract = self.create_contract(self.user, status=DirectDebitContract.STATUS.active)
        assert contract.status == DirectDebitContract.STATUS.active

        responses.post(
            self.api_url,
            json={
                'code': '2200',
                'error': 'امکان بروزرسانی برای این بانک در حال حاضر غیر فعال است.',
                'errors': [
                    {
                        'code': '2200',
                        'error': 'امکان بروزرسانی برای این بانک در حال حاضر غیر فعال است.',
                    }
                ],
            },
            status=400,
        )
        response = self._send_request(contract.id, new_status)
        check_response(
            response,
            400,
            'failed',
            'StatusUnchangedError',
            'The third-party could not change the status',
        )

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.active

    def test_contract_change_status_of_others(self):
        new_status = 'deactive'
        contract = self.create_contract(self.user2, status=DirectDebitContract.STATUS.active)
        assert contract.status == DirectDebitContract.STATUS.active

        response = self._send_request(contract.id, new_status)
        assert response.status_code == 404

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.active

import json
import os
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import status
from rest_framework.test import APITestCase, override_settings

from exchange.accounts.models import BankAccount, BankCard, UploadedFile, User, VerificationRequest
from exchange.base.models import Settings
from tests.base.utils import set_feature_status


@override_settings(IS_TESTNET=True)
class TestKycApisForTestAccounts(APITestCase):
    @classmethod
    def setUpTestData(cls):
        set_feature_status('kyc2', status=True)

    def setUp(self):
        cache.clear()
        self.user: User = User.objects.get(pk=201)
        self.verification_profile = self.user.get_verification_profile()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        Settings.set('finnotech_verification_api_token', 'XXX')

    def _change_parameters_in_object(self, obj, update_fields: dict):
        obj.__dict__.update(**update_fields)
        obj.save()

    def _change_user_parameters(self, update_fields: Dict[str, str]):
        self._change_parameters_in_object(self.user, update_fields)

    def _setup_user(self, user_params: Dict[str, str], verification_params: Dict[str, str]):
        self._change_parameters_in_object(self.user, user_params)
        self._change_parameters_in_object(self.verification_profile, verification_params)

    def _post_request(self, url: str, data: dict) -> HttpResponse:
        return self.client.post(url, data)

    def _check_response(
        self,
        response: HttpResponse,
        status_code: int,
        status_data: Optional[str] = None,
        code: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Any:
        assert response.status_code == status_code
        data = response.json()
        if status_data:
            assert data['status'] == status_data
        if code:
            assert data['code'] == code
        if message:
            assert data['message'] == message
        return data

    def _check_verification_request(self, verification_request: VerificationRequest):
        user_verification_request = VerificationRequest.objects.filter(
            user=self.user,
            tp=verification_request.tp,
        ).last()
        assert user_verification_request.status == verification_request.status
        assert user_verification_request.api_verification == verification_request.api_verification

    def _check_bank_card(self, bank_card: BankCard):
        card = BankCard.objects.filter(user=self.user).last()
        assert card.card_number == bank_card.card_number
        assert card.confirmed == bank_card.confirmed
        assert card.api_verification == bank_card.api_verification

    def _check_bank_account(self, bank_account: BankAccount):
        iban = BankAccount.objects.filter(user=self.user).last()
        assert iban.shaba_number == bank_account.shaba_number
        assert iban.confirmed == bank_account.confirmed
        assert iban.is_from_bank_card == bank_account.is_from_bank_card
        assert iban.api_verification == bank_account.api_verification

    def _add_to_test_accounts(self, username: str):
        test_accounts: List['str'] = Settings.get_list('username_test_accounts')
        if username not in test_accounts:
            test_accounts.append(username)
            Settings.set_dict('username_test_accounts', test_accounts)

    def _create_fake_data_for_auto_kyc(self):
        self.ufile_main_image = UploadedFile(
            filename=uuid.uuid4(),
            user=self.user,
            tp=UploadedFile.TYPES.kyc_main_image,
        )
        with open(self.ufile_main_image.disk_path, 'w+') as destination:
            destination.write('main_image')
        self.ufile_main_image.save()
        self.addCleanup(os.remove, self.ufile_main_image.disk_path)

        self.ufile_image = UploadedFile(filename=uuid.uuid4(), user=self.user, tp=UploadedFile.TYPES.kyc_image)
        with open(self.ufile_image.disk_path, 'w+') as destination:
            destination.write('gif')
        self.ufile_image.save()
        self.addCleanup(os.remove, self.ufile_image.disk_path)

        self.ufile_video = UploadedFile(filename=uuid.uuid4(), user=self.user, tp=UploadedFile.TYPES.kyc_video)
        with open(self.ufile_video.disk_path, 'w+') as destination:
            destination.write('video')
        self.ufile_video.save()
        self.addCleanup(os.remove, self.ufile_video.disk_path)

    def test_identity_not_in_test_account(self):
        # update user data
        self._setup_user(
            user_params={'user_type': User.USER_TYPES.level0, 'email': 'test@gmail.com', 'mobile': '09120000000'},
            verification_params={'identity_confirmed': False, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        # set identity
        response = self._post_request(
            '/users/profile-edit',
            data={
                'firstName': 'علی',
                'lastName': 'آقا',
                'nationalCode': '6300004554',
                'birthday': '1372-11-15',
            },
        )
        self._check_response(response, status.HTTP_200_OK, 'ok')
        # send identity verification
        response = self._post_request('/users/verify', data={'tp': 'identity'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        self._check_verification_request(
            VerificationRequest(
                tp=VerificationRequest.TYPES.identity,
                status=VerificationRequest.STATUS.confirmed,
                api_verification=json.dumps({'verification': True}),
            ),
        )

    @responses.activate
    def test_identity_verification_call_api_confirmed(self):
        # setup response
        national_code = '6300004554'
        birthday = '1372-11-15'
        first_name = 'علی'
        last_name = 'آقا'
        data_responses = {
            'result': {
                'nationalCode': national_code,
                'birthDate': '1365/11/25',
                'status': 'DONE',
                'fullName': 'علی آقا',
                'fullNameSimilarity': 100,
                'firstName': first_name,
                'firstNameSimilarity': 100,
                'lastName': last_name,
                'lastNameSimilarity': 100,
                'fatherName': 'علی',
                'fatherNameSimilarity': 100,
                'deathStatus': 'زنده',
            },
            'status': 'DONE',
            'trackId': 'nid-inq-9602281200',
        }
        params = {
            'nationalCode': national_code,
            'birthDate': '1372/11/15',
            'firstName': first_name,
            'fullName': 'علی آقا',
            'lastName': last_name,
        }
        responses.get(
            url='https://apibeta.finnotech.ir/oak/v2/clients/nobitex/nidVerification',
            json=data_responses,
            status=200,
            match=[responses.matchers.query_param_matcher(params)],
        )

        # update user data
        self._setup_user(
            user_params={'user_type': User.USER_TYPES.level0, 'email': 'test@gmail.com', 'mobile': '09120000000'},
            verification_params={'identity_confirmed': False, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # set identity
        response = self._post_request(
            '/users/profile-edit',
            data={
                'firstName': first_name,
                'lastName': last_name,
                'nationalCode': national_code,
                'birthday': birthday,
            },
        )
        self._check_response(response, status.HTTP_200_OK, 'ok')
        # send identity verification
        response = self._post_request('/users/verify', data={'tp': 'identity'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        data_responses.update({'verification': True})
        self._check_verification_request(
            VerificationRequest(
                tp=VerificationRequest.TYPES.identity,
                status=VerificationRequest.STATUS.confirmed,
                api_verification=json.dumps(data_responses),
            ),
        )

    @responses.activate
    def test_identity_verification_call_api_rejected(self):
        # setup response
        national_code = '6300004554'
        birthday = '1372-11-15'
        first_name = 'علی'
        last_name = 'آقا'
        data_responses = {
            'result': {
                'nationalCode': national_code,
                'birthDate': '1365/11/25',
                'status': 'DONE',
                'fullName': 'علی آقا',
                'fullNameSimilarity': 100,
                'firstName': first_name,
                'firstNameSimilarity': 100,
                'lastName': last_name,
                'lastNameSimilarity': 100,
                'fatherName': 'علی',
                'fatherNameSimilarity': 100,
                'deathStatus': 'مرده',
            },
            'status': 'DONE',
            'trackId': 'nid-inq-9602281200',
        }
        params = {
            'nationalCode': national_code,
            'birthDate': '1372/11/15',
            'firstName': first_name,
            'fullName': 'علی آقا',
            'lastName': last_name,
        }
        responses.get(
            url='https://apibeta.finnotech.ir/oak/v2/clients/nobitex/nidVerification',
            json=data_responses,
            status=200,
            match=[responses.matchers.query_param_matcher(params)],
        )

        # update user data
        self._setup_user(
            user_params={'user_type': User.USER_TYPES.level0, 'email': 'test@gmail.com', 'mobile': '09120000000'},
            verification_params={'identity_confirmed': False, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # set identity
        response = self._post_request(
            '/users/profile-edit',
            data={
                'firstName': first_name,
                'lastName': last_name,
                'nationalCode': national_code,
                'birthday': birthday,
            },
        )
        self._check_response(response, status.HTTP_200_OK, 'ok')
        # send identity verification
        response = self._post_request('/users/verify', data={'tp': 'identity'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        data_responses.update({'verification': False})
        self._check_verification_request(
            VerificationRequest(
                tp=VerificationRequest.TYPES.identity,
                status=VerificationRequest.STATUS.rejected,
                api_verification=json.dumps(data_responses),
            ),
        )

    def test_mobile_identity_not_in_test_account(self):
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        # change mobile
        response = self._post_request('/users/profile-edit', data={'mobile': '09120000001'})
        self._check_response(response, status.HTTP_200_OK, 'ok')

    @responses.activate
    def test_mobile_identity_call_api_confirmed(self):
        national_code = '6300004554'
        mobile = '09120000001'
        data_responses = {
            'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
            'result': {
                'isValid': True,
            },
            'status': 'DONE',
        }
        params = {'nationalCode': national_code, 'mobile': mobile}
        responses.get(
            url='https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify',
            json=data_responses,
            status=200,
            match=[responses.matchers.query_param_matcher(params)],
        )
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # change mobile
        response = self._post_request('/users/profile-edit', data={'mobile': mobile})
        self._check_response(response, status.HTTP_200_OK, 'ok')

    @responses.activate
    def test_mobile_identity_call_api_rejected(self):
        national_code = '6300004554'
        mobile = '09120000001'
        data_responses = {
            'trackId': 'b14bade6-77a3-4d62-9f5a-9a46af700dce',
            'result': {
                'isValid': False,
            },
            'status': 'DONE',
        }
        params = {'nationalCode': national_code, 'mobile': mobile}
        responses.get(
            url='https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/shahkar/verify',
            json=data_responses,
            status=200,
            match=[responses.matchers.query_param_matcher(params)],
        )
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # change mobile
        response = self._post_request('/users/profile-edit', data={'mobile': mobile})
        self._check_response(response, status.HTTP_200_OK, 'failed', 'ValidationError', 'NotOwnedByUser')

    def test_address_verification_in_test_account(self):
        # the new KYC process remains the same whether a user is added to the test list or not.
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # change mobile
        response = self._post_request('/users/profile-edit', data={'address': 'تهران', 'city': 'تهران'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        # send identity verification
        response = self._post_request('/users/verify', data={'tp': 'address'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        self._check_verification_request(
            VerificationRequest(
                tp=VerificationRequest.TYPES.address,
                status=VerificationRequest.STATUS.new,
                api_verification=None,
            ),
        )

    def test_selfie_verification_in_test_account(self):
        # the new KYC process remains the same whether a user is added to the test list or not.
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
                'city': 'تهران',
                'address': 'تهران',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
                'address_confirmed': True,
            },
        )
        self._add_to_test_accounts(self.user.username)
        # load fake data for verification request
        self._create_fake_data_for_auto_kyc()
        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'image/jpeg']
            response = self._post_request(
                '/users/verify',
                data={
                    'tp': 'selfie',
                    'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                    'explanations': 'for test',
                },
            )
            self._check_response(response, status.HTTP_200_OK, 'ok')
            self._check_verification_request(
                VerificationRequest(
                    tp=VerificationRequest.TYPES.selfie,
                    status=VerificationRequest.STATUS.new,
                    api_verification=None,
                ),
            )

    def test_auto_kyc_verification_not_in_test_account(self):
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
                'city': 'تهران',
                'address': 'تهران',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
                'address_confirmed': True,
            },
        )
        # load fake data for verification request
        self._create_fake_data_for_auto_kyc()
        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'image/jpeg']
            response = self._post_request(
                '/users/verify',
                data={
                    'tp': 'auto_kyc',
                    'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                    'explanations': 'for test',
                },
            )
            self._check_response(response, status.HTTP_200_OK, 'ok')
            self._check_verification_request(
                VerificationRequest(
                    tp=VerificationRequest.TYPES.auto_kyc,
                    status=VerificationRequest.STATUS.confirmed,
                    api_verification=json.dumps({'verification': True}),
                ),
            )

    @responses.activate
    def test_auto_kyc_verification_call_api_confirmed(self):
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
                'national_serial_number': '123',
                'city': 'تهران',
                'address': 'تهران',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
                'phone_confirmed': True,
                'address_confirmed': True,
            },
        )
        self._add_to_test_accounts(self.user.username)
        # load fake data for verification request
        self._create_fake_data_for_auto_kyc()
        # load response data
        data_responses = {
            'verification_result': {
                'errorCode': '',
                'errorMessage': '',
                'data': {
                    'result': True,
                    'details': {
                        'distance': 0.95465468484,
                    },
                    'duration': 0.95465654654,
                },
            },
            'liveness_result': {
                'errorCode': '',
                'errorMessage': '',
                'data': {
                    'FaceAnchor': '3 of 5 anchor completed',
                    'Duration': 0.225465486,
                    'Score': '0.001546848',
                    'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                    'State': 'true',
                },
            },
        }
        live_face = open(self.ufile_main_image.disk_path, 'rb')
        liveness_clip = open(self.ufile_image.disk_path, 'rb')
        payload = {'ssn': '6300004554', 'serial': '123', 'liveness_threshold': 0.9}
        files = {'live_face': live_face, 'liveness_clip': liveness_clip}
        responses.post(
            url='https://napi.jibit.ir/newalpha/api/authorization',
            json=data_responses,
            status=200,
            match=[responses.matchers.multipart_matcher(files, data=payload)],
        )
        # send request
        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'image/jpeg']
            response = self._post_request(
                '/users/verify',
                data={
                    'tp': 'auto_kyc',
                    'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                    'explanations': 'for test',
                },
            )
            self._check_response(response, status.HTTP_200_OK, 'ok')
            data_responses = {'liveness': data_responses, 'verification': True}
            self._check_verification_request(
                VerificationRequest(
                    tp=VerificationRequest.TYPES.auto_kyc,
                    status=VerificationRequest.STATUS.confirmed,
                    api_verification=json.dumps(data_responses),
                ),
            )

    @responses.activate
    def test_auto_kyc_verification_call_api_rejected(self):
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
                'national_serial_number': '123',
                'city': 'تهران',
                'address': 'تهران',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
                'phone_confirmed': True,
                'address_confirmed': True,
            },
        )
        self._add_to_test_accounts(self.user.username)
        # load fake data for verification request
        self._create_fake_data_for_auto_kyc()
        # load response data
        data_responses = {
            'verification_result': {
                'errorCode': '',
                'errorMessage': '',
                'data': {
                    'result': True,
                    'details': {
                        'distance': 0.95465468484,
                    },
                    'duration': 0.95465654654,
                },
            },
            'liveness_result': {
                'errorCode': '105',
                'errorMessage': 'چهره در فیلم دریافتی یافت نشد',
                'data': '',
            },
        }
        live_face = open(self.ufile_main_image.disk_path, 'rb')
        liveness_clip = open(self.ufile_image.disk_path, 'rb')
        payload = {'ssn': '6300004554', 'serial': '123', 'liveness_threshold': 0.9}
        files = {'live_face': live_face, 'liveness_clip': liveness_clip}
        responses.post(
            url='https://napi.jibit.ir/newalpha/api/authorization',
            json=data_responses,
            status=200,
            match=[responses.matchers.multipart_matcher(files, data=payload)],
        )
        # send request
        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'image/jpeg']
            response = self._post_request(
                '/users/verify',
                data={
                    'tp': 'auto_kyc',
                    'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                    'explanations': 'for test',
                },
            )
            self._check_response(response, status.HTTP_200_OK, 'ok')
            data_responses = {
                'liveness': {
                    'error': 'چهره در فیلم دریافتی یافت نشد',
                },
                'verification': False,
            }
            self._check_verification_request(
                VerificationRequest(
                    tp=VerificationRequest.TYPES.auto_kyc,
                    status=VerificationRequest.STATUS.new,
                    api_verification=json.dumps(data_responses),
                ),
            )

    def test_bank_card_verification_not_in_test_account(self):
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
            },
        )
        # add card
        response = self._post_request('/users/cards-add', {'number': '6037991522518822'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        self._check_bank_card(
            BankCard(
                card_number='6037991522518822',
                confirmed=True,
                api_verification=json.dumps({'verification': True}),
            ),
        )

    def test_bank_card_verification_call_api_confirmed(self):
        # update user data
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
            },
        )
        # add card
        response = self._post_request('/users/cards-add', {'number': '6037991522518822'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        self._check_bank_card(
            BankCard(
                card_number='6037991522518822',
                confirmed=True,
                api_verification=json.dumps({'verification': True}),
            ),
        )

    @responses.activate
    def test_bank_card_verification_call_api_rejected(self):
        # update user data
        self._setup_user(
            user_params={
                'first_name': 'علی',
                'last_name': 'آقا',
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={
                'identity_confirmed': True,
                'mobile_confirmed': True,
                'email_confirmed': True,
            },
        )
        self._add_to_test_accounts(self.user.username)
        # load response data
        data_responses = {
            'result': {
                'destCard': 'xxxx-xxxx-xxxx-3899',
                'name': 'علی آقایی',
                'result': '0',
                'description': 'موفق',
                'doTime': '1396/06/15 12:32:04',
                'bankName': 'بانک تجارت',
            },
            'status': 'DONE',
            'trackId': 'get-cardInfo-0232',
        }
        responses.get(
            url='https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/6037991522518822?sandbox=true',
            json=data_responses,
            status=200,
        )
        # add card
        response = self._post_request('/users/cards-add', {'number': '6037991522518822'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        data_responses.update({'verification': False})
        self._check_bank_card(
            BankCard(
                card_number='6037991522518822',
                confirmed=False,
                api_verification=json.dumps(data_responses),
            ),
        )

    def test_bank_account_verification_not_in_test_account(self):
        self._setup_user(
            user_params={
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        # add banck account
        response = self._post_request('/users/accounts-add', {'shaba': 'IR050120000000000000011111'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        self._check_bank_account(
            BankAccount(
                shaba_number='IR050120000000000000011111',
                confirmed=True,
                api_verification=json.dumps({'verification': True}),
                is_from_bank_card=False,
            ),
        )

    @responses.activate
    def test_bank_account_verification_call_api_confirmed(self):
        # update user data
        self._setup_user(
            user_params={
                'first_name': 'علی',
                'last_name': 'آقایی',
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # load response data
        data_responses = {
            'trackId': 'e716bf23-6e04-4b78-97d7-09d0c3c88b74',
            'result': {
                'IBAN': 'IR460170000000346416632004',
                'bankName': 'بانک ملی ایران',
                'deposit': '0346419332494',
                'depositDescription': 'حساب فعال است',
                'depositComment': '',
                'depositOwners': [
                    {
                        'firstName': 'علی',
                        'lastName': 'آقایی',
                    },
                ],
                'depositStatus': '02',
                'errorDescription': 'بدون خطا',
            },
            'status': 'DONE',
        }
        responses.get(
            url='https://apibeta.finnotech.ir/oak/v2/clients/nobitex/ibanInquiry?iban=IR460170000000346416632004',
            json=data_responses,
            status=200,
        )
        # add banck account
        response = self._post_request('/users/accounts-add', {'shaba': 'IR460170000000346416632004'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        data_responses.update({'verification': True})
        self._check_bank_account(
            BankAccount(
                shaba_number='IR460170000000346416632004',
                confirmed=True,
                api_verification=json.dumps(data_responses),
                is_from_bank_card=False,
            ),
        )

    @responses.activate
    def test_bank_account_verification_call_api_rejected(self):
        # update user data
        self._setup_user(
            user_params={
                'first_name': 'علی',
                'last_name': 'آقا',
                'user_type': User.USER_TYPES.level1,
                'email': 'test@gmail.com',
                'mobile': '09120000000',
                'national_code': '6300004554',
            },
            verification_params={'identity_confirmed': True, 'mobile_confirmed': True, 'email_confirmed': True},
        )
        self._add_to_test_accounts(self.user.username)
        # load response data
        data_responses = {
            'trackId': 'e716bf23-6e04-4b78-97d7-09d0c3c88b74',
            'result': {
                'IBAN': 'IR460170000000346416632004',
                'bankName': 'بانک ملی ایران',
                'deposit': '0346419332494',
                'depositDescription': 'حساب فعال است',
                'depositComment': '',
                'depositOwners': [
                    {
                        'firstName': 'علی',
                        'lastName': 'آقایی',
                    },
                ],
                'depositStatus': '02',
                'errorDescription': 'بدون خطا',
            },
            'status': 'DONE',
        }
        responses.get(
            url='https://apibeta.finnotech.ir/oak/v2/clients/nobitex/ibanInquiry?iban=IR460170000000346416632004',
            json=data_responses,
            status=200,
        )
        # add banck account
        response = self._post_request('/users/accounts-add', {'shaba': 'IR460170000000346416632004'})
        self._check_response(response, status.HTTP_200_OK, 'ok')
        data_responses.update({'verification': False})
        self._check_bank_account(
            BankAccount(
                shaba_number='IR460170000000346416632004',
                confirmed=False,
                api_verification=json.dumps(data_responses),
                is_from_bank_card=False,
            ),
        )

import datetime
import json
import os
import uuid
from typing import Any
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import (
    BankAccount,
    BankCard,
    ChangeMobileRequest,
    Tag,
    UploadedFile,
    User,
    UserEvent,
    UserMergeRequest,
    UserOTP,
    UserPreference,
    UserRestriction,
    UserSms,
    UserTag,
    VerificationProfile,
    VerificationRequest,
)
from exchange.accounts.serializers import serialize_bank_account, serialize_bank_card, serialize_user
from exchange.accounts.views.profile import EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY
from exchange.base.models import Settings
from exchange.base.validators import validate_email
from exchange.features.models import QueueItem
from exchange.security.models import LoginAttempt
from tests.asset_backed_credit.helper import ABCMixins
from tests.base.utils import set_feature_status


class SerializationTest(TestCase):

    def setUp(self):
        cache.clear()
        self.user = User.objects.get(pk=202)
        LoginAttempt.objects.create(user=self.user, ip='31.56.129.161', is_successful=False)

    def test_serialize_user_1(self):
        profile = serialize_user(self.user, opts={})
        assert profile['username'] == 'user2@example.com'
        assert profile['name'] == 'User Two'

    def test_serialize_user_2(self):
        self.user.postal_code = '1111112222'
        self.user.national_serial_number = "test32test"
        self.user.save()
        account1 = BankAccount.objects.create(
            account_number='1', shaba_number='IR27053000000000000000001', bank_id=53,
            user=self.user, owner_name=self.user.get_full_name(), confirmed=False, status=0)
        account2 = BankAccount.objects.create(
            account_number='tester', shaba_number='IR949990052886858901740421', bank_id=BankAccount.BANK_ID.vandar,
            user=self.user, owner_name=self.user.get_full_name(), confirmed=False, status=0)
        card1 = BankCard.objects.create(
            card_number='5022290023811112', bank_id=53, bank_name='پاسارگاد', user=self.user,
            owner_name=self.user.get_full_name(), confirmed=False, status=0)
        card2 = BankCard.objects.create(
            card_number='5022290023811101', bank_id=53, bank_name='پاسارگاد', user=self.user,
            owner_name=self.user.get_full_name(), confirmed=True, status=1)
        sort_key = lambda d: d.get('id', 0)
        cards = [serialize_bank_card(card1), serialize_bank_card(card2)]
        accounts = [serialize_bank_account(account1)]
        payment_accounts = [serialize_bank_account(account2)]
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['username'] == 'user2@example.com'
        assert profile['firstName'] == 'User'
        assert profile['lastName'] == 'Two'
        assert profile['id'] == 202
        assert sorted(profile['bankCards'], key=sort_key) == cards
        assert profile['bankAccounts'] == accounts
        assert profile['paymentAccounts'] == payment_accounts
        assert profile['postalCode'] == '1111112222'
        assert profile['verifications']['nationalSerialNumber'] == True
        # Run again for testing cached values
        profile = serialize_user(self.user, opts={'level': 2})
        assert sorted(profile['bankCards'], key=sort_key) == cards
        assert profile['bankAccounts'] == accounts
        assert profile['paymentAccounts'] == payment_accounts

    def test_serialize_user_2_verifications(self):
        profile = serialize_user(self.user, opts={'level': 2})
        assert not profile['verifications']["email"]
        self.user.email = 'test@test.com'
        self.user.save(update_fields=['email'])
        self.user.do_verify_email()
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["email"]

        assert not profile['verifications']["phone"]
        self.user.phone = '12345678'
        self.user.save(update_fields=['phone'])
        vp = self.user.get_verification_profile()
        vp.phone_confirmed = True
        vp.save()
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["phone"]

        assert not profile['verifications']["mobile"]
        self.user.mobile = '09371234567'
        self.user.save(update_fields=['mobile'])
        self.user.do_verify_mobile()
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["mobile"]

        assert not profile['verifications']["identity"]
        vr = VerificationRequest.objects.create(user=self.user, tp=1, explanations="test")  # confirmed
        vr.status = 2
        vr.save(update_fields=['status'])
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["identity"]

        assert not profile['verifications']["selfie"]
        vr = VerificationRequest.objects.create(user=self.user, tp=3, explanations="test")  # confirmed
        vr.status = 2
        vr.save(update_fields=['status'])
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["selfie"]

        assert not profile['verifications']["auto_kyc"]
        self.user.do_verify_liveness_alpha()
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["auto_kyc"]

        assert not profile['verifications']["bankAccount"]
        account = BankAccount.objects.create(
            account_number='1', shaba_number='IR27053000000000000000001', bank_id=53,
            user=self.user, owner_name=self.user.get_full_name(), confirmed=False, status=0)
        account.confirmed = True
        account.update_status(save=False)
        cache.set('user_{}_bank_info'.format(self.user.pk), {'accounts': [serialize_bank_account(account)]}, 3600)
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["bankAccount"]

        assert not profile['verifications']["bankCard"]
        card1 = BankCard.objects.create(
            card_number='5022290023811112', bank_id=53, bank_name='پاسارگاد', user=self.user,
            owner_name=self.user.get_full_name(), confirmed=False, status=0)
        card1.confirmed = True
        card1.update_status(save=False)
        cache.set('user_{}_bank_info'.format(self.user.pk), {'cards': [serialize_bank_card(card1)]}, 3600)
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["bankCard"]

        assert not profile['verifications']["address"]
        self.user.address = 'خیابان تست سمت راست'
        self.user.city = 'مشهد'
        self.user.do_verify_address()
        self.user.save(update_fields=['address'])
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["address"]
        assert profile['verifications']["city"]

        assert profile['verifications']["phoneCode"]
        self.user.do_verify_phone_code()
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["phoneCode"]

        assert not profile['verifications']["mobileIdentity"]
        vp = self.user.get_verification_profile()
        vp.mobile_identity_confirmed = True
        vp.save()
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['verifications']["mobileIdentity"]

    def test_serialize_user_2_pending_verifications(self):
        profile = serialize_user(self.user, opts={'level': 2})
        assert not profile['pendingVerifications']['auto_kyc']
        VerificationRequest.objects.create(user=self.user, tp=4, explanations="test")
        profile = serialize_user(self.user, opts={'level': 2})
        assert profile['pendingVerifications']['auto_kyc']

    def test_serialize_user_features(self):
        default_features = settings.NOBITEX_OPTIONS['features'].get('enabledFeatures', []) + ['NobitexJibitIDeposit']
        user = self.user
        user.user_type = user.USER_TYPE_LEVEL1

        # Portfolio bit flag
        user.track = QueueItem.BIT_FLAG_PORTFOLIO
        profile = serialize_user(user, opts={'level': 2})
        assert profile['features'] == ['Portfolio'] + default_features
        # Beta status
        user.track = 0
        user.set_beta_status(True)
        f1 = QueueItem.objects.create(user=user, feature=QueueItem.FEATURES.xchange, status=QueueItem.STATUS.waiting)
        profile = serialize_user(user, opts={'level': 2})
        assert profile['features'] == ['Beta'] + default_features
        # Enabled queued features
        f1.status = QueueItem.STATUS.done
        f1.save()
        profile = serialize_user(user, opts={'level': 2})
        assert profile['features'] == ['Xchange', 'Beta'] + default_features

        Settings.set('cobank_check_feature_flag', 'no')
        profile = serialize_user(user, opts={'level': 2})
        assert 'CorporateBanking' in profile['features']

        assert 'CobankCards' not in profile['features']
        Settings.set('cobank_card_check_feature_flag', 'no')
        profile = serialize_user(user, opts={'level': 2})
        assert 'CobankCards' in profile['features']


    def test_serialize_bank_account(self):
        number = '1-777-654'
        shaba = 'IR27053000000100324200001'
        account = BankAccount(id=1, account_number=number, shaba_number=shaba, bank_id=53, user=self.user,
                              owner_name=self.user.get_full_name(), confirmed=False, status=0)
        acc = serialize_bank_account(account)
        assert acc['id'] == 1
        assert acc['number'] == number
        assert acc['shaba'] == shaba
        assert acc['bank'] == 'کار‌آفرین'
        assert acc['owner'] == 'User Two'
        assert acc['confirmed'] is False
        assert acc['status'] == 'new'
        account.confirmed = True
        account.update_status(save=False)
        acc = serialize_bank_account(account)
        assert acc['confirmed'] is True
        assert acc['status'] == 'confirmed'

    def test_serialize_bank_account_blubank(self):
        number = '611828005107169901'
        shaba = 'IR050560611828005107169901'
        account = BankAccount(
            id=1,
            account_number=number,
            shaba_number='IR050560613828005107169901',
            bank_id=53,
            user=self.user,
            owner_name=self.user.get_full_name(),
            confirmed=False,
            status=0,
        )
        acc = serialize_bank_account(account)
        assert acc['number'] == number
        assert acc['shaba'] == 'IR050560613828005107169901'
        assert acc['bank'] == 'کار‌آفرین'

        account.shaba_number = shaba
        account.account_number = '123456789'
        account.save()
        acc = serialize_bank_account(account)
        assert acc['number'] == '123456789'
        assert acc['shaba'] == shaba
        assert acc['bank'] == 'بلوبانک'

    def test_serialize_payment_account(self):
        account_id = 'tester'
        shaba = 'IR949990052886858901740421'
        account = BankAccount(account_number=account_id, bank_id=BankAccount.BANK_ID.vandar, user=self.user)
        account.shaba_number = BankAccount.generate_fake_shaba(account.bank_id, account_id)
        assert account.shaba_number == shaba
        acc = serialize_bank_account(account)
        assert acc['account'] == account_id
        assert acc['service'] == 'وندار'

    def test_serialize_bank_card(self):
        number = '5022290023811112'
        card = BankCard(id=1, card_number=number, bank_id=53, bank_name='پاسارگاد', user=self.user,
                        owner_name=self.user.get_full_name(), confirmed=False, status=0)
        card = serialize_bank_card(card)
        assert card['id'] == 1
        assert card['number'] == '5022-2900-2381-1112'
        assert card['bank'] == 'پاسارگاد'
        assert card['owner'] == 'User Two'
        assert card['confirmed'] is False
        assert card['status'] == 'new'


class TestUserProfile(APITestCase):

    def setUp(self):
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.verification_profile = User.objects.get(id=201).get_verification_profile()
        self.verification_profile.email_confirmed = True
        self.verification_profile.save()

    def test_uneditable_profiles(self):
        user = User.objects.get(id=201)
        user.national_code = '0011000058'
        user.mobile = '09192039842'
        user.address = 'tehran'
        user.phone = '0216655799'
        user.user_type = User.USER_TYPES.level2
        user.save()
        vp = user.get_verification_profile()
        vp.phone_confirmed = True
        vp.identity_confirmed = False
        vp.save()
        # Unauthorized update
        r = self.client.post('/users/profile-edit', data={
            'firstName': 'آرش', 'lastName': 'دباغ', 'nationalCode': '6300004554',
            'mobile': '09192039988', 'address': 'تبریز', 'phone': '02166557766',
        }).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'UserLevelRestriction'
        assert r['message'] == 'FirstNameUneditable'
        user.refresh_from_db()
        assert user.first_name == 'User'
        assert user.last_name == 'One'
        assert user.national_code == '0011000058'
        assert user.mobile == '09192039842'
        assert user.address == 'tehran'
        assert user.phone == '0216655799'

    def test_profile_edit_track(self):
        url = '/users/profile-edit'
        user = User.objects.get(id=201)
        assert user.track is None
        # Enable alpha
        r = self.client.post(url, {'track': 12288}).json()
        assert r['status'] == 'ok'
        assert r['updates'] == 1
        user.refresh_from_db()
        assert user.track == 12288
        # Normal
        r = self.client.post(url, {'track': 0}).json()
        assert r['status'] == 'ok'
        assert r['updates'] == 1
        user.refresh_from_db()
        assert user.track == 0
        # Invalid track
        r = self.client.post(url, {'track': 40000}).json()
        assert r['status'] == 'ok'
        assert r['updates'] == 0
        user.refresh_from_db()
        assert user.track == 0

    def test_profile_edit_enabled_by_kyc2(self):
        user = User.objects.get(id=201)
        user.email = None
        user.mobile = None
        user.user_type = User.USER_TYPES.level0
        user.save(update_fields=['email', 'mobile', 'user_type'])

        self.verification_profile = user.get_verification_profile()
        self.verification_profile.email_confirmed = False
        self.verification_profile.mobile_confirmed = False
        self.verification_profile.save()

        # kyc2 key activate
        set_feature_status("kyc2", True)
        # send request
        url = '/users/profile-edit'
        data = {
            'firstName': 'آرش', 'lastName': 'دباغ', 'nationalCode': '6300004554',
            'email': 'x@x.com', 'address': 'تبریز', 'phone': '02166557766',
        }
        r = self.client.post(url, data).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'UserLevelRestriction'
        assert r['message'] == 'Email and Mobile are not confirmed'

        # mobile confirmed
        self.verification_profile = user.get_verification_profile()
        self.verification_profile.mobile_confirmed = True
        self.verification_profile.save()
        data = {
            'firstName': 'آرش', 'lastName': 'دباغ', 'nationalCode': '6300004554',
            'email': 'x@x.com', 'address': 'تبریز', 'phone': '02166557766',
        }
        r = self.client.post(url, data).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'ValidationError'
        assert r['message'] == 'Email is not editable with other parameters.'

        # mobile confirmed
        self.verification_profile = user.get_verification_profile()
        self.verification_profile.mobile_confirmed = True
        self.verification_profile.save()
        data = {
            'firstName': 'آرش', 'lastName': 'دباغ', 'nationalCode': '6300004554',
            'address': 'تبریز', 'phone': '02166557766',
        }
        r = self.client.post(url, data).json()
        assert r['status'] == 'ok'
        assert r['updates'] == 6

    def test_confirm_address_on_city_address(self):
        user = User.objects.get(id=201)

        vp = user.get_verification_profile()
        assert not vp.address_confirmed

        # kyc2 key activate
        set_feature_status("kyc2", True)
        # send request
        url = '/users/profile-edit'
        data = {'city': 'مشهد', 'address': 'خیابان اول'}
        r = self.client.post(url, data).json()

        assert r['status'] == 'ok'
        assert r['updates'] == 2

        vp.refresh_from_db()
        assert vp.address_confirmed


class TestUserVerify(APITestCase):

    def create_fake_data(self):
        self.ufile_main_image = UploadedFile(filename=uuid.uuid4(), user=self.user, tp=UploadedFile.TYPES.kyc_main_image)
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

    def update_verification(self) -> VerificationProfile:
        # update_verification_status
        self.user.address = 'مشهد'
        self.user.city = 'مشهد'
        self.user.phone = '12345678'
        self.user.email = 'test@test.com'
        self.user.national_code = '0921234567'
        self.user.national_serial_number = 'sd5sad4656d'
        self.user.save()
        vp = self.user.get_verification_profile()
        vp.phone_confirmed = (
            vp.mobile_identity_confirmed
        ) = (
            vp.email_confirmed
        ) = (
            vp.bank_account_confirmed
        ) = vp.mobile_confirmed = vp.identity_confirmed = vp.bank_confirmed = vp.address_confirmed = True
        vp.save()
        return vp

    def user_verify_success_mock(self, url, **headers):
        mock_response = Mock()
        mock_response.status_code = status.HTTP_200_OK
        base_url = Settings.get('auto_kyc_url', 'https://napi.jibit.ir/newalpha/api')
        if url == f'{base_url}/authorization':
            mock_response.json.return_value = {
                "verification_result": {
                    "errorCode": "",
                    "errorMessage": "",
                    "data": {
                        "result": True,
                        "details": {
                            "distance": 0.95465468484
                        },
                        "duration": 0.95465654654
                    }
                },
                "liveness_result": {
                    "errorCode": "",
                    "errorMessage": "",
                    "data": {
                        "FaceAnchor": "3 of 5 anchor completed",
                        "Duration": 0.225465486,
                        "Score": "0.001546848",
                        "Guide": "The score lower than threshold is live and higher that threshold is spoof",
                        "State": "true"
                    }
                }
            }
        elif url == f'{base_url}/asr':
            mock_response.json.return_value = {
                "errorCode": "",
                "errorMessage": "",
                "data": {
                    "distance": 0.4,
                    "nobitex": True,
                    "state": True,
                    "time": 4.2
                }
            }
        else:
            mock_response.json.return_value = None
        return mock_response

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.create_fake_data()

    def test_prevent_sending_two_same_verification_request(self):
        response = self.client.post('/users/verify', data={'tp': 'address'})
        assert response.status_code == status.HTTP_200_OK
        expected_result = {
            'status': 'ok',
        }
        assert expected_result == response.json()

        response = self.client.post('/users/verify', data={'tp': 'address'})
        assert response.status_code == status.HTTP_409_CONFLICT
        expected_result = {'status': 'failed', 'code': 'VerificationRequestFail', 'message': 'درخواست فعال وجود دارد.'}
        assert expected_result == response.json()

    def test_prevent_sending_verification_request_after_confirmation(self):
        response = self.client.post('/users/verify', data={'tp': 'address'})
        assert response.status_code == status.HTTP_200_OK
        expected_result = {
            'status': 'ok',
        }
        assert expected_result == response.json()
        VerificationRequest.objects.filter(user=self.user, tp=VerificationRequest.TYPES.address).update(
            status=VerificationRequest.STATUS.confirmed,
        )

        response = self.client.post('/users/verify', data={'tp': 'address'})
        assert response.status_code == status.HTTP_409_CONFLICT
        expected_result = {
            'status': 'failed',
            'code': 'VerificationRequestFail',
            'message': 'درخواست تایید شده وجود دارد.',
        }
        assert expected_result == response.json()

    @override_settings(IS_PROD=True)
    def test_upload_and_user_verify(self):
        # upload file
        upload_response = self.client.post('/users/upload-file', data={"file": ''})
        assert upload_response.status_code == status.HTTP_200_OK
        upload_result = upload_response.json()
        assert upload_result['status'] == 'failed'

        # verify
        assert not self.user.has_tag_cant_upgrade_level2
        self.prevent_to_lvl2_tag = Tag.objects.create(name="عدم ارتقاء سطح ۲", tp=2)
        UserTag.objects.create(user=self.user, tag=self.prevent_to_lvl2_tag)
        assert self.user.has_tag_cant_upgrade_level2

        response = self.client.post(path='/users/verify', data={
            'tp': 'auto_kyc',
            'documents': f'file_name2,file_name2,file_name3',
            'explanations': 'for test'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        assert self.user.user_type == User.USER_TYPES.level0

        response = self.client.post(path='/users/verify', data={
            'tp': 'auto_kyc',
            'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
            'explanations': 'for test1'
        })
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        expected_result = {'status': 'failed',
                           'code': 'VerificationRestricted',
                           'message': 'User is restricted.',
                           }
        assert result == expected_result

        UserTag.objects.get(user=self.user, tag=self.prevent_to_lvl2_tag).delete()

        vp = self.update_verification()
        vp.mobile_identity_confirmed = False
        vp.save()

        assert self.user.user_type == User.USER_TYPES.level1
        assert not self.user.has_tag_cant_upgrade_level2
        assert vp.is_verified_level1

        vp.address_confirmed = False
        vp.save()

        # when user level is 1
        with patch('requests.post') as mock_requests, \
             patch('exchange.accounts.views.profile.magic') as mock_magic:
            mock_magic.from_file.return_value = 'image/jpeg'
            mock_requests.side_effect = self.user_verify_success_mock
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test 1.5'
            })
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        expected_result = {
            'status': 'failed',
            'code': 'VerificationDenied',
            'message': 'مراحل قبل تکمیل نیست',
        }
        assert result == expected_result
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level1

        # when user level is 0
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()
        with patch('requests.post') as mock_requests, \
            patch('exchange.accounts.views.profile.magic') as mock_magic:
            mock_magic.from_file.return_value = 'image/jpeg'
            mock_requests.side_effect = self.user_verify_success_mock
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test 1.6'
            })
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        expected_result = {
            'status': 'failed',
            'code': 'VerificationDenied',
            'message': 'مراحل قبل تکمیل نیست',
        }
        assert result == expected_result
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level0

        self.user.user_type = User.USER_TYPES.level1
        self.user.address = 'مشهد'
        self.user.save()
        vp = self.user.get_verification_profile()
        vp.mobile_identity_confirmed = True
        vp.address_confirmed = True
        vp.save()
        set_feature_status("kyc2", False)
        with patch('requests.post') as mock_requests, patch(
            'exchange.accounts.views.profile.magic.from_file'
        ) as mock_magic:
            mock_magic.side_effect = ['image/gif', 'image/jpeg']
            mock_requests.side_effect = self.user_verify_success_mock
            response = self.client.post(
                path='/users/verify',
                data={
                    'tp': 'auto_kyc',
                    'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                    'explanations': 'for test 2',
                },
            )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        expected_result = {
            'status': 'ok',
        }
        assert result == expected_result
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level2

    def test_success_in_kyc_v2(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.address = 'مشهد'
        self.user.city = 'مشهد'
        self.user.mobile = '09120000000'
        self.user.save()
        set_feature_status('kyc2', status=True)
        vp = self.user.get_verification_profile()
        vp.mobile_identity_confirmed = False
        vp.mobile_confirmed = True
        vp.phone_confirmed = True
        vp.address_confirmed = True
        vp.identity_confirmed = True
        vp.save()
        with patch('requests.post') as mock_requests, \
             patch('exchange.accounts.views.profile.magic.from_file') as mock_magic:
            mock_magic.side_effect = ['image/gif', 'image/jpeg']
            mock_requests.side_effect = self.user_verify_success_mock
            response = self.client.post(
                path='/users/verify',
                data={
                    'tp': 'auto_kyc',
                    'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                    'explanations': 'for test 2',
                },
            )
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        expected_result = {
            'status': 'ok',
        }
        assert result == expected_result
        self.user.refresh_from_db()
        assert self.user.user_type == User.USER_TYPES.level2

    def test_user_verify_when_active_req_exists(self):
        vr_selfie = VerificationRequest.objects.create(
            user=self.user,
            tp=VerificationRequest.TYPES.selfie,
            status=VerificationRequest.STATUS.new
        )
        self.update_verification()
        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'image/jpeg']
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test'
            })
            self.assertTrue(response.status_code, status.HTTP_409_CONFLICT)
            expected_result = {
                'status': 'failed',
                'code': 'VerificationRequestFail',
                'message': 'درخواست فعال وجود دارد.'
            }
            self.assertDictEqual(expected_result, response.json())
            vr_selfie.delete()

        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'image/jpeg']
            VerificationRequest.objects.create(
                user=self.user,
                tp=VerificationRequest.TYPES.auto_kyc,
                status=VerificationRequest.STATUS.new
            )
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test'
            })
            self.assertTrue(response.status_code, status.HTTP_409_CONFLICT)
            expected_result = {
                'status': 'failed',
                'code': 'VerificationRequestFail',
                'message': 'درخواست فعال وجود دارد.'
            }
            self.assertDictEqual(expected_result, response.json())

    def test_user_verify_with_bad_docs(self):
        self.update_verification()

        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['audio/mp3', 'audio/wav']
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test'
            })
            result = response.json()
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            expected_result = {
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فرمت تصویر زنده قابل قبول نمی‌باشد.',
            }
            self.assertDictEqual(result, expected_result)

        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['image/gif', 'audio/mp3']
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_image.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test'
            })
            result = response.json()
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            expected_result = {
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فرمت عکس سلفی قابل قبول نمی‌باشد.',
            }
            self.assertDictEqual(result, expected_result)

    def test_incomplete_files(self):
        self.update_verification()

        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['video/mp4']
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_video.filename.hex}',
                'explanations': 'for test'
            })
            result = response.json()
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            expected_result = {
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فایل های ارسالی کامل نمی باشد.',
            }
            self.assertDictEqual(result, expected_result)

        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['video/mp4', 'image/jpeg']
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_video.filename.hex},{self.ufile_main_image.filename.hex}',
                'explanations': 'for test'
            })
            result = response.json()
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            expected_result = {
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فایل های ارسالی کامل نمی باشد.',
            }
            self.assertDictEqual(result, expected_result)

        with patch('exchange.accounts.views.profile.magic.from_file') as magic_mock:
            magic_mock.side_effect = ['video/mp4', 'image/gif']
            response = self.client.post(path='/users/verify', data={
                'tp': 'auto_kyc',
                'documents': f'{self.ufile_video.filename.hex},{self.ufile_image.filename.hex}',
                'explanations': 'for test'
            })
            result = response.json()
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            expected_result = {
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فایل های ارسالی کامل نمی باشد.',
            }
            self.assertDictEqual(result, expected_result)


class TestBankAccount(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0010010010'
        cls.user.mobile = '09100100100'
        cls.user.save(update_fields=('national_code', 'mobile'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    @patch('exchange.accounts.views.profile.task_convert_iban_to_account_number.apply_async')
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_bank_account_add(self, mock_account_number_task):
        iban = 'IR050120000000000000011111'
        response = self.client.post('/users/accounts-add', {'shaba': iban})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        bank_account = BankAccount.objects.last()
        assert bank_account
        assert bank_account.shaba_number == iban
        assert bank_account.bank_id == BankAccount.BANK_ID.mellat
        assert bank_account.bank_name == 'ملت'
        assert bank_account.display_name == 'ملت: IR050120000000000000011111'
        assert bank_account.user == self.user
        assert bank_account.owner_name == 'User One'
        assert bank_account.confirmed

        mock_account_number_task.assert_called_once_with((bank_account.id,), expires=60 * 60)

    def _test_failed_bank_account_add(self, data, error_code):
        previous_accounts = BankAccount.objects.count()
        response = self.client.post('/users/accounts-add', data)
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == error_code
        assert BankAccount.objects.count() == previous_accounts

    @patch('exchange.accounts.views.profile.task_convert_iban_to_account_number.apply_async')
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_bank_account_duplicate_add(self, mock_account_number_task):
        iban = 'IR050120000000000000011111'
        response = self.client.post('/users/accounts-add', {'shaba': iban})
        assert response.json()['status'] == 'ok'

        mock_account_number_task.reset_mock()
        self._test_failed_bank_account_add({'shaba': iban}, error_code='DuplicatedShaba')
        mock_account_number_task.assert_not_called()

    @patch('exchange.accounts.views.profile.task_convert_iban_to_account_number.apply_async')
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_bank_account_add_with_wrong_iban(self, mock_account_number_task):
        self._test_failed_bank_account_add({'shaba': 'IR27053000000000000000001'}, error_code='ValidationError')
        mock_account_number_task.assert_not_called()

    @patch('exchange.accounts.views.profile.task_convert_iban_to_account_number.apply_async')
    @patch('django.db.transaction.on_commit', lambda t: t())
    def test_bank_account_add_with_empty_identity_data(self, mock_account_number_task):
        self.user.national_code = None
        self.user.save(update_fields=('national_code',))
        self._test_failed_bank_account_add({'shaba': 'IR27053000000000000000001'}, error_code='UserLevelRestriction')
        mock_account_number_task.assert_not_called()


class TestPaymentAccount(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0010010010'
        cls.user.mobile = '09100100100'
        cls.user.save(update_fields=('national_code', 'mobile'))
        UserPreference.set(cls.user, 'system_enable_vandar_deposit', 'true')

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_payment_account_add(self):
        response = self.client.post('/users/payment-accounts-add', {'account': 'test', 'service': 'vandar'})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        bank_account = BankAccount.objects.last()
        assert bank_account
        assert bank_account.shaba_number
        assert bank_account.bank_id == BankAccount.BANK_ID.vandar
        assert bank_account.bank_name == 'وندار'
        assert bank_account.display_name == 'وندار: test'
        assert bank_account.user == self.user
        assert bank_account.owner_name == 'User One'
        assert not bank_account.confirmed

    def _test_failed_payment_account_add(self, data, error_code):
        previous_accounts = BankAccount.objects.count()
        response = self.client.post('/users/payment-accounts-add', data)
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == error_code
        assert BankAccount.objects.count() == previous_accounts

    def test_payment_account_duplicate_add(self):
        response = self.client.post('/users/payment-accounts-add', {'account': 'test', 'service': 'vandar'})
        assert response.json()['status'] == 'ok'
        self._test_failed_payment_account_add({'account': 'test', 'service': 'vandar'}, error_code='DuplicateAccount')

    def test_bank_account_add_with_long_account_id(self):
        # Vandar allows at most 40 characters
        self._test_failed_payment_account_add(
            {'account': 'there-must-be-some-thing-wrong-with-my-id', 'service': 'vandar'}, error_code='ParseError',
        )
        # account_id db column allows at most 25 characters
        self._test_failed_payment_account_add(
            {'account': 'there-may-be-some-thing-wrong-with-my-id', 'service': 'vandar'}, error_code='ValidationError',
        )

    def test_payment_account_add_with_insufficient_data(self):
        self._test_failed_payment_account_add({'account': 'test'}, error_code='ParseError')
        self._test_failed_payment_account_add({'service': 'vandar'}, error_code='ParseError')

    def test_payment_account_add_with_wrong_bank(self):
        self._test_failed_payment_account_add({'account': 'test', 'service': 'nonexistent'}, error_code='ParseError')
        self._test_failed_payment_account_add({'account': 'test', 'service': 'tejarat'}, error_code='ValidationError')

    def test_payment_account_add_without_being_enabled(self):
        self.user.preferences.all().delete()
        self._test_failed_payment_account_add({'account': 'test', 'service': 'vandar'}, error_code='PaymentUnavailable')
        UserPreference.set(self.user, 'system_enable_vandar_deposit', 'false')
        self._test_failed_payment_account_add({'account': 'test', 'service': 'vandar'}, error_code='PaymentUnavailable')

    def test_payment_account_add_with_empty_identity_data(self):
        self.user.national_code = None
        self.user.save(update_fields=('national_code',))
        self._test_failed_payment_account_add(
            {'account': 'test', 'service': 'vandar'}, error_code='UserLevelRestriction',
        )


class TestChangeMobile(TestCase):
    profile_edit_url = '/users/profile-edit'
    verify_mobile_url = '/users/verify-mobile'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.get_verification_profile()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.user.mobile = '09351234567'
        self.user.save()
        self.new_mobile = '09151234567'
        self.user2 = User.objects.get(pk=202)
        self.user2.mobile = '09371234567'
        self.user2.save()
        self.user.get_verification_profile().email_confirmed = True
        self.user.get_verification_profile().save()

    def test_create_change_mobile_request(self):
        change_obj = ChangeMobileRequest.create(user=self.user, new_mobile=self.new_mobile)
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.new)
        self.assertEqual(change_obj.old_mobile, self.user.mobile)
        self.assertEqual(change_obj.new_mobile, self.new_mobile)

        new_change_obj = ChangeMobileRequest.create(user=self.user, new_mobile=self.new_mobile)
        change_obj.refresh_from_db()
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.failed)
        self.assertEqual(new_change_obj.status, ChangeMobileRequest.STATUS.new)
        self.assertEqual(new_change_obj.old_mobile, self.user.mobile)

    def test_get_active_request(self):
        change_obj = ChangeMobileRequest.create(user=self.user, new_mobile=self.new_mobile)
        active_req = ChangeMobileRequest.get_active_request(self.user)
        self.assertEqual(change_obj, active_req)
        new_change_obj = ChangeMobileRequest.create(user=self.user, new_mobile=self.new_mobile)
        active_req = ChangeMobileRequest.get_active_request(self.user)
        self.assertNotEqual(change_obj, active_req)
        self.assertEqual(new_change_obj, active_req)
        new_change_obj.status = ChangeMobileRequest.STATUS.failed
        new_change_obj.save()
        active_req = ChangeMobileRequest.get_active_request(self.user)
        self.assertIsNone(active_req)

    def test_send_otp(self):
        change_obj = ChangeMobileRequest.create(user=self.user, new_mobile=self.new_mobile)

        # old mobile otp
        otp_obj, error = change_obj.send_otp()
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.old_mobile_otp_sent)
        self.assertIsNone(error)
        self.assertEqual(otp_obj.otp_type, UserOTP.OTP_TYPES.mobile)
        self.assertEqual(otp_obj.otp_usage, UserOTP.OTP_Usage.change_phone_number)
        self.assertTrue(otp_obj.is_sent)
        user_otp_objs = UserOTP.active_otps(user=self.user, tp=UserOTP.OTP_TYPES.mobile, usage=UserOTP.OTP_Usage.change_phone_number)
        self.assertIn(otp_obj, user_otp_objs)

        # new mobile otp
        new_otp_obj, new_error = change_obj.send_otp()
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.new_mobile_otp_sent)
        self.assertIsNone(new_error)

        fail_otp_obj, the_error = change_obj.send_otp()
        self.assertIsNone(fail_otp_obj)
        self.assertIsNotNone(the_error)

    @patch('exchange.accounts.models.UserOTP.send')
    def test_send_otp_send_fail(self, send_mock):
        send_mock.return_value = False
        change_obj = ChangeMobileRequest.create(user=self.user, new_mobile=self.new_mobile)
        otp_obj, error = change_obj.send_otp()
        self.assertIsNone(otp_obj)
        self.assertEqual(error, 'Send OTP sms failed')
        otp_obj = UserOTP.objects.get(otp_type=UserOTP.OTP_TYPES.mobile,
                                      otp_usage=UserOTP.OTP_Usage.change_phone_number,
                                      phone_number=self.user.mobile)
        self.assertTrue(otp_obj.otp_status, UserOTP.OTP_STATUS.disabled)

    def test_log(self):
        self.assertFalse(ChangeMobileRequest.log(self.user, 0))
        self.assertTrue(ChangeMobileRequest.log(self.user, UserEvent.EDIT_MOBILE_ACTION_TYPES.success, 'test'))
        user_event = UserEvent.objects.get(user=self.user,
                                           action=UserEvent.ACTION_CHOICES.edit_mobile,
                                           action_type=UserEvent.EDIT_MOBILE_ACTION_TYPES.success)
        self.assertIsNotNone(user_event)
        self.assertEqual(user_event.description, 'test')

    def test_add_restriction(self):
        change_mobile_request = ChangeMobileRequest.create(self.user, '09151234567')
        self.assertFalse(change_mobile_request.add_restriction())
        change_mobile_request.status = ChangeMobileRequest.STATUS.success
        change_mobile_request.save()
        self.assertTrue(change_mobile_request.add_restriction())
        user_restriction = UserRestriction.objects.get(user=self.user,
                                           restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin)
        self.assertIsNotNone(user_restriction)
        self.assertEqual(user_restriction.considerations, 'ایجاد محدودیت 48 ساعته برداشت رمز ارز بعلت تغییر شماره موبایل')

    def test_send_user_notif(self):
        change_mobile_request = ChangeMobileRequest.create(self.user, '09151234567')
        self.assertFalse(change_mobile_request.send_user_notif())
        change_mobile_request.status = ChangeMobileRequest.STATUS.success
        change_mobile_request.save()

        self.assertTrue(change_mobile_request.send_user_notif())
        self.assertFalse(UserSms.objects.filter(user=self.user, tp=UserSms.TYPES.process).exists())

        self.assertTrue(change_mobile_request.send_user_notif(change_mobile=False))
        user_sms = UserSms.objects.get(user=self.user, tp=UserSms.TYPES.process)
        self.assertIsNotNone(user_sms)
        self.assertEqual(user_sms.to, self.user.mobile)

    def test_change_mobile_api_level_restriction(self):
        restricted_levels = [
            'active',
            'trusted',
            'nobitex',
            'system',
            'bot',
            'staff',
        ]
        for user_level in restricted_levels:
            self.user.user_type = User.USER_TYPES._identifier_map[user_level]
            self.user.save()
            response = self.client.post(path=self.profile_edit_url, data={'mobile': self.new_mobile})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            expected_result = {
                    'status': 'failed',
                    'code': 'UserLevelRestriction',
                    'message': 'MobileUneditable',
                }
            self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
            self._assert_change_mobile_failed()

    def test_check_app_version_android(self):
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
            headers={
                'user-agent': 'Android/1.0.0',
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        expected_result = {'status': 'failed', 'code': 'PleaseUpdateApp', 'message': 'Please Update App'}
        assert response.json() == expected_result

    def test_check_app_version_IOS(self):
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
            headers={
                'user-agent': 'iOSApp/1.0.0',
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        expected_result = {'status': 'failed', 'code': 'PleaseUpdateApp', 'message': 'Please Update App'}
        assert response.json() == expected_result

    @patch('exchange.accounts.captcha.CaptchaHandler.verify')
    def test_captcha_failure(self, mock_verify):
        mock_verify.return_value = False
        response = self.client.post(path=self.profile_edit_url, data={'mobile': self.new_mobile})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        expected_result = {
            'status': 'failed',
            'message': 'کپچا به درستی تایید نشده',
            'code': 'کپچا به درستی تایید نشده',
        }
        assert response.json() == expected_result

    def test_change_mobile_api_mobile_validation_error(self):
        response = self.client.post(path=self.profile_edit_url, data={'mobile': '123'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Mobile validation failed',
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self._assert_change_mobile_failed()

    def test_change_mobile_api_mobile_already_registered_with_cannot_merge(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save(update_fields=['user_type'])
        self.user2.user_type = User.USER_TYPES.level1
        self.user2.save(update_fields=['user_type'])
        vp = self.user2.get_verification_profile()
        vp.mobile_confirmed = True
        vp.save()
        response = self.client.post(path=self.profile_edit_url, data={'mobile': self.user2.mobile})
        assert response.status_code, status.HTTP_200_OK
        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'NotOwnedByUser',
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self._assert_change_mobile_failed()

    def test_change_mobile_api_mobile_already_registered_with_can_merge(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save(update_fields=['user_type'])
        self.user2.user_type = User.USER_TYPES.level0
        self.user2.save(update_fields=['user_type'])
        vp = self.user2.get_verification_profile()
        vp.mobile_confirmed = True
        vp.save()
        response = self.client.post(path=self.profile_edit_url, data={'mobile': self.user2.mobile})
        assert response.status_code, status.HTTP_200_OK
        expected_result = {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'MobileAlreadyRegistered',
            'canMerge': True,
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self._assert_change_mobile_failed()

    @patch('exchange.accounts.captcha.CaptchaHandler.verify')
    def test_change_mobile_api_success_and_verify(self, mock_verify_captcha):
        mock_verify_captcha.return_value = True
        response = self.client.post(path=self.profile_edit_url, data={'mobile': self.new_mobile})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {
            'status': 'ok',
            'updates': 0,
            'change_mobile_status': {
                'code': 1,
                'text': 'Old Mobile OTP Sent'
            }
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self._assert_change_mobile_success()
        otp_obj = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.change_phone_number,
        ).first()

        # verify old mobile
        response = self.client.post(path=self.verify_mobile_url, data={'otp': otp_obj.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {
            'status': 'ok',
            'change_mobile_status': {
                'code': 2,
                'text': 'New Mobile OTP Sent'
            }
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        change_obj = ChangeMobileRequest.get_active_request(self.user)
        self.assertIsNotNone(change_obj)
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.new_mobile_otp_sent)
        sms_obj = UserSms.get_verification_messages(self.user).order_by('-created_at').first()
        self.assertIsNotNone(sms_obj)
        self.assertEqual(sms_obj.to, self.new_mobile)
        otp_obj = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.change_phone_number,
        ).order_by('-created_at').first()
        self.assertIsNotNone(otp_obj)
        self.assertEqual(otp_obj.phone_number, self.new_mobile)
        self.assertTrue(otp_obj.is_sent)

        # verify new mobile
        response = self.client.post(path=self.verify_mobile_url, data={'otp': otp_obj.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {
            'status': 'ok',
            'change_mobile_status': {
                'code': 3,
                'text': 'Success'
            }
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        change_obj = ChangeMobileRequest.objects.get(user=self.user, status=ChangeMobileRequest.STATUS.success)
        self.assertIsNotNone(change_obj)
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.success)
        self.assertTrue(self.user.is_restricted('WithdrawRequestCoin'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.mobile, self.new_mobile)

    def test_change_mobile_api_when_tfa_enabled_fail(self):
        old_mobile = self.user.mobile
        Settings.set('tfa_for_change_mobile', 'enabled')
        self.user.requires_2fa = True
        self.user.save()

        # When X-TOTP missing
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {'code': 'Invalid2FA', 'message': 'msgInvalid2FA', 'status': 'failed'}
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.mobile, old_mobile)
        self._assert_change_mobile_failed()

        # When X-TOTP invalid
        response = self.client.post(
            path=self.profile_edit_url,
            headers={'X-TOTP': '1234'},
            data={'mobile': self.new_mobile},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {'code': 'Invalid2FA', 'message': 'msgInvalid2FA', 'status': 'failed'}
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.mobile, old_mobile)
        self._assert_change_mobile_failed()

    @patch('exchange.accounts.views.profile.check_user_otp')
    def test_change_mobile_api_when_tfa_enabled_success(self, mock):
        # When X-TOTP is correct
        Settings.set('tfa_for_change_mobile', 'enabled')
        mock.return_value = True
        old_mobile = self.user.mobile
        self.user.requires_2fa = True
        self.user.save()

        response = self.client.post(
            path=self.profile_edit_url,
            headers={'X-TOTP': '-1'},
            data={'mobile': self.new_mobile},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_result = {
            'status': 'ok',
            'updates': 0,
            'change_mobile_status': {
                'code': 1,
                'text': 'Old Mobile OTP Sent',
            },
        }
        self.assertJSONEqual(str(response.content, encoding='utf8'), expected_result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.mobile, old_mobile)
        self._assert_change_mobile_success()

    def _assert_change_mobile_failed(self):
        change_obj = ChangeMobileRequest.get_active_request(self.user)
        self.assertIsNone(change_obj)

        sms_obj = UserSms.get_verification_messages(self.user).first()
        self.assertIsNone(sms_obj)

        otp_obj = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.change_phone_number,
        ).first()

        self.assertIsNone(otp_obj)

    def _assert_change_mobile_success(self):
        change_obj = ChangeMobileRequest.get_active_request(self.user)
        self.assertIsNotNone(change_obj)
        self.assertEqual(change_obj.status, ChangeMobileRequest.STATUS.old_mobile_otp_sent)
        self.assertEqual(change_obj.old_mobile, self.user.mobile)
        self.assertEqual(change_obj.new_mobile, self.new_mobile)

        sms_obj = UserSms.get_verification_messages(self.user).first()
        self.assertIsNotNone(sms_obj)
        self.assertEqual(sms_obj.to, self.user.mobile)

        otp_obj = UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.change_phone_number,
        ).first()

        self.assertIsNotNone(otp_obj)
        self.assertEqual(otp_obj.phone_number, self.user.mobile)
        self.assertTrue(otp_obj.is_sent)

    def test_user_have_active_merge_request(self):
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.need_approval,
            merge_by=UserMergeRequest.MERGE_BY.mobile,
            main_user= self.user,
            second_user= self.user,
        )
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
        )
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'HasActiveMergeRequestError'
        assert data['message'] == 'User has active merge request.'

    def test_user_have_active_tara_user_service(self):
        abc_mix = ABCMixins()
        service = abc_mix.create_service()
        abc_mix.create_user_service(user=self.user, service=service)
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
        )
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'UserHasActiveTaraService'
        assert data['message'] == 'User has active tara service.'

        response = self.client.post(path=self.verify_mobile_url, data={'otp': '12345'})
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'UserHasActiveTaraService'
        assert data['message'] == 'User has active tara service.'

    def test_user_restriction_on_mobile_change(self):
        user_restriction = UserRestriction.add_restriction(self.user, 'ChangeMobile')
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'failed'
        assert data['code'] == 'MobileChangeRestricted'
        assert data['message'] == 'Mobile change is restricted for user.'

        user_restriction.delete()
        response = self.client.post(
            path=self.profile_edit_url,
            data={'mobile': self.new_mobile},
        )
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        otp_obj = (
            UserOTP.active_otps(
                user=self.user,
                tp=UserOTP.OTP_TYPES.mobile,
                usage=UserOTP.OTP_Usage.change_phone_number,
            )
            .order_by('-created_at')
            .first()
        )
        assert otp_obj is not None

        user_restriction = UserRestriction.add_restriction(self.user, 'ChangeMobile')
        response = self.client.post(path=self.verify_mobile_url, data={'otp': otp_obj.code})
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'failed'
        assert data['code'] == 'MobileChangeRestricted'
        assert data['message'] == 'Mobile change is restricted for user.'

        user_restriction.delete()
        response = self.client.post(path=self.verify_mobile_url, data={'otp': otp_obj.code})
        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'


class TestCheckMobileWithShahkar(TestCase):
    profile_edit_url = '/users/profile-edit'
    verify_mobile_url = '/users/verify-mobile'
    registration_url = '/auth/registration/'

    def setUp(self) -> None:
        set_feature_status("kyc2", False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_mobile = '09151234567'
        self.user_email = 'test_user@gmail.com'
        self.user_password = '123@Pass'

    def test_change_mobile_obj_when_user_registered_with_mobile(self):
        Settings.set('mobile_register', 'yes')
        registration_request = {
            'mobile': self.user_mobile,
            'username': self.user_mobile,
            'password1': self.user_password,
            'password2': self.user_password,
        }
        registration_response = self.client.post(
            self.registration_url,
            registration_request,
        )
        self.assertEqual(registration_response.status_code, status.HTTP_200_OK)
        response = self.client.post(
            '/otp/request-public',
            {'mobile': self.user_mobile, 'usage': 'welcome_sms'},
        ).json()
        self.assertEqual(response['status'], 'ok')

        mobile_otp = UserSms.objects.filter(to=self.user_mobile).order_by('-created_at').first().text
        registration_request['otp'] = mobile_otp
        registration_response = self.client.post(
            '/auth/registration/',
            registration_request,
        )
        self.assertEqual(registration_response.status_code, status.HTTP_201_CREATED)

        user = User.objects.filter(mobile=self.user_mobile, username=self.user_mobile).first()

        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {registration_response.json()["key"]}'
        # send information of profile to verify user and check Shahkar
        vp = user.get_verification_profile()
        vp.phone_confirmed = False
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.identity_confirmed = False
        vp.save()

        with override_settings(IS_PROD=True):
            with patch('exchange.accounts.models.User.check_mobile_identity') as check_mobile_mock_2:
                check_mobile_mock_2.return_value = True, None
                r = self.client.post(self.profile_edit_url, data={
                    'firstName': 'تست', 'lastName': 'تست نژاد', 'nationalCode': '6300004554', 'address': 'تست آباد',
                }).json()
                self.assertDictEqual(r, {
                    'status': 'ok',
                    'updates': 4
                })
                user.refresh_from_db()
                self.assertEqual(user.national_code, '6300004554')
                self.assertEqual(user.first_name, 'تست')
                self.assertEqual(user.last_name, 'تست نژاد')
                self.assertEqual(user.address, 'تست آباد')

    def test_change_mobile_obj_when_user_registered_with_email(self):
        Settings.set('email_register', 'yes')
        registration_response = self.client.post(self.registration_url, {
            'email': self.user_email,
            'username': self.user_email,
            'password1': self.user_password,
            'password2': self.user_password,
        })
        self.assertEqual(registration_response.status_code, status.HTTP_201_CREATED)

        user = User.objects.filter(email=self.user_email, username=self.user_email).first()
        self.assertIsNotNone(user)

        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {registration_response.json()["key"]}'
        vp = user.get_verification_profile()
        vp.phone_confirmed = False
        vp.email_confirmed = True
        vp.identity_confirmed = False
        vp.save()

        r = self.client.post(self.profile_edit_url, data={
            'mobile': self.user_mobile
        }).json()
        self.assertDictEqual(r, {
            'status': 'ok',
            'updates': 0,
            'change_mobile_status': {
                'code': 2,
                'text': 'New Mobile OTP Sent'
            },
        })
        change_mobile_req_obj = ChangeMobileRequest.objects.filter(user=user,
                                                                   new_mobile=self.user_mobile,
                                                                   status=ChangeMobileRequest.STATUS.new_mobile_otp_sent).first()
        self.assertIsNotNone(change_mobile_req_obj)

        user_sms = UserSms.objects.filter(user=user, to=self.user_mobile).first()
        self.assertIsNotNone(user_sms)
        self.assertEqual(user_sms.tp, UserSms.TYPES.verify_phone)
        sms_text = user_sms.text

        user_otp = UserOTP.objects.filter(user=user, otp_type=UserOTP.OTP_TYPES.mobile,
                                          otp_usage=UserOTP.OTP_Usage.welcome_sms).first()
        self.assertIsNotNone(user_otp)
        self.assertEqual(user_otp.phone_number, self.user_mobile)
        self.assertEqual(user_otp.code, sms_text)

        otp = user_otp.code
        r = self.client.post(self.verify_mobile_url, data={
            'otp': otp
        }).json()
        self.assertDictEqual(r, {
            'status': 'ok',
            'change_mobile_status': {
                'code': 3,
                'text': 'Success'
            },
        })
        user.refresh_from_db()
        self.assertEqual(user.mobile, self.user_mobile)

        with override_settings(IS_PROD=True):
            with patch('exchange.accounts.models.User.check_mobile_identity') as check_mobile_mock_2:
                check_mobile_mock_2.return_value = True, None
                r = self.client.post(self.profile_edit_url, data={
                    'firstName': 'تست', 'lastName': 'تست نژاد', 'nationalCode': '6300004554', 'address': 'تست آباد',
                }).json()
                self.assertDictEqual(r, {
                    'status': 'ok',
                    'updates': 4
                })
                user.refresh_from_db()
                self.assertEqual(user.national_code, '6300004554')
                self.assertEqual(user.first_name, 'تست')
                self.assertEqual(user.last_name, 'تست نژاد')
                self.assertEqual(user.address, 'تست آباد')


class TestConfirmMobileOldProcess(TestCase):
    profile_edit_url = '/users/profile-edit'
    verify_mobile_url = '/users/verify-mobile'
    otp_request_url = '/otp/request'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        vp = self.user.get_verification_profile()
        vp.mobile_confirmed = False
        vp.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.user.mobile = ''
        self.user.save()

    def test_confirm_existed_mobile(self):
        """
        suppose user doesn't have mobile in db
        old process is in this order
        otp-request
        verify-mobile
        so system doesn't create ChangeMobileRequest for user
        """
        vp = self.user.get_verification_profile()
        self.assertEqual(vp.mobile_confirmed, False)
        response = self.client.post(path=self.otp_request_url, data={'type': 'mobile'})
        self.assertDictEqual(response.json(), {'status': 'ok'})
        otp_obj = UserOTP.objects.filter(otp_type=UserOTP.OTP_TYPES.mobile).first()
        self.assertIsNotNone(otp_obj)
        otp = otp_obj.code

        response_verify = self.client.post(path=self.verify_mobile_url, data={'otp': 123456})
        self.assertDictEqual(response_verify.json(), {
            'status': 'failed',
            'code': 'VerificationError',
            'message': 'ChangeMobileRequestNotFound'
        })
        vp.refresh_from_db()
        self.assertEqual(vp.mobile_confirmed, False)

        response_verify = self.client.post(path=self.verify_mobile_url, data={'otp': otp})
        self.assertDictEqual(response_verify.json(), {'status': 'ok'})
        vp.refresh_from_db()
        self.assertEqual(vp.mobile_confirmed, True)


class ChangeEmailTests(APITestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.user_vp = self.user.get_verification_profile()
        User.objects.filter(pk=self.user.pk).update(user_type=User.USER_TYPES.level0)
        self.user.refresh_from_db()

        VerificationProfile.objects.filter(pk=self.user_vp.pk).update(email_confirmed=False)
        self.user_vp.refresh_from_db()

    def _call_api(self, new_email):
        return self.client.post(
            path='/users/profile-edit',
            data={'email': new_email},
        ).json()

    def test_confirmed_email_change(self):
        self.user_vp.email_confirmed = True
        self.user_vp.save()
        assert self.user.get_verification_profile().email_confirmed
        response = self._call_api('09278911423')
        assert response['status'] == 'failed'
        assert response['code'] == 'UserLevelRestriction'
        assert response['message'] == 'EmailUneditable'

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_unconfirmed_email_change(self, mock_send_email: Mock):
        def check_email(*args, **kwargs):
            assert args[0] == new_email
            assert args[1] == 'otp'
        mock_send_email.side_effect = check_email

        assert self.user_vp.email_confirmed is False
        new_email = 'someothermail@gmail.com'
        assert validate_email(new_email) is True
        response = self._call_api(new_email)
        assert response['status'] == 'ok'
        assert response['updates'] == 2
        assert cache.get(f'email_verification_attempt:{self.user.pk}') == new_email
        self.user.refresh_from_db()
        user_otp = self.user.otps.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_status=UserOTP.OTP_STATUS.new,
        ).first()
        assert user_otp is not None
        assert user_otp.otp_usage == UserOTP.OTP_Usage._identifier_map['email-verification']

    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_unconfirmed_email_change_failed_and_social_register_by_email_succeed(self, mock_send_email: Mock):
        email = 'target_person_email@gmail.com'

        # ---------- an attacker send another user email for verification as his/her email --------------

        # given->
        self.user.email = None
        self.user.save(update_fields=['email'])

        assert self.user.email is None
        assert self.user_vp.email_confirmed is False
        assert validate_email(email) is True

        # when->
        response = self._call_api(email)

        # then->
        assert response['status'] == 'ok'
        assert response['updates'] == 2
        self.user.refresh_from_db()
        assert cache.get(f'email_verification_attempt:{self.user.pk}') == email
        assert self.user_vp.email_confirmed is False

        user_otp = self.user.otps.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_status=UserOTP.OTP_STATUS.new,
        ).first()

        assert user_otp is not None
        assert user_otp.otp_usage == UserOTP.OTP_Usage._identifier_map['email-verification']

        # ---------- real user logs in to the system with his/her email --------------

        # given->
        request_data = {"token": "valid-user-token", "device": "MaN4spkr", "remember": "yes"}
        id_token_payload = {
            'aud': '1039155241638-5ehvg8etjmdo2i6v7h8553m3hak0n7sp.apps.googleusercontent.com',
            'azp': '1039155241638-5ehvg8etjmdo2i6v7h8553m3hak0n7sp.apps.googleusercontent.com',
            'email': email,
            'email_verified': True,
            'exp': 1741428500,
            'family_name': 'alavi',
            'given_name': 'ali',
            'iat': 1741424900,
            'iss': 'https://accounts.google.com',
            'jti': '7c249fe2aca751b4b30ee0c57e5b234bc13603b3',
            'name': 'ali alavi',
            'nbf': 1741424600,
            'picture': 'https://lh3.googleusercontent.com/a/ACg8ocJglw5mL8oKjO7KVRk1HTi7iweYHbqP_UPymL5rZKB9drwQKQ=s96-c',
            'sub': '114386838446789955832',
        }

        # when->
        with patch('google.oauth2.id_token.verify_oauth2_token', return_value=id_token_payload):
            response = self.client.post(
                '/auth/google/', data=json.dumps(request_data, indent=4), content_type='application/json'
            ).json()

        # then->
        assert response['status'] == 'ok'
        assert response['key'] is not None
        assert response['device'] is not None

        registered_user = User.objects.filter(email=email).first()
        assert registered_user is not None
        assert registered_user.is_email_verified == True
        assert registered_user.id != self.user.id  # attacker could not abuse target person email

        # ---------- if otp code is stolen anyway by attacker, verify will be failed --------------
        # given->
        user_otp = self.user.otps.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_status=UserOTP.OTP_STATUS.new,
        ).first()

        # when->
        response = self.client.post(
            '/users/verify-email', data=json.dumps({'otp': user_otp.code}, indent=4), content_type='application/json'
        ).json()
        # then->
        assert response['status'] == 'failed'

    def test_set_and_verify_email_success(self):
        # ---------- set email scenario --------------

        # given->
        email = 'sample@gmail.com'
        self.user.email = None
        self.user.save(update_fields=['email'])

        # when->
        response = self._call_api(email)

        # then->
        assert response['status'] == 'ok'

        # ---------- verify email scenario --------------

        # given->
        user_otp = self.user.otps.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_status=UserOTP.OTP_STATUS.new,
        ).first()

        # when->
        response = self.client.post(
            '/users/verify-email', data=json.dumps({'otp': user_otp.code}, indent=4), content_type='application/json'
        ).json()

        # then->
        assert response['status'] == 'ok'
        updated_user = User.objects.filter(email=email).first()
        assert self.user.id == updated_user.id

    def test_resend_otp_for_email_verification(self):
        # ---------- set email scenario --------------

        email = 'sample@gmail.com'
        self.user.email = None
        self.user.save(update_fields=['email'])

        response = self.client.post(
            path='/users/profile-edit',
            data={'email': email},
        ).json()

        assert response['status'] == 'ok'

        otp1 = UserOTP.objects.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_usage=UserOTP.OTP_Usage._identifier_map['email-verification'],
            user=self.user,
        ).first()
        assert otp1 is not None
        self.user.otp_expiry = timezone.now() - datetime.timedelta(minutes=22)
        self.user.save(update_fields=['otp_expiry'])

        # ---------- resend email otp scenario --------------

        data = {
            "type": "email",
            "usage": "email-verification",
        }
        response = self.client.post(
            path='/otp/request',
            data=data,
        ).json()
        assert response.get('status') == 'ok'

        otp2 = (
            UserOTP.objects.filter(
                otp_type=UserOTP.OTP_TYPES.email,
                otp_usage=UserOTP.OTP_Usage._identifier_map['email-verification'],
                user=self.user,
            )
            .exclude(pk=otp1.pk)
            .first()
        )

        assert otp2 is not None
        assert otp2.code != otp1.code

        # ---------- verify email scenario --------------

        # when->
        response = self.client.post(
            '/users/verify-email', data=json.dumps({'otp': otp2.code}, indent=4), content_type='application/json'
        ).json()

        # then->
        assert response['status'] == 'ok'
        updated_user = User.objects.filter(email=email).first()
        assert self.user.id == updated_user.id

    def test_change_and_verify_email_when_otp_expired_failed(self):
        # ---------- change email scenario --------------

        # given->
        email = 'sample@gmail.com'
        self.user.save(update_fields=['email'])

        # when->
        response = self._call_api(email)

        # then->
        assert response['status'] == 'ok'

        # ---------- verify email scenario --------------

        # given->
        user_otp = self.user.otps.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_status=UserOTP.OTP_STATUS.new,
        ).first()
        cache.delete(f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{self.user.pk}')

        # when->
        response = self.client.post(
            '/users/verify-email', data=json.dumps({'otp': user_otp.code}, indent=4), content_type='application/json'
        ).json()

        # then->
        assert response['status'] == 'failed'

    def test_change_to_repetitive_email(self):
        other_users_email = User.objects.get(pk=204).email
        assert validate_email(other_users_email) is True
        response = self._call_api(other_users_email)
        assert response['status'] == 'failed'
        assert response['code'] == 'ValidationError'
        assert response['message'] == 'EmailAlreadyRegistered'

    def test_email_validation(self):
        assert self.user_vp.email_confirmed is False
        bad_email = 'someOtherMail@gmil.com'
        assert validate_email(bad_email) is False
        response = self._call_api(bad_email)
        assert response['status'] == 'failed'
        assert response['code'] == 'ValidationError'
        assert response['message'] == 'EmailValidationFailed'

    def test_user_have_active_merge_request(self):
        UserMergeRequest.objects.create(
            status=UserMergeRequest.STATUS.need_approval,
            merge_by=UserMergeRequest.MERGE_BY.email,
            main_user= self.user,
            second_user= self.user,
        )
        new_email = 'someothermail@gmail.com'
        response = self._call_api(new_email)
        assert response['status'] == 'failed'
        assert response['code'] == 'HasActiveMergeRequestError'
        assert response['message'] == 'User has active merge request.'


class TestUserOTP(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.get_verification_profile().email_confirmed = True
        self.user.get_verification_profile().save()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.user.mobile = '09351234567'
        self.user.save()

    def test_user_otp_verify_success_on_recreate(self):
        user: User = self.user
        otp1 = user.generate_otp(tp=UserOTP.OTP_TYPES.email)
        user_otp1 = user.generate_otp_obj(tp=UserOTP.OTP_TYPES.email, usage=UserOTP.OTP_Usage.generic, otp=otp1)

        otp2 = user.generate_otp(tp=UserOTP.OTP_TYPES.email)
        user_otp2 = user.generate_otp_obj(tp=UserOTP.OTP_TYPES.email, usage=UserOTP.OTP_Usage.generic, otp=otp2)

        user_otp1.refresh_from_db()
        self.assertEqual(user_otp1.code, user_otp2.code)
        self.assertEqual(user_otp1.otp_status, UserOTP.OTP_STATUS.disabled)
        obj, error = UserOTP.verify(user_otp2.code, UserOTP.OTP_TYPES.email, UserOTP.OTP_Usage.generic, self.user)
        self.assertEqual(error, None)


class TestOTPRequest(APITestCase):

    def setUp(self):
        self.user = User.objects.get(pk=202)
        self.user.mobile = '09151234567'
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def _call_api(self, data):
        return self.client.post(
            path='/otp/request',
            data=data,
        ).json()

    def test_address_book_otp_request(self):
        data = {
            "type": "mobile",
            "usage": "address_book",
        }
        response = self._call_api(data)
        assert response.get('status') == 'ok'
        user_sms: UserSms = UserSms.objects.get(user=self.user, tp=UserSms.TYPES.verify_new_address,
                                                template=UserSms.TEMPLATES.verify_new_address)
        assert user_sms.to == self.user.mobile
        assert user_sms.created_at >= timezone.now() - timezone.timedelta(seconds=1)

        user_otp = UserOTP.objects.get(otp_type=UserOTP.OTP_TYPES.mobile, otp_usage=UserOTP.OTP_Usage.address_book,
                                       user=self.user)
        assert user_otp
        user_otp.mark_as_used()

        data = {
            "type": "mobile",
        }
        response = self._call_api(data)
        assert response.get('status') == 'ok'
        user_sms = UserSms.objects.filter(user=self.user).order_by('-created_at').first()
        assert user_sms.tp != UserSms.TYPES.verify_new_address
        assert user_sms.template != UserSms.TEMPLATES.verify_new_address

    def test_otp_for_email_verification(self):
        data = {
            "type": "email",
            "usage": "anti_phishing_code",
        }
        response = self._call_api(data)
        assert response.get('status') == 'failed'
        assert response.get('code') == 'UnverifiedEmail'
        assert not UserOTP.objects.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_usage=UserOTP.OTP_Usage.anti_phishing_code,
            user=self.user,
        ).exists()
        data = {
            "type": "email",
            "usage": "email-verification",
        }
        response = self._call_api(data)
        assert response.get('status') == 'ok'
        otp = UserOTP.objects.filter(
            otp_type=UserOTP.OTP_TYPES.email,
            otp_usage=UserOTP.OTP_Usage._identifier_map['email-verification'],
            user=self.user,
        ).first()
        assert otp is not None


class TestEditSocialLogin(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user.auth_token.key}")

    def _post_request(self, data: dict) -> HttpResponse:
        return self.client.post("/users/profile-edit", data)

    def _check_response(
        self, response: HttpResponse, status_code: int, status_data: str = None, code: str = None, message: str = None
    ) -> Any:
        assert response.status_code == status_code
        data = response.json()
        if status_data:
            assert data["status"] == status_data
        if code:
            assert data["code"] == code
        if message:
            assert data["message"] == message
        return data

    def _check_social_login(self, user: User, social_login_enabled: bool):
        assert user.social_login_enabled == social_login_enabled

    def deactivate_social_login_without_password(self):
        self.user.social_login_enabled = True
        self.user.password = "!nobitex"
        self.user.save(update_fields=["password", "social_login_enabled"])
        response = self._post_request({"socialLoginEnabled": False})
        self._check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data="failed",
            code="UserAccountDoesNotHavePassword",
            message="UserAccount does not have password.",
        )

    def deactivate_social_login_with_password(self):
        self.user.social_login_enabled = True
        self.user.password = "nobitex"
        self.user.save(update_fields=["password", "social_login_enabled"])
        response = self._post_request({"socialLoginEnabled": False})
        self._check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data="ok",
        )

    def deactivate_disabled_social_login(self):
        self.user.social_login_enabled = False
        self.user.password = "nobitex"
        self.user.save(update_fields=["password", "social_login_enabled"])
        response = self._post_request({"socialLoginEnabled": False})
        self._check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data="ok",
        )

    def activate_disabled_social_login(self):
        self.user.social_login_enabled = False
        self.user.save(update_fields=["social_login_enabled"])
        response = self._post_request({"socialLoginEnabled": True})
        self._check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data="ok",
        )


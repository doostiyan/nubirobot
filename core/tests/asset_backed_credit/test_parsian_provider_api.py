from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import ThirdPartyError
from exchange.asset_backed_credit.externals.providers.parsian import (
    PARSIAN,
    DebitCardOTPRequestAPI,
    DebitCardSuspendAPI,
    GetCityAPI,
    GetProvinceAPI,
    IssueChildCardAPI,
    ParsianAPI,
)
from exchange.asset_backed_credit.models import OutgoingAPICallLog
from exchange.asset_backed_credit.services.debit.schema import DebitCardUserInfoSchema
from exchange.asset_backed_credit.services.logging import process_abc_outgoing_api_logs
from tests.asset_backed_credit.helper import MockCacheValue


class TestParsianProvider(TestCase):
    def setUp(self):
        cache.clear()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.parsian.api.GetProvinceAPI.request', lambda self, name: 1)
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.GetCityAPI.request',
        lambda self, province_id, name: 100,
    )
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '1000200030004000')
    @patch.object(ParsianAPI, 'PARENT_CARD_PASSWORD', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_issue_child_card(self):
        user_info = DebitCardUserInfoSchema(
            first_name='علی',
            last_name='محمدی',
            first_name_en='ali',
            last_name_en='mohammadi',
            national_code='1223334444',
            birth_cert_no='1000',
            mobile='09121002020',
            father_name='حسین',
            gender=User.GENDER.male,
            birth_date='1360/10/12',
            postal_code='1020304050',
            province='تهران',
            city='تهران',
            address='ورودی شهر سمت راست',
            color=5,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
                'CardRequestId': 1000,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '1000',
                                'NationalCode': '1223334444',
                                'PersianFirstName': 'علی',
                                'PersianLastName': 'محمدی',
                                'LatinFirstName': 'ali',
                                'LatinLastName': 'mohammadi',
                                'GenderTypeCode': 1,
                                'FatherName': 'حسین',
                                'BirthDate': '1360/10/12',
                                'CellNumber': '09121002020',
                                'Address': 'ورودی شهر سمت راست',
                                'ZipCode': '1020304050',
                            }
                        ],
                        'FeeAmount': 0,
                        'CityId': 100,
                        'Indicator': '12345',
                        'DesignCode': '14535-Golbehi',
                        'SecondPassword': 'password',
                        'ParentCardNumber': '1000200030004000',
                    }
                ),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        result = IssueChildCardAPI().request(user_info=user_info)
        assert result.is_success == True
        assert result.error_code == None
        assert result.message == 'success'
        assert result.card_request_id == 1000

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1
        log = OutgoingAPICallLog.objects.last()
        assert log.request_body.get('ParentCardNumber') == '*****'
        assert log.request_body.get('SecondPassword') == '*****'
        assert log.request_body.get('Detail')[0].get('NationalCode') == '*****'

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.parsian.api.GetProvinceAPI.request', lambda self, name: 1)
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.GetCityAPI.request',
        lambda self, province_id, name: 100,
    )
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '1000200030004000')
    @patch.object(ParsianAPI, 'PARENT_CARD_PASSWORD', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_issue_child_failed_with_error_code(self):
        user_info = DebitCardUserInfoSchema(
            first_name='علی',
            last_name='محمدی',
            first_name_en='ali',
            last_name_en='mohammadi',
            national_code='1223334444',
            birth_cert_no='1000',
            mobile='09121002020',
            father_name='حسین',
            gender=User.GENDER.male,
            birth_date='1360/10/12',
            postal_code='1020304050',
            province='تهران',
            city='تهران',
            address='ورودی شهر سمت راست',
            color=6,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={'IsSuccess': False, 'ErrorCode': 10, 'Message': 'failure', 'CardRequestId': None},
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '1000',
                                'NationalCode': '1223334444',
                                'PersianFirstName': 'علی',
                                'PersianLastName': 'محمدی',
                                'LatinFirstName': 'ali',
                                'LatinLastName': 'mohammadi',
                                'GenderTypeCode': 1,
                                'FatherName': 'حسین',
                                'BirthDate': '1360/10/12',
                                'CellNumber': '09121002020',
                                'Address': 'ورودی شهر سمت راست',
                                'ZipCode': '1020304050',
                            }
                        ],
                        'FeeAmount': 0,
                        'CityId': 100,
                        'Indicator': '12345',
                        'DesignCode': '14535-Banafsh',
                        'SecondPassword': 'password',
                        'ParentCardNumber': '1000200030004000',
                    }
                ),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        result = IssueChildCardAPI().request(user_info=user_info)
        assert result.is_success == False
        assert result.error_code == 10
        assert result.message == 'failure'
        assert result.card_request_id is None

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1
        log = OutgoingAPICallLog.objects.last()
        assert log.request_body.get('ParentCardNumber') == '*****'
        assert log.request_body.get('SecondPassword') == '*****'
        assert log.request_body.get('Detail')[0].get('NationalCode') == '*****'

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.providers.parsian.api.GetProvinceAPI.request', lambda self, name: 1)
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_issue_child_card_failure_city_id_not_found(self):
        user_info = DebitCardUserInfoSchema(
            first_name='علی',
            last_name='محمدی',
            first_name_en='ali',
            last_name_en='mohammadi',
            national_code='1223334444',
            birth_cert_no='1000',
            mobile='09121002020',
            father_name='حسین',
            gender=User.GENDER.male,
            birth_date='1360/10/12',
            postal_code='1020304050',
            province='تهران',
            city='تهران',
            address='ورودی شهر سمت راست',
            color=6,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'CardRequestId': 11131719,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '1000',
                                'NationalCode': '1223334444',
                                'PersianFirstName': 'علی',
                                'PersianLastName': 'محمدی',
                                'LatinFirstName': 'ali',
                                'LatinLastName': 'mohammadi',
                                'GenderTypeCode': 1,
                                'FatherName': 'حسین',
                                'BirthDate': '1360/10/12',
                                'CellNumber': '09121002020',
                                'Address': 'ورودی شهر سمت راست',
                                'ZipCode': '1020304050',
                            }
                        ],
                        'FeeAmount': '',
                        'CityId': 100,
                        'Indicator': '12345',
                        'DesignCode': '14535-Banafsh',
                        'SecondPassword': '',
                        'ParentCardNumber': '',
                    }
                ),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 100, 'ProvinceId': 1, 'PersianTitle': 'اصفهان'},
                    {'Id': 101, 'ProvinceId': 1, 'PersianTitle': 'کاشان'},
                    {'Id': 102, 'ProvinceId': 1, 'PersianTitle': 'نطنز'},
                    {'Id': 103, 'ProvinceId': 1, 'PersianTitle': 'شهرضا'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 1}),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        with self.assertRaises(ThirdPartyError):
            IssueChildCardAPI().request(user_info=user_info)

    @responses.activate
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    def test_get_province_id(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getProvince',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'GetProvinceDetails': [
                    {'Id': 1, 'PersianTitle': 'تهران'},
                    {'Id': 2, 'PersianTitle': 'اصفهان'},
                    {'Id': 3, 'PersianTitle': 'فارس'},
                    {'Id': 4, 'PersianTitle': 'خراسان رضوی'},
                    {'Id': 5, 'PersianTitle': 'کرمان'},
                    {'Id': 6, 'PersianTitle': 'گلستان'},
                ],
            },
            status=200,
            match=[responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='})],
        )

        province_id = GetProvinceAPI().request(name='کرمان')
        assert province_id == 5

    @responses.activate
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    def test_get_city_id(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 100, 'ProvinceId': 1, 'PersianTitle': 'تهران'},
                    {'Id': 101, 'ProvinceId': 1, 'PersianTitle': 'اندیشه'},
                    {'Id': 102, 'ProvinceId': 1, 'PersianTitle': 'بومهن'},
                    {'Id': 103, 'ProvinceId': 1, 'PersianTitle': 'پردیس'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 1}),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        city_id = GetCityAPI().request(province_id=1, name='پردیس')
        assert city_id == 103

    @responses.activate
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    def test_request_otp_code(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/Issuer/HashCard',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
                'GetHashCardsRequest': {'HashCode': '4889500040003000', 'CardNumber': '6221500060007000'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'CardNumber': '6221500060007000'}),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/Issuer/SendSMSToCardHolder',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {'CardNumberHash': '4889500040003000', 'LastFourDigitNumber': '7000'}
                ),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )
        success = DebitCardOTPRequestAPI().request(pan='6221500060007000')
        assert success

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 2

        log1, log2 = list(OutgoingAPICallLog.objects.order_by('id'))[-2:]
        assert log1.request_body.get('CardNumber') == '*****'
        assert log1.response_body.get('GetHashCardsRequest').get('HashCode') == '*****'
        assert log1.response_body.get('GetHashCardsRequest').get('CardNumber') == '*****'
        assert log2.request_body.get('CardNumberHash') == '*****'

    @responses.activate
    @patch.object(PARSIAN, 'username', 'username')
    @patch.object(PARSIAN, 'password', 'password')
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '5050100022228888')
    def test_suspend_card_api(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/Issuer/SuspendChildCard',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'ParentCardNumber': '5050100022228888',
                        'ChildCardNumber': '5041200022225555',
                        'SuspendIdentifier': 1,
                        'Description': 'درخواست مشتری',
                    }
                ),
                responses.matchers.header_matcher({'Authorization': f'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}),
            ],
        )

        success = DebitCardSuspendAPI().request(pan='5041200022225555')
        assert success

        process_abc_outgoing_api_logs()
        assert OutgoingAPICallLog.objects.all().count() == 1

        log = OutgoingAPICallLog.objects.order_by('id').last()
        assert log.request_body.get('ParentCardNumber') == '*****'
        assert log.request_body.get('ChildCardNumber') == '*****'
        assert log.request_body.get('SuspendIdentifier') == 1

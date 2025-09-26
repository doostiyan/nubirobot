from datetime import datetime
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers.parsian import ParsianAPI
from exchange.asset_backed_credit.models import (
    Card,
    CardDeliveryAddressAPISchema,
    CardRequestAPISchema,
    InternalUser,
    Service,
    UserFinancialServiceLimit,
    UserServicePermission,
)
from exchange.asset_backed_credit.services.debit.card import (
    create_debit_card,
    register_debit_cards_in_third_party,
    settle_debit_cards_issue_cost,
)
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins, MockCacheValue


class TestDebitCardIssueCron(TestCase, ABCMixins):
    def setUp(self):
        cache.clear()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()

    @classmethod
    def setUpTestData(cls):
        Settings.set('abc_debit_card_creation_enabled', 'yes')
        user, _ = User.objects.get_or_create(
            username='john.doe',
            national_code='1234567890',
            first_name='جان',
            last_name='دو',
            father_name='جان پدر',
            birthday=datetime(2000, 2, 3),
            mobile='09123456789',
            requires_2fa=True,
            user_type=User.USER_TYPES.level2,
        )
        internal_user = InternalUser.objects.create(
            uid=user.uid,
            user_type=user.user_type,
            national_code=user.national_code,
            mobile=user.mobile,
            email=user.email,
        )
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_active=True, is_available=True
        )

        Service.objects.get_or_create(provider=Service.PROVIDERS.nobifi, tp=Service.TYPES.debit, is_active=True)

        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=10_000, max_limit=100_000)
        UserServicePermission.objects.create(user=user, service=service, created_at=timezone.now())

        cls.user = user
        cls.internal_user = internal_user
        cls.service = service

    @responses.activate
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '1000200030004000')
    @patch.object(ParsianAPI, 'PARENT_CARD_PASSWORD', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_register_debit_card(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
                'CardRequestId': 11131719,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '100',
                                'NationalCode': '1234567890',
                                'PersianFirstName': 'جان',
                                'PersianLastName': 'دو',
                                'LatinFirstName': 'john',
                                'LatinLastName': 'doe',
                                'GenderTypeCode': 0,
                                'FatherName': 'جان پدر',
                                'BirthDate': '1378/11/14',
                                'CellNumber': '09123456789',
                                'Address': 'خیابان دوم',
                                'ZipCode': '1234012340',
                            }
                        ],
                        'FeeAmount': 0,
                        'CityId': 103,
                        'Indicator': '12345',
                        'DesignCode': '14535-Piazi',
                        'SecondPassword': 'password',
                        'ParentCardNumber': '1000200030004000',
                    }
                ),
            ],
        )

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
                    {'Id': 6, 'PersianTitle': 'سیستان وبلوچستان'},
                ],
            },
            status=200,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 100, 'ProvinceId': 6, 'PersianTitle': 'زابل'},
                    {'Id': 101, 'ProvinceId': 6, 'PersianTitle': 'چابهار'},
                    {'Id': 102, 'ProvinceId': 6, 'PersianTitle': 'زاهدان'},
                    {'Id': 103, 'ProvinceId': 6, 'PersianTitle': 'ایرانشهر'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 6}),
            ],
        )

        card_info = CardRequestAPISchema(
            firstName='john',
            lastName='doe',
            birthCertNo='100',
            color=2,
            deliveryAddress=CardDeliveryAddressAPISchema(
                province='سیستان و بلوچستان', city='ایران شهر', postalCode='1234012340', address='خیابان دوم'
            ),
        )
        card = create_debit_card(user=self.user, internal_user=self.internal_user, card_info=card_info)
        settle_debit_cards_issue_cost()
        register_debit_cards_in_third_party()

        card.refresh_from_db()
        assert card.status == Card.STATUS.registered
        assert card.internal_user == self.internal_user
        assert card.internal_user.id
        assert card.internal_user.id == self.internal_user.id
        assert card.provider_info.get('id') == 11131719

    @responses.activate
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '1000200030004000')
    @patch.object(ParsianAPI, 'PARENT_CARD_PASSWORD', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_third_party_error(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={
                'IsSuccess': False,
                'ErrorCode': 'code',
                'Message': 'failure',
                'CardRequestId': None,
            },
            status=400,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '100',
                                'NationalCode': '1234567890',
                                'PersianFirstName': 'جان',
                                'PersianLastName': 'دو',
                                'LatinFirstName': 'john',
                                'LatinLastName': 'doe',
                                'GenderTypeCode': 0,
                                'FatherName': 'جان پدر',
                                'BirthDate': '1378/11/14',
                                'CellNumber': '09123456789',
                                'Address': 'خیابان دوم',
                                'ZipCode': '1234012340',
                            }
                        ],
                        'FeeAmount': 0,
                        'CityId': 103,
                        'Indicator': '12345',
                        'DesignCode': '14535-Golbehi',
                        'SecondPassword': 'password',
                        'ParentCardNumber': '1000200030004000',
                    }
                ),
            ],
        )

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
                    {'Id': 6, 'PersianTitle': 'سیستان وبلوچستان'},
                ],
            },
            status=200,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 100, 'ProvinceId': 6, 'PersianTitle': 'زابل'},
                    {'Id': 101, 'ProvinceId': 6, 'PersianTitle': 'چابهار'},
                    {'Id': 102, 'ProvinceId': 6, 'PersianTitle': 'زاهدان'},
                    {'Id': 103, 'ProvinceId': 6, 'PersianTitle': 'ایرانشهر'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 6}),
            ],
        )

        card_info = CardRequestAPISchema(
            firstName='john',
            lastName='doe',
            birthCertNo='100',
            color=5,
            deliveryAddress=CardDeliveryAddressAPISchema(
                province='سیستان و بلوچستان', city='ایران شهر', postalCode='1234012340', address='خیابان دوم'
            ),
        )
        card = create_debit_card(user=self.user, internal_user=self.internal_user, card_info=card_info)
        settle_debit_cards_issue_cost()
        register_debit_cards_in_third_party()

        card.refresh_from_db()
        assert card.status == Card.STATUS.issuance_payment_skipped
        assert card.internal_user == self.internal_user
        assert card.internal_user.id
        assert card.internal_user.id == self.internal_user.id
        assert card.provider_info.get('id') is None

    @responses.activate
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '1000200030004000')
    @patch.object(ParsianAPI, 'PARENT_CARD_PASSWORD', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_register_debit_card_service_not_available(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
                'CardRequestId': 11131719,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '100',
                                'NationalCode': '1234567890',
                                'PersianFirstName': 'جان',
                                'PersianLastName': 'دو',
                                'LatinFirstName': 'john',
                                'LatinLastName': 'doe',
                                'GenderTypeCode': 0,
                                'FatherName': 'جان پدر',
                                'BirthDate': '1378/11/14',
                                'CellNumber': '09123456789',
                                'Address': 'خیابان دوم',
                                'ZipCode': '1234012340',
                            }
                        ],
                        'FeeAmount': 0,
                        'CityId': 103,
                        'Indicator': '12345',
                        'DesignCode': '14535-Khaki',
                        'SecondPassword': 'password',
                        'ParentCardNumber': '1000200030004000',
                    }
                ),
            ],
        )

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
                    {'Id': 6, 'PersianTitle': 'سیستان وبلوچستان'},
                ],
            },
            status=200,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 100, 'ProvinceId': 6, 'PersianTitle': 'زابل'},
                    {'Id': 101, 'ProvinceId': 6, 'PersianTitle': 'چابهار'},
                    {'Id': 102, 'ProvinceId': 6, 'PersianTitle': 'زاهدان'},
                    {'Id': 103, 'ProvinceId': 6, 'PersianTitle': 'ایرانشهر'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 6}),
            ],
        )

        card_info = CardRequestAPISchema(
            firstName='john',
            lastName='doe',
            birthCertNo='100',
            color=4,
            deliveryAddress=CardDeliveryAddressAPISchema(
                province='سیستان و بلوچستان', city='ایران شهر', postalCode='1234012340', address='خیابان دوم'
            ),
        )
        card = create_debit_card(user=self.user, internal_user=self.internal_user, card_info=card_info)

        self.service.is_available = False
        self.service.save(update_fields=['is_available'])

        settle_debit_cards_issue_cost()
        register_debit_cards_in_third_party()

        card.refresh_from_db()
        assert card.status == Card.STATUS.registered
        assert card.provider_info.get('id') == 11131719

    @responses.activate
    @patch.object(ParsianAPI, 'PARENT_CARD_NUMBER', '1000200030004000')
    @patch.object(ParsianAPI, 'PARENT_CARD_PASSWORD', 'password')
    @patch(
        'exchange.asset_backed_credit.externals.providers.parsian.api.IssueChildCardAPI._get_random_indicator',
        lambda *_: '12345',
    )
    def test_register_debit_card_invalid_user_data_in_users(self):
        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/issueChildCard',
            json={
                'IsSuccess': True,
                'ErrorCode': None,
                'Message': 'success',
                'CardRequestId': 11131719,
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'Detail': [
                            {
                                'BirthCertificateNumber': '100',
                                'NationalCode': '1234567890',
                                'PersianFirstName': 'جان',
                                'PersianLastName': 'دو',
                                'LatinFirstName': 'john',
                                'LatinLastName': 'doe',
                                'GenderTypeCode': 0,
                                'FatherName': 'جان پدر',
                                'BirthDate': '1378/11/14',
                                'CellNumber': '09123456789',
                                'Address': 'خیابان دوم',
                                'ZipCode': '1234012340',
                            }
                        ],
                        'FeeAmount': 0,
                        'CityId': 103,
                        'Indicator': '12345',
                        'DesignCode': '14535-Mesi',
                        'SecondPassword': 'password',
                        'ParentCardNumber': '1000200030004000',
                    }
                ),
            ],
        )

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
                    {'Id': 6, 'PersianTitle': 'سیستان وبلوچستان'},
                ],
            },
            status=200,
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 100, 'ProvinceId': 6, 'PersianTitle': 'زابل'},
                    {'Id': 101, 'ProvinceId': 6, 'PersianTitle': 'چابهار'},
                    {'Id': 102, 'ProvinceId': 6, 'PersianTitle': 'زاهدان'},
                    {'Id': 103, 'ProvinceId': 6, 'PersianTitle': 'ایرانشهر'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 6}),
            ],
        )

        responses.post(
            url='https://issuer.pec.ir/pec/api/issuer/getCities',
            json={
                'IsSuccess': True,
                'ErrorCode': '',
                'Message': 'success',
                'Data': [
                    {'Id': 200, 'ProvinceId': 1, 'PersianTitle': 'تهران'},
                    {'Id': 201, 'ProvinceId': 1, 'PersianTitle': 'اندیشه'},
                ],
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher({'ProvinceId': 1}),
            ],
        )

        card_info = CardRequestAPISchema(
            firstName='john',
            lastName='doe',
            birthCertNo='100',
            color=3,
            deliveryAddress=CardDeliveryAddressAPISchema(
                province='سیستان و بلوچستان', city='ایران شهر', postalCode='1234012340', address='خیابان دوم'
            ),
        )

        card = create_debit_card(user=self.user, internal_user=self.internal_user, card_info=card_info)

        no_father_name_user, _ = User.objects.get_or_create(
            username='jane.doe',
            national_code='1000020000',
            first_name='جانان',
            last_name='سه',
            birthday=datetime(2000, 2, 3),
            mobile='09121002030',
            requires_2fa=True,
            user_type=User.USER_TYPES.level2,
        )
        no_father_name_internal_user = InternalUser.objects.create(
            uid=no_father_name_user.uid,
            user_type=no_father_name_user.user_type,
            national_code=no_father_name_user.national_code,
            mobile=no_father_name_user.mobile,
            email=no_father_name_user.email,
        )
        UserServicePermission.objects.create(user=no_father_name_user, service=self.service, created_at=timezone.now())

        no_father_name_card_info = CardRequestAPISchema(
            firstName='jane',
            lastName='se',
            birthCertNo='200',
            color=1,
            deliveryAddress=CardDeliveryAddressAPISchema(
                province='تهران', city='تهران', postalCode='1000020000', address='خیابان دوم'
            ),
        )

        no_father_name_card = create_debit_card(
            user=no_father_name_user, internal_user=no_father_name_internal_user, card_info=no_father_name_card_info
        )

        settle_debit_cards_issue_cost()
        register_debit_cards_in_third_party()

        card.refresh_from_db()
        assert card.status == Card.STATUS.registered
        assert card.internal_user == self.internal_user
        assert card.internal_user.id
        assert card.internal_user.id == self.internal_user.id
        assert card.provider_info.get('id') == 11131719

        no_father_name_card.refresh_from_db()
        assert no_father_name_card.status == Card.STATUS.issuance_payment_skipped
        assert no_father_name_card.internal_user == no_father_name_internal_user
        assert no_father_name_card.provider_info.get('id') is None

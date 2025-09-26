from unittest.mock import patch

import pytz
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import (
    Card,
    CardRequestAPISchema,
    InternalUser,
    Service,
    UserFinancialServiceLimit,
    UserServicePermission,
)
from exchange.asset_backed_credit.services.debit.card import create_debit_card
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.calendar import ir_now
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins
from tests.features.utils import BetaFeatureTestMixin


class CreateDebitCardApiTestCase(BetaFeatureTestMixin, ABCMixins, APITestCase):
    URL = '/asset-backed-credit/debit/cards'

    feature = DEBIT_FEATURE_FLAG

    @classmethod
    def setUpTestData(cls):
        Settings.set('abc_debit_card_creation_enabled', 'yes')
        user, _ = User.objects.get_or_create(first_name='john', last_name='doe', username='user')
        internal_user = InternalUser.objects.create(uid=user.uid, user_type=user.user_type)
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_available=True, is_active=True
        )
        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=10_000, max_limit=10_000_000)

        cls.nobifi_service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.nobifi, tp=Service.TYPES.debit, is_active=True
        )

        cls.user = user
        cls.internal_user = internal_user
        cls.service = service

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_feature_is_not_activated(self):
        resp = self.client.get(path=self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_success(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=ir_now())
        card = create_debit_card(
            user=self.user,
            internal_user=self.internal_user,
            card_info=CardRequestAPISchema(firstName='john', lastName='doe', birthCertNo='1234', color=3),
        )
        card.pan = '5041100020003000'
        card.status = Card.STATUS.activated
        card.issued_at = ir_now()
        card.save()

        resp = self.client.get(path=self.URL)
        assert card.internal_user.id
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'ok',
            'cards': [
                {
                    'id': card.id,
                    'firstName': 'john',
                    'lastName': 'doe',
                    'pan': '504110******3000',
                    'color': 3,
                    'status': 'activated',
                    'issuedAt': card.issued_at.astimezone(pytz.UTC).isoformat(),
                }
            ],
        }

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_card_has_no_pan_success(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=ir_now())
        card = create_debit_card(
            user=self.user,
            internal_user=self.internal_user,
            card_info=CardRequestAPISchema(firstName='john', lastName='doe', birthCertNo='1234', color=1),
        )
        card.status = Card.STATUS.requested
        card.save()

        resp = self.client.get(path=self.URL)
        assert card.internal_user.id
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'ok',
            'cards': [
                {
                    'id': card.id,
                    'firstName': 'john',
                    'lastName': 'doe',
                    'pan': None,
                    'color': 1,
                    'status': 'requested',
                    'issuedAt': None,
                }
            ],
        }

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_service_not_found(self):
        self.request_feature(self.user, 'done')

        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=ir_now())
        card = create_debit_card(
            user=self.user,
            internal_user=self.internal_user,
            card_info=CardRequestAPISchema(firstName='john', lastName='doe', birthCertNo='1234', color=2),
        )
        card.pan = '5041100020003000'
        card.status = Card.STATUS.activated
        card.save()

        with patch(
            'exchange.asset_backed_credit.models.service.Service.get_matching_active_service', lambda **kwargs: None
        ):
            resp = self.client.get(path=self.URL)
            assert card.internal_user.id
            assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert resp.json() == {
                'status': 'failed',
                'code': 'ServiceNotFoundError',
                'message': 'ServiceNotFoundError',
            }

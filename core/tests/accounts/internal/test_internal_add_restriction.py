from unittest.mock import MagicMock, patch
from uuid import uuid4

from exchange.accounts.models import User, UserRestriction, UserRestrictionChangeHistory
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.internal import idempotency
from exchange.base.internal.services import Services
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class TestInternalAddRestriction(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/users/%s/add-restriction'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')

    def _request(
        self,
        uid=None,
        restriction=None,
        considerations=None,
        description=None,
        duration_hours=None,
        headers=None,
        ref_id=None,
    ):
        uid = uid or self.user.uid
        data = {}
        if restriction is not None:
            data.update({'restriction': restriction})
        if considerations is not None:
            data.update({'considerations': considerations})
        if description is not None:
            data.update({'description': description})
        if duration_hours is not None:
            data.update({'durationHours': duration_hours})
        if ref_id is not None:
            data.update({'refId': ref_id})
        return self.client.post(self.URL % uid, data=data, headers=headers or {})

    def assert_failed(self, response, status_code, body):
        assert response.status_code == status_code
        assert response.json() == body

    @mock_internal_service_settings
    def test_internal_add_restriction(self):
        restriction = 'WithdrawRequest'
        considerations = 'test test'
        description = UserRestrictionsDescription.INACTIVE_SECURE_WITHDRAWAL.name
        duration_hours = 2
        ref_id = 1
        response = self._request(
            restriction=restriction,
            considerations=considerations,
            description=description,
            duration_hours=duration_hours,
            ref_id=ref_id,
        )

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        restriction_q = UserRestriction.objects.filter(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequest,
        )
        assert restriction_q.count() == 1
        restriction = restriction_q.first()
        assert restriction.description == UserRestrictionsDescription.INACTIVE_SECURE_WITHDRAWAL.value.format(
            duration=duration_hours
        )
        assert restriction.considerations == 'test test'
        assert restriction.source == Services.ABC
        assert restriction.ref_id == ref_id

        # request only with restriction
        response = self._request(restriction='Gateway', ref_id=ref_id)

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        restriction_q = UserRestriction.objects.filter(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.Gateway,
        )
        assert restriction_q.count() == 1
        restriction = restriction_q.first()
        assert restriction.description is None
        assert restriction.considerations == ''
        assert restriction.source == Services.ABC
        assert restriction.ref_id == ref_id

        user_restriction_change_history_q = UserRestrictionChangeHistory.objects.filter(user_restriction=restriction)
        assert user_restriction_change_history_q.count() == 1
        user_restriction_change_history = user_restriction_change_history_q.first()
        assert user_restriction_change_history.user_restriction == restriction
        assert user_restriction_change_history.change_type == UserRestrictionChangeHistory.CHANGE_TYPE_CHOICES.add
        assert user_restriction_change_history.change_by_service == Services.ABC
        assert user_restriction_change_history.ref_id == ref_id

    @mock_internal_service_settings
    @patch('exchange.accounts.views.internal.UserRestriction.add_restriction')
    def test_internal_add_restriction_idempotency(self, mock_add_restriction: MagicMock):
        restriction = 'WithdrawRequest'
        considerations = 'test test'
        description = UserRestrictionsDescription.INACTIVE_SECURE_WITHDRAWAL.name
        ref_id = 1
        idempotency_key = str(uuid4())

        duration_hours = 2
        for _ in range(2):
            response = self._request(
                restriction=restriction,
                considerations=considerations,
                description=description,
                duration_hours=duration_hours,
                ref_id=ref_id,
                headers={
                    idempotency.IDEMPOTENCY_HEADER: idempotency_key,
                },
            )

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        mock_add_restriction.assert_called_once()

    @mock_internal_service_settings
    def test_internal_add_restriction_user_invalid_restriction(self):
        restriction = 'invalid'
        response = self._request(restriction=restriction)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid choices: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_add_restriction_user_invalid_description(self):
        restriction = 'WithdrawRequest'
        description = 'invalid'
        duration_hours = 2
        response = self._request(
            restriction=restriction,
            description=description,
            duration_hours=duration_hours,
        )
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid enum: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_add_restriction_user_invalid_duration_hours(self):
        restriction = 'WithdrawRequest'
        duration_hours = 'invalid-int'
        response = self._request(
            restriction=restriction,
            duration_hours=duration_hours,
        )
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid integer value: "invalid-int"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_add_restriction_user_missing_restriction(self):
        response = self._request()
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing choices value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_add_restriction_user_not_found(self):
        restriction = 'WithdrawRequest'
        ref_id = 1
        response = self._request(str(uuid4()), restriction=restriction, ref_id=ref_id)
        self.assert_failed(response, 404, {'message': 'User not found', 'error': 'NotFound'})

    @mock_internal_service_settings
    def test_internal_add_restriction_no_ref_id(self):
        restriction = 'WithdrawRequest'
        response = self._request(restriction=restriction)
        self.assert_failed(
            response, 400, {'code': 'ParseError', 'message': 'Missing integer value', 'status': 'failed'}
        )

    @mock_internal_service_settings
    def test_internal_add_restriction_invalid_uuid(self):
        response = self._request('invalid-uuid')
        assert response.status_code == 404

    @mock_internal_service_settings
    def test_internal_add_restriction_token_without_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token("notification")}')
        response = self._request()
        self.assert_failed(response, 404, {'detail': 'یافت نشد.'})

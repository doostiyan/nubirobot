from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from exchange.accounts.models import User, UserRestriction, UserRestrictionChangeHistory
from exchange.base.internal import idempotency
from exchange.base.internal.services import Services
from tests.helpers import (
    APITestCaseWithIdempotency,
    InternalAPITestMixin,
    create_internal_token,
    mock_internal_service_settings,
)


class TestInternalRemoveRestriction(InternalAPITestMixin, APITestCaseWithIdempotency):
    URL = '/internal/users/%s/remove-restriction'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.restriction_type = 'WithdrawRequest'
        cls.ref_id = 1
        cls.restriction = UserRestriction.add_restriction(
            user=cls.user,
            restriction=getattr(UserRestriction.RESTRICTION, cls.restriction_type),
            duration=timedelta(hours=1),
            source=Services.ABC,
            ref_id=cls.ref_id,
        )
        cls.restriction_removals = cls.restriction.restriction_removals

        cls.restriction_type_2 = 'WithdrawRequestCoin'
        cls.ref_id_2 = 2
        cls.restriction_2 = UserRestriction.add_restriction(
            user=cls.user,
            restriction=getattr(UserRestriction.RESTRICTION, cls.restriction_type_2),
            duration=timedelta(hours=1),
            source=None,
            ref_id=cls.ref_id_2,
        )
        cls.restriction_removals_2 = cls.restriction_2.restriction_removals

        cls.restriction_type_3 = 'WithdrawRequestRial'
        cls.ref_id_3 = 3
        cls.restriction_3 = UserRestriction.add_restriction(
            user=cls.user,
            restriction=getattr(UserRestriction.RESTRICTION, cls.restriction_type_3),
            duration=timedelta(hours=1),
            source=Services.ADMIN,
            ref_id=cls.ref_id_3,
        )
        cls.restriction_removals_3 = cls.restriction_3.restriction_removals

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token(Services.ABC.value)}')

    def _request(self, uid=None, restriction=None, ref_id=None, headers=None):
        uid = uid or self.user.uid
        data = {}
        if restriction is not None:
            data.update({'restriction': restriction})
        if ref_id is not None:
            data.update({'refId': ref_id})
        return self.client.post(self.URL % uid, data=data, headers=headers or {})

    def assert_failed(self, response, status_code, body):
        assert response.status_code == status_code
        assert response.json() == body

    @mock_internal_service_settings
    def test_internal_remove_restriction(self):
        """The same service created this restriction, also wants to remove it, so it can be removed"""
        assert self.restriction_removals.count() == 1

        response = self._request(restriction=self.restriction_type, ref_id=self.ref_id)

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        assert (
            UserRestriction.objects.filter(
                user=self.user,
                restriction=getattr(UserRestriction.RESTRICTION, self.restriction_type),
            ).count()
            == 0
        )
        assert self.restriction_removals.count() == 0

        # When there is no restriction
        response = self._request(restriction=self.restriction_type, ref_id=self.ref_id)

        assert response.status_code == 200, response.json()
        assert response.json() == {}

        user_restriction_change_history_q = UserRestrictionChangeHistory.objects.filter(
            user_restriction__isnull=True,
            user=self.user,
            restriction=getattr(UserRestriction.RESTRICTION, self.restriction_type),
            change_type=UserRestrictionChangeHistory.CHANGE_TYPE_CHOICES.remove,
        )
        assert user_restriction_change_history_q.count() == 1
        user_restriction_change_history = user_restriction_change_history_q.first()
        assert user_restriction_change_history.user_restriction is None
        assert user_restriction_change_history.change_type == UserRestrictionChangeHistory.CHANGE_TYPE_CHOICES.remove
        assert user_restriction_change_history.change_by_service == Services.ABC
        assert user_restriction_change_history.ref_id == self.ref_id

    @mock_internal_service_settings
    def test_internal_remove_restriction_different_service_added_restriction(self):
        """
        A different service created this restriction, nothing goes wrong, it will not remove that restriction and
        it will return 200
        """
        response = self._request(restriction=self.restriction_type_3, ref_id=self.ref_id_3)

        assert response.status_code == 200
        assert (
            UserRestriction.objects.filter(
                user=self.user,
                restriction=getattr(UserRestriction.RESTRICTION, self.restriction_type_3),
                ref_id=self.ref_id_3,
            ).count()
            == 1
        )
        assert self.restriction_removals_3.count() == 1

    @mock_internal_service_settings
    def test_internal_remove_restriction_no_service_added_restriction(self):
        """
        No service created this restriction, nothing goes wrong, it will not remove that restriction and
        it will return 200
        """
        assert self.restriction_removals_2.count() == 1

        response = self._request(restriction=self.restriction_type_2, ref_id=self.ref_id_2)

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        assert (
            UserRestriction.objects.filter(
                user=self.user,
                restriction=getattr(UserRestriction.RESTRICTION, self.restriction_type_2),
            ).count()
            == 1
        )
        assert self.restriction_removals_2.count() == 1

    @mock_internal_service_settings
    @patch('exchange.accounts.views.internal.UserRestriction.delete_with_removals')
    def test_internal_remove_restriction_idempotency(self, mock_delete_with_removals: MagicMock):
        restriction = 'WithdrawRequest'
        ref_id = 1
        idempotency_key = str(uuid4())

        for _ in range(2):
            response = self._request(
                restriction=restriction,
                ref_id=ref_id,
                headers={
                    idempotency.IDEMPOTENCY_HEADER: idempotency_key,
                },
            )

        assert response.status_code == 200, response.json()
        assert response.json() == {}
        mock_delete_with_removals.assert_called_once()

    @mock_internal_service_settings
    def test_internal_remove_restriction_user_invalid_restriction(self):
        restriction = 'invalid'
        response = self._request(restriction=restriction)
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Invalid choices: "invalid"', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_remove_restriction_user_missing_restriction(self):
        response = self._request()
        self.assert_failed(
            response,
            400,
            {'status': 'failed', 'message': 'Missing choices value', 'code': 'ParseError'},
        )

    @mock_internal_service_settings
    def test_internal_remove_restriction_user_not_found(self):
        restriction = 'WithdrawRequest'
        ref_id = 1
        response = self._request(str(uuid4()), restriction=restriction, ref_id=1)
        self.assert_failed(response, 404, {'message': 'User not found', 'error': 'NotFound'})

    @mock_internal_service_settings
    def test_internal_remove_restriction_invalid_uuid(self):
        response = self._request('invalid-uuid')
        assert response.status_code == 404

    @mock_internal_service_settings
    def test_internal_remove_restriction_token_without_permission(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {create_internal_token("notification")}')
        response = self._request()
        self.assert_failed(response, 404, {'detail': 'یافت نشد.'})

    @mock_internal_service_settings
    def test_internal_remove_restriction_no_ref_id(self):
        restriction = 'WithdrawRequest'
        response = self._request(restriction=restriction)
        self.assert_failed(
            response, 400, {'code': 'ParseError', 'message': 'Missing integer value', 'status': 'failed'}
        )

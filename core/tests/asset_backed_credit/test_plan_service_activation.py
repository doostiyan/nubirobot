from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserServicePermission


class UserServiceTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.filter(pk=202).first()
        self.services = Service.objects.bulk_create(
            [
                Service(
                    tp=Service.TYPES.credit,
                    provider=Service.PROVIDERS.tara,
                    is_active=True,
                    contract_id='123',
                ),
                Service(
                    tp=Service.TYPES.loan,
                    provider=Service.PROVIDERS.tara,
                    is_active=False,
                    contract_id='456',
                ),
            ],
        )
        self.user_services = UserServicePermission.objects.bulk_create(
            [
                UserServicePermission(
                    user=self.user,
                    service=self.services[1],
                    created_at=timezone.now(),
                    revoked_at=timezone.now(),
                ),
                UserServicePermission(
                    user=self.user,
                    service=self.services[0],
                    created_at=timezone.now(),
                    revoked_at=timezone.now(),
                ),
                UserServicePermission(
                    user=self.user,
                    service=self.services[0],
                    created_at=timezone.now(),
                ),
            ],
        )

    def test_active_plan_service_function(self):
        assert not UserServicePermission.has_permission(
            self.user,
            self.services[1].provider,
            self.services[1].tp,
        )

        assert UserServicePermission.has_permission(
            self.user,
            self.services[0].provider,
            self.services[0].tp,
        )

from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit


class UserFinancialServiceLimitTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit, is_active=True
        )
        cls.other_service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, is_active=True
        )

        user = User.objects.get(pk=201)
        user.user_type = User.USER_TYPES.level1
        user.save(update_fields=('user_type',))
        cls.user = user

    def test_priority_min_max_from_user_service_limit(self):
        UserFinancialServiceLimit.set_user_limit(user=self.user, min_limit=1000, max_limit=10_000)
        UserFinancialServiceLimit.set_user_service_limit(
            user=self.user, service=self.service, min_limit=2000, max_limit=7000
        )
        UserFinancialServiceLimit.set_user_type_service_limit(
            user_type=User.USER_TYPES.level1, service=self.service, min_limit=3000, max_limit=9000
        )
        UserFinancialServiceLimit.set_service_limit(service=self.service, min_limit=500, max_limit=10_000)

        limit = UserFinancialServiceLimit.get_user_service_limit(user=self.user, service=self.service)
        assert limit.min_limit == 2000
        assert limit.max_limit == 7000

    def test_priority_min_from_user_service_max_from_user_limit(self):
        UserFinancialServiceLimit.set_user_limit(user=self.user, max_limit=12_000)
        UserFinancialServiceLimit.set_user_service_limit(
            user=self.user,
            service=self.service,
            min_limit=3000,
        )
        UserFinancialServiceLimit.set_user_type_service_limit(
            user_type=User.USER_TYPES.level1, service=self.service, min_limit=1500, max_limit=6000
        )
        UserFinancialServiceLimit.set_service_limit(service=self.service, min_limit=500, max_limit=10_000)

        limit = UserFinancialServiceLimit.get_user_service_limit(user=self.user, service=self.service)
        assert limit.min_limit == 3000
        assert limit.max_limit == 12_000

    def test_priority_min_from_user_max_from_user_type_service_limit(self):
        UserFinancialServiceLimit.set_user_limit(user=self.user, min_limit=1000)
        UserFinancialServiceLimit.set_user_type_service_limit(
            user_type=User.USER_TYPES.level1, service=self.service, min_limit=1500, max_limit=7500
        )
        UserFinancialServiceLimit.set_service_limit(service=self.service, min_limit=500, max_limit=10_000)

        limit = UserFinancialServiceLimit.get_user_service_limit(user=self.user, service=self.service)
        assert limit.min_limit == 1000
        assert limit.max_limit == 7500

    def test_priority_user_min_from_service_type_max_from_user_service_limit(self):
        UserFinancialServiceLimit.set_user_limit(user=self.user, max_limit=12_000)
        UserFinancialServiceLimit.set_user_service_limit(
            user=self.user,
            service=self.service,
            max_limit=23_000,
        )
        UserFinancialServiceLimit.set_user_type_service_limit(
            user_type=User.USER_TYPES.level1, service=self.other_service, min_limit=1500, max_limit=7500
        )
        UserFinancialServiceLimit.set_service_limit(service=self.service, max_limit=20_000)
        UserFinancialServiceLimit.set_service_type_limit(
            service_type=Service.TYPES.credit, min_limit=1000, max_limit=10_000
        )

        limit = UserFinancialServiceLimit.get_user_service_limit(user=self.user, service=self.service)
        assert limit.min_limit == 1000
        assert limit.max_limit == 23_000

    def test_priority_per_service_limits(self):
        UserFinancialServiceLimit.set_service_limit(service=self.service, min_limit=500, max_limit=5000)
        UserFinancialServiceLimit.set_service_limit(service=self.other_service, min_limit=400, max_limit=4000)

        UserFinancialServiceLimit.set_service_type_limit(
            service_type=Service.TYPES.credit, min_limit=800, max_limit=2000
        )
        UserFinancialServiceLimit.set_service_type_limit(
            service_type=Service.TYPES.loan, min_limit=500, max_limit=10_000
        )

        UserFinancialServiceLimit.set_service_provider_limit(
            service_provider=Service.PROVIDERS.tara, min_limit=300, max_limit=3000
        )
        UserFinancialServiceLimit.set_service_provider_limit(
            service_provider=Service.PROVIDERS.vency, min_limit=700, max_limit=70_000
        )

        limits = UserFinancialServiceLimit.get_limits_per_service()

        assert limits[self.service.id].min_limit == 500
        assert limits[self.service.id].max_limit == 5000
        assert limits[self.other_service.id].min_limit == 400
        assert limits[self.other_service.id].max_limit == 4000

    def test_priority_per_service_limit_different_min_max_source(self):
        UserFinancialServiceLimit.set_service_limit(
            service=self.service,
            min_limit=500,
        )
        UserFinancialServiceLimit.set_service_limit(
            service=self.other_service,
            max_limit=5000,
        )
        UserFinancialServiceLimit.set_service_type_limit(
            service_type=Service.TYPES.credit, min_limit=200, max_limit=2500
        )
        UserFinancialServiceLimit.set_service_type_limit(
            service_type=Service.TYPES.loan, min_limit=600, max_limit=60_000
        )

        UserFinancialServiceLimit.set_service_provider_limit(
            service_provider=Service.PROVIDERS.tara,
            min_limit=300,
        )
        UserFinancialServiceLimit.set_service_provider_limit(service_provider=Service.PROVIDERS.vency, max_limit=70_000)

        limits = UserFinancialServiceLimit.get_limits_per_service()

        assert limits[self.service.id].min_limit == 500
        assert limits[self.service.id].max_limit == 2500
        assert limits[self.other_service.id].min_limit == 600
        assert limits[self.other_service.id].max_limit == 5000

from decimal import Decimal

import pytest
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import MinimumInitialDebtError, ServiceLimitNotSet
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit
from exchange.base.models import Settings


class UserFinancialServiceLimitTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

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

        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=500)

    def test_get_user_limit(self):
        # Case 1: No matching limit
        with pytest.raises(ServiceLimitNotSet):
            UserFinancialServiceLimit.get_user_service_limit(self.user, service=self.services[0])

        UserFinancialServiceLimit.set_service_limit(self.services[0], max_limit=500)
        result = UserFinancialServiceLimit.get_user_service_limit(self.user, service=self.services[0])
        assert result.max_limit == 500

        UserFinancialServiceLimit.set_user_type_service_limit(
            service=self.services[0],
            user_type=User.USER_TYPES.level1,
            max_limit=200,
        )
        UserFinancialServiceLimit.set_user_type_service_limit(
            service=self.services[0],
            user_type=User.USER_TYPES.level2,
            max_limit=300,
        )
        UserFinancialServiceLimit.set_user_type_service_limit(
            service=self.services[0],
            user_type=User.USER_TYPES.verified,
            max_limit=400,
        )
        result = UserFinancialServiceLimit.get_user_service_limit(self.user, service=self.services[0])
        assert result.max_limit == 300

        UserFinancialServiceLimit.set_user_service_limit(
            user=self.user,
            service=self.services[0],
            max_limit=150,
        )
        result = UserFinancialServiceLimit.get_user_service_limit(self.user, service=self.services[0])
        assert result.max_limit == 150

        UserFinancialServiceLimit.set_user_limit(user=self.user, max_limit=100)
        result = UserFinancialServiceLimit.get_user_service_limit(self.user, service=self.services[0])
        assert result.max_limit == 150

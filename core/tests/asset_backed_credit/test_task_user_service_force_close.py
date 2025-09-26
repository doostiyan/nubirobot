from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, SettlementTransaction, UserService, UserServicePermission
from exchange.asset_backed_credit.tasks import task_force_close_user_service


class TestTaskForceCloseUserService(TestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_success(self):
        service, _ = Service.objects.get_or_create(provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit)
        service.is_active = True
        service.save()

        user_services = []
        for i in range(5):
            user, _ = User.objects.get_or_create(username=f'test-user-{i}')
            permission = UserServicePermission.objects.create(user=user, service=service)
            user_services.append(
                UserService.objects.create(
                    user=user,
                    service=service,
                    user_service_permission=permission,
                    initial_debt=1_000_000_0,
                    current_debt=1_000_000_0,
                )
            )

        SettlementTransaction.objects.create(
            user_service=user_services[4], amount=100_000_0, status=SettlementTransaction.STATUS.confirmed
        )

        service_ids = [service.id for service in user_services]
        service_ids.append(service_ids[-1] + 1)
        result = task_force_close_user_service.delay(service_ids).result

        for service_id in service_ids[0:3]:
            assert result[service_id]['status'] == 'success'
            assert result[service_id]['message'] == 'user service closed by force'

        service_id = service_ids[4]
        assert result[service_id]['status'] == 'failure'
        assert result[service_id]['message'] == 'user service has pending settlements'

        service_id = service_ids[5]
        assert result[service_id]['status'] == 'failure'
        assert result[service_id]['message'] == 'user service not found'

        for service_id in service_ids[:4]:
            assert UserService.objects.get(id=service_id).closed_at is not None

        assert UserService.objects.get(id=service_ids[4]).closed_at is None

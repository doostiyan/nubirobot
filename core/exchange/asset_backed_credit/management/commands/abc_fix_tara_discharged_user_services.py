from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.asset_backed_credit.exceptions import ServiceAlreadyDeactivated
from exchange.asset_backed_credit.models import OutgoingAPICallLog, Service, UserService
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.base.calendar import ir_now


class Command(BaseCommand):
    help = 'Fix Tara discharged user'

    USER_SERVICE_IDS = [24103]

    def handle(self, *args, **options):
        try:
            service = Service.objects.get(provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit, is_active=True)
        except Service.DoesNotExist:
            self.stdout.write(self.style.ERROR('Invalid service requested'))
            return

        logs = OutgoingAPICallLog.objects.select_related('user_service').filter(
            api_url__icontains='discharge',
            response_code=200,
            status=OutgoingAPICallLog.STATUS.success,
            user_service_id__in=self.USER_SERVICE_IDS,
            user_service__current_debt__gt=0,
            user_service__service=service,
        )

        user_services = [
            log.user_service
            for log in logs
            if log.user_service.current_debt == Decimal(log.request_body.get('amount', '-1'))
        ]

        processed_user_services = []
        for user_service in user_services:
            if user_service.id in processed_user_services:
                self.stdout.write(self.style.ERROR(f'user_service {user_service.id} already passed'))
                continue
            with transaction.atomic():
                _user_service = UserService.objects.select_for_update(no_key=True).get(id=user_service.id)
                try:
                    dispatcher = api_dispatcher(_user_service)
                    available_balance = dispatcher.get_available_balance()
                    if available_balance > 0:
                        self.stdout.write(
                            self.style.ERROR_OUTPUT(f'user service is not zero in provider! id: {_user_service.id}')
                        )

                    self._close(user_service, UserService.STATUS.closed)
                    dispatcher._send_close_notification()

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'user-service {_user_service.id}-{_user_service.user.mobile} closed successfully'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error: {_user_service.id}-{_user_service.user.mobile}, {str(e)}')
                    )

                processed_user_services.append(_user_service.id)

    @transaction.atomic
    def _close(self, user_service: UserService, status: int) -> None:
        """
        finalize the current settlement of the user if the settlement is not closed before and has zero current debt

        Parameters:
            - status (int): the selected status of the finalized settlement
            - closed_at (Optional[datetime]): the closure date of the settlement
            - save (bool): save settlement
        """
        user_service.assert_is_active()

        user_service.current_debt = 0
        user_service.status = status
        user_service.closed_at = ir_now()
        try:
            user_service.user_service_permission.deactivate()
        except ServiceAlreadyDeactivated:
            self.style.WARNING(
                f'user-service {user_service.id}-{user_service.user.mobile} permission already deactivated'
            )

        user_service.save(
            update_fields=(
                'current_debt',
                'status',
                'closed_at',
            )
        )

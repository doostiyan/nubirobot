from decimal import Decimal

from django.core.management import BaseCommand
from django.db import transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import InternalUser, Service, UserServicePermission
from exchange.asset_backed_credit.services.user_service import create_user_service


class Command(BaseCommand):
    help = 'Fixes pending Digipay accounts'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, help='user id')

    def handle(self, *args, **options):
        user_id = options.get('id')
        user = User.objects.get(id=user_id)
        internal_user = InternalUser.objects.filter(uid=user.uid).first()
        service = Service.objects.get(provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        user_permission = UserServicePermission.get_active_permission_by_service(user=user, service=service)
        if not user_permission:
            raise ValueError(f'No permission for user {user} and service {service}')

        tracking_code = '14339446501740835645163'

        with transaction.atomic():
            create_user_service(
                user=user,
                internal_user=internal_user,
                service=service,
                initial_debt=Decimal(260000000),
                permission=user_permission,
                account_number=tracking_code,
            )

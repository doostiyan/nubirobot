import json

from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService, UserServicePermission

DATA_BY_USER_ID_UPDATE = {'6221064861424279': '1001'}

DATA_BY_USER_ID = {'6221064861424667': '2344247'}


class Command(BaseCommand):
    help = "Create User-Service for (mobile, card-number) rows"

    @staticmethod
    def _get_data_by_user_id() -> dict:
        return DATA_BY_USER_ID

    @staticmethod
    def _get_data_by_user_id_for_update() -> dict:
        return DATA_BY_USER_ID_UPDATE

    @transaction.atomic
    def handle(self, *args, **options):
        service = Service.objects.get(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        result = {}
        for card_number, user_id in self._get_data_by_user_id().items():
            result[user_id] = {'card-number': card_number}

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                result[user_id].update({'user': 'not found', 'user_service': 'none'})
                continue
            except User.MultipleObjectsReturned:
                result[user_id].update({'user': 'multiple users', 'user_service': 'none'})

            try:
                self.create_user_service(card_number, service, user)
            except Exception as e:
                self.stdout.write(self.style.ERROR(str(e)))
                result[user_id].update({'user': 'found', 'user_service': 'error'})
                continue

            result[user_id].update({'user': 'found', 'user_service': 'ok'})

        for card_number, user_id in self._get_data_by_user_id_for_update().items():
            result[user_id] = {'card-number': card_number}

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                result[user_id].update({'user': 'not found', 'user_service': 'none'})
                continue
            except User.MultipleObjectsReturned:
                result[user_id].update({'user': 'multiple users', 'user_service': 'none'})

            try:
                updated = self.update_user_service(card_number, service, user)
                if not updated:
                    result[user_id].update({'user': 'found', 'user_service': 'error'})
                    continue
            except Exception as e:
                self.stdout.write(self.style.ERROR(str(e)))
                result[user_id].update({'user': 'found', 'user_service': 'error'})
                continue

            result[user_id].update({'user': 'found', 'user_service': 'ok'})

        self.stdout.write(
            self.style.NOTICE('Command Done'),
        )
        self.stdout.write(self.style.NOTICE(json.dumps(result)))

    @staticmethod
    def create_user_service(card_number, service, user):
        user_service_permission, _ = UserServicePermission.objects.get_or_create(user=user, service=service)
        UserService.objects.get_or_create(
            service=service,
            user=user,
            user_service_permission=user_service_permission,
            account_number=card_number,
            current_debt=0,
            initial_debt=0,
        )

    @staticmethod
    def update_user_service(card_number, service, user):
        updated_rows = UserService.objects.filter(account_number=card_number, service=service).update(user=user)
        return updated_rows != 0

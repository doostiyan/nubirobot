from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User

CHAT_ID = 'aee968bae9fc49eab103cde3fa2b5b18'

class FillUserIdOfChartsCommandTestCase(TestCase):
    def test_not_exist(self):
        number_of_users = User.objects.filter(chat_id__isnull=False).count()
        assert number_of_users
        call_command('fix_user_chat_id', batch_size=500, dry_run=False)
        assert User.objects.filter(chat_id__isnull=False).distinct('chat_id').count() == number_of_users

    def test_fix_user_id(self):
        postfix = '-user@test-fix-chat-id.com'
        same_chat_ids = [
            User(username=f'{num}' + postfix, email=f'{num}' + postfix, chat_id=CHAT_ID) for num in range(10)
        ]
        same_chat_ids = User.objects.bulk_create(same_chat_ids)

        number_of_users = User.objects.filter(chat_id__isnull=False).count()
        assert User.objects.filter(chat_id=CHAT_ID).count() == 10
        call_command('fix_user_chat_id', batch_size=500, dry_run=True)
        assert User.objects.filter(chat_id=CHAT_ID).count() == 10

        call_command('fix_user_chat_id', batch_size=500)
        assert User.objects.filter(chat_id=CHAT_ID).count() == 1
        assert User.objects.filter(chat_id__isnull=False).distinct('chat_id').count() == number_of_users

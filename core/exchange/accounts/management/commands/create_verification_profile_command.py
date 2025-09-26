from django.core.management import BaseCommand

from exchange.accounts.models import User, VerificationProfile


class Command(BaseCommand):
    def handle(self, *args, **options):
        users_without_vp = User.objects.filter(verification_profile__isnull=True)
        vps = [VerificationProfile(user=user) for user in users_without_vp]
        VerificationProfile.objects.bulk_create(vps, batch_size=1000)

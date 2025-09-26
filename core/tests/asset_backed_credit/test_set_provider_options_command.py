from django.core.management import call_command
from django.test import TestCase

from exchange.asset_backed_credit.models import Service


class CommandsTestCase(TestCase):
    def setUp(self):
        self.service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            defaults={
                'options': {
                    'dummy_key': 'dummy_value',
                }
            },
        )
        self.service.save()

    def test_command(self):
        call_command('abc_set_service_provider_options')

        self.service.refresh_from_db()
        assert self.service.options == {'dummy_key': 'dummy_value', 'provider_fee': 23, 'periods': [1, 3, 6, 9, 12]}
        assert self.service.interest == 23

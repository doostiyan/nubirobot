from unittest import TestCase

from django.core.management import call_command

from exchange.asset_backed_credit.models import Card, CardSetting
from tests.asset_backed_credit.helper import ABCMixins


class AddDefaultCardLimitsSettingsTest(TestCase, ABCMixins):

    def test_command_successfully_adds_two_default_card_levels(self):
        previous_count = CardSetting.objects.count()

        call_command('abc_add_default_debit_card_limits')

        assert previous_count + 2 == CardSetting.objects.count()
        assert CardSetting.objects.get(
            level=1,
            label='سطح یک',
            per_transaction_amount_limit=100_000_000,
            daily_transaction_amount_limit=100_000_000,
            monthly_transaction_amount_limit=100_000_000,
            cashback_percentage=0.0,
        )
        assert CardSetting.objects.get(
            level=2,
            label='سطح دو',
            per_transaction_amount_limit=1_000_000_000,
            daily_transaction_amount_limit=1_000_000_000,
            monthly_transaction_amount_limit=5_000_000_000,
            cashback_percentage=0.0,
        )

    def test_with_level_one_exists(self):
        level1 = self.create_card_setting(1, 1, 1, 1, 1)
        previous_count = CardSetting.objects.count()

        call_command('abc_add_default_debit_card_limits')

        assert previous_count + 1 == CardSetting.objects.count()
        assert CardSetting.objects.get(
            level=2,
            label='سطح دو',
            per_transaction_amount_limit=1_000_000_000,
            daily_transaction_amount_limit=1_000_000_000,
            monthly_transaction_amount_limit=5_000_000_000,
            cashback_percentage=0.0,
        )
        level1.refresh_from_db()
        assert level1.per_transaction_amount_limit == 1
        assert level1.daily_transaction_amount_limit == 1
        assert level1.monthly_transaction_amount_limit == 1
        assert level1.cashback_percentage == 1

    def test_command_adds_level_one_to_all_existing_cards_with_no_level(self):
        user_service = self.create_user_service()
        card1 = self.create_card(self.generate_random_pan(), user_service)
        card2 = self.create_card(self.generate_random_pan(), user_service)
        level_setting20 = self.create_card_setting(20)
        card3 = self.create_card(self.generate_random_pan(), user_service, setting=level_setting20)

        assert card1.setting is None
        assert card2.setting is None
        assert card3.setting == level_setting20

        call_command('abc_add_default_debit_card_limits')

        card1.refresh_from_db()
        card2.refresh_from_db()
        card3.refresh_from_db()
        level1 = CardSetting.objects.get(level=1)

        assert card1.setting == level1
        assert card2.setting == level1
        assert card3.setting == level_setting20

    def tearDown(self):
        Card.objects.all().delete()
        CardSetting.objects.all().delete()

from unittest.mock import patch

from django.test import TestCase

from exchange.corporate_banking.integrations.jibit.cards_list import CardDTO
from exchange.corporate_banking.models import CoBankAccount, CoBankCard
from exchange.corporate_banking.models.constants import ACCOUNT_TP, COBANK_PROVIDER, NOBITEX_BANK_CHOICES
from exchange.corporate_banking.services.accounts import CardSyncService


class TestCardSyncService(TestCase):
    def setUp(self):
        self.bank_account = CoBankAccount.objects.create(
            iban='IR12345678901234567890',
            account_number='123456789',
            provider=COBANK_PROVIDER.jibit,
            bank=NOBITEX_BANK_CHOICES.mellat,
            provider_bank_id=5,
            account_tp=ACCOUNT_TP.operational,
        )
        self.service = CardSyncService()

        self.card_dto = CardDTO(
            id=1111,
            cardNumber='5022291012345678',
            iban='IR12345678901234567890',
            active=True,
        )

    @patch('exchange.corporate_banking.services.accounts.CobankJibitCardsList.get_cards')
    def test_creates_new_card(self, mock_get_cards):
        mock_get_cards.return_value = [self.card_dto]

        self.service.sync_bank_cards(self.bank_account)

        created_card = CoBankCard.objects.filter(bank_account=self.bank_account).first()
        assert created_card is not None
        assert created_card.card_number == '5022291012345678'
        assert created_card.provider_card_id == '1111'
        assert created_card.provider_is_active is True

    @patch('exchange.corporate_banking.services.accounts.CobankJibitCardsList.get_cards')
    def test_updates_existing_card(self, mock_get_cards):
        existing_card = CoBankCard.objects.create(
            bank_account=self.bank_account,
            card_number='5022291012345678',
            provider_card_id='9999',  # will be updated
            provider_is_active=False,  # will be updated
        )

        mock_get_cards.return_value = [self.card_dto]
        self.service.sync_bank_cards(self.bank_account)

        existing_card.refresh_from_db()
        assert existing_card.provider_card_id == '1111'
        assert existing_card.provider_is_active is True

    @patch('exchange.corporate_banking.services.accounts.CobankJibitCardsList.get_cards')
    def test_skips_update_if_data_unchanged(self, mock_get_cards):
        existing_card = CoBankCard.objects.create(
            bank_account=self.bank_account,
            card_number=self.card_dto.cardNumber,
            provider_card_id=str(self.card_dto.id),
            provider_is_active=self.card_dto.active,
        )
        mock_get_cards.return_value = [self.card_dto]

        with patch.object(CoBankCard.objects, 'bulk_update') as mock_bulk_update, patch.object(
            CoBankCard.objects, 'bulk_create'
        ) as mock_bulk_create:
            self.service.sync_bank_cards(self.bank_account)
            mock_bulk_update.assert_not_called()
            mock_bulk_create.assert_not_called()

            assert CoBankCard.objects.count() == 1
            existing_card.refresh_from_db()
            assert existing_card.provider_card_id == str(self.card_dto.id)
            assert existing_card.provider_is_active is self.card_dto.active

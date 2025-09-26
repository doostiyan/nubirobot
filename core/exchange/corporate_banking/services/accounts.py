from exchange.corporate_banking.integrations.jibit.cards_list import CobankJibitCardsList
from exchange.corporate_banking.models import CoBankCard


class CardSyncService:
    def sync_bank_cards(self, bank):
        existing_cards = {card.card_number: card for card in CoBankCard.objects.filter(bank_account=bank)}
        jibit_cards = CobankJibitCardsList(bank_account=bank).get_cards()

        cards_to_create = []
        cards_to_update = []

        for card_data in jibit_cards:
            existing_card = existing_cards.get(card_data.cardNumber)
            if existing_card:
                if self._update_existing_card(existing_card, card_data):
                    cards_to_update.append(existing_card)
            else:
                new_card = self._create_new_card(bank, card_data)
                cards_to_create.append(new_card)

        self._bulk_save_cards(cards_to_create, cards_to_update)

    def _update_existing_card(self, existing_card, card_data):
        fields_changed = False
        if existing_card.provider_is_active != card_data.active:
            existing_card.provider_is_active = card_data.active
            fields_changed = True

        if existing_card.provider_card_id != str(card_data.id):
            existing_card.provider_card_id = str(card_data.id)
            fields_changed = True

        return fields_changed

    def _create_new_card(self, bank, card_data):
        return CoBankCard(
            bank_account=bank,
            card_number=card_data.cardNumber,
            provider_is_active=card_data.active,
            provider_card_id=str(card_data.id),
        )

    def _bulk_save_cards(self, to_create, to_update):
        if to_create:
            CoBankCard.objects.bulk_create(to_create)

        if to_update:
            CoBankCard.objects.bulk_update(to_update, ['provider_is_active', 'provider_card_id'])

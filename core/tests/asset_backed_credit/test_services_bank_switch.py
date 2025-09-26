from decimal import Decimal
from unittest import TestCase

from exchange.asset_backed_credit.models import DebitSettlementTransaction
from exchange.asset_backed_credit.services.debit.bank_switch import reverse_payment
from exchange.base.models import RIAL
from tests.asset_backed_credit.helper import ABCMixins


class TestBankSwitchService(TestCase, ABCMixins):
    def test_reverse_payment(self):
        amount = Decimal(1000)
        user_service = self.create_user_service(initial_debt=amount)
        settlement = self.create_debit_settlement(user_service=user_service, amount=amount)

        self.charge_exchange_wallet(settlement.user_service.user, RIAL, settlement.amount)

        user_withdraw_transaction = settlement.user_rial_wallet.create_transaction(
            tp='manual', amount=-settlement.amount
        )
        user_withdraw_transaction.commit()
        provider_deposit_transaction = settlement.provider.rial_wallet.create_transaction(
            tp='manual', amount=settlement.amount
        )
        provider_deposit_transaction.commit()
        settlement.user_withdraw_transaction = user_withdraw_transaction
        settlement.provider_deposit_transaction = provider_deposit_transaction
        settlement.user_service.update_current_debt(-settlement.amount)
        settlement.save()

        settlement = reverse_payment(settlement.id)

        settlement.user_rial_wallet.refresh_from_db()
        assert settlement.user_reverse_transaction
        assert settlement.user_reverse_transaction.amount == -user_withdraw_transaction.amount
        assert settlement.provider_reverse_transaction
        assert settlement.provider_reverse_transaction.amount == -provider_deposit_transaction.amount
        assert settlement.user_rial_wallet.balance == amount
        assert settlement.status == DebitSettlementTransaction.STATUS.reversed

        user_service.refresh_from_db()
        assert user_service.current_debt == 0

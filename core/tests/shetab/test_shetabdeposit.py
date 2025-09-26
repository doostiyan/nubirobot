from decimal import Decimal
from unittest.mock import MagicMock, patch

import responses
from django.conf import settings
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, override_settings

from exchange.accounts.models import BankCard, User, UserPreference
from exchange.base.models import RIAL, Settings
from exchange.shetab.models import ShetabDeposit
from exchange.wallet.models import Transaction, Wallet


class ShetabDepositTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)
        self.card = BankCard.objects.create(
            user=self.user,
            card_number='1234123412341234',
            owner_name=self.user.get_full_name(),
            bank_id=10,
            confirmed=True,
            status=BankCard.STATUS.confirmed,
        )

    def create_shetab_deposit(self, amount, status=None, user=None, create_date=None):
        deposit = ShetabDeposit.objects.create(
            user=user or self.user,
            selected_card=self.card,
            status_code=ShetabDeposit.STATUS.pay_success if status is None else status,
            user_card_number=self.card.card_number,
            amount=amount,
            nextpay_id='32',
        )
        if create_date:
            deposit.created_at = create_date
            deposit.save()
        deposit.sync = MagicMock()
        deposit.sync_and_update()
        return deposit

    def test_block_balance_process(self):
        amount = Decimal('1_000_000_0')
        rial_wallet = Wallet.get_user_wallet(self.user, RIAL)
        initial_balance = rial_wallet.balance
        deposit = ShetabDeposit.objects.create(
            user=self.user,
            selected_card=self.card,
            amount=amount,
            nextpay_id='tbbp1',
        )
        # Simulate handler.sync
        deposit.status_code = ShetabDeposit.STATUS.pay_success
        deposit.user_card_number = '1' * 16
        deposit.save(update_fields=['status_code', 'user_card_number'])
        # Final steps of sync_and_update
        deposit.create_transaction()
        net_amount = deposit.net_amount
        deposit.refresh_from_db()
        assert deposit.status_code == ShetabDeposit.STATUS.invalid_card
        assert deposit.transaction
        assert deposit.transaction.tp == Transaction.TYPE.deposit
        assert deposit.transaction.amount == net_amount
        assert deposit.transaction.balance == initial_balance + net_amount
        # Check blocked balance
        block_transaction = Transaction.objects.filter(
            ref_module=Transaction.REF_MODULES['ShetabBlock'],
            ref_id=deposit.pk,
        ).first()
        assert block_transaction
        assert block_transaction.amount == -net_amount
        assert block_transaction.tp == Transaction.TYPE.manual
        assert block_transaction.balance == initial_balance
        assert block_transaction.id > deposit.transaction.id
        # Check balance unblock
        deposit.user_card_number = self.card.card_number
        deposit.save(update_fields=['user_card_number'])
        deposit.status_code = ShetabDeposit.STATUS.pay_success
        deposit.save(update_fields=['status_code'])
        deposit.unblock_balance()
        deposit.refresh_from_db()
        rial_wallet.refresh_from_db()
        unblock_transaction = Transaction.objects.filter(
            wallet=rial_wallet,
            ref_module=Transaction.REF_MODULES['ReverseTransaction'],
            ref_id=block_transaction.pk,
        ).first()
        assert unblock_transaction
        assert unblock_transaction.amount == net_amount
        assert unblock_transaction.tp == Transaction.TYPE.manual
        assert unblock_transaction.balance == initial_balance + net_amount
        assert rial_wallet.balance == initial_balance + net_amount

    @patch.dict(settings.NOBITEX_OPTIONS, shetabFee=dict(min=1000, max=5000, rate=Decimal('0.01')))
    def test_check_fee_calculation(self):
        fee_min = 1000

        # Checking lower bound
        amount = 1_000_0
        deposit = self.create_shetab_deposit(amount)
        assert deposit.transaction
        assert deposit.fee == fee_min
        assert deposit.amount == amount
        assert deposit.net_amount == amount - fee_min
        assert deposit.transaction.amount == amount - fee_min

        # Checking middle range
        amount = 30_000_0
        deposit = self.create_shetab_deposit(amount)
        assert deposit.fee == 300_0 # 30_000_0 * 0.01

        # Check round down
        amount = 30_005_1
        deposit = self.create_shetab_deposit(amount)
        assert deposit.fee == 300_0 # int(30_005_1 * 0.01)

        # Checking higher bound
        amount = 300_000_0
        deposit = self.create_shetab_deposit(amount)
        assert deposit.fee == 5000


class ShetabDepositAPITest(APITestCase):
    URL = '/users/wallets/deposit/shetab'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def _create_bank_cards(self, bank_card_number: int):
        bank_cards = [
            BankCard(
                user=self.user,
                card_number=str(1234123412341234 + i),
                owner_name=self.user.get_full_name(),
                bank_id=10,
                confirmed=True,
                status=BankCard.STATUS.confirmed,
            )
            for i in range(bank_card_number)
        ]
        BankCard.objects.bulk_create(bank_cards)
        return BankCard.objects.filter(user=self.user)

    @override_settings(IS_PROD=True)
    @patch('exchange.shetab.handlers.jibit.JibitHandler.sync')
    def test_shetab_deposit_backend_more_than_20_cards(self, _):
        bank_cards = self._create_bank_cards(30)
        Settings.set('shetab_deposit_backend', 'toman')
        Settings.set('shetab_deposit_special_users_backend', 'jibit')

        response = self.client.post(self.URL, dict(amount=1000, selectedCard=bank_cards[0].id))
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'

        assert ShetabDeposit.objects.filter(user=self.user).last().broker == ShetabDeposit.BROKER.jibit

    @override_settings(IS_PROD=True)
    @responses.activate
    def test_shetab_deposit_vandar(self):
        UserPreference.set(self.user, 'system_shetab_gateway', 'vandar')
        bank_cards = self._create_bank_cards(30)
        valid_bank_cards = [bank_cards[15].card_number] + [b.card_number for b in reversed(bank_cards)][:9]
        responses.post(
            url='https://ipg.vandar.io/api/v3/send',
            json={'status': 1, 'token': 'abcd'},
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'amount': 1000,
                        'api_key': 'b44fbd8273bd9988900a64c7b969593b5d004046',
                        'callback_url': 'https://api.nobitex1.ir/users/wallets/deposit/shetab-callback?gateway=vandar',
                        'description': 'nobitex115',
                        'factorNumber': 'nobitex115',
                        'payerIdentity': 201,
                        'valid_card_number': valid_bank_cards,
                    },
                ),
            ],
        )
        response = self.client.post(self.URL, dict(amount=1000, selectedCard=bank_cards[15].id))
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert ShetabDeposit.objects.filter(user=self.user).last().broker == ShetabDeposit.BROKER.vandar


class ShetabDepositListAPITest(APITestCase):
    URL = '/users/wallets/deposits/list'

    def setUp(self):
        self.user = User.objects.create_user(username='tiadoubalisdflkafylgy')
        self.user.user_type = User.USER_TYPES.level2
        self.user.auth_token = Token.objects.create(user=self.user, key='124536755')
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_list_shetab_deposits(self):
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.pay_success,
        )
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.confirmation_failed,
        )
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.invalid_card,
        )
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.refunded,
        )
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.pay_new,
        )
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.pending_request,
        )
        ShetabDeposit.objects.create(
            broker=ShetabDeposit.BROKER.jibit_v2,
            user=self.user,
            amount=100000,
            status_code=ShetabDeposit.STATUS.amount_mismatch,
        )
        response = self.client.get(self.URL)
        output = response.json()
        deposits = output['deposits']
        statuses = []
        for deposit in deposits:
            statuses.append(deposit.get('status'))
        self.assertCountEqual(
            statuses,
            [
                'new',
                'success',
                'shetabRefunded',
                'shetabInvalidCard',
            ],
        )
        assert response.status_code == 200

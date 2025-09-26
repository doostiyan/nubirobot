from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.accounts.models import User
from exchange.wallet.models import Wallet
from exchange.features.models import QueueItem

from exchange.credit import models
from exchange.credit import helpers


class BaseApiTest(TestCase):
    url = None

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.get(pk=201)
        QueueItem.objects.create(feature=QueueItem.FEATURES.vip_credit, user=cls.user, status=QueueItem.STATUS.done,)
        cls.currency = Currencies.btc
        cls.wallet = Wallet.get_user_wallet(cls.user, cls.currency)
        cls.system_wallet = Wallet.get_user_wallet(helpers.get_system_user_id(), cls.currency,)

    def setUp(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.wallet.balance = 1
        self.wallet.save(update_fields=('balance',),)
        self.system_wallet.balance = 4
        self.system_wallet.save(update_fields=('balance',),)
        self.plan_kwargs = {
            'user': self.user,
            'starts_at': ir_now() - timedelta(days=1),
            'expires_at': ir_now() + timedelta(days=1),
            'maximum_withdrawal_percentage': Decimal('.5'),
            'credit_limit_percentage': Decimal('.2'),
            'credit_limit_in_usdt': Decimal('10000'),
        }
        self.plan = models.CreditPlan.objects.create(**self.plan_kwargs)

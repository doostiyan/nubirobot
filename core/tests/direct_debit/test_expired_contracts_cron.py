import datetime

from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.direct_debit.crons import DirectDebitExpiredContracts
from exchange.direct_debit.models import DirectDebitContract
from tests.direct_debit.helper import DirectDebitMixins


class ExpiredContractsCronTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data.json',)

    @classmethod
    def setUpTestData(cls):
        cls.WAITING_FOR_CONFIRM = DirectDebitContract.STATUS.waiting_for_confirm
        cls.CANCELLED = DirectDebitContract.STATUS.cancelled
        cls.ACTIVE = DirectDebitContract.STATUS.active
        cls.EXPIRED = DirectDebitContract.STATUS.expired

    def setUp(self):
        self.user = User.objects.get(pk=201)

    def tearDown(self):
        DirectDebitContract.objects.all().delete()

    def test_expired_contracts_cron_not_active(self):
        self.create_contract(user=self.user, status=self.WAITING_FOR_CONFIRM)

        DirectDebitExpiredContracts().run()
        _contract = DirectDebitContract.objects.filter(user=self.user).first()
        assert _contract
        assert _contract.status == self.WAITING_FOR_CONFIRM

        _contract.status = self.CANCELLED
        _contract.save()

        DirectDebitExpiredContracts().run()
        _contract.refresh_from_db()
        assert _contract.status == self.CANCELLED

    def test_expired_contracts_cron_active_not_expired(self):
        self.create_contract(user=self.user, status=self.ACTIVE)

        DirectDebitExpiredContracts().run()
        _contract = DirectDebitContract.objects.filter(user=self.user).first()
        assert _contract
        assert _contract.status == self.ACTIVE

    def test_expired_contracts_cron_expired(self):
        self.create_contract(user=self.user, status=self.ACTIVE, expire_date=ir_now() - datetime.timedelta(minutes=1))

        DirectDebitExpiredContracts().run()
        _contract = DirectDebitContract.objects.filter(user=self.user).first()
        assert _contract
        assert _contract.status == self.EXPIRED

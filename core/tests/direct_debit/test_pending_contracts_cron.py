import datetime

from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.direct_debit.crons import DirectDebitContractCreateOrUpdateTimeoutCron
from exchange.direct_debit.models import DirectDebitContract
from tests.direct_debit.helper import DirectDebitMixins


class PendingContractsCronTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data.json',)

    @classmethod
    def setUpTestData(cls):
        cls.WAITING_FOR_CONFIRM = DirectDebitContract.STATUS.waiting_for_confirm
        cls.INITIALIZING = DirectDebitContract.STATUS.initializing
        cls.CANCELLED = DirectDebitContract.STATUS.cancelled
        cls.ACTIVE = DirectDebitContract.STATUS.active
        cls.EXPIRED = DirectDebitContract.STATUS.expired
        cls.FAILED = DirectDebitContract.STATUS.failed
        cls.WAITING_FOR_UPDATE = DirectDebitContract.STATUS.waiting_for_update
        cls.FAILED_UPDATE = DirectDebitContract.STATUS.failed_update

    def setUp(self):
        self.user = User.objects.get(pk=201)

    def test_pending_contracts_cron(self):
        self.create_contract(user=self.user, status=self.WAITING_FOR_CONFIRM)

        DirectDebitContractCreateOrUpdateTimeoutCron().run()
        _contract = DirectDebitContract.objects.filter(user=self.user).first()
        assert _contract
        assert _contract.status == self.WAITING_FOR_CONFIRM

        _contract.created_at = ir_now() - datetime.timedelta(minutes=16)
        _contract.save()
        DirectDebitContractCreateOrUpdateTimeoutCron().run()
        _contract.refresh_from_db()
        assert _contract
        assert _contract.status == self.FAILED

    def test_pending_contracts_cron_multiple_record(self):
        _contract0 = self.create_contract(user=self.user, status=self.WAITING_FOR_CONFIRM)
        _contract0.created_at = ir_now() - datetime.timedelta(minutes=16)
        _contract0.save()

        _contract1 = self.create_contract(user=self.user, status=self.WAITING_FOR_CONFIRM)

        _contract2 = self.create_contract(user=self.user, status=self.INITIALIZING)
        _contract2.created_at = ir_now() - datetime.timedelta(minutes=16)
        _contract2.save()

        _contract3 = self.create_contract(user=self.user, status=self.WAITING_FOR_UPDATE)
        _contract4 = self.create_contract(user=self.user, status=self.WAITING_FOR_UPDATE)
        _contract4.created_at = ir_now() - datetime.timedelta(minutes=16)
        _contract4.save()

        DirectDebitContractCreateOrUpdateTimeoutCron().run()
        _contract0.refresh_from_db()
        _contract1.refresh_from_db()
        _contract2.refresh_from_db()
        _contract3.refresh_from_db()
        _contract4.refresh_from_db()

        assert _contract0.status == self.FAILED
        assert _contract1.status == self.WAITING_FOR_CONFIRM
        assert _contract2.status == self.FAILED
        assert _contract3.status == self.WAITING_FOR_UPDATE
        assert _contract4.status == self.FAILED_UPDATE

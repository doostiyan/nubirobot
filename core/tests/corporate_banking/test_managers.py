from decimal import Decimal
from unittest.mock import patch

from django.db.models import Q
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    NOBITEX_BANK_CHOICES,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankStatement,
    ThirdpartyLog,
)


class TestBulkGetOrCreateManager(TestCase):
    def setUp(self):
        self.bank = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999991',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )
        self.existing_1 = ThirdpartyLog.objects.create(
            api_url='https://example1.com',
            status=ThirdpartyLog.STATUS.success,
            provider=ThirdpartyLog.PROVIDER.alpha,
            service=ThirdpartyLog.SERVICE.liveness,
            retry=1,
            request_details={},
            response_details={},
            content_object=self.bank,
            status_code=1,
        )
        self.existing_2 = ThirdpartyLog.objects.create(
            api_url='https://example2.com',
            status=ThirdpartyLog.STATUS.failure,
            provider=ThirdpartyLog.PROVIDER.toman,
            service=ThirdpartyLog.SERVICE.cobank_statements,
            retry=2,
            request_details={},
            response_details={},
            content_object=self.bank,
            status_code=2,
        )
        # Another record with same api_url as existing_1 but different status
        self.existing_3 = ThirdpartyLog.objects.create(
            api_url='https://example1.com',
            status=ThirdpartyLog.STATUS.failure,
            provider=ThirdpartyLog.PROVIDER.alpha,
            service=ThirdpartyLog.SERVICE.cobank_statements,
            retry=3,
            request_details={},
            response_details={},
            content_object=self.bank,
            status_code=3,
        )

    def test_bulk_get_or_create_single_field_uniqueness(self):
        """
        Test using a single field for uniqueness (e.g. api_url).
        If any item has an api_url that already exists, we should NOT create a new record.
        """
        new_items = [
            ThirdpartyLog(
                api_url='https://example1.com',  # same as existing_1 and existing_3
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.alpha,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=4,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=-1,
            ),
            ThirdpartyLog(
                api_url='https://example3.com',  # new URL
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.alpha,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=4,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=-1,
            ),
        ]

        created_items, existing_items = ThirdpartyLog.objects.bulk_get_or_create(
            items=new_items, unique_fields=['api_url']
        )
        assert len(created_items) == 1
        assert len(existing_items) == 2
        assert created_items[0].api_url == 'https://example3.com'
        assert existing_items.first().api_url == 'https://example1.com'

    def test_bulk_get_or_create_two_fields_uniqueness(self):
        """
        Test using two fields for uniqueness, e.g. (api_url, status).
        An item is considered 'already existing' only if BOTH fields match.
        """
        new_items = [
            # This matches existing_1 by (api_url='example1', status=0) so it should NOT be created
            ThirdpartyLog(
                api_url='https://example1.com',
                status=ThirdpartyLog.STATUS.success,
                provider=ThirdpartyLog.PROVIDER.toman,  # The rest are mostly different from existing_1
                service=ThirdpartyLog.SERVICE.cobank_statements,
                retry=5,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=100,
            ),
            # This matches existing_2's api_url but a DIFFERENT status=0, so it SHOULD be created
            ThirdpartyLog(
                api_url='https://example2.com',
                status=ThirdpartyLog.STATUS.success,
                provider=ThirdpartyLog.PROVIDER.toman,
                service=ThirdpartyLog.SERVICE.cobank_statements,
                retry=2,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=1,
            ),
            # This matches existing_2's status but has a different api_url, so it SHOULD be created
            ThirdpartyLog(
                api_url='https://example4.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.toman,
                service=ThirdpartyLog.SERVICE.cobank_statements,
                retry=6,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=10,
            ),
            # This does not match existing_1/2/3 on (api_url, status), so it SHOULD be created
            ThirdpartyLog(
                api_url='https://123123.example.com',
                status=ThirdpartyLog.STATUS.success,
                provider=ThirdpartyLog.PROVIDER.toman,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=10,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=-1,
            ),
        ]

        created_items, existing_items = ThirdpartyLog.objects.bulk_get_or_create(
            items=new_items, unique_fields=['api_url', 'status']
        )
        created_items = sorted(list(created_items), key=lambda x: x.retry)

        assert len(created_items) == 3
        assert len(existing_items) == 1
        assert existing_items.first().api_url == new_items[0].api_url
        assert created_items[0].api_url == new_items[1].api_url
        assert created_items[1].api_url == new_items[2].api_url
        assert created_items[2].api_url == new_items[3].api_url
        assert existing_items.first().status == new_items[0].status
        assert created_items[0].status == new_items[1].status
        assert created_items[1].status == new_items[2].status
        assert created_items[2].status == new_items[3].status

    def test_bulk_get_or_create_three_fields_uniqueness(self):
        """
        Test using three fields for uniqueness, e.g. (api_url, status, retry).
        All three must match an existing item to be considered 'existing'.
        """
        new_items = [
            # This differs from existing_1 only by status=1, => Should be created
            ThirdpartyLog(
                api_url='https://example1.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.alpha,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=1,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=-1,
            ),
            # This EXACTLY matches existing_2 on (api_url='example2', status=1, retry=2), so should NOT be created
            ThirdpartyLog(
                api_url='https://example2.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.toman,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=2,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=500,
            ),
            # This partially matches existing_3 on api_url/status but differs on provider => Should be created
            ThirdpartyLog(
                api_url='https://example1.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.alpha,
                service=ThirdpartyLog.SERVICE.cobank_statements,
                retry=30,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=-1,
            ),
        ]

        created_items, existing_items = ThirdpartyLog.objects.bulk_get_or_create(
            items=new_items, unique_fields=['api_url', 'status', 'retry']
        )
        created_items = sorted(list(created_items), key=lambda x: x.retry)

        assert len(created_items) == 2
        assert len(existing_items) == 1
        assert existing_items.first().api_url == new_items[1].api_url
        assert created_items[0].api_url == new_items[0].api_url
        assert created_items[1].api_url == new_items[2].api_url
        assert existing_items.first().status == new_items[1].status
        assert created_items[0].status == new_items[0].status
        assert created_items[1].status == new_items[2].status
        assert existing_items.first().retry == new_items[1].retry
        assert created_items[0].retry == new_items[0].retry
        assert created_items[1].retry == new_items[2].retry

    def test_get_query_conditions(self):
        items = [
            ThirdpartyLog(
                api_url='https://example1.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.alpha,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=1,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=2,
            ),
            ThirdpartyLog(
                api_url='https://example2.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.toman,
                service=ThirdpartyLog.SERVICE.liveness,
                retry=3,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=4,
            ),
            ThirdpartyLog(
                api_url='https://example3.com',
                status=ThirdpartyLog.STATUS.failure,
                provider=ThirdpartyLog.PROVIDER.alpha,
                service=ThirdpartyLog.SERVICE.cobank_statements,
                retry=5,
                request_details={},
                response_details={},
                content_object=self.bank,
                status_code=6,
            ),
        ]
        conditions = ThirdpartyLog.objects._get_query_conditions(
            items=items,
            query_fields=['api_url', 'retry', 'status_code'],
        )
        assert conditions == (
            Q(api_url='https://example1.com', retry=1, status_code=2)
            | Q(api_url='https://example2.com', retry=3, status_code=4)  # item[0] conditions
            | Q(api_url='https://example3.com', retry=5, status_code=6)  # item[1] conditions  # item[2] conditions
        )


@patch.object(CoBankStatement, 'UPDATABLE_FIELDS', {'source_iban', 'tp', 'amount'})
@patch.object(
    CoBankStatement,
    'UPDATABLE_STATUSES',
    {
        'source_iban': {STATEMENT_STATUS.new, STATEMENT_STATUS.pending_admin, STATEMENT_STATUS.rejected},
        'tp': {STATEMENT_STATUS.new, STATEMENT_STATUS.pending_admin, STATEMENT_STATUS.rejected},
        'amount': {STATEMENT_STATUS.new, STATEMENT_STATUS.pending_admin, STATEMENT_STATUS.rejected},
    },
)
@patch.object(
    CoBankStatement,
    'UPDATABLE_AMOUNTS',
    {
        'source_iban': {None, '', '123'},
        'tp': {STATEMENT_TYPE.deposit},
        'amount': {Decimal('100.00'), Decimal('50.00')},
    },
)
class TestBulkUpdateOrCreate(TestCase):
    def setUp(self):
        self.account = CoBankAccount.objects.create(
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999991',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )

    def test_bulk_update_and_create(self):
        """
        - One record already exists with `provider_statement_id=1001`.
        - We update its `amount` field.
        - We create a new record with `provider_statement_id=1002`.
        """

        CoBankStatement.objects.create(
            provider_statement_id='1001',
            destination_account=self.account,
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
        )

        # New data: one update, one new insert
        new_statements = [
            CoBankStatement(
                provider_statement_id='1001',
                destination_account=self.account,
                amount=Decimal('200.00'),
                tp=STATEMENT_TYPE.deposit,
            ),
            CoBankStatement(
                provider_statement_id='1002',
                destination_account=self.account,
                amount=Decimal('300.00'),
                tp=STATEMENT_TYPE.deposit,
            ),
        ]

        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            new_statements,
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['amount'],
        )

        # Check the existing record was updated
        updated_statement = CoBankStatement.objects.get(provider_statement_id='1001')
        assert updated_statement.amount == Decimal('200.00')

        # Check that new record was created
        assert CoBankStatement.objects.filter(provider_statement_id='1002').exists()

        # Validate the created and existing lists
        assert len(created_items) == 1
        assert updated_items_count == 1

    def test_no_update_when_data_same(self):
        CoBankStatement.objects.create(
            provider_statement_id='1003',
            destination_account=self.account,
            amount=Decimal('500.00'),
            tp=STATEMENT_TYPE.deposit,
        )

        new_statements = [
            CoBankStatement(
                provider_statement_id='1003',
                destination_account=self.account,
                amount=Decimal('500.00'),
                tp=STATEMENT_TYPE.deposit,
            ),
        ]

        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            new_statements,
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['amount'],
        )

        assert len(created_items) == 0
        assert updated_items_count == 0

    def test_bulk_update_or_create_multiple(self):
        CoBankStatement.objects.create(
            provider_statement_id='1004',
            destination_account=self.account,
            amount=Decimal('50.00'),
            tp=STATEMENT_TYPE.deposit,
        )
        CoBankStatement.objects.create(
            provider_statement_id='1005',
            destination_account=self.account,
            amount=Decimal('75.00'),
            tp=STATEMENT_TYPE.deposit,
        )

        new_statements = [
            CoBankStatement(
                provider_statement_id='1004',
                destination_account=self.account,
                amount=Decimal('55.00'),
                tp=STATEMENT_TYPE.deposit,
            ),  # Update
            CoBankStatement(
                provider_statement_id='1005',
                destination_account=self.account,
                amount=Decimal('75.00'),
                tp=STATEMENT_TYPE.deposit,
            ),  # No change
            CoBankStatement(
                provider_statement_id='1006',
                destination_account=self.account,
                amount=Decimal('125.00'),
                tp=STATEMENT_TYPE.deposit,
            ),  # New
        ]

        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            new_statements,
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['amount'],
        )

        assert CoBankStatement.objects.get(provider_statement_id='1004').amount == Decimal('55.00')
        assert CoBankStatement.objects.get(provider_statement_id='1005').amount == Decimal('75.00')
        assert CoBankStatement.objects.filter(provider_statement_id='1006').exists()

        assert len(created_items) == 1
        assert updated_items_count == 1

    def test_bulk_update_or_create_empty(self):
        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            [],
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['amount'],
        )

        assert len(created_items) == 0
        assert updated_items_count == 0

    def test_bulk_partial_update(self):
        CoBankStatement.objects.create(
            provider_statement_id='1001',
            destination_account=self.account,
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
        )

        new_statements = [
            CoBankStatement(
                provider_statement_id='1001',
                destination_account=self.account,
                amount=Decimal('200.00'),
                tp=STATEMENT_TYPE.deposit,
            ),
        ]

        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            new_statements,
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['amount', 'tp'],
        )

        updated_statement = CoBankStatement.objects.get(provider_statement_id='1001')
        assert updated_statement.amount == Decimal('200.00')
        assert updated_statement.tp == STATEMENT_TYPE.deposit

        assert len(created_items) == 0
        assert updated_items_count == 1

    def test_bulk_multi_field_update(self):
        CoBankStatement.objects.create(
            provider_statement_id='1001',
            destination_account=self.account,
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
        )

        new_statements = [
            CoBankStatement(
                provider_statement_id='1001',
                destination_account=self.account,
                amount=Decimal('200.00'),
                tp=STATEMENT_TYPE.withdraw,
            ),
        ]

        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            new_statements,
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['amount', 'tp'],
        )

        updated_statement = CoBankStatement.objects.get(provider_statement_id='1001')
        assert updated_statement.amount == Decimal('200.00')
        assert updated_statement.tp == STATEMENT_TYPE.withdraw

        assert len(created_items) == 0
        assert updated_items_count == 1

    def test_only_updatable_statements_get_updated(self):
        updatable_statement = CoBankStatement.objects.create(
            provider_statement_id='1001',
            destination_account=self.account,
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
            source_iban='123',
        )
        unupdatable_statement = CoBankStatement.objects.create(
            provider_statement_id='1002',
            destination_account=self.account,
            amount=Decimal('100.00'),
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.executed,
            source_iban='123',
        )
        updatable_statement.source_iban = '456'
        unupdatable_statement.source_iban = '456'

        created_items, updated_items_count = CoBankStatement.objects.bulk_update_or_create(
            [updatable_statement, unupdatable_statement],
            unique_fields=['provider_statement_id', 'destination_account'],
            update_fields=['source_iban'],
        )

        assert updated_items_count == 1
        updatable_statement.refresh_from_db()
        assert updatable_statement.source_iban == '456'
        unupdatable_statement.refresh_from_db()
        assert unupdatable_statement.source_iban == '123'

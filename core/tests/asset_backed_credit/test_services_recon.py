import datetime
import unittest
from unittest.mock import MagicMock, call, patch

import pytest
from django.test import override_settings

from exchange.asset_backed_credit.exceptions import (
    ReconAlreadyProcessedError,
    ServiceNotFoundError,
    SettlementReconError,
)
from exchange.asset_backed_credit.models import DebitSettlementTransaction, Recon, Service, SettlementRecon
from exchange.asset_backed_credit.services.debit.recon import _normalize_transaction, reconcile
from exchange.asset_backed_credit.tasks import task_add_debit_reconcile
from exchange.base.calendar import ir_now, ir_tz
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import ABCMixins


class TestRecon(unittest.TestCase, ABCMixins):
    def setUp(self):
        Settings.set('abc_debit_recon_ftp_process_enabled', 'yes')
        Settings.set('abc_debit_recon_settlement_evaluation_enabled', 'yes')
        Settings.set('abc_debit_recon_settlement_process_enabled', 'yes')

    def test_recon_already_processed_error(self):
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        recon_date = ir_now()
        Recon.objects.create(service=service, recon_date=recon_date, status=Recon.Status.PROCESSED, closed_at=ir_now())
        with pytest.raises(ReconAlreadyProcessedError):
            reconcile(recon_date=recon_date)

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_all_steps_disabled_do_nothing(self, mock_read_file_from_sftp):
        Settings.set('abc_debit_recon_ftp_process_enabled', 'no')
        Settings.set('abc_debit_recon_settlement_evaluation_enabled', 'no')
        Settings.set('abc_debit_recon_settlement_process_enabled', 'no')

        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user_1 = self.create_user()
        user_2 = self.create_user()
        user_service_1 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_1)
        user_service_2 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_2)

        settlement_1 = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service_1,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_1.save()
        settlement_2 = DebitSettlementTransaction(
            amount=37000,
            user_service=user_service_2,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248600',
            trace_id='029117',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_2.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.INITIATED
        assert not recon.file
        assert not recon.closed_at
        settlement_1.refresh_from_db()
        assert settlement_1.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_1 = SettlementRecon.objects.filter(settlement_id=settlement_1.id).first()
        assert not settlement_recon_1
        settlement_2.refresh_from_db()
        assert settlement_2.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_2 = SettlementRecon.objects.filter(settlement_id=settlement_2.id).first()
        assert not settlement_recon_2

    @override_settings(ABC_ACTIVE_DEBIT_SERVICE_PROVIDER_ID=-1)
    @patch('exchange.base.storages.read_file_from_sftp')
    def test_active_debit_service_not_found(self, mock_read_file_from_sftp):
        Settings.set('abc_debit_recon_settlement_process_enabled', 'no')

        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user_1 = self.create_user()
        user_2 = self.create_user()
        user_service_1 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_1)
        user_service_2 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_2)

        settlement_1 = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service_1,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_1.save()
        settlement_2 = DebitSettlementTransaction(
            amount=37000,
            user_service=user_service_2,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248600',
            trace_id='029117',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_2.save()

        with pytest.raises(ServiceNotFoundError):
            reconcile()

        recon = Recon.objects.first()
        assert not recon
        settlement_1.refresh_from_db()
        assert settlement_1.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_1 = SettlementRecon.objects.filter(settlement_id=settlement_1.id).first()
        assert not settlement_recon_1
        settlement_2.refresh_from_db()
        assert settlement_2.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_2 = SettlementRecon.objects.filter(settlement_id=settlement_2.id).first()
        assert not settlement_recon_2

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_settlement_and_evaluation_process_disabled_do_nothing(self, mock_read_file_from_sftp):
        Settings.set('abc_debit_recon_settlement_evaluation_enabled', 'no')
        Settings.set('abc_debit_recon_settlement_process_enabled', 'no')

        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user_1 = self.create_user()
        user_2 = self.create_user()
        user_service_1 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_1)
        user_service_2 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_2)

        settlement_1 = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service_1,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_1.save()
        settlement_2 = DebitSettlementTransaction(
            amount=37000,
            user_service=user_service_2,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248600',
            trace_id='029117',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_2.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.FILE_TRANSFERRED
        assert recon.file
        assert not recon.closed_at
        settlement_1.refresh_from_db()
        assert settlement_1.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_1 = SettlementRecon.objects.filter(settlement_id=settlement_1.id).first()
        assert not settlement_recon_1
        settlement_2.refresh_from_db()
        assert settlement_2.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_2 = SettlementRecon.objects.filter(settlement_id=settlement_2.id).first()
        assert not settlement_recon_2

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_settlement_evaluation_corrupted_data(self, mock_read_file_from_sftp):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '\n'
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        with pytest.raises(SettlementReconError):
            reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.FILE_TRANSFERRED

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_settlement_process_disabled_do_nothing(self, mock_read_file_from_sftp):
        Settings.set('abc_debit_recon_settlement_process_enabled', 'no')

        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user_1 = self.create_user()
        user_2 = self.create_user()
        user_service_1 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_1)
        user_service_2 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_2)

        settlement_1 = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service_1,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_1.save()
        settlement_2 = DebitSettlementTransaction(
            amount=37000,
            user_service=user_service_2,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248600',
            trace_id='029117',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_2.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.EVALUATED
        assert recon.file
        assert not recon.closed_at
        settlement_1.refresh_from_db()
        assert settlement_1.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_1 = SettlementRecon.objects.get(settlement_id=settlement_1.id)
        assert settlement_recon_1.status == SettlementRecon.Status.SUCCESS
        assert not settlement_recon_1.description
        settlement_2.refresh_from_db()
        assert settlement_2.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_2 = SettlementRecon.objects.get(settlement_id=settlement_2.id)
        assert settlement_recon_2.status == SettlementRecon.Status.SUCCESS
        assert not settlement_recon_2.description

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_confirmed_found_in_ftp_change_to_confirmed_plus_one_ftp_record_not_found_in_settlements_success(
        self, mock_read_file_from_sftp
    ):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
            '02113019103014031117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/031117/0000'
            '/93/0000/   5041000011119999/   5041000011119999/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user_1 = self.create_user()
        user_2 = self.create_user()
        user_service_1 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_1)
        user_service_2 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_2)

        settlement_1 = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service_1,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_1.save()
        settlement_2 = DebitSettlementTransaction(
            amount=37000,
            user_service=user_service_2,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248600',
            trace_id='029117',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_2.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement_1.refresh_from_db()
        assert settlement_1.status == DebitSettlementTransaction.STATUS.confirmed
        settlement_recon_1 = SettlementRecon.objects.get(settlement_id=settlement_1.id)
        assert settlement_recon_1.status == SettlementRecon.Status.SUCCESS
        assert not settlement_recon_1.description
        settlement_2.refresh_from_db()
        assert settlement_2.status == DebitSettlementTransaction.STATUS.confirmed
        settlement_recon_2 = SettlementRecon.objects.get(settlement_id=settlement_2.id)
        assert settlement_recon_2.status == SettlementRecon.Status.SUCCESS
        assert not settlement_recon_2.description
        settlement_recon_3 = SettlementRecon.objects.get(extra_info__pan='5041000011119999')
        assert settlement_recon_3.status == SettlementRecon.Status.NOT_FOUND
        assert settlement_recon_3.description == 'equivalent settlement for trace_id: 031117 not found!'

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_rejected_not_found_in_ftp_do_nothing(self, mock_read_file_from_sftp):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        settlement = DebitSettlementTransaction(
            amount=52000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.unknown_rejected,
            pan='5041000011112222',
            rrn='323881248689',
            trace_id='029116',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected
        settlement_recon = SettlementRecon.objects.get(settlement_id=settlement.id)
        assert settlement_recon.status == SettlementRecon.Status.NEW
        assert not settlement_recon.description

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_confirmed_do_nothing(self, mock_read_file_from_sftp):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        settlement = DebitSettlementTransaction(
            amount=37000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.confirmed,
            pan='5041000011116666',
            rrn='323881248611',
            trace_id='029118',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed
        settlement_recon = SettlementRecon.objects.filter(settlement_id=settlement.id).first()
        assert not settlement_recon

    @patch('exchange.asset_backed_credit.tasks.task_reverse_debit_payment.delay')
    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_confirmed_not_found_in_ftp_considered_old_transaction_revert(
        self, mock_read_file_from_sftp, mock_task_reverse_debit_payment
    ):
        Settings.set('abc_debit_recon_settlement_process_reverse_enabled', 'yes')

        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        # unknown confirmed - not found in ftp - considered old transaction (> 72hrs) - revert
        settlement = DebitSettlementTransaction(
            amount=91000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248612',
            trace_id='029119',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=5),
        )
        settlement.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        assert mock_task_reverse_debit_payment.call_count == 1
        mock_task_reverse_debit_payment.assert_has_calls([call(settlement.id)])

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_confirmed_found_in_ftp_invalid_amount(self, mock_read_file_from_sftp):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029120/0000/8888/0/0000000000000/000000017000/D/444/Y/23368704/14/0000/N/029120/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        settlement = DebitSettlementTransaction(
            amount=11000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011116666',
            rrn='323881248613',
            trace_id='029120',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=3),
        )
        settlement.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon = SettlementRecon.objects.get(settlement_id=settlement.id)
        assert settlement_recon.status == SettlementRecon.Status.INVALID_AMOUNT
        assert settlement_recon.description
        assert 'invalid amount' in settlement_recon.description

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_confirmed_found_in_ftp_invalid_status(self, mock_read_file_from_sftp):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029121/0000/8888/0/0000000000000/000000072000/D/444/Y/23368704/14/0000/N/029121/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        settlement = DebitSettlementTransaction(
            amount=72000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.unknown_rejected,
            pan='5041000011116666',
            rrn='323881248614',
            trace_id='029121',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected
        settlement_recon = SettlementRecon.objects.get(settlement_id=settlement.id)
        assert settlement_recon.status == SettlementRecon.Status.INVALID_STATUS
        assert settlement_recon.description
        assert 'invalid status' in settlement_recon.description

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_record_exists_in_ftp_not_found_in_settlements_success(self, mock_read_file_from_sftp):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029117/0000/8888/0/0000000000000/000000037000/D/444/Y/23368704/14/0000/N/029117/0000'
            '/93/0000/   5041000011116666/   5041000011116666/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user_1 = self.create_user()
        user_service_1 = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user_1)

        settlement_1 = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service_1,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement_1.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement_1.refresh_from_db()
        assert settlement_1.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon_1 = SettlementRecon.objects.get(settlement_id=settlement_1.id)
        assert settlement_recon_1.status == SettlementRecon.Status.NEW
        assert not settlement_recon_1.description
        settlement_recon_2 = SettlementRecon.objects.get(extra_info__pan='5041000011116666')
        assert settlement_recon_2.status == SettlementRecon.Status.NOT_FOUND
        assert settlement_recon_2.description == 'equivalent settlement for trace_id: 029117 not found!'

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_confirmed_found_in_ftp_settlement_recon_already_exists_change_to_confirmed(
        self, mock_read_file_from_sftp
    ):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        settlement = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement.save()
        settlement_recon = SettlementRecon(
            settlement=settlement,
            status=SettlementRecon.Status.NEW,
        )
        settlement_recon.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed
        settlement_recon = SettlementRecon.objects.get(settlement_id=settlement.id)
        assert settlement_recon.status == SettlementRecon.Status.SUCCESS
        assert settlement_recon.recon
        assert not settlement_recon.description

    @patch('exchange.base.storages.read_file_from_sftp')
    def test_unknown_confirmed_found_in_ftp_settlement_recon_already_exists_with_success_status_no_change(
        self, mock_read_file_from_sftp
    ):
        mock_read_file_from_sftp.return_value = (
            '02113019103014029115/0000/8888/0/0000000000000/000000010000/D/444/Y/23368704/14/0000/N/029115/0000'
            '/93/0000/   5041000011112222/   5041000011112222/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/\n'
        )

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)

        user = self.create_user()
        user_service = self.create_user_service(current_debt=0, initial_debt=62000, service=service, user=user)

        settlement = DebitSettlementTransaction(
            amount=10000,
            user_service=user_service,
            status=DebitSettlementTransaction.STATUS.unknown_confirmed,
            pan='5041000011112222',
            rrn='323881248688',
            trace_id='029115',
            terminal_id='23368704',
            created_at=ir_now() - datetime.timedelta(days=2),
        )
        settlement.save()
        settlement_recon = SettlementRecon(
            settlement=settlement,
            status=SettlementRecon.Status.SUCCESS,
        )
        settlement_recon.save()

        reconcile()

        recon = Recon.objects.first()
        assert recon.status == Recon.Status.PROCESSED
        assert recon.file
        assert recon.closed_at
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement_recon = SettlementRecon.objects.get(settlement_id=settlement.id)
        assert settlement_recon.status == SettlementRecon.Status.SUCCESS
        assert not settlement_recon.recon
        assert not settlement_recon.description



class TestReconDecodeTransaction(unittest.TestCase):
    def test_success(self):
        trx = (
            '02113019103014238941/0000/8888/0/0000000000000/000000100000/D/444/Y/04460123/14/0000/N/238941/0000'
            '/93/0000/   6221064412345678/   6221064412345678/0000000000000000000/0000000000000/0000000000000'
            '/00/581672061/622106/0/0/'
        )

        decoded_trx = _normalize_transaction(trx)

        assert decoded_trx.date == '021130'
        assert decoded_trx.time == '191030'
        assert decoded_trx.pos_condition_code == '14'
        assert decoded_trx.trace_id == '238941'
        assert decoded_trx.account_number == '0000000000000'
        assert decoded_trx.amount == 100000
        assert decoded_trx.amount_type == 'D'
        assert decoded_trx.pr_code == '444'
        assert decoded_trx.terminal_id == '04460123'
        assert decoded_trx.acquirer_institution_code == '93'
        assert decoded_trx.pan == '6221064412345678'
        assert decoded_trx.acquirer_institution == '581672061'
        assert decoded_trx.issuer_institution == '622106'


class TestAddReconcileTask(unittest.TestCase):
    @patch('exchange.asset_backed_credit.services.debit.recon.run_ftp_process')
    @patch('exchange.asset_backed_credit.services.debit.recon._get_or_create_recon')
    def test_call_task_with_specific_date(self, mock_get_or_create_recon, mock_run_ftp_process):
        mock_recon = MagicMock()
        mock_recon.status = Recon.Status.INITIATED
        mock_get_or_create_recon.return_value = mock_recon

        task_add_debit_reconcile('2025-04-12T11:24:38.123456')

        mock_get_or_create_recon.assert_called_once_with(
            datetime.datetime(
                2025,
                4,
                12,
                11,
                24,
                38,
                123456,
            ).astimezone(ir_tz())
        )
        mock_run_ftp_process.assert_called_once_with(mock_recon)

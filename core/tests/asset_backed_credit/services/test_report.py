import datetime
import uuid
from datetime import timedelta
from decimal import Decimal

import jdatetime
from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import (
    CreditReport,
    IncomingAPICallLog,
    ReportAttachment,
    Service,
    SettlementTransaction,
    UserService,
    UserServicePermission,
)
from exchange.asset_backed_credit.services.report import generate_requested_reports_attachments
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.market.models import Order


class LoanReportTestCase(TestCase):
    def setUp(self):
        self.service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency, tp=Service.TYPES.loan, defaults={'is_active': True}
        )
        initiated = UserService.STATUS.initiated
        settled = UserService.STATUS.settled
        self.user_service_1 = self.create_user_service('1000000000', Decimal('1000'), Decimal('1000'), initiated)
        log = self.create_incoming_log(
            tp='lock',
            request_body={
                'amount': '1000',
                'trackId': str(uuid.uuid4()),
                'serviceType': 'loan',
                'nationalCode': '1000000000',
                'uniqueIdentifier': str(self.user_service_1.account_number),
            },
            user_service=self.user_service_1,
        )
        log.created_at = datetime.datetime.strptime('2024-08-10', '%Y-%m-%d')
        log.save()

        track_id = uuid.UUID('22ef9392-74fa-4ba7-b5d0-cf583e341222')
        self.settlement_1 = self.create_settlement_transaction(self.user_service_1, Decimal('1000'))
        self.settlement_log_1 = self.create_incoming_log(
            tp='settlement',
            request_body={
                'amount': '1000',
                'trackId': str(track_id),
                'serviceType': 'loan',
                'nationalCode': '1000000000',
            },
            user_service=self.user_service_1,
        )

        self.user_service_1.status = UserService.STATUS.settled
        self.user_service_1.save()

        self.user_service_2 = self.create_user_service('1000000001', Decimal('2000'), Decimal('1000'), initiated)
        log = self.create_incoming_log(
            tp='lock',
            request_body={
                'amount': '2000',
                'trackId': str(uuid.uuid4()),
                'serviceType': 'loan',
                'nationalCode': '1000000001',
                'uniqueIdentifier': str(self.user_service_2.account_number),
            },
            user_service=self.user_service_2,
        )
        log.created_at = datetime.datetime.strptime('2024-09-10', '%Y-%m-%d')
        log.save()

        track_id = uuid.UUID('22ef9392-74fa-4ba7-b5c0-cf5833d412d8')
        self.incoming_log1 = self.create_incoming_log(
            tp='unlock',
            request_body={
                'amount': '350',
                'trackId': str(track_id),
                'serviceType': 'loan',
                'nationalCode': '1000000001',
            },
            user_service=self.user_service_1,
        )

        track_id = uuid.UUID('a73c69a8-4eb9-4df9-8025-6a1b113b79a2')
        self.settlement_2 = self.create_settlement_transaction(self.user_service_2, Decimal('400'))
        self.settlement_log_2 = self.create_incoming_log(
            tp='settlement',
            request_body={
                'amount': '400',
                'trackId': str(track_id),
                'serviceType': 'loan',
                'nationalCode': '1000000001',
            },
            user_service=self.user_service_2,
        )

        track_id = uuid.UUID('22ef9392-74fa-4ba7-b5c0-cf5833d41222')
        self.incoming_log2 = self.create_incoming_log(
            tp='unlock',
            request_body={
                'amount': '1000',
                'trackId': str(track_id),
                'serviceType': 'loan',
                'nationalCode': '1000000001',
            },
            user_service=self.user_service_2,
        )

        self.user_service_3 = self.create_user_service('1000000000', Decimal('1000'), Decimal('800'), settled)
        self.user_service_3.installment_amount = None
        self.user_service_3.save()

        log = self.create_incoming_log(
            tp='lock',
            request_body={
                'amount': '1000',
                'trackId': str(uuid.uuid4()),
                'serviceType': 'loan',
                'nationalCode': '1000000000',
                'uniqueIdentifier': str(self.user_service_3.account_number),
            },
            user_service=self.user_service_3,
        )
        log.created_at = datetime.datetime.strptime('2024-10-10', '%Y-%m-%d')
        log.save()


        self.order_1 = self.create_order(
            currency=13,
            price=Decimal('280000'),
            amount=Decimal('100'),
            status=2,
            matched_amount=Decimal('100'),
            fee=Decimal('53200'),
            user=self.user_service_3.user,
            matched_total_price=Decimal('28000000'),
        )
        self.order_2 = self.create_order(
            currency=13,
            price=Decimal('220000'),
            amount=Decimal('100'),
            status=2,
            matched_amount=Decimal('200'),
            fee=Decimal('53200'),
            user=self.user_service_3.user,
            matched_total_price=Decimal('22000000'),
        )
        orders = [self.order_1, self.order_2]
        self.settlement_3 = self.create_settlement_transaction(self.user_service_3, Decimal('500'), orders)
        track_id = uuid.UUID('22ef9392-74fa-4ba7-3333-cf222e341222')
        self.settlement_log_3 = self.create_incoming_log(
            tp='settlement',
            request_body={
                'amount': '500',
                'trackId': str(track_id),
                'serviceType': 'loan',
                'nationalCode': '1000000000',
            },
            user_service=self.user_service_3,
        )

        track_id = uuid.UUID('22ef9392-74fa-4ba7-b5c0-cf5833d412d0')
        self.incoming_log3 = self.create_incoming_log(
            tp='unlock',
            request_body={
                'amount': '200',
                'trackId': str(track_id),
                'serviceType': 'loan',
                'nationalCode': '1000000000',
            },
            user_service=self.user_service_3,
        )

    def test_full_report_attachment_generation_and_content_validation(self):
        report = CreditReport.objects.create(service=self.service, type=CreditReport.Type.ALL)
        assert CreditReport.Status.CREATED == report.status
        generate_requested_reports_attachments()

        report.refresh_from_db()
        report_attachments = ReportAttachment.objects.filter(report=report)
        assert len(report_attachments) == 4
        for attachments in report_attachments:
            if attachments.attachment_type == ReportAttachment.AttachmentType.LOCK:
                with open(attachments.file.path, 'r') as f:
                    lines = f.readlines()
                    assert set(lines) == {
                        ','.join(
                            [
                                'شماره ملی کاربر',
                                'شناسه وام',
                                'تاریخ ایجاد',
                                'مبلغ وام',
                                'مدت وام',
                                'بدهی اولیه',
                                'بدهی فعلی',
                                'وضعیت وام',
                                'تاریخ بسته شدن',
                                'شناسه درخواست\n',
                            ]
                        ),
                        self._get_init_row(self.user_service_1),
                        self._get_init_row(self.user_service_2),
                        self._get_init_row(self.user_service_3),
                    }

            elif attachments.attachment_type == ReportAttachment.AttachmentType.UNLOCK:
                with open(attachments.file.path, 'r') as f:
                    lines = f.readlines()
                    assert set(lines) == {
                        'شماره ملی کاربر,شناسه وام,وضعیت وام,شناسه درخواست,تاریخ ارسال,مبلغ آزادسازی\n',
                        self._get_unlock_row(self.incoming_log1, self.user_service_1),
                        self._get_unlock_row(self.incoming_log2, self.user_service_2),
                        self._get_unlock_row(self.incoming_log3, self.user_service_3),
                    }

            elif attachments.attachment_type == ReportAttachment.AttachmentType.SETTLEMENT:
                with open(attachments.file.path, 'r') as f:
                    lines = f.readlines()
                    assert set(lines) == {
                        ','.join(
                            [
                                'تاریخ ایجاد',
                                'شماره ملی کاربر',
                                'شناسه وام',
                                'مبلغ وام',
                                'بدهی اولیه',
                                'بدهی فعلی',
                                'مبلغ اقساط',
                                'مدت اقساط',
                                'هزینه سرویس دهنده',
                                'وضعیت وام',
                                'شناسه درخواست',
                                'مبلغ درخواست تسویه',
                                'وضعیت درخواست تسویه',
                                'همخوانی مبلغ تسویه',
                                'ارز سفارش',
                                'مبلغ سفارش',
                                'مقدار سفارش',
                                'وضعیت سفارش',
                                'مقدار مچ شده سفارش',
                                'مبلغ مچ شده سفارش',
                                'فی سفارش',
                                'مبلغ واقعی سفارش\n',
                            ]
                        ),
                        self._get_settlement_row(
                            self.settlement_1, self.user_service_1, None, '22ef9392-74fa-4ba7-b5d0-cf583e341222'
                        ),
                        self._get_settlement_row(
                            self.settlement_2, self.user_service_2, None, 'a73c69a8-4eb9-4df9-8025-6a1b113b79a2'
                        ),
                        self._get_settlement_row(
                            self.settlement_3, self.user_service_3, self.order_1, '22ef9392-74fa-4ba7-3333-cf222e341222'
                        ),
                        self._get_settlement_row(
                            self.settlement_3, self.user_service_3, self.order_2, '22ef9392-74fa-4ba7-3333-cf222e341222'
                        ),
                    }
            elif attachments.attachment_type == ReportAttachment.AttachmentType.SETTLEMENT_MISMATCH:
                with open(attachments.file.path, 'r') as f:
                    lines = f.readlines()
                    assert set(lines) == {
                        ','.join(
                            [
                                'تاریخ ایجاد',
                                'شماره ملی کاربر',
                                'شناسه وام',
                                'مبلغ وام',
                                'بدهی اولیه',
                                'بدهی فعلی',
                                'مبلغ اقساط',
                                'مدت اقساط',
                                'هزینه سرویس دهنده',
                                'وضعیت وام',
                                'شناسه درخواست',
                                'مبلغ درخواست تسویه',
                                'وضعیت درخواست تسویه',
                                'همخوانی مبلغ تسویه',
                                'ارز سفارش',
                                'مبلغ سفارش',
                                'مقدار سفارش',
                                'وضعیت سفارش',
                                'مقدار مچ شده سفارش',
                                'مبلغ مچ شده سفارش',
                                'فی سفارش',
                                'مبلغ واقعی سفارش\n',
                            ]
                        ),
                        self._get_settlement_row(
                            self.settlement_1, self.user_service_1, None, '22ef9392-74fa-4ba7-b5d0-cf583e341222'
                        ),
                        self._get_settlement_row(
                            self.settlement_3, self.user_service_3, self.order_1, '22ef9392-74fa-4ba7-3333-cf222e341222'
                        ),
                        self._get_settlement_row(
                            self.settlement_3, self.user_service_3, self.order_2, '22ef9392-74fa-4ba7-3333-cf222e341222'
                        ),
                    }
            else:
                assert False, f"Unexpected attachment type: {attachments.attachment_type}"

        assert CreditReport.Status.COMPLETED == report.status

    def test_report_only_settlement(self):
        report = CreditReport.objects.create(service=self.service, type=CreditReport.Type.SETTLEMENT)
        generate_requested_reports_attachments()

        report.refresh_from_db()
        report_attachments = ReportAttachment.objects.filter(report=report)
        assert len(report_attachments) == 1
        with open(report_attachments.first().file.path, 'r') as f:
            lines = f.readlines()
            assert set(lines) == {
                ','.join(
                    [
                        'تاریخ ایجاد',
                        'شماره ملی کاربر',
                        'شناسه وام',
                        'مبلغ وام',
                        'بدهی اولیه',
                        'بدهی فعلی',
                        'مبلغ اقساط',
                        'مدت اقساط',
                        'هزینه سرویس دهنده',
                        'وضعیت وام',
                        'شناسه درخواست',
                        'مبلغ درخواست تسویه',
                        'وضعیت درخواست تسویه',
                        'همخوانی مبلغ تسویه',
                        'ارز سفارش',
                        'مبلغ سفارش',
                        'مقدار سفارش',
                        'وضعیت سفارش',
                        'مقدار مچ شده سفارش',
                        'مبلغ مچ شده سفارش',
                        'فی سفارش',
                        'مبلغ واقعی سفارش\n',
                    ]
                ),
                self._get_settlement_row(
                    self.settlement_1, self.user_service_1, None, '22ef9392-74fa-4ba7-b5d0-cf583e341222'
                ),
                self._get_settlement_row(
                    self.settlement_2, self.user_service_2, None, 'a73c69a8-4eb9-4df9-8025-6a1b113b79a2'
                ),
                self._get_settlement_row(
                    self.settlement_3, self.user_service_3, self.order_1, '22ef9392-74fa-4ba7-3333-cf222e341222'
                ),
                self._get_settlement_row(
                    self.settlement_3, self.user_service_3, self.order_2, '22ef9392-74fa-4ba7-3333-cf222e341222'
                ),
            }
        assert report.status == CreditReport.Status.COMPLETED

    def test_report_with_start_date(self):
        start_date = jdatetime.date(1403, 6, 1).togregorian()
        report = CreditReport.objects.create(service=self.service, type=CreditReport.Type.LOCK, start_date=start_date)
        generate_requested_reports_attachments()

        report.refresh_from_db()
        report_attachments = ReportAttachment.objects.filter(report=report)
        assert len(report_attachments) == 1
        with open(report_attachments.first().file.path, 'r') as f:
            lines = f.readlines()
            assert set(lines) == {
                ','.join([
                    'شماره ملی کاربر',
                    'شناسه وام',
                    'تاریخ ایجاد',
                    'مبلغ وام',
                    'مدت وام',
                    'بدهی اولیه',
                    'بدهی فعلی',
                    'وضعیت وام',
                    'تاریخ بسته شدن',
                    'شناسه درخواست\n',
                ]),
                self._get_init_row(self.user_service_2),
                self._get_init_row(self.user_service_3),
            }
        assert report.status == CreditReport.Status.COMPLETED

    def test_report_with_start_date_and_end_date(self):
        start_date = jdatetime.date(1403, 6, 1).togregorian()
        end_date = jdatetime.date(1403, 7, 1).togregorian()
        report = CreditReport.objects.create(
            service=self.service, type=CreditReport.Type.LOCK, start_date=start_date, end_date=end_date
        )
        generate_requested_reports_attachments()

        report.refresh_from_db()
        report_attachments = ReportAttachment.objects.filter(report=report)
        assert len(report_attachments) == 1
        with open(report_attachments.first().file.path, 'r') as f:
            lines = f.readlines()
            assert set(lines) == {
                ','.join([
                    'شماره ملی کاربر',
                    'شناسه وام',
                    'تاریخ ایجاد',
                    'مبلغ وام',
                    'مدت وام',
                    'بدهی اولیه',
                    'بدهی فعلی',
                    'وضعیت وام',
                    'تاریخ بسته شدن',
                    'شناسه درخواست\n',
                ]),
                self._get_init_row(self.user_service_2),
            }
        assert report.status == CreditReport.Status.COMPLETED

    def test_report_attachment_contains_error_when_settlement_and_log_count_out_of_sync(self):
        """Test when incoming logs and lhl counts don't match"""
        report = CreditReport.objects.create(
            service=self.service, type=CreditReport.Type.SETTLEMENT, start_date=ir_now().date() + timedelta(days=1)
        )
        user_service = self.create_user_service(
            '1000000002', Decimal('1000'), Decimal('1000'), UserService.STATUS.initiated
        )

        settlement = self.create_settlement_transaction(user_service, Decimal('1000'))
        settlement.created_at = settlement.created_at + timedelta(days=1)
        settlement.save()

        generate_requested_reports_attachments()

        attachments = ReportAttachment.objects.filter(
            report=report, attachment_type=ReportAttachment.AttachmentType.SETTLEMENT
        )
        with open(attachments.first().file.path, 'r') as f:
            lines = f.readlines()
            assert set(lines) == {
                ','.join(
                    [
                        'تاریخ ایجاد',
                        'شماره ملی کاربر',
                        'شناسه وام',
                        'مبلغ وام',
                        'بدهی اولیه',
                        'بدهی فعلی',
                        'مبلغ اقساط',
                        'مدت اقساط',
                        'هزینه سرویس دهنده',
                        'وضعیت وام',
                        'شناسه درخواست',
                        'مبلغ درخواست تسویه',
                        'وضعیت درخواست تسویه',
                        'همخوانی مبلغ تسویه',
                        'ارز سفارش',
                        'مبلغ سفارش',
                        'مقدار سفارش',
                        'وضعیت سفارش',
                        'مقدار مچ شده سفارش',
                        'مبلغ مچ شده سفارش',
                        'فی سفارش',
                        'مبلغ واقعی سفارش\n',
                    ]
                ),
                ','.join(['error'] * 21 + ['error\n']),
            }

    def test_report_attachment_contains_error_when_settlement_and_log_creation_time_out_of_sync(self):
        report = CreditReport.objects.create(
            service=self.service, type=CreditReport.Type.SETTLEMENT, start_date=ir_now().date() + timedelta(days=2)
        )
        user_service = self.create_user_service(
            '1000000002', Decimal('1000'), Decimal('1000'), UserService.STATUS.initiated
        )

        settlement = self.create_settlement_transaction(user_service, Decimal('400'))
        settlement.created_at = settlement.created_at + timedelta(days=2)
        settlement.save()

        settlement_log_1 = self.create_incoming_log(
            tp='settlement',
            request_body={
                'amount': '400',
                'trackId': str(uuid.uuid4()),
                'serviceType': 'loan',
                'nationalCode': '1000000002',
            },
            user_service=user_service,
        )
        settlement_log_1.created_at = settlement_log_1.created_at + timedelta(days=2, minutes=5)
        settlement_log_1.save()

        generate_requested_reports_attachments()

        attachments = ReportAttachment.objects.filter(
            report=report, attachment_type=ReportAttachment.AttachmentType.SETTLEMENT
        )
        with open(attachments.first().file.path, 'r') as f:
            lines = f.readlines()
            assert set(lines) == {
                ','.join(
                    [
                        'تاریخ ایجاد',
                        'شماره ملی کاربر',
                        'شناسه وام',
                        'مبلغ وام',
                        'بدهی اولیه',
                        'بدهی فعلی',
                        'مبلغ اقساط',
                        'مدت اقساط',
                        'هزینه سرویس دهنده',
                        'وضعیت وام',
                        'شناسه درخواست',
                        'مبلغ درخواست تسویه',
                        'وضعیت درخواست تسویه',
                        'همخوانی مبلغ تسویه',
                        'ارز سفارش',
                        'مبلغ سفارش',
                        'مقدار سفارش',
                        'وضعیت سفارش',
                        'مقدار مچ شده سفارش',
                        'مبلغ مچ شده سفارش',
                        'فی سفارش',
                        'مبلغ واقعی سفارش\n',
                    ]
                ),
                ','.join(['error'] * 21 + ['error\n']),
            }

    def test_settlement_logs_unsync_amount(self):
        report = CreditReport.objects.create(
            service=self.service, type=CreditReport.Type.SETTLEMENT, start_date=ir_now().date() + timedelta(days=2)
        )
        user_service = self.create_user_service(
            '1000000002', Decimal('1000'), Decimal('1000'), UserService.STATUS.initiated
        )

        settlement = self.create_settlement_transaction(user_service, Decimal('400'))
        settlement.created_at = settlement.created_at + timedelta(days=2)
        settlement.save()

        settlement_log_1 = self.create_incoming_log(
            tp='settlement',
            request_body={
                'amount': '1000',
                'trackId': str(uuid.uuid4()),
                'serviceType': 'loan',
                'nationalCode': '1000000002',
            },
            user_service=user_service,
        )
        settlement_log_1.created_at = settlement_log_1.created_at + timedelta(days=2)
        settlement_log_1.save()

        generate_requested_reports_attachments()

        attachments = ReportAttachment.objects.filter(
            report=report, attachment_type=ReportAttachment.AttachmentType.SETTLEMENT
        )
        with open(attachments.first().file.path, 'r') as f:
            lines = f.readlines()
            assert set(lines) == {
                ','.join(
                    [
                        'تاریخ ایجاد',
                        'شماره ملی کاربر',
                        'شناسه وام',
                        'مبلغ وام',
                        'بدهی اولیه',
                        'بدهی فعلی',
                        'مبلغ اقساط',
                        'مدت اقساط',
                        'هزینه سرویس دهنده',
                        'وضعیت وام',
                        'شناسه درخواست',
                        'مبلغ درخواست تسویه',
                        'وضعیت درخواست تسویه',
                        'همخوانی مبلغ تسویه',
                        'ارز سفارش',
                        'مبلغ سفارش',
                        'مقدار سفارش',
                        'وضعیت سفارش',
                        'مقدار مچ شده سفارش',
                        'مبلغ مچ شده سفارش',
                        'فی سفارش',
                        'مبلغ واقعی سفارش\n',
                    ]
                ),
                ','.join(['error'] * 21 + ['error\n']),
            }

    def create_user_service(self, national_code: str, init_debt: Decimal, current_debt: Decimal, status: int):
        user, _ = User.objects.get_or_create(national_code=national_code, defaults={'username': national_code})
        permission = UserServicePermission.objects.create(user=user, service=self.service, created_at=ir_now())
        closed_at = ir_now() if status == UserService.STATUS.settled else None
        return UserService.objects.create(
            user=user,
            service=self.service,
            user_service_permission=permission,
            initial_debt=init_debt,
            current_debt=current_debt,
            principal=init_debt * Decimal('1.2'),
            installment_amount=init_debt * Decimal('0.2'),
            installment_period=6,
            provider_fee_amount=init_debt * Decimal('0.15'),
            status=status,
            closed_at=closed_at,
            account_number=str(uuid.uuid4()),
        )

    def create_incoming_log(self, tp: str, request_body: dict, user_service: UserService = None):
        user, _ = User.objects.get_or_create(
            national_code=request_body['nationalCode'], defaults={'username': request_body['nationalCode']}
        )
        return IncomingAPICallLog.create(
            api_url=f'/asset-backed-credit/v1/{tp}',
            service=self.service.tp,
            user=user,
            internal_user=None,
            response_code=200,
            provider=self.service.provider,
            uid=request_body['trackId'],
            request_body=request_body,
            response_body={'status': 'ok'},
            user_service=user_service,
        )

    def create_settlement_transaction(self, user_service, amount, orders=None):
        settlement = SettlementTransaction.create(user_service=user_service, amount=amount)
        if orders:
            settlement.orders.add(*[order.id for order in orders])

        return settlement

    def create_order(self, currency, price, amount, status, matched_amount, fee, user, matched_total_price):
        return Order.objects.create(
            order_type=Order.ORDER_TYPES.sell,
            src_currency=currency,
            dst_currency=2,
            price=price,
            amount=amount,
            status=status,
            matched_amount=matched_amount,
            fee=fee,
            user=user,
            description='',
            execution_type=Order.EXECUTION_TYPES.limit,
            matched_total_price=matched_total_price,
            param1=None,
            channel=Order.CHANNEL.system_abc_liquidate,
            trade_type=Order.TRADE_TYPES.credit,
        )

    def _get_init_row(self, user_service):
        user_service.refresh_from_db()

        national_code = user_service.user.national_code
        loan_id = user_service.account_number
        init_debt = int(user_service.initial_debt)
        principal = int(user_service.principal)
        period = int(user_service.installment_period)
        current_debt = int(user_service.current_debt)
        created_at = self._get_jdate(user_service.created_at)
        closed_at = self._get_jdate(user_service.closed_at)
        status = UserService.STATUS._display_map.get(user_service.status, None)

        return f'{national_code},{loan_id},{created_at},{principal},{period},{init_debt},{current_debt},{status},{closed_at}\n'

    def _get_unlock_row(self, incoming_log, user_service):
        incoming_log.refresh_from_db()
        user_service.refresh_from_db()

        created_at = self._get_jdate(incoming_log.created_at)
        national_code = incoming_log.user.national_code
        loan_id = user_service.account_number
        amount = int(incoming_log.request_body['amount'])
        status = UserService.STATUS._display_map.get(user_service.status, None)
        track_id = incoming_log.request_body['trackId']

        return f'{national_code},{loan_id},{status},{track_id},{created_at},{amount}\n'

    def _get_settlement_row(self, settlement, user_service, order=None, track_id=''):
        settlement.refresh_from_db()
        user_service.refresh_from_db()
        if order:
            order.refresh_from_db()

        settlement_amount = int(settlement.amount or 0)
        installment_amount = int(user_service.installment_amount or 0)
        provider_fee_amount = int(user_service.provider_fee_amount or 0)

        settlement_is_ok = (
            settlement_amount == installment_amount or settlement_amount == installment_amount + provider_fee_amount
        )

        return '{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n'.format(
            self._get_jdate(settlement.created_at),
            user_service.user.national_code,
            user_service.account_number,
            int(user_service.principal or 0),
            int(user_service.initial_debt),
            int(user_service.current_debt),
            int(user_service.installment_amount or 0),
            int(user_service.installment_period or 0),
            int(user_service.provider_fee_amount or 0),
            UserService.STATUS._display_map.get(user_service.status, None),
            track_id,
            int(settlement.amount),
            SettlementTransaction.STATUS._display_map.get(settlement.status, ''),
            settlement_is_ok,
            Currencies._display_map.get(order.src_currency, None) if order else '',
            order.price if order else '',
            order.amount if order else '',
            order.status if order else '',
            order.matched_amount if order else '',
            order.matched_total_price if order else '',
            order.fee if order else '',
            order.matched_total_price - order.fee if order else '',
        )

    @staticmethod
    def _get_jdate(datetime_=None):
        if datetime_:
            return jdatetime.datetime.fromgregorian(datetime=datetime_).strftime('%Y-%m-%d')
        return ''

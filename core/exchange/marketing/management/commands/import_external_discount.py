import os
from datetime import datetime

import openpyxl
from django.core.management.base import BaseCommand
from tqdm import tqdm

from exchange.base.calendar import ir_now
from exchange.marketing.models import ExternalDiscount
from exchange.marketing.utils import parse_time


class Command(BaseCommand):
    help = 'Import external discount data through excel file for a business'
    discounts = []

    def add_arguments(self, parser):
        parser.add_argument('--excel_file', type=str, required=True, help='path to the excel file')
        parser.add_argument(
            '--business_name', type=str, required=True, help='name of the business that has issued discount codes'
        )
        parser.add_argument(
            '--campaign_id', type=str, required=True, help='the campaign id that discount codes will be used for it'
        )
        parser.add_argument(
            '--enable_time',
            type=str,
            required=False,
            help='codes will be assignable after this date - datetime format -> YYYY-MM-DD HH:MM:SS (wrap in quotes)',
        )
        parser.add_argument('--batch_size', type=int, default=1000, help='size of batch for processing records')

    def handle(self, *args, **kwargs):
        batch_size = kwargs['batch_size']
        enable_time = self.parse_enable_time(kwargs['enable_time'])

        inserted_rows_count = self.insert_records(
            kwargs['excel_file'], kwargs['campaign_id'], kwargs['business_name'], enable_time, batch_size
        )
        self.stdout.write(
            self.style.SUCCESS(f' {inserted_rows_count} discount codes have been proceed \n'),
        )

    def insert_records(
        self, file_name: str, campaign_id: str, business_name: str, enabled_at: datetime, batch_size: int
    ) -> int:

        if not os.path.exists(file_name):
            self.stdout.write(self.style.ERROR(f'No such excel file: {file_name}'))
            return 0

        workbook = openpyxl.load_workbook(file_name, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=False, min_row=2, max_col=1)
        inserted_rows_count = 0

        try:
            for index, row in tqdm(enumerate(rows)):
                (code_cell) = row
                code = str(code_cell[0].value)
                if code is None or code.strip() == '':
                    continue

                self.discounts.append(
                    ExternalDiscount(
                        campaign_id=campaign_id, business_name=business_name, code=code, enabled_at=enabled_at
                    )
                )
                if len(self.discounts) % batch_size == 0:
                    inserted_rows_count += self.flush()

        finally:
            workbook.close()

        if len(self.discounts) > 0:
            inserted_rows_count += self.flush()

        return inserted_rows_count

    def flush(self):
        ExternalDiscount.objects.bulk_create(self.discounts, ignore_conflicts=True)
        inserted_count = len(self.discounts)
        self.discounts.clear()
        return inserted_count

    @staticmethod
    def parse_enable_time(enable_time_param: str) -> datetime:
        if enable_time_param is None:
            return ir_now()

        try:
            return parse_time(enable_time_param, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return ir_now()

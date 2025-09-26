import hashlib
import os
import random
import string
import time
from datetime import timedelta
from tempfile import NamedTemporaryFile

import openpyxl
from django.core.management import call_command
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.marketing.models import ExternalDiscount


class ImportExternalDiscountTest(TestCase):
    COMMAND_NAME = 'import_external_discount'

    def tearDown(self):
        ExternalDiscount.objects.all().delete()

    def create_test_excel_file(self, records_count, duplicate_count=0):
        rows = []
        for i in range(records_count):
            rows.append([self._generate_discount_code()])

        if duplicate_count > 0:
            rows = rows + rows[0:duplicate_count]

        self.excel_file = NamedTemporaryFile(delete=False, suffix='.xlsx')
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['code'])
        for row in rows:
            sheet.append(row)
        workbook.save(self.excel_file.name)
        workbook.close()
        return self.excel_file.name

    @staticmethod
    def _generate_discount_code():
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=3))
        raw_code = str(time.time()) + random_part
        hashed_code = hashlib.sha256(raw_code.encode()).hexdigest()
        referral_code = ''.join([char for char in hashed_code if char.isalnum()])[:7]
        return referral_code.upper()

    def test_insert_discount_success(self):

        # given ->
        discount_count = 1000
        campaign_id = '10M_snapp'
        business_name = 'snapp'
        batch_size = 31
        enable_time = ir_now() + timedelta(minutes=10)
        file_name = self.create_test_excel_file(discount_count)

        # when->
        call_command(
            self.COMMAND_NAME,
            excel_file=file_name,
            business_name=business_name,
            campaign_id=campaign_id,
            enable_time=enable_time.strftime('%Y-%m-%d %H:%M:%S'),
            batch_size=batch_size,
        )
        inserted_count = ExternalDiscount.objects.filter(campaign_id=campaign_id).count()
        discount = ExternalDiscount.objects.filter(campaign_id=campaign_id).first()
        assert discount.code.isalnum()
        assert int(discount.enabled_at.timestamp()) == int(enable_time.timestamp())

        # then->
        assert inserted_count == discount_count

        if self.excel_file and os.path.exists(file_name):
            os.remove(file_name)

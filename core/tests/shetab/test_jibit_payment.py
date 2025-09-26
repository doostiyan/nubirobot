import responses
from django.test import TestCase

from exchange.accounts.models import AdminConsideration, BankAccount, User
from exchange.features.models import QueueItem
from exchange.features.utils import is_feature_enabled
from exchange.shetab.handlers.jibit import JibitPip
from exchange.shetab.models import JibitAccount, JibitDeposit, JibitPaymentId
from exchange.shetab.parsers import parse_bank_swift_name
from exchange.shetab.serializers import serialize_deposit_payment_id
from exchange.wallet.models import BankDeposit
from tests.features.utils import BetaFeatureTestMixin


class JibitPaymentTest(BetaFeatureTestMixin, TestCase):
    feature = 'jibit_pip'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='test_jibit_payment@nobitex.ir')
        cls.valid_jibit_response = {
            'externalReferenceNumber': 'PIP-3',
            'status': 'SUCCESSFUL',
            'bank': 'BKMTIR',
            'bankReferenceNumber': '246320',
            'paymentId': '990008091172',
            'amount': JibitPip.LIMITATION_LEVEL_THREE,
            'destinationAccountIdentifier': 'IR830170000000010810111001',
            'rawBankTimestamp': '1400/2/25 22:26:36',
        }
        cls.bank_account = BankAccount.objects.create(
            owner_name='محمد طاهری',
            bank_id=17,
            bank_name='ملی',
            shaba_number='IR830170000000010810111001',
            account_number='0',
            user=cls.user,
            confirmed=True,
        )
        cls.jibit_account = JibitAccount.objects.create(
            bank=JibitAccount.BANK_CHOICES.BKMTIR,
            iban=cls.valid_jibit_response['destinationAccountIdentifier'],
            account_number='8992439961',
            owner_name='ایوان رایان پیام',
        )
        cls.jibit_payment_id = JibitPaymentId.objects.create(
            bank_account=cls.bank_account,
            jibit_account=cls.jibit_account,
            payment_id=cls.valid_jibit_response['paymentId'],
        )

        cls.request_feature(cls.user, 'done')

    def setUp(self):
        self.sample_jibit_response = {
            'externalReferenceNumber': 'PIP-3',
            'status': 'SUCCESSFUL',
            'bank': 'BKMTIR',
            'bankReferenceNumber': '246320',
            'paymentId': '990008091172',
            'amount': 1_000_000_000_0,
            'destinationAccountIdentifier': 'IR830170000000010810111001',
            'rawBankTimestamp': '1400/2/25 22:26:36',
        }

    def send_request(self):
        responses.get(
            f'{JibitPip.base_address}payments/{self.sample_jibit_response["externalReferenceNumber"]}/verify',
            json={
                'status': 'SUCCESSFUL',
                'paymentId': self.jibit_payment_id.payment_id,
                'amount': self.sample_jibit_response['amount'],
                'externalReferenceNumber': self.sample_jibit_response['externalReferenceNumber']},
        )
        responses.post(JibitPip.base_address + 'tokens/generate', json={
            'accessToken': 'accessToken',
            'refreshToken': 'accessToken',
        })

    def test_serialize_jibit_payment_id(self):
        assert serialize_deposit_payment_id(self.jibit_payment_id) == {
            'id': self.jibit_payment_id.id,
            'accountId': self.bank_account.id,
            'bank': self.bank_account.get_bank_id_display(),
            'iban': self.bank_account.shaba_number,
            'destinationBank': self.jibit_payment_id.jibit_account.get_bank_display(),
            'destinationIban': self.jibit_payment_id.jibit_account.iban,
            'destinationOwnerName': self.jibit_payment_id.jibit_account.owner_name,
            'destinationAccountNumber': self.jibit_payment_id.jibit_account.account_number,
            'paymentId': self.jibit_payment_id.payment_id,
            'type': 'jibit',
        }

    def test_parse_bank_swift_name(self):
        assert parse_bank_swift_name('BKMTIR') == JibitAccount.BANK_CHOICES.BKMTIR
        assert parse_bank_swift_name('MELIIR') == JibitAccount.BANK_CHOICES.MELIIR
        assert parse_bank_swift_name('SABCIR') == JibitAccount.BANK_CHOICES.SABCIR
        assert parse_bank_swift_name('AYBKIR') == JibitAccount.BANK_CHOICES.AYBKIR

    def test_parse_destination_account(self):
        sample_jibit_response = {
            'merchantCode': '6bl11',
            'merchantName': 'نوبیتکس',
            'merchantReferenceNumber': 'test0001',
            'userFullName': 'محمد طاهری',
            'userIban': 'IR83017000000011101111007',
            'userMobile': '09361600356',
            'destinationBank': 'BKMTIR',
            'destinationIban': 'IR760120020000008992439961',
            'destinationDepositNumber': '8992439967',
            'destinationOwnerName': 'ایوان رایان پیام',
            'payId': '990008091172',
        }
        account = JibitPip.parse_destination_account(sample_jibit_response, JibitAccount.ACCOUNT_TYPES.jibit)
        assert account.bank == JibitAccount.BANK_CHOICES.BKMTIR
        assert account.iban == 'IR760120020000008992439961'
        assert account.account_number == '8992439967'
        assert account.owner_name == 'ایوان رایان پیام'
        account2 = JibitPip.parse_destination_account(sample_jibit_response, JibitAccount.ACCOUNT_TYPES.jibit)
        assert account2.pk == account.pk

    def test_create_or_update_jibit_payment(self):
        sample_jibit_response = {
            'externalReferenceNumber': 'PIP-3',
            'status': 'IN_PROGRESS',
            'bank': 'BKMTIR',
            'bankReferenceNumber': '246320',
            'paymentId': '990008091172',
            'amount': 1000000,
            'destinationAccountIdentifier': 'IR830170000000010810111001',
            'rawBankTimestamp': '1400/2/25 22:26:36',
        }
        JibitPip.create_or_update_jibit_payment(sample_jibit_response)
        res = JibitDeposit.objects.first()
        assert res.payment_id.payment_id == '990008091172'
        assert res.payment_id.jibit_account.bank == 2
        assert res.status == 0
        assert res.external_reference_number == 'PIP-3'
        assert res.bank_reference_number == '246320'
        assert res.amount == 1000000
        assert res.raw_bank_timestamp == '1400/2/25 22:26:36'

        fake_sample_jibit_response = {
            'externalReferenceNumber': 'PIP-3',
            'status': 'SUCCESSFUL',
            'bank': 'BKMTIR',
            'bankReferenceNumber': '246320',
            'paymentId': '991008091172',
            'amount': 1000010,
            'destinationAccountIdentifier': 'IR830170000000010810111001',
            'rawBankTimestamp': '1400/2/25 22:26:36',
        }
        fake_request = JibitPip.create_or_update_jibit_payment(fake_sample_jibit_response)
        assert fake_request == (False, 'InvalidPaymentId')

        final_status_sample_jibit_response = {
            'externalReferenceNumber': 'PIP-3',
            'status': 'FAILED',
            'bank': 'BKMTIR',
            'bankReferenceNumber': '246320',
            'paymentId': '990008091172',
            'amount': 1000000,
            'destinationAccountIdentifier': 'IR830170000000010810111001',
            'rawBankTimestamp': '1400/2/25 22:26:36',
        }
        fianl_status_request = JibitPip.create_or_update_jibit_payment(final_status_sample_jibit_response)

        assert fianl_status_request == (True, None)

    @responses.activate
    def test_approve_bank_deposit_based_on_jibit_payment(self):
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save(update_fields=['user_type'])
        responses.get(f'{JibitPip.base_address}payments/{self.valid_jibit_response["externalReferenceNumber"]}/verify',
                      json={'status': 'SUCCESSFUL',
                            'paymentId': self.jibit_payment_id.payment_id,
                            'amount': self.valid_jibit_response['amount'],
                            'externalReferenceNumber': self.valid_jibit_response['externalReferenceNumber']},
                      )
        responses.post(JibitPip.base_address + 'tokens/generate', json={
            'accessToken': 'accessToken',
            'refreshToken': 'accessToken',
        })
        JibitPip.create_or_update_jibit_payment(self.valid_jibit_response)
        res = JibitDeposit.objects.first()
        assert res.payment_id.payment_id == '990008091172'
        assert res.status == JibitDeposit.STATUS.SUCCESSFUL
        assert is_feature_enabled(res.bank_deposit.user, QueueItem.FEATURES.jibit_pip)
        assert res.bank_deposit.status == BankDeposit.STATUS.confirmed
        assert res.bank_deposit.confirmed
        assert res.bank_deposit.transaction
        assert AdminConsideration.objects.filter(
            content_type__model='bankdeposit',
            user=res.bank_deposit.user,
            object_id=res.bank_deposit.id,
            consideration='تایید شده',
        ).exists()

    @responses.activate
    def test_approving_bank_deposit_based_on_jibit_payment_above_limit(self):
        sample_jibit_response = {
            'externalReferenceNumber': 'PIP-3',
            'status': 'SUCCESSFUL',
            'bank': 'BKMTIR',
            'bankReferenceNumber': '246320',
            'paymentId': '990008091172',
            'amount': JibitPip.LIMITATION_LEVEL_THREE + 10,
            'destinationAccountIdentifier': 'IR830170000000010810111001',
            'rawBankTimestamp': '1400/2/25 22:26:36',
        }
        responses.get(f'{JibitPip.base_address}payments/{sample_jibit_response["externalReferenceNumber"]}/verify',
                      json={'status': 'SUCCESSFUL',
                            'paymentId': self.jibit_payment_id.payment_id,
                            'amount': sample_jibit_response['amount'],
                            'externalReferenceNumber': sample_jibit_response['externalReferenceNumber']},
                      )
        responses.post(JibitPip.base_address + 'tokens/generate', json={
            'accessToken': 'accessToken',
            'refreshToken': 'accessToken',
        })
        JibitPip.create_or_update_jibit_payment(sample_jibit_response)
        res = JibitDeposit.objects.first()
        assert res.payment_id.payment_id == '990008091172'
        assert res.status == JibitDeposit.STATUS.SUCCESSFUL
        assert res.bank_deposit.status == BankDeposit.STATUS.new
        assert not res.bank_deposit.confirmed
        assert not res.bank_deposit.transaction

    @responses.activate
    def test_approving_bank_deposit_above_base_limitation(self):
        self.send_request()
        JibitPip.create_or_update_jibit_payment(self.sample_jibit_response)
        res = JibitDeposit.objects.first()
        assert res.payment_id.payment_id == '990008091172'
        assert res.status == JibitDeposit.STATUS.SUCCESSFUL
        assert res.bank_deposit.status == BankDeposit.STATUS.new
        assert not res.bank_deposit.confirmed
        assert not res.bank_deposit.transaction

    @responses.activate
    def test_approving_bank_deposit_level1_limitation(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save(update_fields=['user_type'])
        self.sample_jibit_response['amount'] = JibitPip.LIMITATION_LEVEL_ONE
        self.send_request()
        JibitPip.create_or_update_jibit_payment(self.sample_jibit_response)
        res = JibitDeposit.objects.filter(bank_reference_number='246320').first()
        assert res.payment_id.payment_id == '990008091172'
        assert res.status == JibitDeposit.STATUS.SUCCESSFUL
        assert res.bank_deposit.status == BankDeposit.STATUS.confirmed
        assert res.bank_deposit.confirmed
        assert res.bank_deposit.transaction

        # Above limitation
        self.sample_jibit_response['amount'] = JibitPip.LIMITATION_LEVEL_ONE + 1_000_000_0
        self.sample_jibit_response['bankReferenceNumber'] = '1246320'
        self.sample_jibit_response['externalReferenceNumber'] = 'PIP-2'
        self.send_request()
        JibitPip.create_or_update_jibit_payment(self.sample_jibit_response)
        res = JibitDeposit.objects.filter(bank_reference_number='1246320').first()
        assert res.payment_id.payment_id == '990008091172'
        assert res.bank_deposit.status == BankDeposit.STATUS.new
        assert not res.bank_deposit.transaction

    @responses.activate
    def test_jibit_payment_fee(self):
        self.user.user_type = User.USER_TYPES.trusted
        self.user.save(update_fields=['user_type'])
        responses.get(f'{JibitPip.base_address}payments/{self.valid_jibit_response["externalReferenceNumber"]}/verify',
                      json={'status': 'SUCCESSFUL',
                            'paymentId': self.jibit_payment_id.payment_id,
                            'amount': self.valid_jibit_response['amount'],
                            'externalReferenceNumber': self.valid_jibit_response['externalReferenceNumber']},
                      )
        responses.post(JibitPip.base_address + 'tokens/generate', json={
            'accessToken': 'accessToken',
            'refreshToken': 'accessToken',
        })
        JibitPip.create_or_update_jibit_payment(self.valid_jibit_response)
        res = JibitDeposit.objects.first()
        assert res.payment_id.payment_id == '990008091172'
        assert is_feature_enabled(res.bank_deposit.user, QueueItem.FEATURES.jibit_pip)
        assert res.status == JibitDeposit.STATUS.SUCCESSFUL
        assert res.bank_deposit.status == BankDeposit.STATUS.confirmed
        assert res.bank_deposit.amount == 5_000_000_000
        assert res.bank_deposit.fee == 500_000
        assert res.bank_deposit.confirmed
        assert res.bank_deposit.transaction
        assert res.bank_deposit.transaction.amount == 4_999_500_000

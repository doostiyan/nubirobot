import hashlib

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import BankAccount, BankCard, Notification, User
from exchange.base.models import RIAL, IPLogged, Settings
from exchange.base.tasks import run_admin_task
from exchange.shetab.handlers.nobitex import NobitexHandler
from exchange.wallet.models import BankDeposit, Transaction, Wallet

from .handlers import (
    IDPayHandler,
    JibitHandler,
    JibitHandlerV2,
    PayHandler,
    PaypingHandler,
    TomanHandler,
    VandarHandler,
)
from .handlers.vandar2step import Vandar2StepHandler


class ShetabDeposit(IPLogged):
    BROKER = Choices(
        (0, 'manual', 'Manual'),
        (1, 'nextpay', 'NextPay'),
        (2, 'payir', 'Pay.ir'),
        (3, 'payping', 'PayPing'),
        (4, 'idpay', 'IDPay'),
        (5, 'vandar', 'Vandar'),
        (6, 'jibit', 'Jibit'),
        (7, 'vandar2step', 'Vandar2Step'),
        (8, 'sayment', 'Sayment'),
        (9, 'jibit_v2', 'JibitV2'),
        (10, 'nobitex', 'Nobitex'),
        (11, 'toman', 'Toman'),
    )
    STATUS = Choices(
        (0, 'pay_new', 'Pay New'),
        (1, 'pay_success', 'Pay Success'),
        (100001, 'invalid_ip', 'Invalid IP'),
        (102030, 'invalid_card', 'Invalid Card'),
        (102040, 'refunded', 'Refunded'),
        (-1, 'pending_request', 'Pending Request'),
        (-2, 'confirmation_failed', 'Confirmation Failed'),
        (-3, 'amount_mismatch', 'Amount Mismatch'),
    )

    # Basic Details
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان')
    user = models.ForeignKey(get_user_model(), related_name='shetab_deposits',
                             verbose_name='کاربر', on_delete=models.CASCADE)
    selected_card = models.ForeignKey(BankCard, related_name='shetab_deposits', null=True, blank=True,
                                      verbose_name='کارت انتخابی', on_delete=models.SET_NULL)

    # Deposit Status
    status_code = models.IntegerField(default=-9999, verbose_name='وضعیت')
    user_card_number = models.CharField(max_length=50, blank=True, verbose_name='شماره کارت')
    user_card_hash = models.CharField(max_length=100, blank=True, verbose_name='هش کارت')

    # Financial Details
    amount = models.BigIntegerField(verbose_name='مبلغ واریزی', help_text='ریال')
    fee = models.BigIntegerField(default=0, verbose_name='کارمزد', help_text='ریال')
    transaction = models.ForeignKey(Transaction, null=True, blank=True, verbose_name='تراکنش', on_delete=models.CASCADE)

    # Gateway Details
    broker = models.IntegerField(choices=BROKER, default=BROKER.nextpay, verbose_name='درگاه پرداخت')
    nextpay_id = models.CharField(max_length=50, db_index=True, null=True, blank=True, verbose_name='شماره پیگیری')
    gateway_redirect_url = models.CharField(max_length=1000, null=True, blank=True, verbose_name='آدرس انتقال به درگاه')
    next_redirect_url = models.CharField(max_length=100, null=True, blank=True, verbose_name='آدرس بازگشت')

    anomaly_score = models.SmallIntegerField(null=True, blank=True)
    class Meta:
        verbose_name = 'واریز شتابی'
        verbose_name_plural = verbose_name

    handler_class = {
        BROKER.payir: PayHandler,
        BROKER.payping: PaypingHandler,
        BROKER.idpay: IDPayHandler,
        BROKER.vandar: VandarHandler,
        BROKER.vandar2step: Vandar2StepHandler,
        BROKER.jibit: JibitHandler,
        BROKER.jibit_v2: JibitHandlerV2,
        BROKER.nobitex: NobitexHandler,
        BROKER.toman: TomanHandler,
    }

    @property
    def handler(self):
        return self.handler_class[self.broker]

    @property
    def order_id(self):
        return self.pk

    @property
    def external_order_id(self):
        return '{nx}{pk}'.format(nx=self.nextpay_id[:8], pk=self.pk)

    @property
    def is_valid(self):
        return self.is_card_valid and self.is_requested and self.is_status_valid

    @property
    def is_requested(self):
        return self.nextpay_id and self.nextpay_id != '0'

    @property
    def is_payir(self):
        return self.broker == self.BROKER.payir

    @property
    def is_payping(self):
        return self.broker == self.BROKER.payping

    @property
    def is_card_valid(self):
        return self.user_card_number and self.user_card_number != '0000-0000-0000-0000'

    @property
    def is_status_valid(self):
        if self.status_code in [self.STATUS.invalid_card, self.STATUS.refunded]:
            return True
        return self.is_status_done

    @property
    def is_status_done(self):
        if self.broker:
            return self.status_code == 1
        return True

    @property
    def effective_date(self):
        if self.transaction:
            return self.transaction.created_at
        return self.created_at

    @property
    def net_amount(self):
        return self.amount - self.fee

    def calculate_fee(self) -> int:
        shetab_fee = settings.NOBITEX_OPTIONS['shetabFee']
        min_fee = shetab_fee['min']
        max_fee = shetab_fee['max']

        fee = int(self.amount * shetab_fee['rate'])

        if fee < min_fee:
            fee = min_fee
        elif fee > max_fee:
            fee = max_fee

        return fee

    def sync(self, request, **kwargs):
        if 'retry' in kwargs and not kwargs['retry']:
            del kwargs['retry']
        self.handler.sync(self, request, **kwargs)

    def sync_and_update(self, request=None, retry=False):
        if self.transaction:
            if self.status_code == self.STATUS.invalid_card:
                # Handle re-authenticated deposits with invalid card
                if not self.check_card_number():
                    return False
                with transaction.atomic():
                    self.status_code = self.STATUS.pay_success
                    self.save(update_fields=['status_code'])
                    self.unblock_balance()
                return True
            return True
        if not self.is_requested:
            return False
        self.sync(request, retry=retry)
        return self.create_transaction()

    def create_transaction(self):
        """Create transaction and set fee for this deposit."""
        if not self.is_status_valid or not self.is_card_valid:
            return False
        wallet = Wallet.get_user_wallet(self.user, RIAL)
        description = 'واریز شتابی - شماره کارت: {} - شماره پیگیری: {}'.format(self.user_card_number, self.nextpay_id)
        self.fee = self.calculate_fee()
        net_amount = self.amount - self.fee
        with transaction.atomic():
            _transaction = wallet.create_transaction(
                tp='deposit', amount=net_amount, description=description, allow_negative_balance=True
            )
            _transaction.commit(ref=self, allow_negative_balance=True)
            self.transaction = _transaction
            self.save(update_fields=['transaction', 'fee'])
        if not Settings.is_disabled('detect_deposit_for_fraud'):
            transaction.on_commit(
                lambda: run_admin_task('detectify.check_deposit_fraud', deposit_id=self.pk)
            )
        return True

    def sync_card(self):
        if not self.transaction:
            return False
        default_card_number = '1' * 16
        user_card_number = self.handler.get_user_card_number(self) or default_card_number
        if user_card_number in [default_card_number, self.user_card_number]:
            return False
        self.user_card_number = user_card_number
        self.save(update_fields=['user_card_number'])
        return self.sync_and_update()

    def get_pay_redirect_url(self):
        if not self.is_requested:
            return '#'
        return self.handler.get_api_redirect_url(self)

    get_pay_redirect_url.short_description = 'آدرس موثر انتقال به درگاه'

    def check_card_number(self, card_number=None, update_status=True):
        user_card_number = self.user_card_number if not card_number else card_number
        approved_cards = BankCard.get_user_bank_cards(self.user)
        # Check by card number hash
        if self.user_card_hash:
            for card in approved_cards:
                hasher = hashlib.sha256()
                hasher.update(card.card_number.encode('utf8'))
                if self.user_card_hash == hasher.hexdigest():
                    return True
            return False
        # Handle many special cases of payping
        if self.is_payping and user_card_number == '-':
            return True
        user_card_number = user_card_number.replace('-', '')
        if len(user_card_number) < 16 and '*' in user_card_number:
            while len(user_card_number) < 16:
                user_card_number = user_card_number.replace('*', '**', 1)
        while len(user_card_number) > 16 and '**' in user_card_number:
            user_card_number = user_card_number.replace('**', '*', 1)
        # Check if any of user's approved card matches with this card number
        card_is_valid = any(card.check_number_matches(user_card_number) for card in approved_cards)
        if not card_is_valid:
            # Testnet has simulated shetab deposit, so allow any card number
            if settings.IS_TESTNET:
                return True
            # Set shetab deposit status to invalid_card (102030)
            if update_status:
                self._invalid_card_flag = True
                self.status_code = self.STATUS.invalid_card
                self.save(update_fields=['status_code'])
            return False
        return True

    def block_balance(self):
        """Block the amount of this deposit for the user."""
        Notification.notify_admins(
            f'بررسی موقت واریز شتابی ناهمنام #{self.id}',
            title='💳 واریز شتابی',
            channel='operation',
        )
        # Skip if already blocked
        wallet = Wallet.get_user_wallet(self.user, RIAL)
        block_transaction = Transaction.objects.filter(
            wallet=wallet,
            ref_module=Transaction.REF_MODULES['ShetabBlock'],
            ref_id=self.pk,
        )
        if block_transaction.exists():
            return False
        # Block deposit amount
        transaction = wallet.create_transaction(
            tp='manual',
            amount=-self.net_amount,
            description='بررسی موقت واریز شتابی ناهمنام #{}'.format(self.pk),
        )
        transaction.commit(ref=Transaction.Ref('ShetabBlock', self.pk))
        self._invalid_card_flag = False
        return True

    def unblock_balance(self):
        """Unblock the amount of deposit if there is a block transaction for it."""
        Notification.notify_admins(
            f'پایان بررسی واریز شتابی ناهمنام #{self.id}',
            title='💳 واریز شتابی',
            channel='operation',
        )
        wallet = Wallet.get_user_wallet(self.user, RIAL)
        # Skip if not blocked
        block_transaction = Transaction.objects.filter(
            wallet=wallet,
            ref_module=Transaction.REF_MODULES['ShetabBlock'],
            ref_id=self.pk,
        ).first()
        if not block_transaction:
            return False
        # Skip if already unblocked
        unblock_transaction = Transaction.objects.filter(
            wallet=wallet,
            ref_module=Transaction.REF_MODULES['ReverseTransaction'],
            ref_id=block_transaction.pk,
        )
        if unblock_transaction.exists():
            return False
        # Create unblock transaction
        transaction = wallet.create_transaction(
            tp='manual',
            amount=-block_transaction.amount,
            description='پایان بررسی واریز شتابی ناهمنام #{} و تراکنش #{}'.format(self.pk, block_transaction.pk),
        )
        if not transaction:
            return False
        transaction.commit(ref=Transaction.Ref('ReverseTransaction', block_transaction.pk))
        return True

    @classmethod
    def get_blocked_deposits(cls, user=None):
        blocked_deposits = cls.objects.filter(status_code=cls.STATUS.invalid_card)
        if user:
            if isinstance(user, int):
                blocked_deposits = blocked_deposits.filter(user_id=user)
            else:
                blocked_deposits = blocked_deposits.filter(user=user)
        return blocked_deposits

    @classmethod
    def update_user_invalid_deposits(cls, user):
        for deposit in cls.get_blocked_deposits(user=user).select_related('user'):
            deposit.sync_and_update()


class JibitAccount(models.Model):
    BANK_CHOICES = Choices(
        (0, 'BMJIIR', 'markazi'),
        (1, 'BOIMIR', 'SANAT_VA_MADAN'),
        (2, 'BKMTIR', 'ملت'),
        (3, 'REFAIR', 'REFAH'),
        (4, 'BKMNIR', 'MASKAN'),
        (5, 'SEPBIR', 'SEPAH'),
        (6, 'KESHIR', 'KESHAARZI'),
        (7, 'MELIIR', 'ملی'),
        (8, 'BTEJIR', 'TEJARAT'),
        (9, 'BSIRIR', 'SADERAT'),
        (10, 'EDBIIR', 'TOSEAH_SADERAT'),
        (11, 'PBIRIR', 'POST'),
        (12, 'TTBIIR', 'TOSEAH_TAAVON'),
        (13, 'BTOSIR', 'TOSEAH'),
        (14, 'GHAVIR', 'GHAVAMIN'),
        (15, 'GHAVIR', 'KARAFARIN'),
        (16, 'BKPAIR', 'PARSIAN'),
        (17, 'BEGNIR', 'EGHTESADE_NOVIN'),
        (18, 'SABCIR', 'SAMAN'),
        (19, 'BKBPIR', 'PASARGAD'),
        (20, 'SRMBIR', 'SARMAIEH'),
        (21, 'SINAIR', 'SINA'),
        (22, 'MEHRIR', 'MEHR_IRANIAN'),
        (23, 'CIYBIR', 'SHAHR'),
        (24, 'AYBKIR', 'AYANDEH'),
        (25, 'TOSMIR', 'GARDESHGARI'),
        (26, 'HEKMIR', 'HEKMAT_IRANIAN'),
        (27, 'ANSBIR', 'RESALAT'),
        (28, 'DAYBIR', 'DEY'),
        (29, 'IRZAIR', 'IRANZAMIN'),
        (30, 'MELLIR', 'MELAL'),
        (31, 'KHMIIR', 'KAVARMIANEH'),
        (32, 'IVBBIR', 'IRAN_VENEZOELA'),
        (33, 'NOORIR', 'NOOR'),
        (34, 'MEGHIR', 'MEHR_EGHTESAD'),
    )
    ACCOUNT_TYPES = Choices(
        (0, 'jibit', 'Jibit'),
        (1, 'nobitex_jibit', 'NobitexJibit'),
    )

    bank = models.IntegerField(choices=BANK_CHOICES, default=BANK_CHOICES.MELIIR, verbose_name='بانک')
    iban = models.CharField(max_length=26, verbose_name='شماره شبای مقصد', unique=True)
    account_number = models.CharField(max_length=25, unique=True, verbose_name='شماره حساب مقصد')
    owner_name = models.CharField(max_length=100, verbose_name='نام صاحب حساب')
    account_type = models.SmallIntegerField(choices=ACCOUNT_TYPES, default=ACCOUNT_TYPES.jibit, verbose_name='نوع حساب')

    class Meta:
        verbose_name = 'حساب‌های نزد جیبیت'
        verbose_name_plural = verbose_name


class JibitPaymentId(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, verbose_name='حساب بانکی')
    jibit_account = models.ForeignKey(JibitAccount, on_delete=models.CASCADE, verbose_name='حساب جیبیت')
    payment_id = models.CharField(max_length=25, verbose_name='شناسه پرداخت')
    created_at = models.DateTimeField(default=now, db_index=True, verbose_name='زمان')

    REFERENCE_PREFIXES = {
        JibitAccount.ACCOUNT_TYPES.jibit: 'NA',
        JibitAccount.ACCOUNT_TYPES.nobitex_jibit: 'NJ',
    }

    class Meta:
        verbose_name = 'شناسه واریز'
        verbose_name_plural = verbose_name

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'jibit_account',
                    'payment_id',
                ],
                name='shetab_%(class)s_jibit_account_payment_id_unique',
            )
        ]

    @property
    def reference_number(self):
        return self.get_reference_number(self.bank_account.id, self.jibit_account.account_type)

    @classmethod
    def get_reference_number(cls, bank_id: int, account_type: int = JibitAccount.ACCOUNT_TYPES.jibit):
        return f'{cls.REFERENCE_PREFIXES[account_type]}{bank_id}'

    @property
    def deposit_account(self):
        return self.jibit_account

    @property
    def type(self):
        return JibitAccount.ACCOUNT_TYPES._triples[self.jibit_account.account_type][1]


class JibitDeposit(models.Model):
    STATUS = Choices(
        (0, 'IN_PROGRESS', 'در حال پردازش'),
        (1, 'WAITING_FOR_MERCHANT_VERIFY', 'در حال انتظار تایید'),
        (2, 'FAILED', 'ناموفق'),
        (3, 'SUCCESSFUL', 'موفق'),
    )
    STATUSES_ACCEPTABLE = [STATUS.SUCCESSFUL, STATUS.WAITING_FOR_MERCHANT_VERIFY]
    STATUSES_FINAL = [STATUS.SUCCESSFUL, STATUS.FAILED]

    payment_id = models.ForeignKey(JibitPaymentId, on_delete=models.CASCADE, verbose_name='حساب بانکی')
    bank_deposit = models.ForeignKey(BankDeposit, on_delete=models.CASCADE,
                                     null=True, blank=True, verbose_name='واریز بانکی')
    created_at = models.DateTimeField(default=now, db_index=True, verbose_name='زمان')
    status = models.IntegerField(choices=STATUS, default=STATUS.IN_PROGRESS)
    external_reference_number = models.CharField(max_length=50, verbose_name='شناسه واریز در جیبیت')
    bank_reference_number = models.CharField(max_length=255, verbose_name='شناسه واریز بانک')
    amount = models.BigIntegerField(verbose_name='مبلغ واریزی', help_text='ریال')
    raw_bank_timestamp = models.CharField(max_length=50, verbose_name='زمان واریز')

    class Meta:
        verbose_name = 'واریزی‌های جیبیت'
        verbose_name_plural = verbose_name
        unique_together = ['payment_id', 'external_reference_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_status = self.status

    def save(self, *args, **kwargs):
        if self.status == JibitDeposit.STATUS.SUCCESSFUL and (
            self.id is None or not self._initial_status == JibitDeposit.STATUS.SUCCESSFUL
        ):
            Notification.notify_admins(
                message=f'انجام شد. {self.external_reference_number} واریز با شناسه‌ی جیبیت',
                title='واریز شناسه‌دار',
                channel='operation',
            )
        return super().save(*args, **kwargs)


class VandarAccount(models.Model):
    uuid = models.CharField(max_length=40, unique=True, verbose_name='شناسه وندار کاربر')
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='کاربر')
    created_at = models.DateTimeField(default=now, db_index=True, verbose_name='زمان')

    class Meta:
        verbose_name = 'حساب وندار'
        verbose_name_plural = 'حساب‌های وندار'

    @property
    def iban(self) -> str:
        return Settings.get('vandar_shaba_number', settings.VANDAR_SHABA_NUMBER)

    @property
    def account_number(self) -> str:
        return Settings.get('vandar_account_number', settings.VANDAR_ACCOUNT_NUMBER)

    @property
    def bank_id(self) -> int:
        return int(self.iban[4:7])

    def get_bank_display(self) -> str:
        return BankAccount.BANK_ID._display_map[self.bank_id]

    @property
    def owner_name(self) -> str:
        return 'تجارت الکترونیک ارسباران'


class VandarPaymentId(models.Model):
    vandar_account = models.OneToOneField(VandarAccount, on_delete=models.CASCADE, verbose_name='حساب وندار')
    bank_account = models.OneToOneField(BankAccount, on_delete=models.CASCADE, verbose_name='حساب بانکی')
    payment_id = models.CharField(max_length=25, unique=True, db_index=True, verbose_name='شناسه پرداخت')
    created_at = models.DateTimeField(default=now, db_index=True, verbose_name='زمان')

    class Meta:
        verbose_name = 'شناسه واریز وندار'
        verbose_name_plural = 'شناسه‌های واریز وندار'

    @property
    def deposit_account(self):
        return self.vandar_account

    @property
    def type(self):
        return 'vandar'

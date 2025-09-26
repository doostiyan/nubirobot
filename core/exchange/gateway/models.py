import uuid
from decimal import Decimal
from urllib.parse import urlparse

from django.db import models
from model_utils import Choices

from exchange.accounts.models import Confirmed, User
from exchange.base.fields import RoundedDecimalField
from exchange.base.models import RIAL, TETHER, Currencies


class PaymentGatewayUser(Confirmed):
    api = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    secret = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, verbose_name='کاربر', on_delete=models.CASCADE)
    domain = models.CharField(max_length=250, verbose_name='دامنه')
    site_name = models.CharField(max_length=250, verbose_name='نام پذیرنده')
    logo_image = models.ForeignKey('accounts.UploadedFile', null=True, blank=True, related_name='+', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'درگاه'
        verbose_name_plural = verbose_name
        unique_together = [['user', 'domain']]

    def __str__(self):
        return 'درگاه {}'.format(self.site_name)

    def get_domains_url(self):
        domains = []
        for d in self.domain.split(','):
            domains.append(urlparse(d.lower())._replace(query='')._replace(fragment='').netloc)
        return domains


class PaymentGatewayInvoice(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    pg_user = models.ForeignKey(PaymentGatewayUser, verbose_name='کاربر درگاه', on_delete=models.CASCADE)
    amount = models.PositiveIntegerField(verbose_name='مقدار ریالی', null=True)
    amount_tether = models.PositiveIntegerField(verbose_name='مقدار دلاری', null=True)
    redirect = models.URLField(max_length=600)
    mobile = models.CharField(max_length=12, null=True, blank=True, verbose_name='موبایل')
    factor_number = models.CharField(max_length=200, null=True, blank=True, verbose_name='شماره فاکتور')
    description = models.CharField(max_length=255, null=True, blank=True, verbose_name='توضیحات')

    class Meta:
        verbose_name = 'فاکتور درگاه'
        verbose_name_plural = verbose_name

    def __str__(self):
        return 'فاکتور #{} {} به مبلغ {}'.format(self.pk, self.factor_number, self.settle_amount)

    @property
    def settle_tp(self):
        return RIAL if self.amount else TETHER

    @property
    def settle_amount(self):
        return self.amount or self.amount_tether


GatewayCurrencies = Choices(
    (Currencies.btc, 'btc', 'Bitcoin'),
    (Currencies.ltc, 'ltc', 'Litcoin'),
    (Currencies.xrp, 'xrp', 'Ripple')
)

AVAILABLE_GATEWAY_CURRENCIES = [
    GatewayCurrencies.btc,
    GatewayCurrencies.ltc,
    GatewayCurrencies.xrp,
]


class PendingWalletRequest(models.Model):
    STATUS = Choices('pending', 'unknown', 'paid', 'expired', 'partial', 'unconfirmed')
    REFUND_STATUS = [STATUS.expired, STATUS.partial]
    req_id = models.CharField(max_length=100, null=True, blank=True)
    pg_req = models.ForeignKey(PaymentGatewayInvoice, verbose_name='درخواست درگاه', on_delete=models.CASCADE,
                               related_name='wallet_request')
    uri = models.CharField(max_length=400, null=True, blank=True)
    address = models.CharField(max_length=400, null=True, blank=True)
    crypto_amount = models.BigIntegerField(verbose_name='مقدار ارز دیجیتال')
    expiry = models.PositiveIntegerField(verbose_name='زمان اعتبار', null=True, blank=True)
    status = models.CharField(choices=STATUS, max_length=20, default=STATUS.unknown)
    confirmations = models.IntegerField(default=0)
    created_time = models.DateTimeField(db_index=True)
    tp = models.IntegerField(choices=GatewayCurrencies, default=GatewayCurrencies.btc)
    rate = RoundedDecimalField(max_digits=20, decimal_places=10, verbose_name='نرخ تبدیل')

    tx_hash = models.CharField(max_length=200, null=True, blank=True)
    settle_tx = models.ForeignKey('wallet.Transaction', on_delete=models.CASCADE, null=True, verbose_name='تراکنش تسویه')

    verify = models.BooleanField(default=False)
    settle = models.BooleanField(default=False)
    create_order = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'پرداخت درگاه'
        verbose_name_plural = verbose_name
        unique_together = [['req_id', 'tp'], ['pg_req', 'tp']]

    @property
    def exact_crypto_amount(self):
        places = {
            Currencies.btc: Decimal('1e-8'),
            Currencies.ltc: Decimal('1e-8'),
            Currencies.xrp: Decimal('1e-2'),
        }
        return Decimal(str(self.crypto_amount)) * places.get(self.tp, Decimal('1'))

    @property
    def effective_date(self):
        if self.settle_tx:
            return self.settle_tx.created_at
        return self.created_time


class PaymentGatewayLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    pg_user = models.ForeignKey(PaymentGatewayUser, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.IntegerField(default=0)
    code_description = models.CharField(max_length=1000, blank=True, default='')
    description = models.CharField(max_length=1000, blank=True, default='')
    method = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name = 'لاگ درگاه'
        verbose_name_plural = verbose_name


class PaymentRequestRefund(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    pg_req = models.ForeignKey(PendingWalletRequest, on_delete=models.SET_NULL, null=True, blank=True)
    token = models.CharField(max_length=200, blank=True, default='')
    refund_address = models.CharField(max_length=300, blank=True, default='')
    reference_code = models.UUIDField(default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        verbose_name = 'درخواست بازگشت وجه'
        verbose_name_plural = verbose_name

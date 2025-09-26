import hashlib
import hmac
from decimal import Decimal
from typing import Optional

import requests
from django.conf import settings
from django.db import models
from django.db.models import JSONField
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.formatting import f_m
from exchange.base.models import RIAL, TAG_NEEDED_CURRENCIES, Currencies
from exchange.wallet.models import Wallet, WalletDepositAddress, WalletDepositTag, WithdrawRequest


class PostalOrder(models.Model):
    """Represent a request for postal order (manual, padro or ...)"""
    STATUS = Choices(
        (0, 'new', 'جدید'),
        (1, 'registered', 'ثبت درخواست'),
        (2, 'picked_up', 'تحویل به پست'),
        (3, 'delivered', 'تحویل شده'),
        (4, 'failed', 'ناموفق'),
    )
    PROVIDERS = Choices(
        (0, 'manual', 'ارسال دستی'),
        (1, 'padro', 'ارسال از طریق پادرو'),
    )
    created_at = models.DateTimeField(default=now)

    status = models.IntegerField(choices=STATUS, default=STATUS.new, null=False, verbose_name='وضعیت')
    provider = models.IntegerField(choices=PROVIDERS, null=True, verbose_name='پروایدر')

    order_id = models.CharField(max_length=200, null=True, verbose_name='کد سفارش')

    source_city = models.CharField(max_length=20, null=False, verbose_name='کد شهر مبدا')
    destination_city = models.CharField(max_length=20, null=False, verbose_name='کد شهر مقصد')

    sender_name = models.CharField(max_length=250, verbose_name='نام فرستنده')
    sender_postal_code = models.CharField(max_length=10, null=False, verbose_name='کد پستی فرستنده')
    sender_phone_number = models.CharField(max_length=12, null=False, verbose_name='شماره موبایل فرستنده')
    receiver_name = models.CharField(max_length=250, verbose_name='نام گیرنده')
    receiver_postal_code = models.CharField(max_length=10, null=False, verbose_name='کد پستی گیرنده')
    receiver_address = models.TextField(null=False, verbose_name='آدرس گیرنده')
    receiver_phone_number = models.CharField(max_length=12, null=False, verbose_name='شماره موبایل گیرنده')
    receiver_comment = models.TextField(null=False, verbose_name='پیام گیرنده')

    provider_code = models.CharField(max_length=100, null=True, verbose_name='شناسه پروایدر')
    provider_name = models.CharField(max_length=100, null=True, verbose_name='نام پروایدر')
    price = models.DecimalField(max_digits=25, decimal_places=10, null=True, verbose_name='هزینه ارسال')
    from_hours = models.IntegerField(null=True, verbose_name='زمان ارسال (از)')
    to_hours = models.IntegerField(null=True, verbose_name='زمان ارسال (تا)')
    service_type = models.CharField(max_length=100, null=True, verbose_name='نوع سرویس')
    service_type_label = models.CharField(max_length=100, null=True, verbose_name='عنوان نوع سرویس')
    pickup_date = models.DateField(null=True, verbose_name='تاریخ جمع آوری')
    pickup_from_hour = models.IntegerField(null=True, verbose_name='ساعت جمع آوری (از)')
    pickup_to_hour = models.IntegerField(null=True, verbose_name='ساعت جمع آوری (تا)')

    def __str__(self):
        return self.sender_name


class Parcel(models.Model):
    """Every instance represent a postal package in a postal order"""
    created_at = models.DateTimeField(default=now)

    weight = models.IntegerField(null=False, verbose_name='وزن')
    value = models.DecimalField(max_digits=25, decimal_places=10, null=False, verbose_name='ارزش بسته')
    width = models.IntegerField(null=False, verbose_name='عرض بسته')
    height = models.IntegerField(null=False, verbose_name='طول بسته')
    depth = models.IntegerField(null=False, verbose_name='ارتفاع بسته')
    content = models.CharField(max_length=500, null=False, verbose_name='محتوای بسته')
    name = models.CharField(max_length=200, null=False, verbose_name='نام بسته')
    postal_orders = models.ManyToManyField(PostalOrder, related_name='parcels', through='PostalOrderParcel')

    def __str__(self):
        return self.name


class PostalOrderParcel(models.Model):
    postal_order = models.ForeignKey(PostalOrder, related_name='postal_order_parcels', on_delete=models.CASCADE,
                                     verbose_name='سفارش پستی')
    parcel = models.ForeignKey(Parcel, related_name='parcel_postal_orders', on_delete=models.CASCADE,
                               verbose_name='بسته پستی')
    parcel_num = models.IntegerField(default=1, verbose_name='تعداد', null=False, blank=False)
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return f'{self.postal_order} - {self.parcel}'


class BaseGiftInfo(models.Model):
    """Abstract model for fields shared in gift card and gift batch models"""
    GIFT_TYPES = Choices(
        (0, 'physical', 'Physical'),
        (1, 'digital', 'Digital'),
    )

    REDEEM_TYPE = Choices(
        (0, 'lightning', 'Lightning'),
        (1, 'internal', 'Internal'),
    )
    # Receiver Details shared in two gift models.
    receiver_email = models.EmailField(null=True)
    mobile = models.CharField(max_length=20, null=True)
    address = models.TextField(null=True, blank=True)
    postal_code = models.CharField(max_length=100, null=True, blank=True)
    otp_enabled = models.BooleanField(default=False)
    is_sealed = models.BooleanField(default=False, null=True)

    # Financial Details
    amount = models.DecimalField(max_digits=25, decimal_places=10)
    currency = models.IntegerField(choices=Currencies, null=True)

    # Gift card details
    gift_type = models.IntegerField(choices=GIFT_TYPES)
    gift_sentence = models.CharField(max_length=100)

    # Redeem details
    password = models.CharField(max_length=200)
    redeem_type = models.IntegerField(choices=REDEEM_TYPE)
    redeem_date = models.DateTimeField(null=True)

    # Graphical Details
    card_design = models.ForeignKey('CardDesign', null=True, on_delete=models.PROTECT)
    package_type = models.ForeignKey('GiftPackage', null=True, on_delete=models.PROTECT)

    created_at = models.DateTimeField(default=now)

    class Meta:
        abstract = True


class GiftBatchRequest(BaseGiftInfo):
    """ Batch Grouping of Gift Cards
    """
    BATCH_STATUS = Choices(
        (0, 'new', 'New'),
        (1, 'user_confirmed', 'User Confirmed'),
        (2, 'confirmed', 'Confirmed'),
        (3, 'canceled', 'Canceled'),
    )
    user = models.ForeignKey(User, related_name='gift_batches', on_delete=models.CASCADE)
    number = models.IntegerField(null=True)
    explanation = models.TextField(null=True, blank=True)
    total_amount = models.DecimalField(null=True, default=0, decimal_places=10, max_digits=20)
    amount = models.DecimalField(max_digits=25, decimal_places=10, null=True)
    status = models.IntegerField(choices=BATCH_STATUS, default=BATCH_STATUS.new)
    gift_sentence = models.CharField(max_length=100, null=True)
    gift_type = models.IntegerField(choices=BaseGiftInfo.GIFT_TYPES, null=True)
    password = models.CharField(max_length=200, null=True)
    redeem_type = models.IntegerField(choices=BaseGiftInfo.REDEEM_TYPE, null=True)
    digital_info = JSONField(blank=True, null=True)

    # Postal Order
    postal_order = models.ForeignKey(PostalOrder, related_name='batch_requests', on_delete=models.CASCADE, null=True)
    postal_tracking_code = models.CharField(max_length=100, null=True, blank=True)


class GiftCard(BaseGiftInfo):
    """ Main model for gift card processing, including both withdraw and redeem details.
    """
    GIFT_STATUS = Choices(
        (100, 'review', 'Review'),  # if gift needs review
        (0, 'new', 'New'),
        (1, 'redeemed', 'Redeemed'),
        (2, 'canceled', 'Canceled'),
        (3, 'confirmed', 'Confirmed'),  # if gift_type is physical and is confirmed by staff
        (4, 'verified', 'Verified'),  # a gift is verified after user verifies its initial withdraw
        (5, 'closed', 'Closed'),  # a gift is closed if its initial withdraw remains new or gets rejected
        (6, 'printed', 'Printed'),  # if gift_type is physical and its printed
        (7, 'sent', 'Sent'),  # if gift_type is physical and its printed and is posted
        (8, 'delivered', 'Delivered'),  # if gift_type is physical and its printed and is posted and delivered
    )
    REDEEMABLE_STATUSES = [GIFT_STATUS.verified, GIFT_STATUS.confirmed, GIFT_STATUS.printed,
                           GIFT_STATUS.sent, GIFT_STATUS.delivered]

    # Financial Details
    sender = models.ForeignKey(User, related_name='user_gift_cards', on_delete=models.CASCADE)
    initial_withdraw = models.ForeignKey(WithdrawRequest, related_name='+', on_delete=models.CASCADE, null=True)

    # Gift Card Details
    gift_status = models.IntegerField(choices=GIFT_STATUS, default=GIFT_STATUS.new)

    # Batch Requests
    # TODO: Is this field required?
    gift_batch = models.ForeignKey(GiftBatchRequest, related_name='batch_gifts', on_delete=models.SET_NULL, null=True)

    # Receiver Details
    receiver = models.ForeignKey(User, related_name='user_received_gift_cards', on_delete=models.CASCADE, null=True)
    full_name = models.CharField(max_length=200)
    alternative_address = models.TextField(null=True, blank=True, verbose_name='آدرس جایگزین')

    # Redeem Details
    redeem_code = models.CharField(max_length=100, unique=True)
    redeem_withdraw = models.ForeignKey(WithdrawRequest, related_name='+', on_delete=models.CASCADE, null=True)
    lnurl = models.CharField(max_length=300, null=True, unique=True)
    lnurl_key = models.CharField(max_length=100, null=True)
    redeemed_at = models.DateTimeField(null=True)

    # Postal Order
    postal_order = models.ForeignKey(PostalOrder, related_name='gift_cards', on_delete=models.CASCADE, null=True)

    # Admin
    admin_note = models.TextField(default='', blank=True, verbose_name='یادداشت')

    @property
    def is_redeemed(self):
        return self.gift_status == GiftCard.GIFT_STATUS.redeemed

    @property
    def is_internal(self):
        return self.redeem_type == GiftCard.REDEEM_TYPE.internal

    @property
    def is_lightning(self):
        return self.redeem_type == GiftCard.REDEEM_TYPE.lightning

    @property
    def is_physical(self):
        return self.gift_type == GiftCard.GIFT_TYPES.physical

    @property
    def cost(self):
        if self.gift_type == GiftCard.GIFT_TYPES.physical:
            if self.gift_status in GiftCard.REDEEMABLE_STATUSES and \
               self.gift_batch and \
               self.gift_batch.batch_gifts.filter(gift_status__in=GiftCard.REDEEMABLE_STATUSES).count() > 1:
                return settings.GIFT_CARD_PHYSICAL_PRINT_FEE
            return settings.GIFT_CARD_PHYSICAL_FEE + settings.GIFT_CARD_SEAL_FEE if \
                self.is_sealed else settings.GIFT_CARD_PHYSICAL_FEE
        return Decimal('0')

    @property
    def initial_withdraw_status(self):
        """checks initial withdraw status to be committed and whether if its transaction has been created or not"""
        return (
            self.initial_withdraw and
            self.initial_withdraw.status in WithdrawRequest.STATUSES_COMMITED and
            self.initial_withdraw.transaction is not None
        )

    def set_lnurl(self):
        """retrieves and sets lnurl and it's key."""
        if self.is_redeemed:
            return False

        headers = {}
        payload = bytearray(f'{{"amount":{int(self.amount)}, "usage":1, "count":1}}', 'utf-8')
        secret = bytearray(settings.LND_SERVER_API_KEY, 'utf-8')
        sign = hmac.new(secret, payload, digestmod=hashlib.sha256)
        headers['Authorization'] = sign.hexdigest()
        response = requests.post(
            settings.LND_SERVER_URL,
            data=payload,
            headers=headers,
        )
        if response.status_code != 200:
            return False
        self.lnurl = response.json()['gifts'][0]['lnurl']
        self.lnurl_key = response.json()['gifts'][0]['key']
        self.save(update_fields=['lnurl', 'lnurl_key'])
        return True

    def confirm_internal_gift_withdraw(self, receiver):
        """creation and confirmation of redeem withdraw in case of internal redeem types"""
        gift_user = User.get_gift_system_user()
        gift_wallet = Wallet.get_user_wallet(gift_user, self.currency)
        gifted_user_wallet = Wallet.get_user_wallet(receiver, self.currency)
        address_params = {}
        if self.currency in TAG_NEEDED_CURRENCIES:
            tag = gifted_user_wallet.get_current_deposit_tag(create=True)
            if not tag:
                # user might have address for this kind of coin instead of tag.
                address = gifted_user_wallet.get_current_deposit_address(create=True)
                if not address:
                    return False, None
                if isinstance(address, str):
                    address_params['target_address'] = address
                else:
                    address_params['target_address'] = address.address
            if isinstance(tag, int):
                address_params['tag'] = tag
            else:
                address_params['tag'] = tag.tag

            address = gifted_user_wallet.get_current_deposit_address(create=True)
            if isinstance(address, str):
                address_params['target_address'] = address
            else:
                address_params['target_address'] = address.address

        else:
            address = gifted_user_wallet.get_current_deposit_address(create=True)
            if not address:
                return False, None
            if isinstance(address, str):
                address_params['target_address'] = address
            else:
                address_params['target_address'] = address.address
        network = CURRENCY_INFO[self.currency]['default_network']
        redeem_withdraw = WithdrawRequest.objects.create(
            amount=self.amount,
            tp=WithdrawRequest.TYPE.internal,
            wallet=gift_wallet,
            explanations=f'Gift withdraw from system gift for user {receiver.id}',
            network=network,
            **address_params,
        )
        redeem_withdraw.do_verify()
        return True, redeem_withdraw

    def redeem_lnurl(self, user=None):
        """ Redeem this gift card and return a lnurl for lightning withdraws.

            Response is returned as: (lnurl, error)
        """
        if not self.initial_withdraw_status:
            return None, 'InvalidInitialWithdraw'

        if user is not None:
            self.receiver = user
            self.redeemed_at = now()
            if self.is_lightning:
                if not self.set_lnurl():
                    return None, 'LnurlUnavailable'
                self.gift_status = GiftCard.GIFT_STATUS.redeemed
                self.save(update_fields=['gift_status', 'receiver', 'redeemed_at'])
                self.notify_sender()
                Notification.notify_admins(
                    f'Lightning gift Card and with amount of {f_m(self.amount)}'
                    f' with sender user {self.sender.email} and receiver {self.receiver_email} '
                    f'and currency {self.get_currency_display()}, has been redeemed.',
                    title='دریافت هدیه'
                )
                return self.lnurl, None

            success, redeem_withdraw = self.confirm_internal_gift_withdraw(user)
            if not success:
                return None, 'InternalWithdrawFailed'
            self.gift_status = GiftCard.GIFT_STATUS.redeemed
            self.redeem_withdraw = redeem_withdraw
            self.save(update_fields=['gift_status', 'redeem_withdraw', 'receiver', 'redeemed_at'])
            self.notify_sender()
            Notification.notify_admins(
                f'Internal gift Card with redeem withdraw {self.redeem_withdraw.id} '
                f'and amount {f_m(self.amount)}'
                f' with sender user {self.sender.email} and receiver {self.receiver_email} and '
                f'currency {self.get_currency_display()}, has been redeemed.',
                title='دریافت هدیه'
            )
            return None, None

        if not self.set_lnurl():
            return None, 'LnurlUnavailable'
        self.gift_status = GiftCard.GIFT_STATUS.redeemed
        self.redeemed_at = now()
        self.save(update_fields=['gift_status', 'redeemed_at'])
        self.notify_sender()
        Notification.notify_admins(
            f'Lightning gift Card and with amount of {f_m(self.amount)}'
            f' with sender user {self.sender.email} and currency {self.get_currency_display()}, redeemed.',
            title='دریافت هدیه'
        )
        return self.lnurl, None

    def revert_physical_cost(self):
        """method for reverting physical cost transaction from gift rial wallet to sender rial wallet."""
        if self.is_physical:
            # return physical cost to user rial wallet
            gift_user = User.get_gift_system_user()
            cost = self.cost
            cancel_physical_gift_cost_tr = Wallet.get_user_wallet(gift_user, RIAL).create_transaction(
                amount=-cost,
                description=f'User-{self.sender.id}, cancel transaction for physical gift cost.',
                tp='manual',
            )
            cancel_physical_gift_cost_tr.commit()
            return_physical_cost_tr = Wallet.get_user_wallet(self.sender, RIAL).create_transaction(
                amount=cost,
                description=f'User-{self.sender.id} return physical cost.',
                tp='manual',
            )
            return_physical_cost_tr.commit()

    def notify_sender(self):
        """notify sender of successful receipt of the gift"""
        UserSms.objects.create(
            user=self.sender,
            tp=UserSms.TYPES.gift,
            to=self.sender.mobile,
            text='هدیه‌ی ارسالی نوبیتکس شما با موفقیت توسط گیرنده دریافت شد.',
        )


class CardDesign(models.Model):
    title = models.CharField(max_length=255, verbose_name='عنوان طرح')
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='قیمت', default=0)
    inventory = models.PositiveIntegerField(default=0, verbose_name='موجودی')
    front_image = models.ForeignKey('accounts.UploadedFile', related_name='+', on_delete=models.CASCADE,
                                    verbose_name='تصویر روی کارت', null=True)
    real_front_image = models.ForeignKey('accounts.UploadedFile', related_name='+', on_delete=models.CASCADE,
                                         verbose_name='تصویر واقعی روی کارت', null=True)
    back_image = models.ForeignKey('accounts.UploadedFile', related_name='+', on_delete=models.CASCADE,
                                   verbose_name='تصویر پشت کارت', null=True)
    real_back_image = models.ForeignKey('accounts.UploadedFile', related_name='+', on_delete=models.CASCADE,
                                        verbose_name='تصویر واقعی پشت کارت', null=True)

    def __str__(self):
        return self.title

    @property
    def is_in_stock(self):
        return self.inventory > 0

    @classmethod
    def get_by_title(cls, design_title: str) -> Optional['CardDesign']:
        """
        Retrieve a CardDesign object by its title.

        Args:
            design_title (str): The title of the CardDesign to retrieve.

        Returns:
            CardDesign or None: The CardDesign object if found, None otherwise.
        """
        return cls.objects.filter(title__iexact=design_title).first()


class GiftPackage(models.Model):
    name = models.CharField(max_length=255, null=False, verbose_name='نام بسته‌بندی')
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='قیمت')
    images = models.ManyToManyField('accounts.UploadedFile', related_name='+', verbose_name='تصاویر')
    stock = models.IntegerField(null=False, verbose_name='موجودی')
    weight = models.IntegerField(null=False, verbose_name='وزن بسته')
    width = models.IntegerField(null=False, verbose_name='عرض بسته')
    height = models.IntegerField(null=False, verbose_name='طول بسته')
    depth = models.IntegerField(null=False, verbose_name='ارتفاع بسته')
    can_batch_request = models.BooleanField(default=False)

    def __str__(self):
        return self.name

from decimal import Decimal
from enum import IntEnum
from typing import Optional

from django.db import models
from model_utils import Choices
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel

from exchange.accounts.models import User
from exchange.asset_backed_credit.currencies import ABCCurrencies
from exchange.asset_backed_credit.models import UserService
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.base.calendar import ir_now


class Card(models.Model):
    STATUS = Choices(
        (0, 'requested', 'requested'),  # user has requested
        (90, 'issuance_payment_skipped', 'issuance_payment_skipped'),  # no issue cost needed
        (100, 'issuance_paid', 'issuance_paid'),  # issue cost paid by user
        (10, 'registered', 'registered'),  # registered in third-party provider
        (20, 'issued', 'issued'),  # card is issued
        (30, 'verified', 'verified'),  # card is verified by OTP
        (40, 'activated', 'activated'),  # card is active
        (50, 'restricted', 'restricted'),  # restricted by either nobitex or provider
        (60, 'expired', 'expired'),  # reached expiration date
        (70, 'disabled', 'disabled'),  # disabled by user
        (80, 'suspended', 'suspended'),  # suspended by user
    )

    pan = models.CharField(max_length=20, unique=True, null=True, blank=True)
    status = models.SmallIntegerField(choices=STATUS, default=STATUS.requested)
    created_at = models.DateTimeField(default=ir_now)
    updated_at = models.DateTimeField(default=ir_now)
    issued_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    extra_info = models.JSONField(default=dict, blank=True)
    provider_info = models.JSONField(default=dict, blank=True)
    # relations
    user_service = models.ForeignKey(
        UserService,
        related_name='card',
        on_delete=models.PROTECT,
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    internal_user = models.ForeignKey(
        InternalUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    setting = models.ForeignKey(to='CardSetting', null=True, blank=True, on_delete=models.PROTECT)

    @property
    def masked_pan(self):
        return f'{self.pan[:6]}******{self.pan[-4:]}' if self.pan else None


class CardDeliveryAddressSchema(BaseModel):
    province: str
    city: str
    postal_code: str
    address: str


class CardIssueDataSchema(BaseModel):
    cost: int
    transfer_id: Optional[int] = None
    transfer_currency: Optional[int] = None
    transfer_amount: Optional[Decimal] = None
    settlement_id: Optional[int] = None


class BaseCardRequestSchema(BaseModel):
    class ColorChoices(IntEnum):
        CARBON = 1
        GOLD = 2
        ROSE_GOLD = 3
        OLIVE = 4
        AMBER = 5
        VIOLET = 6

    first_name: str
    last_name: str
    birth_cert_no: str
    color: ColorChoices
    delivery_address: Optional[CardDeliveryAddressSchema] = None


class CardRequestSchema(BaseCardRequestSchema):
    issue_data: Optional[CardIssueDataSchema] = None


class CardDeliveryAddressAPISchema(CardDeliveryAddressSchema):
    model_config = ConfigDict(alias_generator=to_camel)


class CardRequestAPISchema(BaseCardRequestSchema):
    delivery_address: Optional[CardDeliveryAddressAPISchema] = None
    transfer_currency: Optional[int] = None

    model_config = ConfigDict(alias_generator=to_camel)

    @field_validator('transfer_currency')
    @classmethod
    def check_selected_currency(cls, transfer_currency: int):
        from exchange.asset_backed_credit.models import Wallet

        if transfer_currency is not None and transfer_currency not in ABCCurrencies.get_all_currencies(
            wallet_type=Wallet.WalletType.DEBIT
        ):
            raise ValueError()
        return transfer_currency

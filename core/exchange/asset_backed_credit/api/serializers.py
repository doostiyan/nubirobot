from decimal import Decimal
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveInt
from pydantic.alias_generators import to_camel
from rest_framework import serializers

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.wallet import InternalWalletType
from exchange.asset_backed_credit.models import (
    Card,
    OutgoingAPICallLog,
    Service,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
    WalletTransferLog,
)
from exchange.asset_backed_credit.types import TransactionResponse
from exchange.base.models import get_currency_codename
from exchange.base.serializers import register_serializer, serialize_choices


def loan_service_essential_information_serializer(service: Service):
    return {
        'periods': service.options.get('periods'),
        'providerFee': service.options.get('provider_fee'),
        'punishmentRate': service.options.get('punishment_rate'),
        'forcedLiquidationPeriod': service.options.get('forced_liquidation_period'),
        'noPunishmentPeriod': service.options.get('no_punishment_period'),
        'minPrincipalLimit': service.options.get('min_principal_limit'),
        'maxPrincipalLimit': service.options.get('max_principal_limit'),
        'debtToGrantRatio': service.options.get('debt_to_grant_ratio'),
    }


service_type_specific_serializer_map = {
    Service.TYPES.loan: loan_service_essential_information_serializer,
}


def get_service_type_specific_serializer(service_type: Service.TYPES):
    return service_type_specific_serializer_map.get(service_type, lambda _: {})


def service_essential_information(service: Service):
    data = {
        'id': service.id,
        'provider': serialize_choices(Service.PROVIDERS, service.provider),
        'type': serialize_choices(Service.TYPES, service.tp),
        'fee': service.fee,
        'interest': service.interest,
        'providerFa': service.get_provider_display(),
        'typeFa': service.get_tp_display(),
        'isAvailable': service.is_available,
    }
    type_specific_data = get_service_type_specific_serializer(service.tp)(service)
    data.update(**type_specific_data)

    return data


@register_serializer(model=Service)
def serialize_service(service: Service, opts: Optional[Dict] = None):
    min_limit, max_limit = None, None
    if opts and 'limits' in opts:
        limit = opts['limits'].get(service.pk)
        if limit:
            min_limit, max_limit = limit.min_limit, limit.max_limit

    return {
        'minimumDebt': min_limit,
        'maximumDebt': max_limit,
        **service_essential_information(service),
    }


@register_serializer(model=UserServicePermission)
def serialize_service_permission(permission: UserServicePermission, opts: Optional[Dict] = None):
    return {
        'serviceId': permission.service.pk,
        'createdAt': permission.created_at,
        'provider': serialize_choices(Service.PROVIDERS, permission.service.provider),
        'type': serialize_choices(Service.TYPES, permission.service.tp),
    }


@register_serializer(model=UserService)
def serialize_user_service(user_service: UserService, opts=None):
    return {
        'id': user_service.id,
        'createdAt': user_service.created_at,
        'closedAt': user_service.closed_at,
        'currentDebt': user_service.current_debt,
        'initialDebt': user_service.initial_debt,
        'service': service_essential_information(user_service.service),
        'status': user_service.get_status_display(),
        'principal': user_service.principal,
        'totalRepayment': user_service.total_repayment,
        'installmentAmount': user_service.installment_amount,
        'installmentPeriod': user_service.installment_period,
        'collateralFeePercent': user_service.COLLATERAL_FEE_PERCENT,
        'collateralFeeAmount': user_service.COLLATERAL_FEE_AMOUNT,
        'providerFeePercent': user_service.provider_fee_percent,
        'providerFeeAmount': user_service.provider_fee_amount,
        'extraInfo': user_service.extra_info,
    }


@register_serializer(model=Card)
def serialize_card(card: Card, opts: Optional[Dict] = None):
    return {
        'id': card.id,
        'status': card.status,
    }


class OutgoingAPICallLogSerializer(serializers.ModelSerializer):
    user_service_id = serializers.PrimaryKeyRelatedField(source='user_service', read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(source='user', read_only=True)

    class Meta:
        model = OutgoingAPICallLog
        exclude = ('user_service', 'user')


@register_serializer(model=TransactionResponse)
def serialize(response: TransactionResponse, opts: Optional[Dict] = None):
    data = {
        'RespCode': response.status,
        'PAN': response.pan,
        'RID': response.rid,
        'RRN': response.rrn,
        'Trace': response.trace,
    }
    return data


class LoanCalculationSerializer(serializers.Serializer):
    principal = serializers.IntegerField(min_value=0)
    period = serializers.IntegerField(min_value=1)


class CreateUserServiceSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=0)


class CreateLoanUserServiceSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=0)
    period = serializers.IntegerField(min_value=1)


CREATE_USER_SERVICE_SERIALIZERS = {
    Service.TYPES.credit: CreateUserServiceSerializer,
    Service.TYPES.loan: CreateLoanUserServiceSerializer,
    Service.TYPES.debit: CreateUserServiceSerializer,
}


class InitiateCreditSchema(BaseModel):
    amount: PositiveInt
    redirect_url: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
    )


class InitiateLoanSchema(BaseModel):
    amount: PositiveInt
    principal: PositiveInt
    period: PositiveInt
    unique_id: str = Field(alias='uniqueIdentifier')
    redirect_url: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
    )


INITIATE_USER_SERVICE_SCHEMA_MAP = {
    Service.TYPES.credit: InitiateCreditSchema,
    Service.TYPES.loan: InitiateLoanSchema,
}


class UserFinancialServiceLimitSerializer(serializers.ModelSerializer):
    LIMIT_TYPES = dict(getattr(UserFinancialServiceLimit.TYPES, '_identifier_map').items())

    userID = serializers.UUIDField(default=None)
    limitType = serializers.ChoiceField(choices=tuple(LIMIT_TYPES.keys()))
    serviceID = serializers.IntegerField(default=None)
    userType = serializers.ChoiceField(choices=User.USER_TYPES, default=None)

    class Meta:
        model = UserFinancialServiceLimit
        fields = ('userID', 'limitType', 'serviceID', 'userType', 'limit')

    def validate(self, attrs):
        data = super().validate(attrs)
        limit_type = data['tp'] = self.LIMIT_TYPES[data.pop('limitType')]

        if limit_type in (UserFinancialServiceLimit.TYPES.user, UserFinancialServiceLimit.TYPES.user_service):
            if not data.get('userID'):
                raise serializers.ValidationError({'userID': serializers.Field.default_error_messages['required']})

            try:
                user = User.objects.get(uid=data.pop('userID'))
            except User.DoesNotExist:
                raise serializers.ValidationError({'userID': 'user does not exist'})
            data['user'] = user

        if limit_type in (
            UserFinancialServiceLimit.TYPES.service,
            UserFinancialServiceLimit.TYPES.user_service,
            UserFinancialServiceLimit.TYPES.user_type_service,
        ):
            if not data.get('serviceID'):
                raise serializers.ValidationError({'service_id': serializers.Field.default_error_messages['required']})

            try:
                service = Service.objects.get(pk=data.pop('serviceID'))
            except Service.DoesNotExist:
                raise serializers.ValidationError({'service_id': 'service does not exist'})
            data['service'] = service

        if limit_type == UserFinancialServiceLimit.TYPES.user_type_service:
            if data.get('userType') is None:
                raise serializers.ValidationError({'userType': serializers.Field.default_error_messages['required']})

        return data

    def create(self, validated_data):
        if validated_data['tp'] == UserFinancialServiceLimit.TYPES.user:
            return UserFinancialServiceLimit.set_user_limit(
                user=validated_data['user'], max_limit=validated_data['limit']
            )
        if validated_data['tp'] == UserFinancialServiceLimit.TYPES.user_service:
            return UserFinancialServiceLimit.set_user_service_limit(
                user=validated_data['user'], service=validated_data['service'], max_limit=validated_data['limit']
            )
        if validated_data['tp'] == UserFinancialServiceLimit.TYPES.user_type_service:
            return UserFinancialServiceLimit.set_user_type_service_limit(
                service=validated_data['service'],
                user_type=validated_data['userType'],
                max_limit=validated_data['limit'],
            )

        return UserFinancialServiceLimit.set_service_limit(
            service=validated_data['service'], max_limit=validated_data['limit']
        )

    def to_representation(self, instance):
        return {
            'id': instance.pk,
            'limitType': {v: k for k, v in self.LIMIT_TYPES.items()}[instance.tp],
            'limit': instance.limit,
            'userID': instance.user.uid if instance.user else None,
            'serviceID': instance.service.id if instance.service else None,
            'userType': instance.user_type if instance.user_type else None,
        }


class WalletTransferLogCreateResponseSerializer(serializers.Serializer):
    def to_representation(self, instance: WalletTransferLog):
        return {
            'id': instance.id,
            'createdAt': instance.created_at,
            'rejectionReason': '',
            'srcType': InternalWalletType.from_db_value(instance.src_wallet_type),
            'dstType': InternalWalletType.from_db_value(instance.dst_wallet_type),
            'transfers': [
                {'currency': get_currency_codename(currency), 'amount': amount}
                for currency, amount in instance.transfer_items.items()
            ],
        }


class DebitCardListSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    pan: Optional[str] = None
    color: int
    status: str
    issued_at: Optional[str] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class DebitCardTransactionSchema(BaseModel):
    created_at: str
    amount: int
    balance: int
    type: str
    currency: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class DebitCardSettlementSchema(BaseModel):
    created_at: str
    amount: int
    balance: int
    type: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class DebitCardSpendingLimitsSchema(BaseModel):
    daily_limit: int
    monthly_limit: int
    transaction_limit: int

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class DebitCardOverViewSchema(BaseModel):
    available_balance: int
    today_spending: int
    today_remaining_spending: int
    today_remaining_spending_percent: int
    this_month_spending: int
    this_month_remaining_spending: int
    this_month_remaining_spending_percent: int
    this_month_cashback: int
    this_month_cashback_percentage: Decimal
    limits: DebitCardSpendingLimitsSchema

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

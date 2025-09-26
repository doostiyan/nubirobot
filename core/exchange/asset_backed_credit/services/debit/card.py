import hashlib
from decimal import Decimal
from typing import List, Optional, Tuple
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import QuerySet

from exchange.accounts.models import User, UserSms
from exchange.accounts.userlevels import UserLevelManager
from exchange.asset_backed_credit.exceptions import (
    CardAlreadyExists,
    CardInvalidStatusError,
    CardNotFoundError,
    DebitCardCreationServiceTemporaryUnavailable,
    DuplicateDebitCardRequestByUser,
    ServiceAlreadyActivated,
    ServiceNotFoundError,
    ServicePermissionNotFound,
    ServiceUnavailableError,
    ThirdPartyError,
    TransferCurrencyRequiredError,
    UserLevelRestrictionError,
    UserServiceNotFoundError,
)
from exchange.asset_backed_credit.externals.notification import NotificationProvider, notification_provider
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.models import (
    Card,
    CardDeliveryAddressSchema,
    CardIssueDataSchema,
    CardRequestAPISchema,
    CardRequestSchema,
    InternalUser,
    Service,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
    Wallet,
)
from exchange.asset_backed_credit.services.debit.limits import get_default_card_settings
from exchange.asset_backed_credit.services.debit.schema import DebitCardUserInfoSchema
from exchange.asset_backed_credit.services.price import PricingService
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher_v2
from exchange.asset_backed_credit.services.providers.types import CardStatus
from exchange.asset_backed_credit.services.user import get_or_create_internal_user
from exchange.asset_backed_credit.services.user_service import create_user_service
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.asset_backed_credit.types import DebitCardEnableData, WalletDepositInput, WalletTransferItem, WalletType
from exchange.base.calendar import ir_now
from exchange.base.constants import MAX_PRECISION
from exchange.base.logging import report_exception
from exchange.base.models import Settings, get_currency_codename
from exchange.base.validators import validate_transaction_is_atomic

DEBIT_PROVIDER = Service.PROVIDERS.parsian
NOBIFI_PROVIDER = Service.PROVIDERS.nobifi
OTP_EXPIRE_SECONDS = 120


@transaction.atomic
def enable_debit_card_batch(data: List[DebitCardEnableData]):
    check_card_creation_enabled()

    for item in data:
        enable_debit_card(item.user_id, item.pan)


@transaction.atomic
def enable_debit_card(user_id: UUID, pan: str) -> None:
    user = User.objects.get(uid=user_id)
    internal_user = get_or_create_internal_user(user_id=user.uid)
    _is_user_eligible(user)
    service = _get_service()
    user_service_permission = _get_or_create_active_permission(user, internal_user, service)
    card_exists = Card.objects.filter(pan=pan, user=user, user_service__service=service).exists()
    if card_exists:
        raise CardAlreadyExists
    user_service = create_user_service(
        user=user,
        internal_user=internal_user,
        service=service,
        initial_debt=Decimal(0),
        permission=user_service_permission,
        is_service_limit_enabled=False,
        is_margin_ratio_check_enabled=False,
    )
    Card.objects.create(
        pan=pan,
        user_service=user_service,
        user=user,
        internal_user=internal_user,
        status=Card.STATUS.activated,
        setting=get_default_card_settings(),
    )


def _is_user_eligible(user):
    if not UserLevelManager.is_user_verified_as_level_1(user=user):
        raise UserLevelRestrictionError(
            message='UserLevelRestriction',
            description='User is not verified as level 1.',
        )
    if not UserLevelManager.is_user_mobile_identity_confirmed(user=user):
        raise UserLevelRestrictionError(
            message='UserLevelRestriction',
            description='User has no confirmed mobile number.',
        )


def _get_service() -> Service:
    service = Service.get_matching_active_service(provider=DEBIT_PROVIDER, tp=Service.TYPES.debit)
    if not service:
        raise ServiceNotFoundError(message='No active debit service found!')
    return service


def _get_nobifi_service() -> Service:
    service = Service.get_matching_active_service(provider=NOBIFI_PROVIDER, tp=Service.TYPES.debit)
    if not service:
        raise ServiceNotFoundError(message='No active nobifi service found!')
    return service


def _get_active_service():
    service = _get_service()
    if not service.is_available:
        raise ServiceUnavailableError('در حال حاضر، امکان درخواست نوبی‌کارت وجود ندارد.')
    return service


def _get_or_create_active_permission(
    user: User, internal_user: InternalUser, service: Service
) -> UserServicePermission:
    user_service_permission = UserServicePermission.get_active_permission_by_service(user=user, service=service)
    if not user_service_permission:
        user_service_permission = UserServicePermission.objects.create(
            user=user, internal_user=internal_user, service=service, created_at=ir_now()
        )
    return user_service_permission


def create_debit_card(user: User, internal_user: InternalUser, card_info: CardRequestAPISchema):
    check_card_creation_enabled()
    service = _get_active_service()
    permission = UserServicePermission.get_active_permission_by_service(user=user, service=service)
    if not permission:
        raise ServicePermissionNotFound()

    if Card.objects.filter(user=user).exists():
        raise ServiceAlreadyActivated('Service is already activated.')

    if user.user_type < User.USER_TYPES.level2:
        raise UserLevelRestrictionError('User is not level-2')

    limit = UserFinancialServiceLimit.get_user_service_limit(user=user, service=service)
    if not limit.max_limit > 0:
        raise UserLevelRestrictionError('User is restricted to use this service')

    card_request = CardRequestSchema.model_validate(card_info.model_dump(mode='json'))

    with transaction.atomic():
        InternalUser.get_lock(user.pk)
        issue_cost = get_service_issue_cost(service=service)
        if issue_cost > 0:
            transfer_id, transfer_amount = transfer_required_issue_cost(
                user=user,
                internal_user=internal_user,
                transfer_currency=card_info.transfer_currency,
                issue_cost=Decimal(issue_cost),
            )
            card_request.issue_data = CardIssueDataSchema(
                cost=issue_cost,
                transfer_id=transfer_id,
                transfer_currency=card_info.transfer_currency,
                transfer_amount=transfer_amount,
            )
        get_or_create_nobifi_user_service(user=user, internal_user=internal_user, debt=Decimal(issue_cost))
        user_service = UserService.objects.create(
            user=user,
            internal_user=internal_user,
            service=service,
            user_service_permission=permission,
            initial_debt=0,
            current_debt=0,
            status=UserService.STATUS.created,
        )
        card = Card.objects.create(
            user=user,
            internal_user=internal_user,
            user_service=user_service,
            status=Card.STATUS.requested,
            extra_info=card_request.model_dump(mode='json'),
            setting=get_default_card_settings(),
        )

    return card


def get_service_issue_cost(service: Service):
    cost = int(service.options.get('card_issue_cost', 0))
    if cost < 0:
        raise ValueError()
    return cost


def transfer_required_issue_cost(
    user: User, internal_user: InternalUser, transfer_currency: int, issue_cost: Decimal
) -> Tuple[Optional[int], Optional[Decimal]]:
    validate_transaction_is_atomic()
    amount = PricingService(
        user=user, internal_user=internal_user, wallet_type=Service.get_related_wallet_type(Service.TYPES.debit)
    ).get_required_collateral(future_service_amount=issue_cost)
    if amount > 0:
        return _transfer_required_issue_cost_amount(
            user=user,
            transfer_currency=transfer_currency,
            amount_needed=amount,
        )
    return None, None


def _transfer_required_issue_cost_amount(user: User, transfer_currency: int, amount_needed: Decimal):
    if not transfer_currency:
        raise TransferCurrencyRequiredError()

    transfer_amount = Decimal(abs(amount_needed) / PriceProvider(transfer_currency).get_nobitex_price())
    transfer_amount = transfer_amount.quantize(MAX_PRECISION)

    _, transfer_request = WalletService.deposit(
        user=user,
        deposit_input=WalletDepositInput(
            srcType=WalletType.SPOT,
            dstType=_get_wallet_type(Service.get_related_wallet_type(Service.TYPES.debit)),
            transfers=[WalletTransferItem(currency=get_currency_codename(transfer_currency), amount=transfer_amount)],
        ),
    )

    return transfer_request.id, transfer_amount


def _get_wallet_type(wallet_type: Wallet.WalletType) -> WalletType:
    if wallet_type == Wallet.WalletType.DEBIT:
        return WalletType.DEBIT
    return WalletType.COLLATERAL


def get_or_create_nobifi_user_service(user: User, internal_user: InternalUser, debt: Decimal) -> UserService:
    nobifi_service = _get_nobifi_service()
    user_service, _ = UserService.objects.get_or_create(
        user=user,
        internal_user=internal_user,
        service=nobifi_service,
        closed_at=None,
        defaults={
            'user_service_permission': _get_or_create_active_permission(user, internal_user, nobifi_service),
            'initial_debt': debt,
            'current_debt': debt,
            'status': UserService.STATUS.created,
        },
    )
    return user_service


@transaction.atomic
def update_cards_info():
    cards = (
        Card.objects.filter(status__in=(Card.STATUS.registered, Card.STATUS.verified))
        .select_related('user_service', 'user_service__service')
        .select_for_update(of=('self',), no_key=True)
    )
    for card in cards:
        _update_card_info(card)


@transaction.atomic
def _update_card_info(card: Card):
    try:
        dispatcher = api_dispatcher_v2(
            provider=card.user_service.service.provider, service_type=card.user_service.service.tp
        )
        card_detail = dispatcher.get_card(provider_id=card.provider_info['id'])
        if card.status == Card.STATUS.verified and card_detail.status == CardStatus.active:
            _update_card_as_activated(card)
        elif card.status == Card.STATUS.registered and card_detail.status == CardStatus.issued:
            _update_card_as_issued(card)
    except (ThirdPartyError, ValueError, NotImplementedError):
        return


def _update_card_as_activated(card: Card):
    card.status = Card.STATUS.activated
    card.activated_at = ir_now()
    card.save(update_fields=['status', 'activated_at'])
    user_first_name = card.user.first_name if card.user.first_name else 'کاربر'
    notification_provider.send_notif(
        user=card.user,
        message='ضمن عرض تبریک، نوبی‌پی شما با موفقیت فعال شد. هم‌اکنون می‌توانید با دارایی خود از فروشگاه‌های سراسر کشور خرید کنید.',
    )
    notification_provider.send_sms(
        user=card.user,
        text=user_first_name,
        tp=NotificationProvider.MESSAGE_TYPES.abc_debit_card_activated,
        template=UserSms.TEMPLATES.abc_debit_card_activated,
    )


def _update_card_as_issued(card: Card):
    card.status = Card.STATUS.issued
    card.issued_at = ir_now()
    card.save(update_fields=['status', 'issued_at'])
    user_first_name = card.user.first_name if card.user.first_name else 'کاربر'
    notification_provider.send_notif(
        user=card.user,
        message='نوبی‌پی شما با موفقیت صادر شد و در روزهای آینده در آدرسی که تعیین کرده‌اید، به دست شما می‌رسد.',
    )
    notification_provider.send_sms(
        user=card.user,
        text=user_first_name,
        tp=NotificationProvider.MESSAGE_TYPES.abc_debit_card_issued,
        template=UserSms.TEMPLATES.abc_debit_card_issued,
    )


def activate_debit_card(user: User, card_id: int) -> Card:
    if not user.requires_2fa:
        raise UserLevelRestrictionError('User 2FA is not activated.')

    if user.user_type < User.USER_TYPES.level2:
        raise UserLevelRestrictionError('User is not level-2.')

    card = Card.objects.select_for_update(no_key=True).get(user=user, id=card_id)
    if card.status != Card.STATUS.disabled:
        raise CardInvalidStatusError()

    card.status = Card.STATUS.activated
    card.updated_at = ir_now()
    card.save(update_fields=['status', 'updated_at'])
    return card


def disable_debit_card(user: User, card_id: int) -> Card:
    if not user.requires_2fa:
        raise UserLevelRestrictionError('User 2FA is not activated.')

    if user.user_type < User.USER_TYPES.level2:
        raise UserLevelRestrictionError('User is not level-2.')

    card = Card.objects.select_for_update(no_key=True).get(user=user, id=card_id)
    if card.status != Card.STATUS.activated:
        raise CardInvalidStatusError()

    card.status = Card.STATUS.disabled
    card.updated_at = ir_now()
    card.save(update_fields=['status', 'updated_at'])
    return card


@transaction.atomic
def register_debit_cards_in_third_party():
    for card in (
        Card.objects.filter(status__in=[Card.STATUS.issuance_payment_skipped, Card.STATUS.issuance_paid])
        .select_related('user_service__service', 'user')
        .select_for_update(of=('self',), no_key=True)
    ):
        try:
            _register_debit_card(card)
        except Exception:
            report_exception()
            continue


def _register_debit_card(card: Card):
    user = card.user

    card_info = CardRequestSchema.model_validate(card.extra_info)

    if card_info.delivery_address:
        delivery_address = card_info.delivery_address
    else:
        delivery_address = CardDeliveryAddressSchema(
            province=user.province, city=user.city, postal_code=user.postal_code, address=user.address
        )
    user_info = DebitCardUserInfoSchema(
        first_name=user.first_name,
        last_name=user.last_name,
        first_name_en=card_info.first_name,
        last_name_en=card_info.last_name,
        national_code=user.national_code,
        birth_cert_no=card_info.birth_cert_no,
        mobile=user.mobile,
        father_name=user.father_name,
        gender=user.gender,
        birth_date=user.birthday_shamsi,
        postal_code=delivery_address.postal_code,
        province=delivery_address.province,
        city=delivery_address.city,
        address=delivery_address.address,
        color=card_info.color,
    )

    service = card.user_service.service
    card_request_id = api_dispatcher_v2(provider=service.provider, service_type=service.tp).issue_card(
        user_info=user_info
    )

    card.status = Card.STATUS.registered
    card.provider_info.update({'id': card_request_id})
    card.updated_at = ir_now()
    card.save(update_fields=['status', 'updated_at', 'provider_info'])


def request_debit_card_otp(user: User, pan: str):
    if _is_card_otp_is_already_requested_by_user(user, pan):
        raise DuplicateDebitCardRequestByUser()

    if not user.requires_2fa:
        raise UserLevelRestrictionError('User 2FA is not activated.')

    if user.user_type < User.USER_TYPES.level2:
        raise UserLevelRestrictionError('User is not level-2')

    service = _get_service()
    limit = UserFinancialServiceLimit.get_user_service_limit(user=user, service=service)
    if not limit.max_limit > 0:
        raise UserLevelRestrictionError('User is restricted to use this service')

    if not Card.objects.filter(user=user, status=Card.STATUS.issued).exists():
        raise UserServiceNotFoundError('User-Service not found')

    success = api_dispatcher_v2(provider=service.provider, service_type=service.tp).request_otp_code(pan=pan)
    if not success:
        raise ThirdPartyError('failed to request OTP code')

    _set_card_otp_request_log_for_user(user, pan)


def _is_card_otp_is_already_requested_by_user(user: User, pan: str) -> bool:
    key = _get_user_otp_request_on_card_key(user, pan)
    return cache.get(key) is not None


def _set_card_otp_request_log_for_user(user: User, pan: str):
    key = _get_user_otp_request_on_card_key(user, pan)
    cache.set(key, 1, timeout=OTP_EXPIRE_SECONDS)


def _get_user_otp_request_on_card_key(user: User, pan: str) -> str:
    _id = hashlib.sha3_256(f'{user.uid}:{pan}'.encode()).hexdigest()
    return f'abc:debit:otp:request:{_id}'


def verify_debit_card_otp(user: User, pan: str, code: str):
    if not user.requires_2fa:
        raise UserLevelRestrictionError('User 2FA is not activated.')

    if user.user_type < User.USER_TYPES.level2:
        raise UserLevelRestrictionError('User is not level-2')

    service = _get_service()
    limit = UserFinancialServiceLimit.get_user_service_limit(user=user, service=service)
    if not limit.max_limit > 0:
        raise UserLevelRestrictionError('User is restricted to use this service')

    card = Card.objects.filter(user=user, status=Card.STATUS.issued).last()
    if not card:
        raise UserServiceNotFoundError('User-Service not found')

    success = api_dispatcher_v2(provider=service.provider, service_type=service.tp).verify_otp_code(pan=pan, code=code)
    if not success:
        raise ThirdPartyError('failed to verify OTP code')

    card.pan = pan
    card.status = Card.STATUS.verified
    card.updated_at = ir_now()
    card.save(update_fields=['pan', 'status', 'updated_at'])


def get_debit_cards(user: User) -> QuerySet[Card]:
    service = _get_service()
    return Card.objects.filter(user=user, user_service__service=service)


def get_debit_card(user: User, card_id: int) -> Optional[Card]:
    return get_debit_cards(user).get(id=card_id)


def suspend_debit_card(user: User, card_id: int):
    if not user.requires_2fa:
        raise UserLevelRestrictionError('User 2FA is not activated.')

    if user.user_type < User.USER_TYPES.level2:
        raise UserLevelRestrictionError('User is not level-2.')

    try:
        card = Card.objects.select_for_update(no_key=True).get(user=user, id=card_id)
    except Card.DoesNotExist:
        raise CardNotFoundError('card not found.')

    if card.status not in [Card.STATUS.activated, Card.STATUS.disabled]:
        raise CardInvalidStatusError('card is not active or disabled.')

    service = _get_service()
    is_success = api_dispatcher_v2(provider=service.provider, service_type=service.tp).suspend_card(pan=card.pan)
    if is_success:
        card.status = Card.STATUS.suspended
        card.updated_at = ir_now()
        card.save(update_fields=['status', 'updated_at'])
    else:
        raise ThirdPartyError('failed to suspend card.')


def check_card_creation_enabled():
    if not Settings.get_flag('abc_debit_card_creation_enabled', default='yes'):
        raise DebitCardCreationServiceTemporaryUnavailable


def settle_debit_cards_issue_cost():
    for card in Card.objects.filter(status=Card.STATUS.requested):
        _settle_debit_card_issue_cost(card)


def _settle_debit_card_issue_cost(card: Card):
    request_info = CardRequestSchema.model_validate(card.extra_info)
    if not request_info.issue_data or not request_info.issue_data.cost > 0:
        card.status = Card.STATUS.issuance_payment_skipped
        card.save(update_fields=['status'])
        return

    raise NotImplementedError()

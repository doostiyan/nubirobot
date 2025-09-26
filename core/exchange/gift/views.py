import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from ipware import get_client_ip

from exchange.accounts.models import BankAccount, Notification, User, UserSms
from exchange.accounts.userlevels import UserLevelManager
from exchange.accounts.views.auth import check_user_otp, validate_request_captcha
from exchange.base.api import api, email_required_api, public_api, public_post_api
from exchange.base.calendar import ir_now
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.crypto import random_string, random_string_digit
from exchange.base.formatting import f_m
from exchange.base.helpers import get_max_withdraw_amount, get_min_withdraw_amount
from exchange.base.models import RIAL, TAG_NEEDED_CURRENCIES, Currencies, Settings, get_currency_codename
from exchange.base.normalizers import normalize_email, normalize_mobile
from exchange.base.parsers import parse_bool, parse_currency, parse_iso_date, parse_money
from exchange.base.serializers import serialize_currency
from exchange.base.validators import validate_email, validate_mobile, validate_postal_code
from exchange.gift.models import CardDesign, GiftBatchRequest, GiftCard, GiftPackage
from exchange.gift.parsers import parse_gift_redeem, parse_gift_type
from exchange.gift.serializers import serialize_gift_card
from exchange.wallet.models import Wallet, WithdrawRequest, WithdrawRequestPermit


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@api
@email_required_api
def create_gift_batch_request(request):
    """for creating requests of users who want to order many gifts

        POST /gift/create-gift-batch
    """
    user: User = request.user
    gift_batch = GiftBatchRequest.objects.create(
        user=user,
        number=request.g('number'),
        total_amount=parse_money(request.g('total_amount')),
        gift_type=parse_gift_type(request.g('gift_type')),
        password=request.g('password') or '1111',
    )
    otp = random_string_digit(6)
    cache.set(f'gift_batch_otp_{gift_batch.id}', otp, 300)
    UserSms.objects.create(
        user=user,
        tp=UserSms.TYPES.gift,
        to=user.mobile,
        text=f'کد تایید درخواست هدیه‌ی دسته‌ای نوبیتکس شما‌ {otp}',
    )
    return {
        'status': 'ok',
        'batch_id': gift_batch.id,
    }


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@api
def confirm_gift_batch(request):
    """confirming gift batch request by sent otp to user"""
    otp = request.g('otp')
    batch_id = request.g('batch_id')
    if otp != cache.get(f'gift_batch_otp_{batch_id}'):
        return {
            'status': 'failed',
            'code': 'InvalidOTP',
            'message': 'Invalid OTP',
        }
    gift_batch = GiftBatchRequest.objects.get(pk=batch_id)
    gift_batch.status = GiftBatchRequest.BATCH_STATUS.user_confirmed
    gift_batch.save(update_fields=['status'])
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@api
@email_required_api
def create_gift_card(request):
    """first step for creating gift object followed by confirming the initial gift withdraw

            POST /gift/create-gift
    """
    user: User = request.user
    amount = parse_money(request.g('amount'), required=True)
    currency = parse_currency(request.g('currency'), required=True)
    mobile = normalize_mobile(request.g('mobile'))
    email = normalize_email(request.g('email'))
    gift_type = parse_gift_type(request.g('gift_type'), required=True)
    gift_sentence = request.g('gift_sentence') or ''
    receiver_address = request.g('receiver_address')
    receiver_postal_code = request.g('receiver_postal_code') or ''
    receiver_full_name = request.g('receiver_full_name') or ''
    card_design = CardDesign.get_by_title(request.g('card_design'))
    redeem_date = parse_iso_date(request.g('redeem_date'))
    redeem_type = parse_gift_redeem(request.g('redeem_type'), required=True)
    otp_enabled = parse_bool(request.g('otp_enabled'))
    is_sealed = parse_bool(request.g('is_sealed'))
    password = request.g('password') or ''
    otp = request.headers.get('x-totp')

    if card_design is None:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Gift card design is required.'
        }

    if not gift_sentence:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Gift sentence is required.'
        }
    if not password:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Password is required.'
        }
    if not receiver_full_name:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Receivers full name is required.'
        }
    if gift_type == GiftCard.GIFT_TYPES.physical and not (receiver_postal_code and receiver_address):
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'In case of physical gifts address parameters of receiver should be sent.'
        }

    if gift_type == GiftCard.GIFT_TYPES.physical and not validate_postal_code(receiver_postal_code):
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Postal code validation failed'
        }

    if redeem_date < ir_now():
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Can not choose past date for redeem date.'
        }
    if (
        redeem_type == GiftCard.REDEEM_TYPE.lightning and
        gift_type == GiftCard.GIFT_TYPES.physical and
        amount not in settings.GIFT_CARD_PHYSICAL_AMOUNTS
    ):
        return {
            'status': 'failed',
            'code': 'InvalidAmount',
            'message': 'Invalid rial amount for lightning gift with constant rial value.'
        }

    if not validate_mobile(mobile, strict=True):
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Mobile validation failed'
        }

    if not validate_email(email) and gift_type == GiftCard.GIFT_TYPES.digital:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Email validation failed'
        }
    if gift_type == GiftCard.GIFT_TYPES.digital and not email:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Email is required for digital gifts'
        }

    if email == user.email and gift_type == GiftCard.GIFT_TYPES.digital:
        return {
            'status': 'failed',
            'code': 'InvalidRequest',
            'message': 'can not create internal gift for its own creator.',
        }

    if currency == Currencies.ftm:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'با توجه به فرآیند تبدیل توکن FTM به S امکان درخواست کارت هدیه بر روی این توکن مقدور نیست.',
        }

    sender_wallet = Wallet.get_user_wallet(user, currency)
    is_2fa_enabled = user.requires_2fa
    if user.user_type >= User.USER_TYPES.level2 and not sender_wallet.is_rial and not is_2fa_enabled:
        return {
            'status': 'failed',
            'code': 'PleaseEnable2FA',
            'message': 'لطفاً ابتدا شناسایی دوعاملی را برای حساب خود فعال کنید.',
        }
    if is_2fa_enabled and not check_user_otp(otp, user):
        return {'status': 'failed', 'code': 'Invalid2FA', 'message': 'msgInvalid2FA'}

    network = CURRENCY_INFO[currency]['default_network']
    is_restricted = False
    withdraw_permit = None
    if request.user.is_restricted('WithdrawRequest'):
        is_restricted = True
    if sender_wallet.is_rial and request.user.is_restricted('WithdrawRequestRial'):
        is_restricted = True
    if sender_wallet.is_crypto_currency and request.user.is_restricted('WithdrawRequestCoin'):
        is_restricted = True
    if is_restricted:
        withdraw_permit = WithdrawRequestPermit.get(request.user, sender_wallet.currency, amount)
        if not withdraw_permit:
            return {
                'status': 'failed',
                'code': 'WithdrawUnavailable',
                'message': 'WithdrawUnavailable',
            }

    if not UserLevelManager.is_eligible_to_withdraw(user, sender_wallet.currency, amount, network):
        return {'status': 'failed', 'code': 'WithdrawAmountLimitation', 'message': 'WithdrawAmountLimitation'}

    if not WithdrawRequest.check_user_limit(user, sender_wallet.currency):
        return {'status': 'failed', 'code': 'WithdrawLimitReached', 'message': 'msgWithdrawLimitReached'}

    if not (
        CURRENCY_INFO.get(sender_wallet.currency, {}).get('network_list', {}).get(network, {}).get(
            'withdraw_enable', True)
    ):
        return {
            'status': 'failed',
            'code': 'WithdrawCurrencyUnavailable',
            'message': 'WithdrawCurrencyUnavailable'
        }

    currency_name = get_currency_codename(sender_wallet.currency)
    flag_key = 'withdraw_enabled_{}_{}'.format(currency_name, network.lower())
    if not Settings.get_trio_flag(
        flag_key,
        default='yes',  # all network in network_list filter by withdraw_enable=True
        third_option_value=cache.get(f'binance_withdraw_status_{currency_name}_{network}'),
    ):
        return {
            'status': 'failed',
            'code': '{}WithdrawDisabled'.format(currency_name.upper()),
            'message': 'Withdrawals for {} is temporary disabled'.format(currency_name.upper()),
        }
    amount_to_check = amount
    if gift_type == GiftCard.GIFT_TYPES.physical and currency == RIAL:
        amount_to_check += settings.GIFT_CARD_PHYSICAL_FEE
        if is_sealed:
            amount_to_check += settings.GIFT_CARD_SEAL_FEE
    elif gift_type == GiftCard.GIFT_TYPES.physical:
        # check if user rial wallet has the balance needed for physical fee.
        user_rial_wallet = Wallet.get_user_wallet(user, RIAL)
        rial_amount_to_check = settings.GIFT_CARD_PHYSICAL_FEE
        if is_sealed:
            rial_amount_to_check += settings.GIFT_CARD_SEAL_FEE
        if user_rial_wallet.active_balance < rial_amount_to_check:
            return {
                'status': 'failed',
                'code': 'InsufficientRialBalance',
                'message': 'Insufficient rial balance for physical gift fee.'
            }

    if amount_to_check > sender_wallet.active_balance:
        return {'status': 'failed', 'code': 'InsufficientBalance', 'message': 'Insufficient Balance'}

    # Check minimum withdraw amount
    min_withdraw_amount = Decimal(get_min_withdraw_amount(currency))
    if amount < min_withdraw_amount:
        return {'status': 'failed', 'code': 'AmountTooLow', 'message': 'msgAmountTooLow'}

    # Check maximum withdraw amount
    max_withdraw_amount = Decimal(get_max_withdraw_amount(currency))
    if amount > max_withdraw_amount:
        return {'status': 'failed', 'code': 'AmountTooHigh', 'message': 'msgAmountTooHigh'}

    if not user.get_verification_profile().has_verified_mobile_number:
        return {
            'status': 'failed',
            'code': 'InvalidMobileNumber',
            'message': 'Verified mobile number is required for withdraw.',
        }

    ip = get_client_ip(request)
    ip = ip[0] if ip else None
    gift_user = User.get_gift_system_user()
    gift_wallet = Wallet.get_user_wallet(gift_user, currency)

    # physical card transactions, removes from user rial wallet and adds to system gift wallet.
    if gift_type == GiftCard.GIFT_TYPES.physical:
        gift_card_cost = settings.GIFT_CARD_PHYSICAL_FEE
        if is_sealed:
            gift_card_cost += settings.GIFT_CARD_SEAL_FEE
        # cost removal transaction
        physical_cost_removal_transaction = Wallet.get_user_wallet(user, RIAL).create_transaction(
            amount=-gift_card_cost,
            description=f'User-{user.id}, physical gift cost transaction.',
            tp='manual',
        )
        if physical_cost_removal_transaction is None:
            return {
                'status': 'failed',
                'code': 'InsufficientBalance',
                'message': 'Insufficient rial balance for physical card cost.',
            }
        physical_cost_removal_transaction.commit()
        # cost transaction for system gift user.
        physical_cost_addition_for_system_gift_transaction = Wallet.get_user_wallet(gift_user, RIAL).create_transaction(
            amount=gift_card_cost,
            description=f'Gift account transaction for user-{user.id} physical gift cost.',
            tp='manual',
        )
        physical_cost_addition_for_system_gift_transaction.commit()

    address_params = {}
    bank_account = None
    if currency == RIAL:
        bank_account = get_object_or_404(
            BankAccount, user=gift_user,
            confirmed=True, is_deleted=False, is_temporary=False)
        address_params['target_address'] = bank_account.display_name
    elif currency in TAG_NEEDED_CURRENCIES:
        gift_wallet_tag = gift_wallet.get_current_deposit_tag(create=True)
        if isinstance(gift_wallet_tag, int):
            address_params['tag'] = gift_wallet_tag
        else:
            address_params['tag'] = gift_wallet_tag.tag
        gift_wallet_address = gift_wallet.get_current_deposit_address(create=True)
        if isinstance(gift_wallet_address, str):
            address_params['target_address'] = gift_wallet_address
        else:
            address_params['target_address'] = gift_wallet_address.address
    else:
        gift_wallet_address = gift_wallet.get_current_deposit_address(create=True)
        if isinstance(gift_wallet_address, str):
            address_params['target_address'] = gift_wallet_address
        else:
            address_params['target_address'] = gift_wallet_address.address
    initial_user_withdraw = WithdrawRequest.objects.create(
        tp=WithdrawRequest.TYPE.internal,
        wallet=sender_wallet,
        amount=amount,
        explanations='بابت صدور کارت هدیه',
        ip=ip,
        target_account=bank_account,
        network=network,
        **address_params,
    )

    if withdraw_permit:
        withdraw_permit.is_active = False
        withdraw_permit.withdraw_request = initial_user_withdraw
        withdraw_permit.save(update_fields=['is_active', 'withdraw_request'])

    gift_card = GiftCard.objects.create(
        gift_type=gift_type,
        amount=amount,
        sender=user,
        gift_sentence=gift_sentence,
        currency=currency,
        address=receiver_address,
        full_name=receiver_full_name,
        password=make_password(password),
        postal_code=receiver_postal_code,
        receiver_email=email,
        mobile=mobile,
        redeem_date=redeem_date,
        redeem_type=redeem_type,
        card_design=card_design,
        redeem_code=random_string(32).upper(),
        initial_withdraw=initial_user_withdraw,
        otp_enabled=otp_enabled,
        is_sealed=is_sealed,
    )

    Notification.notify_admins(
        f'Gift Card with initial withdraw {initial_user_withdraw.id} and amount {f_m(amount)}'
        f' with sender user {user.email} and currency {gift_card.get_currency_display()}, with redeem type of '
        f'{gift_card.get_redeem_type_display()} and gift type of {gift_card.get_gift_type_display()}'
        f', has been created.',
        title='ایجاد هدیه'
    )

    return {
        'status': 'ok',
        'gift_withdraw_id': initial_user_withdraw.id,
        'cost': gift_card.cost,
    }


def redeem_ratelimit(group, request):
    """ Ratelimit checker for redeem landing. Used for increasing ratelimit for testnet.
    """
    return '10/30m' if settings.IS_PROD else '60/30m'


@ratelimit(key='user_or_ip', rate=redeem_ratelimit, block=True)
@public_api
def redeem_landing(request, code):
    """returns information about a gift object of the given redeem code

            GET /gift/<str:code>
    """
    if len(code) != 32:
        return {
            'status': 'failed',
            'code': 'InvalidRedeemCode',
            'message': 'Invalid Redeem Code',
        }
    gift_card = get_object_or_404(GiftCard, redeem_code=code)
    if gift_card.mobile is not None and gift_card.otp_enabled:
        otp = random_string_digit(6)
        cache.set(f'gift_otp_{gift_card.id}', otp, 300)
        gift_user = User.get_gift_system_user()
        UserSms.objects.create(
            user=gift_user,
            tp=UserSms.TYPES.gift,
            to=gift_card.mobile,
            text=otp,
            template=UserSms.TEMPLATES.gift_redeem_otp,
        )
    return {
        'redeem_code': gift_card.redeem_code,
        'card_design': gift_card.card_design.title,
        'currency': serialize_currency(gift_card.currency),
        'amount': gift_card.amount,
        'mobile_provided': gift_card.otp_enabled,
        'sentence': gift_card.gift_sentence,
        'redeem_type': gift_card.get_redeem_type_display(),
    }


@ratelimit(key='user_or_ip', rate=redeem_ratelimit, block=True)
@api
def redeem_logged_in_user_gift_card(request):
    """Redeem gift cards for logged in users whether the gift type is lightning or internal

        POST /gift/redeem
    """
    if not validate_request_captcha(request):
        return {
            'status': 'failed',
            'code': 'InvalidCaptcha',
            'message': 'کپچا به درستی تایید نشده'
        }

    user = request.user
    redeem_code = request.g('redeem_code')
    gift_password = request.g('password')
    otp = request.g('otp')
    gift_card = get_object_or_404(GiftCard, redeem_code=redeem_code)
    cache_key = f'gift_otp_{gift_card.id}'
    if settings.IS_PROD:
        if gift_card.mobile is not None and otp != cache.get(cache_key):
            return {
                'status': 'failed',
                'code': 'InvalidOTP',
                'message': 'Invalid OTP',
            }

    if not check_password(gift_password, gift_card.password):
        return {
            'status': 'failed',
            'code': 'InvalidPassword',
            'message': 'Invalid Password',
        }

    if gift_card.gift_status == GiftCard.GIFT_STATUS.canceled:
        return {
            'status': 'failed',
            'code': 'CardIsCanceled',
            'message': 'Gift card is canceled.',
        }
    if gift_card.is_internal and gift_card.gift_status not in GiftCard.REDEEMABLE_STATUSES:
        return {
            'status': 'failed',
            'code': 'AlreadyRedeemedOrCanceled',
            'message': 'Gift already redeemed.',
        }

    if gift_card.is_redeemed and gift_card.is_lightning:
        return {
            'status': 'ok',
            'lnUrl': gift_card.lnurl,
        }

    cache.delete(cache_key)
    lnurl, err = gift_card.redeem_lnurl(user)
    if err:
        return {
            'status': 'failed',
            'code': err,
            'message': err,
        }
    # Redeem successful
    if gift_card.is_lightning:
        return {
            'status': 'ok',
            'lnUrl': lnurl,
        }
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate=redeem_ratelimit, block=True)
@public_post_api
def public_redeem_lightning_gift_card(request):
    """redeems the lightning gifts in cases which users aren't nobitex users

        POST /gift/redeem-lightning
    """
    if not validate_request_captcha(request):
        return {
            'status': 'failed',
            'code': 'InvalidCaptcha',
            'message': 'کپچا به درستی تایید نشده'
        }

    redeem_code = request.g('redeem_code')
    gift_password = request.g('password')
    otp = request.g('otp')
    gift_card = get_object_or_404(GiftCard, redeem_code=redeem_code)
    cache_key = f'gift_otp_{gift_card.id}'
    if settings.IS_PROD:
        if gift_card.mobile is not None and otp != cache.get(cache_key):
            return {
                'status': 'failed',
                'code': 'InvalidOTP',
                'message': 'Invalid OTP',
            }

    if not check_password(gift_password, gift_card.password):
        return {
            'status': 'failed',
            'code': 'InvalidPassword',
            'message': 'Invalid Password',
        }

    if gift_card.gift_status == GiftCard.GIFT_STATUS.canceled:
        return {
            'status': 'failed',
            'code': 'CardIsCanceled',
            'message': 'Gift card is canceled.',
        }

    if not gift_card.is_lightning:
        return {
            'status': 'failed',
            'code': 'InvalidRequest',
            'message': 'Wrong endpoint called.',
        }

    cache.delete(cache_key)
    if gift_card.is_redeemed:
        return {
            'status': 'ok',
            'lnUrl': gift_card.lnurl,
        }

    lnurl, err = gift_card.redeem_lnurl()
    if err:
        return {
            'status': 'failed',
            'code': err,
            'message': err,
        }
    return {
        'status': 'ok',
        'lnUrl': lnurl,
    }


@ratelimit(key='user_or_ip', rate='5/30m', block=True)
@public_post_api
def resend_gift_otp(request):
    """resend gift redeem otp and caches it

        POST /gift/resend-gift-otp
    """
    gift = get_object_or_404(GiftCard, redeem_code=request.g('redeem_code'))
    if gift.mobile is None:
        return {
            'status': 'failed',
            'code': 'MobileNotProvided',
            'message': 'Gift does not have receiver mobile'
        }

    if UserSms.objects.filter(
        tp=UserSms.TYPES.gift, to=gift.mobile, created_at__gte=ir_now() - datetime.timedelta(hours=12),
    ).count() > 7:
        return {
            'status': 'failed',
            'code': 'TooManyRequests',
            'message': 'Excessive otps sent to user over past day.'
        }
    cache_key = f'gift_otp_{gift.id}'
    cache.delete(cache_key)
    otp = random_string_digit(6)
    cache.set(cache_key, otp, 300)
    gift_user = User.get_gift_system_user()
    UserSms.objects.create(
        user=gift_user,
        tp=UserSms.TYPES.gift,
        to=gift.mobile,
        text=otp,
        template=UserSms.TEMPLATES.gift_redeem_otp,
    )

    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@api
def user_gift_cards_list(request):
    """returns user's received and sent gifts
        GET /gift/user-gifts
    """
    user = request.user
    user_gifts = GiftCard.objects.select_related(
        'sender',
        'receiver',
    ).filter(
        Q(receiver=user) | Q(sender=user),
    ).exclude(gift_status__in=[GiftCard.GIFT_STATUS.canceled, GiftCard.GIFT_STATUS.new,  GiftCard.GIFT_STATUS.closed])\
        .order_by('-created_at')

    user_serialized_sent_gift_cards = [serialize_gift_card(user_gift) for user_gift in user_gifts if
                                       user_gift.sender_id == user.id]
    user_serialized_received_gift_cards = [serialize_gift_card(user_gift) for user_gift in
                                           user_gifts if user_gift.receiver_id == user.id]
    return {
        'status': 'ok',
        'sent_gift_cards': user_serialized_sent_gift_cards,
        'received_gift_cards': user_serialized_received_gift_cards,
    }


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@api
def gift_packages_list(request):
    return {
        'status': 'ok',
        'giftPackages': GiftPackage.objects.prefetch_related('images').all()
    }

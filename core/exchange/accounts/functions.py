import json
from typing import Dict, List, Optional, T, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django_otp.plugins.otp_totp.models import TOTPDevice
from ipware import get_client_ip
from rest_framework.authtoken.models import Token
from tqdm import tqdm

from exchange.accounts.captcha import CaptchaHandler
from exchange.accounts.constants import DEFAULT_CAPTCHA_USAGE_CONFIGS_V2
from exchange.accounts.models import BankAccount, User
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.coins_info_old import CURRENCY_INFO as OLD_CURRENCY_INFO
from exchange.base.http import get_client_country
from exchange.base.logging import report_event, report_exception
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.base.normalizers import normalize_mobile
from exchange.base.serializers import serialize, show_pseudo_networks_as_network
from exchange.base.validators import validate_email, validate_mobile
from exchange.blockchain.contracts_conf import CONTRACT_INFO
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.celery import app
from exchange.wallet.models import Wallet


def config_user_in_test_net(user) -> None:
    if not settings.IS_TESTNET:
        return
    user.user_type = user.USER_TYPES.level1
    user.save(update_fields=['user_type'])
    wallet = Wallet.get_user_wallet(user, Currencies.rls)
    tr = wallet.create_transaction(
        tp='manual',
        amount=5_000_000_0,
        description='شارژ اعتبار مجازی حساب تست‌نت جهت استفاده در شبیه‌ساز',
    )
    tr.commit()


def find_username(submitted_username: str) -> Tuple[str, Optional[str]]:
    username = submitted_username
    if Settings.get_flag('mobile_login') and validate_mobile(username):
        mobile_users = User.objects.filter(mobile=normalize_mobile(username.strip())).values('username')
        if not len(mobile_users) == 1:
            return submitted_username, 'NotExactlyOneUserWithGivenPhoneNumber'
        username = mobile_users[0]['username']
    elif validate_email(username):
        email_user = User.objects.filter(email=username).values('username').first()
        if email_user is None:
            return username, 'NoUserWithGivenEmail'
        username = email_user['username']
    return username, None


def check_user_otp(otp, user, only_confirmed=True) -> bool:
    if not user:
        return False
    user.otp_device = None
    if not otp or not user.is_authenticated:
        return False
    otp_device = TOTPDevice.objects.filter(user=user)
    if only_confirmed:
        otp_device = otp_device.filter(confirmed=True)
    otp_device = otp_device.last()
    if not otp_device:
        return False
    if not otp_device.verify_token(otp):
        return False
    user.otp_device = otp_device
    return True


def validate_request_captcha(request, check_type=False, using_cache=False) -> bool:
    country = get_client_country(request)
    ip = get_client_ip(request)
    ip = ip[0] if ip else '0.0.0.0'
    captcha_type = request.data.get('captchaType', request.data.get('client', 'web'))
    if captcha_type == 'android':
        captcha_type = 'recaptcha'
    elif captcha_type in ('iOS', 'web'):
        captcha_type = 'django-captcha'

    client_type = 'web' if request.data.get('client', 'web') == 'web' else 'android'
    mobile = request.data.get('mobile')
    extra_data = {'mobile': mobile} if using_cache else None

    country_key = 'IR' if country == 'IR' else 'NON_IR'
    captcha_usage_configs = Settings.get_cached_json('captcha_usage_configs_v2', DEFAULT_CAPTCHA_USAGE_CONFIGS_V2)[
        country_key
    ]

    # Find usage by route
    usage = None
    for _usage, value in captcha_usage_configs.items():
        if _usage != 'default' and value['route'] in request.path:
            usage = _usage
            break

    handler = CaptchaHandler(
        country=country,
        check_type=check_type,
        ip=ip,
        client=client_type,
        captcha_type=captcha_type,
        captcha_key=request.data.get('captcha'),
        key=request.data.get('key'),
        extra_data=extra_data,
        usage=usage,
        url_path=request.path,
    )
    return handler.verify(using_cache=using_cache)


def get_options_v1() -> Dict[str, T]:
    options = serialize(settings.NOBITEX_OPTIONS, opts={'decimalAsFloat': True})
    # Also provide coin-named keys
    for opt in options['perCurrencyOptions']:
        ks = list(options[opt])
        for k in ks:
            currency_name = get_currency_codename(k)
            if not currency_name:
                continue
            # Override for dynamic coin options
            if opt == 'withdrawFees':
                default_network = CURRENCY_INFO[k]['default_network']
                default_value = CURRENCY_INFO[k]['network_list'][default_network]['withdraw_fee']
                override_value = Settings.get(f'withdraw_fee_{currency_name}_{default_network.lower()}', default=default_value)
                if override_value:
                    if override_value.endswith('%'):
                        options[opt][k] = override_value
                    else:
                        options[opt][k] = float(override_value)
            if opt == 'maxWithdraws':
                default_network = CURRENCY_INFO[k]['default_network']
                default_value = CURRENCY_INFO[k]['network_list'][default_network]['withdraw_max']
                override_value = Settings.get(
                    f'withdraw_max_{currency_name}_{default_network.lower()}', default=default_value
                )
                if override_value:
                    options[opt][k] = override_value
            if opt == 'minWithdraws':
                default_network = CURRENCY_INFO[k]['default_network']
                default_value = CURRENCY_INFO[k]['network_list'][default_network]['withdraw_min']
                override_value = Settings.get(
                    f'withdraw_min_{currency_name}_{default_network.lower()}', default=default_value
                )
                if override_value:
                    options[opt][k] = float(override_value)
            # Set currency-named key
            options[opt][currency_name] = options[opt][k]
    return options


def get_options_v2(new_version=False, set_db_defaults=True) -> Dict[str, T]:
    """Return serialized coins info, with dynamic updates from
        Settings in DB.

        Queries: Up to twice the number of networks.
    """
    options = serialize(
        show_pseudo_networks_as_network(CURRENCY_INFO) if new_version else OLD_CURRENCY_INFO,
        opts={'decimalAsFloat': True},
        ignore_keys=['launch_date', 'promote_date', 'contract_addresses'],
        convert_to_camelcase=True,
    )

    binance_withdraw_keys = set()
    binance_deposit_keys = set()

    for currency_info in options.values():
        currency_codename = currency_info['coin']
        for network, _ in currency_info['networkList'].items():
            binance_withdraw_keys.add(f'binance_withdraw_status_{currency_codename}_{network}')
            binance_deposit_keys.add(f'binance_deposit_status_{currency_codename}_{network}')

    binance_withdraw_status = cache.get_many(binance_withdraw_keys)
    binance_deposit_status = cache.get_many(binance_deposit_keys)

    for currency_info in options.values():
        currency_codename = currency_info['coin']
        for network, network_info in currency_info['networkList'].items():
            # Override fee parameter
            network_cache = network
            if network_cache in CurrenciesNetworkName.get_pseudo_network_names():
                _, network_cache = CurrenciesNetworkName.parse_pseudo_network(getattr(Currencies, currency_codename), network_cache)
            withdraw_fee_cache_key = f'withdraw_fee_{currency_codename}_{network_cache.lower()}'
            withdraw_max_cache_key = f'withdraw_max_{currency_codename}_{network_cache.lower()}'
            withdraw_min_cache_key = f'withdraw_min_{currency_codename}_{network_cache.lower()}'
            withdraw_enabled_cache_key = f'withdraw_enabled_{currency_codename}_{network_cache.lower()}'
            deposit_enabled_cache_key = f'deposit_enabled_{currency_codename}_{network_cache.lower()}'
            if CurrenciesNetworkName.is_pseudo_network(network):
                c_address, _ = CurrenciesNetworkName.parse_pseudo_network(getattr(Currencies, currency_codename), network)
                withdraw_fee_cache_key += f'_{c_address}'
                withdraw_max_cache_key += f'_{c_address}'
                withdraw_min_cache_key += f'_{c_address}'
                withdraw_enabled_cache_key += f'_{c_address}'
                deposit_enabled_cache_key += f'_{c_address}'

            network_info['withdrawFee'] = Settings.get(
                withdraw_fee_cache_key,
                default=network_info['withdrawFee'] if set_db_defaults else None,
            ) or network_info['withdrawFee']
            network_info['withdrawMax'] = (
                Settings.get(
                    withdraw_max_cache_key,
                    default=network_info['withdrawMax'] if set_db_defaults else None,
                )
                or network_info['withdrawMax']
            )
            network_info['withdrawMin'] = (
                Settings.get(
                    withdraw_min_cache_key,
                    default=network_info['withdrawMin'] if set_db_defaults else None,
                )
                or network_info['withdrawMin']
            )
            # Override withdraw status parameter
            default_withdraw_status = 'yes' if network_info.get('withdrawEnable', True) else 'no'
            network_info['withdrawEnable'] = Settings.get_trio_flag(
                withdraw_enabled_cache_key,
                default=default_withdraw_status,
                third_option_value=binance_withdraw_status.get(
                    f'binance_withdraw_status_{currency_codename}_{network}'
                ),
            )
            # Override deposit status parameter
            default_deposit_status = 'yes' if network_info.get('depositEnable', True) else 'no'
            network_info['depositEnable'] = Settings.get_trio_flag(
                deposit_enabled_cache_key,
                default=default_deposit_status,
                third_option_value=binance_deposit_status.get(f'binance_deposit_status_{currency_codename}_{network}'),
            )
            network_contract_info = CONTRACT_INFO.get(network, {}).get('mainnet') or {}
            currency_contract_info = network_contract_info.get(getattr(Currencies, currency_codename))
            if currency_contract_info:
                contract_address = currency_contract_info.get('address')
                if contract_address:
                    network_info['contractAddress'] = contract_address
    return options


def get_text_level_features(user_type: int, mobile_identity_confirmed: bool) -> List[str]:
    features = ['واریز ریالی روزانه تا سقف 25 میلیون تومان']
    features.extend(
        {
            User.USER_TYPES.level1: [
                'برداشت ریالی روزانه تا سقف 50 میلیون تومان',
                'واریز رمزارزی روزانه به میزان نامحدود',
            ],
            User.USER_TYPES.level2: [
                'برداشت ریالی روزانه تا سقف 300 میلیون تومان',
                'واریز رمزارزی روزانه به میزان نامحدود',
                f'برداشت رمزارزی روزانه به میزان {300 if mobile_identity_confirmed else 10} میلیون تومان',
            ],
            User.USER_TYPES.verified: [
                'واریز رمزارزی روزانه به میزان نامحدود',
                'برداشت رمزارزی و ریالی روزانه تا سقف ۱ میلیارد تومان',
            ],
        }[user_type],
    )
    if user_type == User.USER_TYPES.level1 and mobile_identity_confirmed:
        features.append('برداشت رمزارزی روزانه به میزان 1 میلیون تومان')
    features.append('امکان استفاده از تمامی ویژگی های محصول نوبیتکس')
    return features


def create_bank_account(
    user: User,
    shaba_number: str,
    deposit: str,
    owner_name: str,
    status: bool,
    confirmed: bool,
    api_verification: json,
    is_from_bank_card: bool,
    *,
    save=True,
) -> Optional[BankAccount]:
    account = BankAccount(
        user=user,
        account_number=deposit or "0",
        shaba_number=shaba_number,
        bank_name="سایر",
        owner_name=owner_name,
        status=status,
        confirmed=confirmed,
        api_verification=api_verification,
        is_from_bank_card=is_from_bank_card,
    )
    if not account.is_valid():
        report_event("IBANValidationError", extras={"src": "CreateBankAccount", "iban": shaba_number})
        return None
    if save:
        account.save()
    return account


def expire_user_token(user: User):
    token = Token.objects.filter(user=user).first()
    if token is not None:
        token.delete()


def hide_email_address(email: str) -> str:
    username, domain = email.split('@')
    if len(username) > 3:
        return username[:3] + '***@' + domain
    return username[:1] + '***@' + domain


def hide_mobile_number(mobile: str) -> str:
    return mobile[:4] + '***' + mobile[-4:]


def get_bank_info_cache_key(user_pk: int) -> str:
    return 'user_{}_bank_info'.format(user_pk)


def revoke_sms_tasks_by_template(templates: str):
    """
    Revokes the celery tasks which are pending to send sms messages of a template in 'templates'
    :param templates: either 'all' or a comma separated list of templates e.g. 'verify_new_address,welcome,kyc_update'
    """
    from exchange.accounts.models import UserSms

    if templates == 'all':
        templates = [template for template in UserSms.TEMPLATES._identifier_map]
        query_conditions = ~Q(delivery_status__contains='Sent') | Q(delivery_status__isnull=True)
    else:
        templates = [template for template in templates.split(',') if template in UserSms.TEMPLATES._identifier_map]
        template_choices = [UserSms.TEMPLATES._identifier_map[template] for template in templates]
        query_conditions = Q(template__in=template_choices) & (
            ~Q(delivery_status__contains='Sent') | Q(delivery_status__isnull=True)
        )
    if not templates:
        raise Exception(
            'Unacceptable list of template, the input template must be either all or a comma separated list of:\n'
            + '\n'.join(template_name for template_name in UserSms.TEMPLATES._identifier_map)
        )

    try:
        sms_ids_by_template = UserSms.objects.filter(query_conditions).values_list('pk', flat=True)
        cache_keys = [UserSms.TASK_ID_CACHE_KEY.format(sms_id=sms_id) for sms_id in sms_ids_by_template]
        task_ids = cache.get_many(cache_keys)
        result = []
        for sms_id in tqdm(task_ids):
            try:
                task_result = app.AsyncResult(task_ids[sms_id])
                task_result.revoke()
                result.append((sms_id, task_ids[sms_id]))
            except Exception:
                pass
        return result, templates

    except Exception as e:
        report_exception()
        raise e

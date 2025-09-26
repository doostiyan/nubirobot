import re

from model_utils import Choices

PROVINCES = [
    'آذربایجان شرقی',
    'آذربایجان غربی',
    'اردبیل',
    'اصفهان',
    'البرز',
    'ایلام',
    'بوشهر',
    'تهران',
    'چهارمحال و بختیاری',
    'خراسان جنوبی',
    'خراسان رضوی',
    'خراسان شمالی',
    'خوزستان',
    'زنجان',
    'سمنان',
    'سیستان و بلوچستان',
    'فارس',
    'قزوین',
    'قم',
    'کردستان',
    'کرمان',
    'کرمانشاه',
    'کهگیلویه و بویراحمد',
    'گلستان',
    'گیلان',
    'لرستان',
    'مازندران',
    'مرکزی',
    'هرمزگان',
    'همدان',
    'یزد',
    'خارج از کشور',
]

PROVINCE_PHONE_CODES = [
    '041',
    '044',
    '045',
    '031',
    '026',
    '084',
    '077',
    '021',
    '038',
    '056',
    '051',
    '058',
    '061',
    '024',
    '023',
    '054',
    '071',
    '028',
    '025',
    '087',
    '034',
    '083',
    '074',
    '017',
    '013',
    '066',
    '011',
    '086',
    '076',
    '081',
    '035',
    '0',
]

company_tags = {
    'company_tag': 'شرکتی',
    'financial_tag': 'حساب شرکتی- در انتظار مالی',
    'lead_tag': 'حساب شرکتی- در انتظار تایید نهایی',
    'end_tag': 'حساب شرکتی-اتمام ارزیابی',
}

auto_tags = {
    'open_identity': 'هویت باز',
    'open_bank': 'اطلاعات بانکی باز',
    'open_selfie': 'عکس احراز باز',
    'open_address': 'آدرس باز',
    'open_mobile': 'موبایل باز',
    'open_all': 'وضعیت باز ندارد'
}

new_tags = {
    'incomplete_documents': 'مدارک تکمیلی'
}

SYSTEM_USER_IDS = Choices(
    (988, 'system_pool_profit', 'System Pool Profit Collector'),
    (989, 'system_fix', 'System Fix'),
    (990, 'system_abc_insurance_fund', 'ABC Insurance Fund'),
    (991, 'system_convert', 'System Convert (aka: Xchange)'),
    (992, 'system_vip_credit', 'System Vip Credit'),
    (993, 'system_staking_rewards', 'System Staking Reward Collector'),
    (994, 'system_staking_fee', 'System Staking Fee Collector'),
    (995, 'system_staking', 'System Staking'),
    (996, 'system_position_fee', 'System Position Fee Collector'),
    (997, 'system_gift', 'System Gift'),
    (998, 'system_withdraw', 'System Withdraw'),
    (999, 'system_fee', 'System Fee Collector'),
)


DEFAULT_CAPTCHA_USAGE_CONFIGS = {
    'default': {'route': '', 'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']},
    'forget-password': {
        'route': 'auth/forget-password',
        'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
    },
}

DEFAULT_CAPTCHA_USAGE_CONFIGS_V2 = {
    'IR': {
        'default': {'route': '', 'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']},
        'forget-password': {
            'route': 'auth/forget-password',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
        'forget-password-commit': {
            'route': 'auth/forget-password-commit',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
        'login': {
            'route': 'auth/login/',
            'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha'],
        },
        'change-mobile': {
            'route': 'users/profile-edit',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
    },
    'NON_IR': {
        'default': {'route': '', 'types': ['django-captcha', 'arcaptcha', 'recaptcha', 'hcaptcha']},
        'forget-password': {
            'route': 'auth/forget-password',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
        'forget-password-commit': {
            'route': 'auth/forget-password-commit',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
        'login': {
            'route': 'auth/login/',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
        'change-mobile': {
            'route': 'users/profile-edit',
            'types': ['arcaptcha', 'recaptcha', 'hcaptcha'],
        },
    },
}

RESTRICTION_REMOVAL_INTERVAL_MINUTES = 15
ACCOUNT_NUMBER_PATTERN = r'^[\d\-.]+$'
ACCOUNT_NUMBER_PATTERN_RE = re.compile(ACCOUNT_NUMBER_PATTERN)

SYSTEM_USER_IDS_CACHE_TIMEOUT = 5 * 60

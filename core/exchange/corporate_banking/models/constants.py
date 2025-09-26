from model_utils import Choices

from exchange.accounts.models import BaseBankAccount

NOBITEX_BANK_CHOICES = BaseBankAccount.BANK_ID
BANK_ID_TO_ENGLISH_NAME = {value: key for (key, value) in NOBITEX_BANK_CHOICES._identifier_map.items()}
JIBIT_BANKS = Choices(
    (0, 'MARKAZI', 'مرکزی'),
    (1, 'SHAHR', 'شهر'),
    (2, 'MELI', 'ملی'),
    (3, 'MELLAT', 'ملت'),
    (4, 'TEJARAT', 'تجارت'),
    (5, 'KESHAVARZI', 'کشاورزی'),
    (6, 'REFAH', 'رفاه'),
    (7, 'PASARGAD', 'پاسارگاد'),
    (8, 'SEPAH', 'سپه'),
    (9, 'SADERAT', 'صادرات ایران'),
    (10, 'RESALAT', 'رسالت'),
    (13, 'AYANDEH', 'آینده'),
    (14, 'MASKAN', 'مسکن'),
    (15, 'SAMAN', 'سامان'),
    (18, 'PARSIAN', 'پارسیان'),
    (19, 'SANAT_VA_MADAN', 'صنعت و معدن'),
    (20, 'TOSEAH_SADERAT', 'توسعه صادرات ایران'),
    (21, 'POST', 'پست ایران'),
    (22, 'TOSEAH_TAAVON', 'توسعه تعاون'),
    (23, 'TOSEAH', 'توسعه'),
    (24, 'GHAVAMIN', 'قوامین'),
    (25, 'KARAFARIN', 'کارآفرین'),
    (26, 'EGHTESADE_NOVIN', 'اقتصاد نوین'),
    (27, 'SARMAIEH', 'سرمایه'),
    (28, 'SINA', 'سینا'),
    (29, 'MEHR_IRANIAN', 'مهر ایرانیان'),
    (30, 'ANSAR', 'انصار'),
    (31, 'GARDESHGARI', 'گردشگری'),
    (32, 'HEKMAT_IRANIAN', 'حکمت ایرانیان'),
    (33, 'DEY', 'دی'),
    (34, 'IRANZAMIN', 'ایران زمین'),
    (35, 'MELAL', 'ملل'),
    (36, 'KAVARMIANEH', 'تعاون منطقه‌ای اسلامی'),
    (37, 'KOSAR', 'کوثر'),
    (38, 'NOOR', 'نور'),
    (39, 'IRAN_VENEZOELA', 'ایران و ونزوئلا'),
    (40, 'MEHR_EGHTESAD', 'مهر اقتصاد'),
    (41, 'UNKNOWN', 'نامشخص'),
)

TOMAN_BANKS = Choices(
    (1, 'Shahr', 'شهر'),
    (2, 'Melli', 'ملی'),
    (3, 'Mellat', 'ملت'),
    (4, 'Tejarat', 'تجارت'),
    (5, 'Keshavarzi', 'کشاورزی'),
    (6, 'RefahKargaran', 'رفاه کارگران'),
    (7, 'Pasargad', 'پاسارگاد'),
    (8, 'Sepah', 'سپه'),
    (9, 'Saderat', 'صادرات'),
    (10, 'Resalat', 'رسالت'),
    (13, 'Ayande', 'آینده'),
    (14, 'Maskan', 'مسکن'),
    (15, 'Saman', 'سامان'),
    (18, 'Parsian', 'پارسیان'),
)

COBANK_PROVIDER = Choices(
    (0, 'toman', 'Toman'),
    (1, 'jibit', 'Jibit'),
    (2, 'vandar', 'Vandar'),  # Not implemented yet
)

COBANK_PROVIDER_MAPPING = {id_: name for id_, name in COBANK_PROVIDER if name != 'vandar'}

TRANSFER_MODE = Choices(
    (1, 'inter_bank', 'بین بانکی'),
    (2, 'intra_bank', 'درون بانکی'),  # e.g. user should only deposit to Melli bank from a Melli bank account
)


ACCOUNT_TP = Choices(
    (1, 'operational', 'عملیاتی برای واریز'),
    (2, 'storage', 'مخزن برای برداشت'),
)


STATEMENT_TYPE = Choices(
    (1, 'deposit', 'واریز'),
    (2, 'withdraw', 'برداشت'),
    (3, 'unknown', 'نامشخص'),
)


STATEMENT_STATUS = Choices(
    (1, 'new', 'New'),
    (2, 'validated', 'Validated'),
    (3, 'executed', 'Executed'),
    (4, 'rejected', 'Rejected'),
    (5, 'pending_admin', 'Pending admin considerations'),
    (6, 'refunded', 'Refunded after being rejected'),
)


REJECTION_REASONS = Choices(
    (1, 'ineligible_user', 'User not eligible for cobank'),
    (2, 'source_account_not_found', 'Source bank account not found'),
    (3, 'shared_source_account', 'Source account belongs to more than one users'),
    (4, 'other', 'Other'),
    (5, 'user_not_found', 'Could not find the user'),
    (6, 'unacceptable_amount', 'Invalid amount'),
    (7, 'no_feature_flag', 'Feature flag not found'),
    (8, 'empty_source_account', 'Source account is empty'),
    (9, 'repeated_reference_code', 'Possible double spend: repeated reference code'),
    (10, 'old_transaction', 'Possible double spend: old transaction date'),
)


REFUND_STATUS = Choices(
    (1, 'new', 'New'),
    (2, 'invalid', 'Invalid'),
    (3, 'sent_to_provider', 'Request sent to provider'),
    (4, 'pending', 'Pending on provider side'),
    (5, 'completed', 'Executed by provider'),
    (6, 'unknown', 'Unknown'),
)

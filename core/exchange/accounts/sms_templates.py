import re

from model_utils import Choices

OLD_SMSIR_TO_NEW_SMSIR_TEMPLATE_CONVERTOR_MAP = {
    3065: 941168,
    6816: 515128,
    51443: 913046,
    51444: 782513,
    54043: 613445,
    55503: 326631,
    63653: 465294,
    68559: 219762,
    70745: 882218,
    72801: 881914,
    72802: 588339,
    75172: 871730,
    77174: 601380,
    77370: 244683,
    77398: 125972,
    77406: 724865,
    77411: 888982,
    77788: 567634,
    77789: 342009,
    77836: 842236,
    78073: 652978,
    78074: 276816,
    78075: 899697,
    80109: 417498,
    80531: 726355,
    80532: 380519,
    80533: 798866,
    81281: 850890,
    81282: 436165,
    81283: 151167,
    81287: 898144,
    81848: 223008,
    82252: 820242,
    82618: 402384,
    83413: 733680,
    83414: 805876,
    83918: 104139,
}

OLD_SMSIR_TO_KAVENEGAR_TEMPLATE_CONVERTOR_MAP = {
    6816: 'Welcome',
    3065: 'Verification',
    54043: 'TfaEnable',
    51443: 'TfaDisable',
    55503: 'KycUpdate',
    63653: 'GiftRedeemOtp',
    68559: 'NewDeviceWithdrawalRestrictionNotif',
    70745: 'GenericChangeNotif',
    72801: 'Withdraw',
    51444: 'WithdrawDetailed',
    72802: 'PasswordRecovery',
    77406: 'SocialUserSetPassword',
    75172: 'VerifyNewAddress',
    77370: 'DeactivateWhitelistModeOtp',
    77411: 'DeactivateWhitelistMode',
    77836: 'SocialTradeLeadershipAcceptance',
    77788: 'UserMergeOtp',
    77789: 'UserMergeSuccessful',
    78073: 'NewDeviceNotif',
    78074: 'ChangePasswordNotif',
    78075: 'SetUserParameter',
    81287: 'GrantFinancialService',
    80109: 'StaffPasswordRecovery',
    80531: 'AbcMarginCall',
    80532: 'AbcMarginCallLiquidate',
    82252: 'AbcLiquidateByProvider',
    81281: 'DirectDebitContractSuccessfullyCreated',
    81282: 'DirectDebitContractSuccessfullyRemoved',
    81283: 'DirectDebitContractCanceled',
    81848: 'AbcMarginCallAdjustment',
    83398: 'DirectDebitDepositSuccessfully',
}

OLD_SMSIR_TEMPLATES = Choices(
    (0, 'default', 'پیش‌فرض'),
    (6816, 'welcome', 'به نوبیتکس خوش آمدید . کد تایید عضویت شما : [VerificationCode] '),
    (3065, 'verification', 'کد تایید شما در سایت نوبیتکس [VerificationCode] است '),
    (54043, 'tfa_enable', 'درخواست فعال سازی شناسه دوعاملی نوبیتکس\nکد: [VerificationCode]'),
    (51443, 'tfa_disable', 'درخواست غیرفعالسازی شناسه دوعاملی نوبیتکس\nکد: [VerificationCode]'),
    (55503, 'kyc_update', 'نوبیتکسی عزیز\nلطفا ایمیل ارسال شده از واحد [VerificationCode] را بررسی نمایید.'),
    (63653, 'gift_redeem_otp', 'کد تایید دریافت کارت هدیه شما در نوبیتکس\n[VerificationCode]'),
    (
        68559,
        'new_device_withdrawal_restriction_notif',
        'هشدار نوبیتکس\n[Duration] محدودیت برداشت بعلت ورود از دستگاه/مرورگر جدید',
    ),
    (70745, 'generic_change_notif', 'نوبیتکس\nکاربر گرامی [ChangeType] شما در نوبیتکس تغییر کرد.'),
    (72801, 'withdraw', 'هشدار!\nاین کد تایید «برداشت» از حساب نوبیتکس شماست: [VerificationCode]'),
    (
        51444,
        'withdraw_detailed',
        'نوبیتکس\nدرخواست برداشت [Fund]\nکد تایید: [VerificationCode]\nلغو اضطراری: https://nobitex.ir/sos/[CancelCode]',
    ),
    (72802, 'password_recovery', 'کد تایید بازیابی رمزعبور در نوبیتکس: [VerificationCode]'),
    (77406, 'social_user_set_password', 'کد یکبار مصرف برای تعیین رمزعبور در حساب کاربری نوبیتکس:  [VerificationCode]'),
    (75172, 'verify_new_address', 'کد تایید افزودن آدرس جدید به دفترآدرس برداشت در نوبیتکس: [VerificationCode]'),
    (77370, 'deactivate_whitelist_mode_otp', 'کد تایید غیرفعال‌سازی حالت برداشت امن نوبیتکس: [VerificationCode]'),
    (77411, 'deactivate_whitelist_mode', 'هشدار نوبیتکس! [Duration] محدودیت برداشت به دلیل غیرفعال‌سازی برداشت امن'),
    (
        77836,
        'social_trade_leadership_acceptance',
        'کاربر گرامی نوبیتکس، درخواست شما برای انتخاب به عنوان تریدر مرجع تایید شده و از تاریخ [Date] امکان دریافت دنبال کننده را خواهید داشت.',
    ),
    (  # TODO Delete, this template is never used
        77778,
        'social_trade_leadership_rejection',
        'کاربر گرامی، درخواست شما برای انتخاب به عنوان تریدر مرجع رد شد. دلیل رد [Reason]',
    ),
    (
        77788,
        'user_merge_otp',
        'هشدار نوبیتکس!\nکد امنیتی برای تایید ادغام شماره تماس شما با حساب زیر:\n[Mobile]\nکد تایید ادغام:\n[VerificationCode]',
    ),
    (
        77789,
        'user_merge_successful',
        'نوبیتکس!\nکاربر گرامی ادغام [Data2] در حساب [Data1] با موفقیت انجام شد.\nبه منظور افزایش امنیت، برداشت رمزارز در حساب شما [Duration] محدود می‌شود.\nدر صورت هرگونه مغایرت با پشتیبانی موضوع را مطرح‌ نمایید.',
    ),
    (  # TODO Delete, this template is never used
        77779,
        'social_trade_notify_leader_of_deletion',
        'کاربر گرامی،‌ از این تاریخ شما امکان دریافت اشتراک جدید را نداشته و '
        'پس از پایان دوره اشتراک کاربران، امکان فعالیت به عنوان تریدر سوشال ترید'
        ' را نخواهید داشت. دلیل: [Reason]',
    ),
    (  # TODO Delete, this template is never used
        77780,
        'social_trade_notify_subscribers_of_leader_deletion',
        'کاربر گرامی، تریدر انتخابی شما تا پایان دوره فعلی اشتراک فعالیت خواهد داشت'
        ' و پس از آن امکان تمدید اشتراک وجود نخواهد داشت.\nتریدر: [Trader]',
    ),
    (  # TODO Delete, this template is never used
        77781,
        'social_trade_notify_trials_of_leader_deletion',
        'کاربر گرامی، به دلیل عدم فعالیت تریدر انتخابی شما، امکان فعال‌سازی اشتراک سوشال ترید'
        ' برای تریدر انتخابی وجود نداشته و دوره آزمایشی اشتراک شما به پایان رسیده است.\nتریدر: [Trader]',
    ),
    (78073, 'new_device_notif', 'هشدار نوبیتکس! ورود با [Device] به حساب نوبیتکس شما'),
    (78074, 'change_password_notif', 'هشدار نوبیتکس! محدودیت [Duration] برداشت به دلیل تغییر گذرواژه'),
    (78075, 'set_user_parameter', 'هشدار نوبیتکس! [Reason] حساب کاربری شما ثبت شد.'),
    (
        81287,
        'grant_financial_service',
        'کد تأیید جهت فعالسازی سرویس [FinancialService] در نوبیتکس\nکد: [VerificationCode]',
    ),
    (
        80109,
        'staff_password_recovery',
        'کد تایید بازیابی رمزعبور حساب کاربری پشتیبانی نوبیتکس شما : [VerificationCode]',
    ),
    (80531, 'abc_margin_call', 'وثیقه شما در [Platform] نوبیتکس در آستانه تبدیل قرار گرفته است.'),
    (80532, 'abc_margin_call_liquidate', 'وثیقه شما در سرویس [Platform] نوبیتکس تبدیل شد.'),
    (
        82252,
        'abc_liquidate_by_provider',
        'مقدار [Amount] تومان از وثیقه‌ی [ServiceName] به‌درخواست [ProviderName] تبدیل و تسویه شد.',
    ),
    (
        81281,
        'direct_debit_contract_successfully_created',
        'قرارداد واریز مستقیم [BankName] شما در نوبیتکس ایجاد شد.',
    ),
    (
        81282,
        'direct_debit_contract_successfully_removed',
        'قرارداد واریز مستقیم [BankName] شما در نوبیتکس حذف شد.',
    ),
    (
        81283,
        'direct_debit_contract_canceled',
        'قرارداد واریز مستقیم شما در نوبیتکس به‌دلیل [Reason] لغو شد.',
    ),
    (
        81848,
        'abc_margin_call_adjustment',
        'به‌دلیل کاهش نسبت ارزش در نوبیتکس، اعتبار شما در [ServiceName] غیرفعال شد.',
    ),
    (
        82618,
        'abc_debit_settlement',
        '[UserFirstName] عزیز،\n[Amount] تومان از رمزارز کیف وثیقه‌ی نوبی‌پی شما تسویه شد.\n مانده‌ی‌ قابل برداشت: [RemainingAmount] تومان\nNobiCard\nRedefine your spending! ',
    ),
    (
        83398,
        'direct_debit_deposit_successfully',
        'واریز مستقیم از حساب [bank_name] به کیف پول نوبیتکس انجام شد. در صورتی که شما این واریز را انجام نداده‌اید در اسرع وقت با پشتیبانی نوبیتکس تماس بگیرید.',
    ),
    (
        83413,
        'abc_debit_card_issued',
        '[UserFirstName] عزیز،\nنوبی‌پی شما با موفقیت صادر شد و در روزهای آینده در آدرسی که تعیین کرده‌اید، به دست شما می‌رسد.\nNobiCard\nRedefine your spending! ',
    ),
    (
        83414,
        'abc_debit_card_activated',
        '[UserFirstName] عزیز،\nضمن عرض تبریک، نوبی‌پی شما با موفقیت فعال شد. هم‌اکنون می‌توانید با دارایی خود از فروشگاه‌های سراسر کشور خرید کنید.\nNobiCard\nRedefine your spending! ',
    ),
    (
        83918,
        'cobank_deposit',
        '[Amount] تومان از مبداء بانک [Bank] به کیف اسپات شما در نوبیتکس واریز شد.',
    ),
)

NEW_SMSIR_TEMPLATES = Choices(
    (151167, 'direct_debit_contract_canceled', 'قرارداد واریز مستقیم شما در نوبیتکس به‌دلیل [Reason] لغو شد.'),
    (
        219762,
        'new_device_withdrawal_restriction_notif',
        'هشدار نوبیتکس\n[Duration] محدودیت برداشت بعلت ورود از دستگاه/مرورگر جدید',
    ),
    (
        223008,
        'abc_margin_call_adjustment',
        'به‌دلیل کاهش نسبت ارزش در نوبیتکس، اعتبار شما در [ServiceName] غیرفعال شد.',
    ),
    (244683, 'deactivate_whitelist_mode_otp', 'کد تایید غیرفعال‌سازی حالت برداشت امن نوبیتکس: [VerificationCode]'),
    (276816, 'change_password_notif', 'هشدار نوبیتکس! محدودیت [Duration] برداشت به دلیل تغییر گذرواژه'),
    (326631, 'kyc_update', 'نوبیتکسی عزیز\nلطفا ایمیل ارسال شده از واحد [VerificationCode] را بررسی نمایید.'),
    (
        342009,
        'user_merge_successful',
        'نوبیتکس!\nکاربر گرامی ادغام [Data2] در حساب [Data1] با موفقیت انجام شد.\nبه منظور افزایش امنیت، برداشت رمزارز در حساب شما [Duration] محدود می‌شود.\nدر صورت هرگونه مغایرت با پشتیبانی موضوع را مطرح‌ نمایید.',
    ),
    (380519, 'abc_margin_call_liquidate', 'وثیقه شما در سرویس [Platform] نوبیتکس تبدیل شد.'),
    (
        417498,
        'staff_password_recovery',
        'کد تایید بازیابی رمزعبور حساب کاربری پشتیبانی نوبیتکس شما : [VerificationCode]',
    ),
    (
        436165,
        'direct_debit_contract_successfully_removed',
        'قرارداد واریز مستقیم [BankName] شما در نوبیتکس حذف شد.',
    ),
    (465294, 'gift_redeem_otp', 'کد تایید دریافت کارت هدیه شما در نوبیتکس\n[VerificationCode]'),
    (515128, 'welcome', 'به نوبیتکس خوش آمدید . کد تایید عضویت شما : [VerificationCode] '),
    (
        567634,
        'user_merge_otp',
        'هشدار نوبیتکس!\nکد امنیتی برای تایید ادغام شماره تماس شما با حساب زیر:\n[Mobile]\nکد تایید ادغام:\n[VerificationCode]',
    ),
    (588339, 'password_recovery', 'کد تایید بازیابی رمزعبور در نوبیتکس: [VerificationCode]'),
    (613445, 'tfa_enable', 'درخواست فعال سازی شناسه دوعاملی نوبیتکس\nکد: [VerificationCode]'),
    (652978, 'new_device_notif', 'هشدار نوبیتکس! ورود با [Device] به حساب نوبیتکس شما'),
    (
        724865,
        'social_user_set_password',
        'کد یکبار مصرف برای تعیین رمزعبور در حساب کاربری نوبیتکس:  [VerificationCode]',
    ),
    (726355, 'abc_margin_call', 'وثیقه شما در [Platform] نوبیتکس در آستانه تبدیل قرار گرفته است.'),
    (
        782513,
        'withdraw_detailed',
        'نوبیتکس\nدرخواست برداشت [Fund]\nکد تایید: [VerificationCode]\nلغو اضطراری: https://nobitex.ir/sos/[CancelCode]',
    ),
    (
        820242,
        'abc_liquidate_by_provider',
        'مقدار [Amount] تومان از وثیقه‌ی [ServiceName] به‌درخواست [ProviderName] تبدیل و تسویه شد.',
    ),
    (
        842236,
        'social_trade_leadership_acceptance',
        'کاربر گرامی نوبیتکس، درخواست شما برای انتخاب به عنوان تریدر مرجع تایید شده و از تاریخ [Date] امکان دریافت دنبال کننده را خواهید داشت.',
    ),
    (
        850890,
        'direct_debit_contract_successfully_created',
        'قرارداد واریز مستقیم [BankName] شما در نوبیتکس ایجاد شد.',
    ),
    (871730, 'verify_new_address', 'کد تایید افزودن آدرس جدید به دفترآدرس برداشت در نوبیتکس: [VerificationCode]'),
    (881914, 'withdraw', 'هشدار!\nاین کد تایید «برداشت» از حساب نوبیتکس شماست: [VerificationCode]'),
    (882218, 'generic_change_notif', 'نوبیتکس\nکاربر گرامی [ChangeType] شما در نوبیتکس تغییر کرد.'),
    (888982, 'deactivate_whitelist_mode', 'هشدار نوبیتکس! [Duration] محدودیت برداشت به دلیل غیرفعال‌سازی برداشت امن'),
    (
        898144,
        'grant_financial_service',
        'کد تأیید جهت فعالسازی سرویس [FinancialService] در نوبیتکس\nکد: [VerificationCode]',
    ),
    (899697, 'set_user_parameter', 'هشدار نوبیتکس! [Reason] حساب کاربری شما ثبت شد.'),
    (913046, 'tfa_disable', 'درخواست غیرفعالسازی شناسه دوعاملی نوبیتکس\nکد: [VerificationCode]'),
    (941168, 'verification', 'کد تایید شما در سایت نوبیتکس [VerificationCode] است '),
    (
        402384,
        'abc_debit_settlement',
        '[UserFirstName] عزیز،\n[Amount] تومان از رمزارز کیف وثیقه‌ی نوبی‌پی شما تسویه شد.\n مانده‌ی‌ قابل برداشت: [RemainingAmount] تومان\nNobiCard\nRedefine your spending! ',
    ),
    (
        554580,
        'direct_debit_deposit_successfully',
        'واریز مستقیم از حساب [bank_name] به کیف پول نوبیتکس انجام شد. در صورتی که شما این واریز را انجام نداده‌اید در اسرع وقت با پشتیبانی نوبیتکس تماس بگیرید.',
    ),
    (
        733680,
        'abc_debit_card_issued',
        '[UserFirstName] عزیز،\nنوبی‌پی شما با موفقیت صادر شد و در روزهای آینده در آدرسی که تعیین کرده‌اید، به دست شما می‌رسد.\nNobiCard\nRedefine your spending! ',
    ),
    (
        805876,
        'abc_debit_card_activated',
        '[UserFirstName] عزیز،\nضمن عرض تبریک، نوبی‌پی شما با موفقیت فعال شد. هم‌اکنون می‌توانید با دارایی خود از فروشگاه‌های سراسر کشور خرید کنید.\nNobiCard\nRedefine your spending! ',
    ),
    (
        104139,
        'cobank_deposit',
        '[Amount] تومان از مبداء بانک [Bank] به کیف اسپات شما در نوبیتکس واریز شد.',
    ),
)

KAVENEGAR_TEMPLATES = Choices(
    ('Welcome', 'به نوبیتکس خوش آمدید . کد تایید عضویت شما : %token '),
    ('Verification', 'کد تایید شما در سایت نوبیتکس %token است '),
    ('TfaEnable', 'درخواست فعال سازی شناسه دوعاملی نوبیتکس' '\n' 'کد: %token'),
    ('TfaDisable', 'درخواست غیرفعالسازی شناسه دوعاملی نوبیتکس' '\n' 'کد: %token'),
    ('KycUpdate', 'نوبیتکسی عزیز' '\n' 'لطفا ایمیل ارسال شده از واحد %token را بررسی نمایید.'),
    ('GiftRedeemOtp', 'کد تایید دریافت کارت هدیه شما در نوبیتکس' '\n' '%token'),
    (
        'NewDeviceWithdrawalRestrictionNotif',
        'هشدار نوبیتکس' '\n' '%token محدودیت برداشت بعلت ورود از دستگاه/مرورگر جدید',
    ),
    ('GenericChangeNotif', 'نوبیتکس' '\n' 'کاربر گرامی %token شما در نوبیتکس تغییر کرد.'),
    ('Withdraw', 'هشدار!' '\n' 'این کد تایید «برداشت» از حساب نوبیتکس شماست: %token'),
    (
        'WithdrawDetailed',
        'نوبیتکس'
        '\n'
        'درخواست برداشت %token'
        '\n'
        'کد تایید: %token2'
        '\n'
        'لغو اضطراری: https://nobitex.ir/sos/%token3',
    ),
    ('PasswordRecovery', 'کد تایید بازیابی رمزعبور در نوبیتکس: %token'),
    ('SocialUserSetPassword', 'کد یکبار مصرف برای تعیین رمزعبور در حساب کاربری نوبیتکس:  %token'),
    ('VerifyNewAddress', 'کد تایید افزودن آدرس جدید به دفترآدرس برداشت در نوبیتکس: %token'),
    ('DeactivateWhitelistModeOtp', 'کد تایید غیرفعال‌سازی حالت برداشت امن نوبیتکس: %token'),
    ('DeactivateWhitelistMode', 'هشدار نوبیتکس! %token محدودیت برداشت به دلیل غیرفعال‌سازی برداشت امن'),
    (
        'SocialTradeLeadershipAcceptance',
        'کاربر گرامی نوبیتکس، درخواست شما برای انتخاب به عنوان تریدر مرجع تایید شده و از تاریخ %token امکان دریافت دنبال کننده را خواهید داشت.',
    ),
    (
        'UserMergeOtp',
        'هشدار نوبیتکس!'
        '\n'
        'کد امنیتی برای تایید ادغام شماره تماس شما با حساب زیر:'
        '\n'
        '%token'
        '\n'
        'کد تایید ادغام:'
        '\n'
        '%token2',
    ),
    (
        'UserMergeSuccessful',
        'نوبیتکس!'
        '\n'
        'کاربر گرامی ادغام %token در حساب %token2 با موفقیت انجام شد.'
        '\n'
        'به منظور افزایش امنیت، برداشت رمزارز در حساب شما %token3 محدود می‌شود.'
        '\n'
        'در صورت هرگونه مغایرت با پشتیبانی موضوع را مطرح‌ نمایید.',
    ),
    ('NewDeviceNotif', 'هشدار نوبیتکس! ورود با %token به حساب نوبیتکس شما'),
    ('ChangePasswordNotif', 'هشدار نوبیتکس! محدودیت %token برداشت به دلیل تغییر گذرواژه'),
    ('SetUserParameter', 'هشدار نوبیتکس! %token حساب کاربری شما ثبت شد.'),
    ('GrantFinancialService', 'کد تأیید جهت فعالسازی سرویس %token در نوبیتکس' '\n' 'کد: %token2'),
    ('StaffPasswordRecovery', 'کد تایید بازیابی رمزعبور حساب کاربری پشتیبانی نوبیتکس شما : %token'),
    ('AbcMarginCall', 'وثیقه شما در %token نوبیتکس در آستانه تبدیل قرار گرفته است.'),
    ('AbcMarginCallLiquidate', 'وثیقه شما در سرویس %token نوبیتکس تبدیل شد.'),
    ('AbcLiquidateByProvider', 'مقدار %token تومان از وثیقه‌ی %token2 به‌درخواست %token3 تبدیل و تسویه شد.'),
    ('DirectDebitContractSuccessfullyCreated', 'قرارداد واریز مستقیم %token شما در نوبیتکس ایجاد شد.'),
    ('DirectDebitContractSuccessfullyRemoved', 'قرارداد واریز مستقیم %token شما در نوبیتکس حذف شد.'),
    ('DirectDebitContractCanceled', 'قرارداد واریز مستقیم شما در نوبیتکس به‌دلیل %token لغو شد.'),
    ('AbcMarginCallAdjustment', 'به‌دلیل کاهش نسبت ارزش در نوبیتکس، اعتبار شما در %token غیرفعال شد.'),
    (
        'DirectDebitDepositSuccessfully',
        'واریز مستقیم از حساب %token به کیف پول نوبیتکس انجام شد. در صورتی که شما این واریز را انجام نداده‌اید در اسرع وقت با پشتیبانی نوبیتکس تماس بگیرید.',
    ),
)

# Example: {0: 'default', 6816: 'welcome', 3065: 'verification', 54043: 'tfa_enable', ...}
OLD_TEMPLATE_NUMBER_TO_TEMPLATE_NAME_DICT = {
    OLD_SMSIR_TEMPLATES._identifier_map[template_name]: template_name
    for template_name in OLD_SMSIR_TEMPLATES._identifier_map
}

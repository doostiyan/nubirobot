from django.db import models
from model_utils import Choices


class SystemBankAccount(models.Model):
    account_number = models.CharField(max_length=25, unique=True)
    shaba_number = models.CharField(max_length=26, unique=True)
    owner_name = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'اکانت بانکی سیستم'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '{} - {}'.format(self.account_number, self.bank_name)


class DepositSystemBankAccount(models.Model):
    BANK_ID = Choices(
        (10, 'centralbank', 'بانک‌مرکزی'),
        (11, 'sanatomadan', 'صنعت‌و‌معدن'),
        (12, 'mellat', 'ملت'),
        (13, 'refah', 'رفاه'),
        (14, 'maskan', 'مسکن'),
        (15, 'sepah', 'سپه'),
        (16, 'keshavarzi', 'کشاورزی'),
        (17, 'melli', 'ملی'),
        (18, 'tejarat', 'تجارت'),
        (19, 'saderat', 'صادرات'),
        (20, 'toseesaderat', 'توسعه‌صادرات'),
        (21, 'postbank', 'پست‌بانک'),
        (22, 'toseetaavon', 'توسعه‌تعاون'),
        (51, 'tosee', 'موسسه‌اعتباری‌توسعه'),
        (52, 'ghavamin', 'قوامین'),
        (53, 'karafarin', 'کار‌آفرین'),
        (54, 'parsian', 'پارسیان'),
        (55, 'eghtesadenovin', 'اقتصاد‌نوین'),
        (56, 'saman', 'سامان'),
        (57, 'pasargad', 'پاسارگاد'),
        (58, 'sarmayeh', 'سرمایه'),
        (59, 'sina', 'سینا'),
        (60, 'mehreiran', 'مهر‌ایران'),
        (61, 'shahr', 'شهر'),
        (62, 'ayandeh', 'آینده'),
        (63, 'ansar', 'انصار'),
        (64, 'gardeshgari', 'گردشگری'),
        (65, 'hekmateiraninan', 'حکمت‌ایرانیان'),
        (66, 'dey', 'دی'),
        (69, 'iranzamin', 'ایران‌زمین'),
        (70, 'resalat', 'رسالت'),
        (73, 'kowsar', 'کوثر'),
        (75, 'melal', 'موسسه‌ملل'),
        (78, 'khavarmiane', 'خاورمیانه'),
        (80, 'noor', 'موسسه‌نور'),
        (95, 'iranvenezoela', 'ایران ونزوئلا'),
        (999, 'vandar', 'وندار'),
        (1000, 'pay', 'پی'),
        (1001, 'mehreghtesad', 'مهر‌اقتصاد'),
    )
    ACCOUNT_TYPE = Choices(
        (1, 'jibit', 'جیبیت')
    )
    account_number = models.CharField(max_length=25, unique=True)
    iban_number = models.CharField(max_length=26, unique=True)
    bank_id = models.IntegerField(choices=BANK_ID, help_text='شناسه بانک')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    description = models.CharField(max_length=1000, blank=True, null=True, verbose_name='توضیحات')
    is_private = models.BooleanField(default=False)
    type_of_account = models.IntegerField(choices=ACCOUNT_TYPE, null=True, blank=True)

    class Meta:
        verbose_name = 'اکانت واریز بانکی سیستم'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '{} - {}'.format(self.account_number, self.get_bank_id_display())

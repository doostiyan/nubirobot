from django import forms


class ControlPanelForm(forms.Form):
    module_matching_engine = forms.ChoiceField(label='موتور معاملات (Matcher)', choices=[
        ('enabled', 'فعال'),
        ('disabled', 'غیرفعال'),
    ])
    module_autotrader_engine = forms.ChoiceField(label='موتور معاملات خوکار (Autotrading)', choices=[
        ('enabled', 'فعال'),
        ('disabled', 'غیرفعال'),
    ])
    module_withdraw_processing = forms.ChoiceField(label='پردازش خودکار درخواست‌های برداشت', choices=[
        ('enabled', 'فعال'),
        ('disabled', 'غیرفعال'),
    ])
    module_deposit_processing = forms.ChoiceField(label='تشخیص واریزهای رمزارزی', choices=[
        ('enabled', 'فعال'),
        ('activeusers', 'کاربران آنلاین'),
        ('onrequest', 'به درخواست کاربر'),
        ('disabled', 'غیرفعال'),
    ])

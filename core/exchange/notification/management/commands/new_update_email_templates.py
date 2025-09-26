import os
from html.parser import HTMLParser

import minify_html
from django.conf import settings
from django.core.management.base import BaseCommand
from post_office.cache import delete as delete_email_cache
from post_office.models import EmailTemplate

sorted_email_names = {
    'template': {
        'subject': '{{ title }}',
        'content': '{{ title }}\n{{content}}',
    },
    'welcome': {
        'subject': 'به نوبیتکس خوش آمدید',
        'content': 'Use this link to confirm your email: \n\n{{domain}}users/email-activation-redirect?token={{token}}',
    },
    'otp': {
        'subject': 'کد تایید نوبیتکس',
        'content': 'Your Nobitex verification token is: {{otp}}',
    },
    'login_notif': {
        'subject': 'ورود به نوبیتکس',
        'content': 'Nobitex Login From New Device\n\nUsername: {{username}}\nIP: {{ip}}\nDate: {{date}}\nDevice: {{device}}',
    },
    'withdraw_request_confirmation_code': {
        'subject': 'تایید درخواست برداشت',
        'content': '{{short_message}}',
    },
    'withdraw_done': {
        'subject': '{{ title }}',
        'content': 'Withdraw request status changed to done',
    },
    'deposit': {
        'subject': 'واریز وجه / ارز انجام شد',
        'content': 'Deposit for {{amount}} {{currency}} confirmed',
    },
    'tfa_otp': {
        'subject': 'غیرفعال‌سازی شناسایی دوعاملی',
        'content': 'Your OTP for disabling two factor authentication in Nobitex: {{otp}}',
    },
    'tfa_enable_notif': {
        'subject': 'فعال‌سازی شناسایی دوعاملی',
        'content': 'Two factor authentication enabled for your Nobitex account.',
    },
    'tfa_removal': {
        'subject': 'شناسایی دوعاملی حساب شما غیرفعال شد',
        'content': 'Two factor authentication disabled for you Nobitex account.',
    },
    'reset_password': {
        'subject': 'بازیابی رمز عبور نوبیتکس',
        'content': 'Nobitex Password Reset Link\n\n{{domain}}reset-password/?t={{token}}/',
    },
    'giftcard': {
        'subject': 'نوبی گیفت',
        'content': 'Nobitex Gift Card',
    },
    'new_device_notif': {
        'subject': 'ورود دستگاه جدید به حساب کاربری',
        'content': 'We noticed new sign-in to your account on an {{device_name}} at {{login_date}} {{login_time}}.',
    },
    'change_email_notif': {
        'subject': 'تغییر ایمیل',
        'content': 'Your email is changed',
    },
    'change_mobile_notif': {
        'subject': 'تغییر شماره موبایل',
        'content': 'The mobile number of your Nobitex account is changed',
    },
    'change_password_notif': {
        'subject': 'تغییر رمز عبور',
        'content': 'Your password is changed',
    },
    'change_anti_phishing_code': {
        'subject': 'تغییر کد آنتی فیشینگ',
        'content': 'Change anti phishing code',
    },
    'set_anti_phishing_code': {
        'subject': 'فعال سازی کد آنتی فیشینگ',
        'content': 'Activation of anti phishing code',
    },
    'margin_call': {
        'subject': 'هشدار لیکوئید شدن موقعیت',
    },
    'liquidation_call': {
        'subject': 'موقعیت شما لیکوئید شد',
    },
    'position_expired': {
        'subject': 'موقعیت شما منقضی شد',
    },
    'pool/delegation_revoke_on_new': {
        'subject': 'درخواست لغو مشارکت ثبت شد',
    },
    'pool/delegation_revoke_on_paid': {
        'subject': 'لغو مشارکت انجام شد',
    },
    'pool/unfilled_capacity_alert': {
        'subject': 'ظرفیت استخر آزاد شد',
    },
    'pool/new_delegation': {
        'subject': 'ثبت مشارکت انجام شد',
    },
    'pool/profit': {
        'subject': 'سود مشارکت واریز شد',
    },
    'staking/create_request': {
        'subject': 'ثبت درخواست استیکینگ',
    },
    'staking/staked': {
        'subject': 'تایید‌ نهایی استیکینگ',
    },
    'staking/reward_deposit_and_extend': {
        'subject': 'تمدید طرح استیکینگ',
    },
    'staking/reward_deposit_no_extend': {
        'subject': 'عدم تمدید طرح استیکینگ',
    },
    'staking/end_request': {
        'subject': 'ثبت درخواست لغو استیکینگ',
    },
    'staking/release': {
        'subject': 'واریز وجه استیکینگ',
    },
    'staking/plan_capacity_increase': {
        'subject': 'افزایش ظرفیت استیکینگ',
    },
    'staking/instant_end_request': {
        'subject': 'لغو آنی استیکینگ',
    },
    'yield_aggregator/create_request': {
        'subject': 'ثبت درخواست ییلد فارمینگ',
    },
    'yield_aggregator/staked': {
        'subject': 'تایید‌ نهایی ییلد فارمینگ',
    },
    'yield_aggregator/reward_deposit_and_extend': {
        'subject': 'تمدید طرح ییلد فارمینگ',
    },
    'yield_aggregator/reward_deposit_no_extend': {
        'subject': 'عدم تمدید طرح ییلد فارمینگ',
    },
    'yield_aggregator/end_request': {
        'subject': 'ثبت درخواست لغو ییلد فارمینگ',
    },
    'yield_aggregator/release': {
        'subject': 'واریز وجه ییلد فارمینگ',
    },
    'yield_aggregator/plan_capacity_increase': {
        'subject': 'افزایش ظرفیت ییلد فارمینگ',
    },
    'yield_aggregator/instant_end_request': {
        'subject': 'لغو آنی ییلد فارمینگ',
    },
    'transaction_history': {
        'subject': 'دانلود تاریخچه تراکنش‌ها',
    },
    'addressbook/deactivate_whitelist_mode': {
        'subject': 'غیرفعال‌سازی حالت برداشت امن',
        'content': 'حالت برداشت امن حساب کاربری شما غیرفعال شد. برداشت از حساب شما به مدت ۲۴ ساعت محدود خواهد شد و پس از آن امکان برداشت از حساب شما به هر آدرسی امکان پذیر خواهد بود.',
    },
    'addressbook/new_address_in_address_book': {
        'subject': 'اضافه شدن آدرس جدید به دفتر آدرس',
    },
    'social_login_set_password_otp': {
        'subject': 'احرازهویت نوبیتکس | تعیین رمزعبور',
    },
    'kyc_param_confirmed_or_rejected': {
        'subject': '{{ title }}',
    },
    'kyc_param_rejected': {
        'subject': '{{ title }}',
    },
    'kyc_param_confirmed': {
        'subject': '{{ title }}',
    },
    'socialtrade/leadership_acceptance': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/leadership_rejection': {
        'subject': '{{ email_title }}',
    },
    'merge/otp_message': {
        'subject': 'کد تایید برای ادغام دو حساب کاربری',
    },
    'merge/successful_message': {
        'subject': 'تایید ادغام',
    },
    'socialtrade/pre_trial_renewal_alert': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/pre_subscription_auto_renewal_alert': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/pre_subscription_non_auto_renewal_alert': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/upcoming_renewal': {
        'subject': '{{ email_title }}',
    },
    'new_user_type_notif': {'subject': 'احراز هویت نوبیتکس - سطح کاربری شما، به {{ level_label }} ارتقا یافت.'},
    'socialtrade/leader_deletion_leader': {
        'subject': '{{email_title}}',
    },
    'socialtrade/leader_deletion_subscribers': {
        'subject': '{{email_title}}',
    },
    'socialtrade/leader_deletion_trials': {
        'subject': '{{email_title}}',
    },
    'socialtrade/change_fee_notify_subscribers': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/successful_trial_renewal': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/successful_subscription_renewal': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/failed_trial_renewal': {
        'subject': '{{ email_title }}',
    },
    'socialtrade/failed_subscription_renewal': {
        'subject': '{{ email_title }}',
    },
    'abc/abc_margin_call': {'subject': 'هشدار آستانه تبدیل اعتبار ریالی'},
    'abc/abc_margin_call_liquidate': {'subject': 'تبدیل دارایی در سرویس اعتبار ریالی'},
    'abc/abc_margin_call_adjustment': {'subject': 'غیرفعال شدن موجودی اعتبار خرید کالا'},
    'abc/abc_liquidate_by_provider': {'subject': 'تبدیل دارایی در سرویس اعتبار ریالی'},
    'abc/abc_service_activated': {'subject': 'تائید فعالسازی سرویس'},
    'abc/abc_user_service_closed': {'subject': 'لغو سرویس'},
    'abc/abc_user_service_close_requested': {'subject': 'درخواست لغو سرویس'},
    'abc/abc_debit_weekly_invoice': {'subject': 'تاریخچه‌ی تراکنش‌های نوبی‌پی'},
    'direct_debit/contract_successfully_created': {
        'subject': '{{email_title}}',
    },
    'direct_debit/contract_successfully_edited': {
        'subject': '{{email_title}}',
    },
    'direct_debit/contract_successfully_removed': {
        'subject': '{{ email_title }}',
    },
    'direct_debit/deposit_successfully': {
        'subject': '{{ email_title }}',
    },
    'direct_debit/deposit_failed': {
        'subject': '{{ email_title }}',
    },
    'direct_debit/edit_contract_failed': {
        'subject': '{{ email_title }}',
    },
    'direct_debit/auto_contract_canceled': {
        'subject': '{{ email_title }}',
    },
    'notify_upcoming_margin_expiration': {
        'subject': 'یادآوری منقضی شدن موقعیت {{ position_side }}',
    },
    'apikey/creation': {
        'subject': '{{ email_title }}',
    },
    'apikey/update': {
        'subject': '{{ email_title }}',
    },
    'apikey/deletion': {
        'subject': '{{ email_title }}',
    },
}


class Command(BaseCommand):
    # TODO Change the command name (remove 'new') after full launch
    help = 'Updates email templates based on notification/email/templates/emails html templates'

    @staticmethod
    def get_email_template_path(email_name):
        path = os.path.join(settings.BASE_DIR, f'exchange/notification/email/templates/emails/{email_name}.html')
        if os.path.isfile(path):
            return path
        return None

    def handle(self, *args, **kwargs):
        use_cache = getattr(settings, 'POST_OFFICE_CACHE', True)
        if use_cache:
            use_cache = getattr(settings, 'POST_OFFICE_TEMPLATE_CACHE', True)

        for email_name, email_content in sorted_email_names.items():
            # since we don't differ languages, it's omitted
            email_template_path = self.get_email_template_path(email_name)
            if email_template_path:
                with open(email_template_path) as html:
                    email_content['html_content'] = minify_html.minify(html.read(), minify_css=True)
                    if 'content' not in email_content:
                        email_content['content'] = self.get_html_text_content(email_content['html_content'])
                    if use_cache:
                        delete_email_cache(email_name + ':')

            _, created = EmailTemplate.objects.update_or_create(name=email_name, defaults=email_content)
            changes = ', '.join(email_content.keys())
            if kwargs.get('verbosity'):
                self.stdout.write(f'{email_name} ---> {"Created with" if created else "Updated"}: {changes}')

    @staticmethod
    def get_html_text_content(html):
        class HTMLFilter(HTMLParser):
            text = ""

            def handle_data(self, data):
                self.text += data + '\n'

        f = HTMLFilter()
        f.feed(html)
        return f.text.replace('{% extends \'email_base.html\' %}', '').strip()

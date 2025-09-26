from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.accounts.models import Notification, UserReferral
from .models import FeeDiscount


@receiver(post_save, sender=UserReferral, dispatch_uid='promotions_referral_based_campaigns')
def promotions_referral_based_campaigns(sender, instance, created, **kwargs):
    if not created:
        return
    # Sharif Blockchain Lab Campaign
    if instance.parent.username == 'hanzaleh.a.n@gmail.com':
        new_user = instance.child
        FeeDiscount.objects.create(
            user=new_user,
            discounted_fee=0,
            total_discount=350000,
            description='تخفیف ثبت‌نام از آزمایشگاه بلاک‌چین شریف: کارمزد صفر برای ده میلیون تومان معامله آغازین',
        )
        Notification.objects.create(
            user=new_user,
            message='به نوبیتکس خوش آمدید! با توجه به ثبت‌نام شما با استفاده از کد تخفیف آزمایشگاه بلاک‌چین شریف، کارمزد شما برای تمامی معاملات تا مجموع ده میلیون تومان صفر خواهد بود.',
        )

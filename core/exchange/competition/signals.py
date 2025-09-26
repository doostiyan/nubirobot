from decimal import Decimal

from django.db.models import Q, F
from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.accounts.models import User, UserReferral
from exchange.base.models import RIAL
from exchange.market.models import OrderMatching
from exchange.wallet.models import Wallet
from .models import Competition, CompetitionRegistration


@receiver(post_save, sender=User, dispatch_uid='competition_new_user_registered')
def new_user_registered(sender, instance, created, **kwargs):
    if not created:
        return
    # Upgrade all new testnet users to Level1
    if instance.user_type < User.USER_TYPES.level1:
        instance.user_type = User.USER_TYPES.level1
        instance.verification_status = User.VERIFICATION.extended
        instance.save(update_fields=['user_type', 'verification_status'])
    # Register user in active competition
    competition = Competition.get_active_competition()
    if not competition:
        return
    competition.register_user(instance)


@receiver(post_save, sender=OrderMatching, dispatch_uid='competition_new_trade_done')
def new_trade_done(sender, instance, created, **kwargs):
    registrations = CompetitionRegistration.objects.filter(Q(user=instance.sell_order.user) | Q(user=instance.buy_order.user), is_active=True)
    for registration in registrations:
        registration.update_current_balance()


@receiver(post_save, sender=UserReferral, dispatch_uid='competition_new_referral_created')
def new_referral_created(sender, instance, created, **kwargs):
    if not created:
        return
    user = instance.parent
    competition = Competition.get_active_competition()
    if not competition or not competition.is_user_registered(user):
        return
    gift_amount = Decimal('50000000')
    wallet = Wallet.get_user_wallet(user, RIAL)
    tr = wallet.create_transaction(
        tp='manual',
        amount=gift_amount,
        description='موجودی جایزه جهت ترید در مسابقه {} به خاطر دعوت از دوستان'.format(competition.name),
    )
    tr.commit()
    CompetitionRegistration.objects.filter(competition=competition, user=user).update(gift_balance=F('gift_balance') + gift_amount)

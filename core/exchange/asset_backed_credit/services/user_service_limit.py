from decimal import Decimal

from exchange.accounts.models import Tag, User, UserTag
from exchange.asset_backed_credit.models import UserFinancialServiceLimit
from exchange.base.logging import report_event


def update_financial_limit_on_users():
    try:
        tag = Tag.objects.get(name='استعلام')
    except Tag.DoesNotExist:
        report_event('Inquiry tag does not exists.')
        return

    set_limit_on_inquiry_tagged_users(inquiry_tag=tag)
    unset_limit_from_users_on_inquiry_tag_removal(inquiry_tag=tag)


def set_limit_on_inquiry_tagged_users(inquiry_tag: Tag):
    user_ids = UserTag.objects.filter(tag=inquiry_tag).values_list('user_id', flat=True)
    already_limited_user_ids = UserFinancialServiceLimit.objects.filter(
        user__isnull=False, tp=UserFinancialServiceLimit.TYPES.user, limit=Decimal(0)
    ).values_list('user_id', flat=True)
    for user in User.objects.filter(id__in=user_ids).exclude(id__in=already_limited_user_ids):
        UserFinancialServiceLimit.set_user_limit(user, max_limit=0)


def unset_limit_from_users_on_inquiry_tag_removal(inquiry_tag: Tag):
    limits = UserFinancialServiceLimit.objects.filter(
        user__isnull=False, tp=UserFinancialServiceLimit.TYPES.user, limit=Decimal(0)
    )

    tagged_user_ids = UserTag.objects.filter(tag=inquiry_tag).values_list('user_id', flat=True)
    limits_to_unset = limits.exclude(user_id__in=tagged_user_ids)
    limits_to_unset.delete()

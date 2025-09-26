from django.db import migrations


def set_referred_user(apps, schema_editor):
    ReferralFee = apps.get_model('market', 'ReferralFee')
    for fee in ReferralFee.objects.all().select_related('matching'):
        if fee.matching.sell_order.user != fee.user:
            user = fee.matching.sell_order.user
        else:
            user = fee.matching.buy_order.user
        fee.referred_user = user
        fee.save(update_fields=['referred_user'])


class Migration(migrations.Migration):
    dependencies = [
        ('market', '0008_referralfee_referred_user'),
    ]
    operations = [
        migrations.RunPython(set_referred_user),
    ]

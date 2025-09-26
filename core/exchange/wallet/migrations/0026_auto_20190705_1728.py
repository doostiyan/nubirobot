from django.db import migrations


def set_deposit_address_currency(apps, schema_editor):
    WalletDepositAddress = apps.get_model('wallet', 'WalletDepositAddress')
    for da in WalletDepositAddress.objects.all().select_related('wallet'):
        da.currency = da.wallet.currency
        da.save(update_fields=['currency'])


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0025_auto_20190705_1725'),
    ]

    operations = [
        migrations.RunPython(set_deposit_address_currency),
    ]

from django.core.management.base import BaseCommand
from exchange.explorer.networkproviders.models.network import Network

ACCOUNT_BASED_NETWORKS = ['ADA', 'ALGO', 'APT', 'ARB', 'AVAX', 'BSC', 'DOT', 'EGLD', 'ENJ', 'ETC', 'ETH', 'FIL', 'FTM',
                          'MATIC', 'NEAR', 'ONE', 'SOL', 'XTZ', 'TRX', 'XMR']
MEMO_BASED_NETWORKS = ['ATOM', 'BNB', 'EOS', 'HBAR', 'PMN', 'TON', 'XLM', 'XRP']
UTXO_BASED_NETWORKS = ['BCH', 'BTC', 'DOGE', 'FLOW', 'LTC']


class Command(BaseCommand):
    help = "Update network types based on predefined lists"

    def handle(self, *args, **kwargs):
        for network in Network.objects.all():
            if network.name in UTXO_BASED_NETWORKS:
                network.type = 'utxo_based'
            elif network.name in MEMO_BASED_NETWORKS:
                network.type = 'memo_based'
            elif network.name in ACCOUNT_BASED_NETWORKS:
                network.type = 'account_based'
            network.save()

from django.core.management.base import BaseCommand
from exchange.explorer.networkproviders.models import Network


class Command(BaseCommand):
    help = "Update block_time for a specific network"

    def add_arguments(self, parser):
        parser.add_argument("network_name", type=str, help="Network name to update its block time")
        parser.add_argument("block_time", type=float, help="New block time")

    def handle(self, *args, **kwargs):
        network_name = kwargs["network_name"]
        new_block_time = kwargs["block_time"]

        try:
            network = Network.objects.get(name=network_name)
            network.block_time = new_block_time
            network.save()
            self.stdout.write(self.style.SUCCESS(
                f"Successfully updated block_time to {new_block_time} for network '{network_name}'."))
        except Network.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Network '{network_name}' not found."))

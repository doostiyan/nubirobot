from django.core.management.base import BaseCommand
from exchange.explorer.networkproviders.models import Network
from exchange.explorer.wallets.service.transaction_address_service import TransactionAddressService


class Command(BaseCommand):
    help = 'Registers a new transaction address'

    def add_arguments(self, parser):
        parser.add_argument('network_symbol', type=str)
        parser.add_argument('address', type=str)
        parser.add_argument('--is_active', type=bool, default=True, help="Set the address as active or inactive")

    def handle(self, *args, **kwargs):
        network_symbol = kwargs['network_symbol'].upper()
        address = kwargs['address']
        is_active = kwargs['is_active']

        try:
            network = Network.objects.get(name=network_symbol)
        except Network.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Network with symbol "{network_symbol}" does not exist.'))
            return

        created_address = TransactionAddressService.create_address(network=network, address=address,
                                                                   is_active=is_active)

        if created_address:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully registered address {address} with network {network_symbol}.'))
        else:
            self.stdout.write(self.style.ERROR(f'Failed to register address {address}.'))

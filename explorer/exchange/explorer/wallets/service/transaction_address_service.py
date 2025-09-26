from exchange.explorer.wallets.models import DepositAddress


# Service Layer for TransactionAddress
class TransactionAddressService:
    @staticmethod
    def create_address(network, address, is_active=True):
        return DepositAddress.objects.create(
            network=network,
            address=address,
            is_active=is_active
        )

    @staticmethod
    def get_all_active_addresses():
        return DepositAddress.objects.filter(is_active=True)

    @staticmethod
    def delete_old_addresses(threshold_date):
        return DepositAddress.objects.filter(updated_at__lt=threshold_date).delete()

    @staticmethod
    def deactivate_address(address):
        obj = DepositAddress.objects.filter(address=address).first()
        if obj:
            obj.is_active = False
            obj.save()
        return obj

    @staticmethod
    def get_network_by_address(address):
        obj = DepositAddress.objects.filter(address=address).select_related('network').first()
        return obj.network if obj else None

    @staticmethod
    def get_active_addresses_by_network(network):
        return DepositAddress.objects.filter(network=network, is_active=True)

    @staticmethod
    def get_active_address_list_by_network(network):
        return DepositAddress.objects.filter(network=network, is_active=True).values_list('address', flat=True)

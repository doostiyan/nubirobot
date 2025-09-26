from rest_framework import serializers

from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.utils import AddressNotExist
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.utils.blockchain import is_network_ready
from exchange.explorer.utils.exception import NetworkNotFoundException
from exchange.explorer.utils.views import validate_address
from django.utils.translation import gettext_lazy as _


class WalletTransactionSerializer(serializers.Serializer):
    TX_DIRECTION_CHOICES = [
        ('outgoing', 'OUTGOING'),
        ('incoming', 'INCOMING')
    ]

    address = serializers.CharField(max_length=300, write_only=True)
    network = serializers.CharField(write_only=True)
    currency = serializers.CharField(allow_blank=True, allow_null=True)
    tx_direction = serializers.ChoiceField(required=False, choices=TX_DIRECTION_CHOICES)

    def validate(self, data):
        network = data.get('network')
        if network not in APIS_CONF or not is_network_ready(network, Operation.ADDRESS_TXS):
            raise NetworkNotFoundException

        if not validate_address(
                address=data.get('address'),
                network=data.get('network'),
                currency=data.get('currency'),
        ):
            raise AddressNotExist(_('Address is not valid'))
        return data

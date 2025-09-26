from rest_framework import serializers
from django.core.exceptions import ValidationError

from exchange.blockchain.apis_conf import APIS_CONF
from exchange.explorer.utils.exception import NetworkNotFoundException
from exchange.explorer.utils.views import validate_address
from django.utils.translation import gettext_lazy as _


class WalletBalanceSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=300)
    balance = serializers.DecimalField(max_digits=30, decimal_places=18, read_only=True)
    contract_address = serializers.CharField(max_length=100, allow_blank=True)
    symbol = serializers.CharField(max_length=10, allow_blank=True)
    network = serializers.CharField(max_length=50, allow_blank=True)
    block_number = serializers.IntegerField()

    def validate(self, data):
        network = self.context.get('network')
        if not (network in APIS_CONF and 'get_balances' in APIS_CONF[network]):
            raise NetworkNotFoundException
        currency = self.context.get('currency')
        address = data['address']
        if not validate_address(address, network, currency):
            raise ValidationError({'address': _('Address is not valid')})
        return data

class BatchWalletBalanceSerializer(serializers.Serializer):
    addresses = serializers.ListSerializer(child=serializers.CharField(max_length=300), write_only=True)
    currency = serializers.CharField(required=True)
    wallet_balances = WalletBalanceSerializer(read_only=True, many=True)

    def validate_currency(self, value):
        """
        Validate that the value is a string.
        """
        if value.isdigit():
            raise serializers.ValidationError(_("The value must be a string."))
        return value

    def validate(self, data):
        network = self.context.get('network')
        if not (network in APIS_CONF and 'get_balances' in APIS_CONF[network]):
            raise NetworkNotFoundException
        currency = data['currency']
        for address in data['addresses']:
            if not validate_address(address, network, currency):
                raise ValidationError(_('Address is not valid'))
        return data

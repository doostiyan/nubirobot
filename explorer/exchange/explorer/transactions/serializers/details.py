from typing import Union
from urllib.parse import urlparse

import pytz
from rest_framework import serializers

from exchange.explorer.networkproviders.models import Network, Provider


class TransactionQueryParamsSerializer(serializers.Serializer):
    currency = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    network = serializers.CharField(required=True)
    provider_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    base_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)

    @classmethod
    def validate_provider_name(cls, value: str) -> str:
        if Provider.objects.filter(name=value).exists():
            return value
        raise serializers.ValidationError('provider name not valid')

    @classmethod
    def validate_network(cls, network: str) -> str:
        if Network.objects.filter(name__iexact=network).exists():
            return network
        raise serializers.ValidationError('network name not valid')

    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if not parsed.scheme.startswith('http'):
            raise serializers.ValidationError('base_url must be a valid HTTP or HTTPS URL.')
        return value


class TransactionSerializer(serializers.Serializer):
    tx_hash = serializers.CharField()
    success = serializers.BooleanField()
    from_address = serializers.CharField()
    to_address = serializers.CharField()
    value = serializers.DecimalField(max_digits=None, decimal_places=None)
    symbol = serializers.CharField()
    confirmations = serializers.IntegerField(default=0)
    block_height = serializers.IntegerField(allow_null=True, default=None)
    block_hash = serializers.CharField(allow_null=True, default=None)
    date = serializers.DateTimeField(allow_null=True, default=None, default_timezone=pytz.UTC)
    memo = serializers.CharField(allow_null=True, default=None)
    tx_fee = serializers.DecimalField(max_digits=None, decimal_places=None, allow_null=True, default=None)
    token = serializers.CharField(allow_null=True, default=None)

    def to_representation(self, data: Union[dict, list]) -> dict:
        if isinstance(data, dict) and (data.get('from_address_str') or data.get('to_address_str')):
            data['from_address'] = data.pop('from_address_str')
            data['to_address'] = data.pop('to_address_str')
        return super().to_representation(data)

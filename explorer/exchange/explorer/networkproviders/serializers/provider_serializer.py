from rest_framework import serializers

from .network_serializer import NetworkSerializer
from .url_serializer import URLSerializer
from ..models import Provider, Network, Operation


class ProviderSerializer(serializers.ModelSerializer):
    network_id = serializers.PrimaryKeyRelatedField(queryset=Network.objects.all(), source='network', required=True)

    class Meta:
        model = Provider
        fields = ('id', 'name', 'network_id', 'support_batch', 'batch_block_limit',
                  'supported_operations', 'default_url_id')


class ProviderDetailSerializer(serializers.ModelSerializer):
    network = NetworkSerializer(required=True)
    urls = URLSerializer(required=True, many=True)

    class Meta:
        model = Provider
        fields = ('id', 'name', 'network', 'support_batch', 'batch_block_limit',
                  'supported_operations', 'default_url', 'urls')


class CheckProviderSerializer(serializers.Serializer):
    network = serializers.CharField(max_length=10, required=True)
    operation = serializers.ChoiceField(choices=Operation.choices, required=True)
    base_url = serializers.URLField(required=True)


class CheckProviderResultSerializer(serializers.Serializer):
    is_healthy = serializers.BooleanField()
    block_head = serializers.IntegerField()
    message = serializers.CharField()

from rest_framework import serializers

from ..models import NetworkDefaultProvider, Provider
from . import NetworkSerializer, ProviderDetailSerializer


class NetworkDefaultProviderSerializer(serializers.ModelSerializer):
    provider_id = serializers.PrimaryKeyRelatedField(queryset=Provider.objects.all(), source='provider', required=True)
    network = serializers.CharField(max_length=10)

    class Meta:
        model = NetworkDefaultProvider
        fields = ('id', 'provider_id', 'operation', 'network')

    def get_unique_together_validators(self):
        """Overriding method to disable unique together checks"""
        return []


class NetworkDefaultProviderDetailSerializer(serializers.ModelSerializer):
    provider = ProviderDetailSerializer(read_only=True)
    network = NetworkSerializer(read_only=True)

    class Meta:
        model = NetworkDefaultProvider
        fields = ('id', 'provider', 'operation', 'network')

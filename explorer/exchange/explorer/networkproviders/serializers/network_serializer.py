from rest_framework import serializers

from ..models import Network


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        fields = ('id', 'name', 'block_limit_per_req')

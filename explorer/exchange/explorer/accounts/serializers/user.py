from rest_framework import serializers

from ...authentication.serializers import APIKeySerializer


class UserSerializer(serializers.Serializer):
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.CharField()
    date_joined = serializers.CharField()
    api_keys = APIKeySerializer(many=True)

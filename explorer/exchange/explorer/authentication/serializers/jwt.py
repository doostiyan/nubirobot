from rest_framework import serializers


class JWTAuthSerializer(serializers.Serializer):
    access = serializers.CharField(required=False, max_length=250)
    refresh = serializers.CharField(required=False, max_length=250)

from rest_framework import serializers

from ..models import UserAPIKey


class APIKeySerializer(serializers.Serializer):
    key = serializers.CharField(read_only=True)
    username = serializers.CharField()
    name = serializers.CharField()
    prefix = serializers.CharField(read_only=True)
    created = serializers.CharField(read_only=True)
    rate = serializers.CharField()
    expiry_date = serializers.CharField(read_only=True)
    revoked = serializers.BooleanField(read_only=True)

    def save(self):
        _, key = UserAPIKey.objects.create_key(name=self.validated_data['name'],
                                               rate=self.validated_data['rate'],
                                               user__username=self.validated_data['username'])

        self.key = key
        return self

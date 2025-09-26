from rest_framework import serializers


class TransactionInputOutputSerializer(serializers.Serializer):
    address = serializers.CharField()
    value = serializers.DecimalField(30, 18)
    currency = serializers.CharField()
    is_valid = serializers.BooleanField()

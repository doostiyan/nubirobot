from rest_framework import serializers


class TransactionTransferSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    currency = serializers.IntegerField()
    _from = serializers.CharField()
    to = serializers.CharField()
    value = serializers.CharField()
    is_valid = serializers.BooleanField()
    type = serializers.CharField()

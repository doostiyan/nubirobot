from rest_framework import serializers


class TransactionOutputSerializer(serializers.Serializer):
    address = serializers.CharField()
    value = serializers.CharField()

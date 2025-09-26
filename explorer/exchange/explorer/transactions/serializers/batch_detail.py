from rest_framework import serializers

from .details import TransactionSerializer


class BatchTransactionDetailSerializer(serializers.Serializer):
    tx_hashes = serializers.ListField(child=serializers.CharField(), write_only=True, allow_null=False,
                                      allow_empty=False)
    transactions = TransactionSerializer(many=True, read_only=True)

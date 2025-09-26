from rest_framework import serializers
from exchange.explorer.transactions.serializers.details import TransactionSerializer


class BlockInfoSerializer(serializers.Serializer):
    latest_processed_block = serializers.IntegerField()
    transactions = TransactionSerializer(many=True)


class BlockHeadSerializer(serializers.Serializer):
    block_head = serializers.IntegerField()

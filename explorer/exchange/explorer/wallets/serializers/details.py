from rest_framework import serializers

from .balance import WalletBalanceSerializer
from ...transactions.serializers.details import TransactionSerializer


class WalletDetailsSerializer(serializers.Serializer):
    address = serializers.CharField()
    network = serializers.CharField()
    balance = WalletBalanceSerializer(many=True)
    transactions = TransactionSerializer(many=True)

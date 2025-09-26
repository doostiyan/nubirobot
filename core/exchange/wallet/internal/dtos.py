from rest_framework import serializers

from exchange.base.api import ParseError
from exchange.base.parsers import parse_choices, parse_currency, parse_uuid
from exchange.wallet.models import Wallet


class WalletParamsDTO(serializers.Serializer):
    uid = serializers.UUIDField()
    type = serializers.CharField()
    currency = serializers.CharField()

    def validate_uid(self, value):
        try:
            uid = parse_uuid(value, required=True)
        except ParseError as e:
            raise serializers.ValidationError(e)
        return uid

    def validate_type(self, value):
        try:
            type = parse_choices(Wallet.WALLET_TYPE, value, required=True)
        except ParseError as e:
            raise serializers.ValidationError(e)
        return type

    def validate_currency(self, value):
        try:
            currency = parse_currency(value, required=True)
        except ParseError as e:
            raise serializers.ValidationError(e)
        return currency

    @property
    def wallet_key(self):
        return f'{self.uid}-{self.currency}-{self.type}'

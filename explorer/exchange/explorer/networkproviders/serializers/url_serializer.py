from rest_framework import serializers
from exchange.explorer.networkproviders.models.url import URL


class URLSerializer(serializers.ModelSerializer):
    class Meta:
        model = URL
        fields = ['id', 'url', 'use_proxy']

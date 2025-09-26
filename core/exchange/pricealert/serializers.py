""" Price Alert Serializers """
from exchange.base.serializers import register_serializer
from .models import PriceAlert


@register_serializer(model=PriceAlert)
def serialize_price_alert(alert, opts=None):
    return {
        'id': alert.id,
        'createdAt': alert.created_at,
        'market': alert.market.symbol,
        'type': alert.get_tp_display(),
        'direction': '+' if alert.param_direction else '-',
        'price': alert.param_value,
        'description': alert.description,
        'channel': alert.get_channel_display(),
        'lastAlert': alert.last_alert,
    }

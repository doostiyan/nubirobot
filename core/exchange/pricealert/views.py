from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from exchange.base.api import APIView
from exchange.base.parsers import parse_money, parse_str
from exchange.market.parsers import parse_market

from .models import PriceAlert
from .parsers import parse_alert_type, parse_channel, parse_delete_item, parse_direction


class PricerAlertsView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='25/5m', method='GET'))
    def get(self, request):
        """Get list of all user's price alerts."""
        alerts = PriceAlert.objects.filter(user=request.user).select_related('market')
        return self.response({
            'status': 'ok',
            'alerts': alerts,
        })

    @method_decorator(ratelimit(key='user_or_ip', rate='10/5m', method='POST'))
    def post(self, request):
        # Parse parameters
        pk = self.g('pk')
        market = parse_market(self.g('market'))
        direction = parse_direction(self.g('direction'))
        price = parse_money(self.g('price'), field=PriceAlert.param_value)
        description = parse_str(self.g('description')) or None
        channel = parse_channel(self.g('channel'))
        tp = parse_alert_type(self.g('tp'))
        if not all([market, price, tp, channel]) or direction is None:
            return self.response({
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Invalid create parameters.',
            })
        if channel & PriceAlert.CHANNELS.sms:  # SMS bit is set in channel
            return self.response({
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'SMS is currently disabled.',
            })
        if pk:
            # Update price alert
            alert = get_object_or_404(PriceAlert, pk=pk, user=request.user)
            alert.market = market
            alert.tp = tp
            alert.param_direction = direction
            alert.param_value = price
            alert.description = description
            alert.channel = channel
            alert.save()
        else:
            # Create a new price alert
            if PriceAlert.objects.filter(user=request.user).count() >= 50:
                return self.response({
                    'status': 'failed',
                    'code': 'TooManyAlerts',
                    'message': 'You can only have 50 active price alerts.',
                })
            alert = PriceAlert.objects.create(
                user=request.user,
                market=market,
                tp=tp,
                param_direction=direction,
                param_value=price,
                description=description,
                cooldown=-1,
                channel=channel,
            )
        return self.response({
            'status': 'ok',
            'alert': alert,
        })

    @method_decorator(ratelimit(key='user_or_ip', rate='25/5m', method='DELETE'))
    def delete(self, request):
        """Delete selected items."""
        delete_items = parse_delete_item(self.g('delete_item'))
        if not delete_items:
            return self.response({
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'No records selected to delete.',
            })
        PriceAlert.objects.filter(
            user=request.user,
            id__in=delete_items
        ).delete()
        return self.response({
            'status': 'ok',
        })

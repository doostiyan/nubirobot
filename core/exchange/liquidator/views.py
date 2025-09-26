from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.base.api import APIView, NobitexAPIError
from exchange.base.parsers import parse_choices, parse_currency, parse_money
from exchange.liquidator import errors
from exchange.liquidator.models import LiquidationRequest


class LiquidationRequestCreateView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='10/1m', method='POST', block=True))
    def post(self, request, **_):
        """API for submitting liquidation request

        POST /QA/liquidation-requests
        """
        src_currency = parse_currency(self.g('src'), required=True)
        dst_currency = parse_currency(self.g('dst'), required=True)
        side = parse_choices(LiquidationRequest.SIDES, self.g('side'), required=True)
        amount = parse_money(self.g('amount'), required=True)
        service = parse_choices(LiquidationRequest.SERVICE_TYPES, self.g('service'), required=True)

        try:
            liquidation_request = LiquidationRequest.create(
                request.user.id, src_currency, dst_currency, side, amount, service=service
            )
        except errors.LiquidatorException as e:
            raise NobitexAPIError(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=e.__class__.__name__) from e

        return self.response(
            {
                'status': 'ok',
                'requestId': liquidation_request.id,
            }
        )

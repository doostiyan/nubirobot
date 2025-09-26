from django.conf import settings
from django.urls import reverse

from exchange.base.helpers import get_base_api_url

from .base import BaseShetabHandler


class NobitexHandler(BaseShetabHandler):
    @classmethod
    def sync(cls, deposit, request, **kwargs):
        from exchange.shetab.models import ShetabDeposit

        if settings.IS_PROD:
            raise TypeError('Nobitex gateway cannot be used in production!')

        if not deposit.pk or not deposit.user or not deposit.amount:
            return
        if deposit.broker != deposit.BROKER.nobitex:
            return
        if deposit.is_requested:
            confirmed_amount = request.POST.get('amount')
            if not confirmed_amount:
                deposit.status_code = 102998
            else:
                confirmed_amount = int(confirmed_amount)
                if confirmed_amount != deposit.amount:
                    deposit.status_code = 102997
                elif request.POST.get('status') == 'accept':
                    deposit.status_code = 1
                    deposit.user_card_number = '1234123412341234'
                else:
                    deposit.status_code = 102999
            deposit.save(update_fields=['status_code', 'user_card_number'])
        else:
            code = deposit.id
            gateway_redirect_url = get_base_api_url(trailing_slash=False) \
                + reverse('sandbox_gateway') \
                + f'?depositId={deposit.id}'

            deposit.status_code = ShetabDeposit.STATUS.pending_request
            if code and code != '0':
                deposit.status_code = 0
                deposit.nextpay_id = str(code)
                deposit.gateway_redirect_url = gateway_redirect_url
            deposit.save(update_fields=['status_code', 'nextpay_id', 'gateway_redirect_url'])

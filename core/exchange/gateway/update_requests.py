import datetime

from django.db.models import Q
from django.utils.timezone import now

from exchange.base.models import Settings
from exchange.gateway.gateway import available_gateway, create_callback_request
from exchange.gateway.models import PendingWalletRequest


def do_update_gateway_requests_round():
    if Settings.is_disabled('module_gateway'):
        print('[Notice] Gateway')
        return

    # Filtering new trades
    pg_requests = PendingWalletRequest.objects.filter(created_time__gte=now() - datetime.timedelta(hours=24))

    # Filtering buy/sell orders to process
    expire_requests = Q(status=PendingWalletRequest.STATUS.expired)
    paid_requests = Q(status=PendingWalletRequest.STATUS.paid)
    pg_pending_requests = pg_requests.exclude(expire_requests | paid_requests)

    # Processing Trades
    for pg_req in pg_pending_requests:
        available_gateway.get(pg_req.tp).get_request(pg_req)

    unsend_verified = Q(pg_req__created_at__lte=now() - datetime.timedelta(minutes=35))
    paid_unverified_requests = pg_requests.filter(paid_requests | unsend_verified)
    for pg_req in paid_unverified_requests:
        create_callback_request(pg_req)

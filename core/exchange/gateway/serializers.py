from exchange.base.serializers import register_serializer, serialize_currency, serialize_choices
from exchange.gateway.models import PendingWalletRequest, PaymentGatewayUser


@register_serializer(model=PaymentGatewayUser)
def serialize_payment_gateway_user(pg, opts):
    return {
        'siteName': pg.site_name,
        'domain': pg.domain,
        'apiKey': str(pg.api),
        'secretKey': str(pg.secret),
        'status': serialize_choices(PaymentGatewayUser.STATUS, pg.status)
    }


@register_serializer(model=PendingWalletRequest)
def serialize_pending_wallet_request(payment, opts):
    print(payment)
    return {
        'id': payment.pk,
        'reqID': payment.req_id,
        'pgReq': payment.pg_req,
        'uri': payment.uri,
        'address': payment.address,
        'cryptoAmount': payment.crypto_amount,
        'expiry': payment.expiry,
        'status': payment.status,
        'confirmations': payment.confirmations,
        'createdDate': payment.created_time,
        'type': serialize_currency(payment.tp),
        'exchangeRate': payment.rate,
        'txHash': payment.tx_hash,
        'verify': payment.verify,
        'settle': payment.settle,
        'createOrder': payment.create_order,
    }
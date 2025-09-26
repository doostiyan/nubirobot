from exchange.base.id_translation import encode_id
from exchange.base.serializers import register_serializer
from exchange.redeem.models import RedeemRequest


@register_serializer(model=RedeemRequest)
def serialize_redeem_request(redeem_request: RedeemRequest, opts=None):
    return {
        'plan': redeem_request.get_plan_display(),
        'user': redeem_request.user.email,
        'amount': redeem_request.amount,
        'redeemValue': redeem_request.redeem_value,
        'status': redeem_request.get_status_display(),
        'hasSana': redeem_request.has_sana,
        'srcTransactionId': encode_id(redeem_request.src_transaction_id)
        if redeem_request.src_transaction_id is not None
        else None,
        'dstTransactionId': encode_id(redeem_request.dst_transaction_id)
        if redeem_request.dst_transaction_id is not None
        else None,
    }

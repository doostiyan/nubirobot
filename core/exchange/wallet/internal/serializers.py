from typing import Any, Dict

from exchange.base.id_translation import encode_id
from exchange.base.serializers import register_serializer, serialize_choices, serialize_currency
from exchange.wallet.internal.types import TransactionResult
from exchange.wallet.models import Transaction


def serialize_tx(tx: Transaction) -> Dict[str, Any]:
    return {
        'id': encode_id(tx.pk),
        'amount': str(tx.amount),
        'currency': serialize_currency(tx.currency),
        'description': tx.description,
        'createdAt': tx.created_at.isoformat(),
        'balance': str(tx.balance),
        'refId': tx.ref_id,
        'refModule': tx.get_ref_module_display(),
        'type': serialize_choices(Transaction.TYPE, tx.tp),
    }


@register_serializer(model=TransactionResult)
def serialize_transaction_result(transaction_result: TransactionResult, opts=None):
    return {
        'tx': serialize_tx(transaction_result.tx) if transaction_result.tx else None,
        'error': transaction_result.error.__class__.__name__ if transaction_result.error else None,
    }

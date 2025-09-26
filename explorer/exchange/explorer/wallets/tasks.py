from copy import deepcopy
import pytz
import datetime
from django.db import transaction
from exchange.explorer.transactions.models import Transfer


def transaction_data(transaction_dto, network_id, operation):
    transaction_dto_copy = deepcopy(transaction_dto)
    data = transaction_dto_copy if isinstance(transaction_dto_copy, dict) else transaction_dto_copy.__dict__
    data.pop('confirmations', None)
    data['created_at'] = datetime.datetime.now(tz=pytz.UTC)
    data['network_id'] = network_id
    data['source_operation'] = operation
    from_address = data.pop('from_address', None)
    to_address = data.pop('to_address', None)
    data['from_address_str'] = from_address or ''
    data['to_address_str'] = to_address or ''
    data['memo'] = data.pop('memo', None) or ''

    return Transfer(**data)


def chunked_bulk_create(model, objects, batch_size, network, ignore_conflicts=False):
    """
    Perform bulk_create in chunks to handle large datasets.
    """
    # Iterate through the objects in chunks
    for i in range(0, len(objects), batch_size):
        chunk = objects[i:i + batch_size]
        with transaction.atomic():
            model.objects.for_network(network).bulk_create(chunk, ignore_conflicts=ignore_conflicts)

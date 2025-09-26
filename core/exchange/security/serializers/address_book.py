from exchange.base.serializers import register_serializer
from exchange.security.models import AddressBookItem


@register_serializer(model=AddressBookItem)
def serialize_address_book_item(address: AddressBookItem, opts):
    serialized = {
        'id': address.pk,
        'title': address.title,
        'address': address.address,
        'network': address.network,
        'createdAt': address.created_at,
    }
    if address.tag:
        serialized['tag'] = address.tag
    return serialized

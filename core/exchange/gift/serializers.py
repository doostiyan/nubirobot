from exchange.base.serializers import register_serializer, serialize_currency
from exchange.gift.models import GiftCard, GiftPackage
from exchange.gift.models import PostalOrder, Parcel


@register_serializer(model=GiftCard)
def serialize_gift_card(gift_card, opts=None):
    gift_status = gift_card.get_gift_status_display()
    package_type = gift_card.package_type
    gift_type = gift_card.get_gift_type_display()
    gift_design = gift_card.card_design.title

    return {
        'id': gift_card.pk,
        'full_name': gift_card.full_name,
        'address': gift_card.address,
        'mobile': gift_card.mobile,
        'postal_code': gift_card.postal_code,
        'package_type': package_type,
        'gift_sentence': gift_card.gift_sentence,
        'amount': gift_card.amount,
        'sender': gift_card.sender,
        'receiver': gift_card.receiver if gift_card.receiver else (
            gift_card.receiver_email if gift_card.receiver_email else gift_card.full_name
        ),
        'currency': serialize_currency(gift_card.currency),
        'gift_type': gift_type,
        'gift_status': gift_status,
        'card_design': gift_design,
        'created_at': gift_card.created_at,
        'redeem_date': gift_card.redeem_date,
    }


@register_serializer(model=Parcel)
def serialize_parcel(parcel, level=0):
    if level == 0:
        return {
            "weight": parcel.weight,
            "value": int(parcel.value),
            "dimension":
                {
                    "width": parcel.width,
                    "height": parcel.height,
                    "depth": parcel.depth
                }
        }
    return {
        "id": parcel.id,
        "content": parcel.content,
        "weight": parcel.weight,
        "value": parcel.value,
        "dimension":
            {
                "width": parcel.width,
                "height": parcel.height,
                "depth": parcel.depth
            }
    }


@register_serializer(model=PostalOrder)
def serialize_postal_order(postal_order, level=0):
    if level == 0:
        return {
            "source_city": postal_order.source_city,
            "destination_city": postal_order.destination_city,
            "parcels": [serialize_parcel(parcel) for parcel in postal_order.parcels.all()]
        }
    return {
        "sender":
            {
                "name": postal_order.sender_name,
                "contact":
                    {
                        "postal_code": postal_order.sender_postal_code,
                        "city": postal_order.source_city,
                        "address": postal_order.sender_address,
                        "phone_number": postal_order.sender_phone_number,
                    }
            },
        "receiver":
            {
                "name": postal_order.receiver_name,
                "contact":
                    {
                        "postal_code": postal_order.receiver_postal_code,
                        "city": postal_order.destination_city,
                        "address": postal_order.receiver_address,
                        "phone_number": postal_order.receiver_phone_number,
                    }
            },
        "provider_code": postal_order.provider_code,
        "payment_type": 1,
        "receiver_comment": postal_order.receiver_comment,
        "service_type": postal_order.service_type,
        "parcels": [serialize_parcel(parcel, level=1) for parcel in postal_order.parcels.all()]
    }


@register_serializer(model=GiftPackage)
def serialize_gift_package(package: GiftPackage, opts=None):
    return {
        'id': package.id,
        'name': package.name,
        'isInStock': True if package.stock > 0 else False,
        'weight': package.weight,
        'width': package.width,
        'height': package.height,
        'depth': package.depth,
        'canBatchRequest': package.can_batch_request,
        'images': [image.serve_url for image in package.images.all()],
    }

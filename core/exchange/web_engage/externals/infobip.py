from typing import Tuple

from exchange.integrations.infobip import InfoBipErrorCodes, InfoBipStatusCodes
from exchange.web_engage.types import ESPDeliveryStatusCode


def translate_infobip_status_codes(status_code: int) -> Tuple[int, str, str]:
    """
    Convert infoBip status codes to web_engage status codes
    Third parameter in response is Event that must be one of these options: SPAM, DELIVERED, BOUNCE or UNSUBSCRIBE
    """

    if status_code in [
        InfoBipStatusCodes.DELIVERED_TO_HANDSET.value,
        InfoBipStatusCodes.DELIVERED_TO_OPERATOR.value,
    ]:
        return ESPDeliveryStatusCode.SUCCESS.value, ESPDeliveryStatusCode.SUCCESS.name, "DELIVERED"
    elif status_code in [
        InfoBipStatusCodes.UNDELIVERABLE_NOT_DELIVERED.value,
        InfoBipStatusCodes.UNDELIVERABLE_REJECTED_OPERATOR.value,
    ]:
        return ESPDeliveryStatusCode.HARD_BOUNCE.value, ESPDeliveryStatusCode.HARD_BOUNCE.name, "BOUNCE"
    elif status_code in [
        InfoBipStatusCodes.REJECTED_NETWORK.value,
        InfoBipStatusCodes.REJECTED_PREFIX_MISSING.value,
        InfoBipStatusCodes.REJECTED_DND.value,
        InfoBipStatusCodes.REJECTED_SOURCE.value,
        InfoBipStatusCodes.REJECTED_NOT_ENOUGH_CREDITS.value,
        InfoBipStatusCodes.REJECTED_SENDER.value,
        InfoBipStatusCodes.REJECTED_DESTINATION_BLOCK.value,
        InfoBipStatusCodes.REJECTED_PREPAID_PACKAGE_EXPIRED.value,
        InfoBipStatusCodes.REJECTED_DESTINATION_NOT_REGISTERED.value,
        InfoBipStatusCodes.REJECTED_ROUTE_NOT_AVAILABLE.value,
        InfoBipStatusCodes.REJECTED_FLOODING_FILTER.value,
        InfoBipStatusCodes.REJECTED_SYSTEM_ERROR.value,
        InfoBipStatusCodes.REJECTED_DUPLICATE_MESSAGE_ID.value,
        InfoBipStatusCodes.REJECTED_INVALID_UDH.value,
        InfoBipStatusCodes.REJECTED_MESSAGE_TOO_LONG.value,
        InfoBipStatusCodes.MISSING_TO.value,
        InfoBipStatusCodes.REJECTED_DESTINATION.value,
    ]:
        return ESPDeliveryStatusCode.ESP_REJECTED_MESSAGE.value, ESPDeliveryStatusCode.ESP_REJECTED_MESSAGE.name, ""
    elif status_code in [
        InfoBipStatusCodes.EXPIRED_EXPIRED.value,
        InfoBipStatusCodes.EXPIRED_DLR_UNKNOWN.value,
    ]:
        return ESPDeliveryStatusCode.REQUEST_TO_ESP_EXPIRED.value, ESPDeliveryStatusCode.REQUEST_TO_ESP_EXPIRED.name, ""


def translate_infobip_error_codes(error_code: int) -> Tuple[any, str]:
    try:
        error_code = int(error_code)

        if error_code == InfoBipErrorCodes.NO_ERROR.value:
            return ESPDeliveryStatusCode.SUCCESS.value, ESPDeliveryStatusCode.SUCCESS.name

        elif error_code in [
            InfoBipErrorCodes.EC_BOUNCED_EMAIL_ADDRESS.value,
            InfoBipErrorCodes.EC_EMAIL_DROPPED.value,
        ]:
            return ESPDeliveryStatusCode.SOFT_BOUNCE.value, ESPDeliveryStatusCode.SOFT_BOUNCE.name

        elif error_code == InfoBipErrorCodes.EC_EMAILS_SPAM_CONTENT.value:
            return ESPDeliveryStatusCode.EMAIL_REPORTED_AS_SPAM.value, ESPDeliveryStatusCode.EMAIL_REPORTED_AS_SPAM.name

        elif error_code == InfoBipErrorCodes.EC_EMAIL_UNSUBSCRIBED_EMAIL_ADDRESS.value:
            return ESPDeliveryStatusCode.EMAIL_UNSUBSCRIBED.value, ESPDeliveryStatusCode.EMAIL_UNSUBSCRIBED.name

        elif error_code == InfoBipErrorCodes.EC_DEFERRED_DUE_TO_INSUFFICIENT_STORAGE.value:
            return (
                ESPDeliveryStatusCode.RECIPIENTS_MAIL_BOX_IS_FULL.value,
                ESPDeliveryStatusCode.RECIPIENTS_MAIL_BOX_IS_FULL.name,
            )

        elif error_code in [
            InfoBipErrorCodes.EC_MAILBOX_TEMPORARY_UNAVAILABLE.value,
            InfoBipErrorCodes.EC_MAILBOX_UNAVAILABLE.value,
        ]:
            return (
                ESPDeliveryStatusCode.MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER.value,
                ESPDeliveryStatusCode.MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER.name,
            )

        elif error_code == InfoBipErrorCodes.EC_EMAIL_BLACKLISTED.value:
            return (
                ESPDeliveryStatusCode.EMAIL_IN_SUPPRESSION_LIST.value,
                ESPDeliveryStatusCode.EMAIL_IN_SUPPRESSION_LIST.name,
            )

        elif error_code == InfoBipErrorCodes.EC_STORAGE_LIMIT_EXCEEDED.value:
            return (
                ESPDeliveryStatusCode.MESSAGE_SENDING_QUOTA_EXCEEDED.value,
                ESPDeliveryStatusCode.MESSAGE_SENDING_QUOTA_EXCEEDED.name,
            )

        elif error_code in [
            InfoBipErrorCodes.EC_TEMPORARY_SENDING_ERROR.value,
            InfoBipErrorCodes.EC_PERMANENT_SENDING_ERROR.value,
            InfoBipErrorCodes.EC_EMAIL_GATEWAY_ERROR.value,
        ]:
            return ESPDeliveryStatusCode.THROTTLING_ERROR.value, ESPDeliveryStatusCode.THROTTLING_ERROR.name

        elif error_code == InfoBipErrorCodes.EC_INVALID_EMAIL_ADDRESS.value:
            return ESPDeliveryStatusCode.INVALID_EMAIL_ADDRESS.value, ESPDeliveryStatusCode.INVALID_EMAIL_ADDRESS.name

    except Exception as e:
        if error_code == 'UNAUTHORIZED':
            return ESPDeliveryStatusCode.AUTHORIZATION_FAILURE.value, ESPDeliveryStatusCode.AUTHORIZATION_FAILURE.name
        raise e

    return ESPDeliveryStatusCode.UNKNOWN_REASON.value, ESPDeliveryStatusCode.UNKNOWN_REASON.name

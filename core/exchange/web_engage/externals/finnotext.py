from exchange.web_engage.types import SmsStatusData, SSPDeliveryStatusCode


def parse_finnotext_response_code(
    finnotext_inquiry_status: int, webengage_number: str, message_id: str
) -> SmsStatusData:
    # successful states . see FINNOTEXT_INQUIRY_ERROR_CODES
    if finnotext_inquiry_status in [1, 11, 19, 20, 21, 22, 24, 100]:
        return SmsStatusData(
            message_id=message_id,
            phone_number=webengage_number,
            status="sms_sent",
            status_code=SSPDeliveryStatusCode.SUCCESS,
            message='',
        )

    elif finnotext_inquiry_status == 10:
        return SmsStatusData(
            message_id=message_id,
            phone_number=webengage_number,
            status="sms_failed",
            status_code=SSPDeliveryStatusCode.MESSAGE_NOT_DELIVERED_BY_MOBILE_NETWORK,
            message="The message was not delivered by the mobile network operator.",
        )

    elif finnotext_inquiry_status in [0, 5]:
        return SmsStatusData(status="sms_accepted")

    elif finnotext_inquiry_status == 23:
        return SmsStatusData(
            message_id=message_id,
            phone_number=webengage_number,
            status="sms_failed",
            status_code=SSPDeliveryStatusCode.RECIPIENT_BLACKLISTED,
            message="blacklisted",
        )
    elif finnotext_inquiry_status == 25:
        return SmsStatusData(
            message_id=message_id,
            phone_number=webengage_number,
            status="sms_failed",
            status_code=SSPDeliveryStatusCode.INVALID_SENDER_ID,
            message="Invalid sender ID",
        )
    else:
        return SmsStatusData(
            message_id=message_id,
            phone_number=webengage_number,
            status="sms_failed",
            status_code=SSPDeliveryStatusCode.UNKNOWN_REASON,
            message="Unknown Reason",
        )

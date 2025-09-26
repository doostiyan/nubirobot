from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ESPDeliveryStatusCode(Enum):
    SUCCESS = 1000
    THROTTLING_ERROR = 9001
    MESSAGE_SENDING_QUOTA_EXCEEDED = 9002
    AUTHENTICATION_FAILURE = 9003
    RECIPIENT_ADDRESS_NOT_SPECIFIED = 9004
    FROM_FIELD_MISSING = 9005
    SOFT_BOUNCE = 9006
    HARD_BOUNCE = 9007
    EMAIL_REPORTED_AS_SPAM = 9008
    EMAIL_UNSUBSCRIBED = 9009
    EMAIL_IN_SUPPRESSION_LIST = 9010
    SENDER_ADDRESS_NOT_VERIFIED = 9011
    ESP_REJECTED_MESSAGE = 9012
    REQUEST_TO_ESP_EXPIRED = 9013
    ESP_UNAVAILABLE = 9014
    IP_NOT_WHITELISTED_WITH_ESP = 9015
    SUBJECT_FIELD_EMPTY = 9016
    INVALID_SENDER_ADDRESS = 9017
    INVALID_EMAIL_ADDRESS = 9018
    RECIPIENTS_MAIL_BOX_IS_FULL = 9019
    ERROR_PROCESSING_EMAIL_AT_ESP = 9020
    MAILBOX_WAS_NOT_FOUND_ON_MAIL_SERVER = 9021
    UNSUPPORTED_OR_UNKNOWN_VERSION = 9022
    AUTHORIZATION_FAILURE = 9024
    MESSAGE_OVERLOADING = 9452
    HOST_EMAIL_SERVER_NOT_FOUND = 9512
    UNKNOWN_REASON = 9999


class SSPDeliveryStatusCode(Enum):
    SUCCESS = 0
    INSUFFICIENT_CREDIT_BALANCE = 2000
    IP_NOT_WHITE_LISTED = 2001
    EMPTY_MESSAGE_BODY = 2002
    INVALID_MOBILE_NUMBER = 2003
    INVALID_SENDER_ID = 2004
    AUTHORIZATION_FAILURE = 2004
    MAX_BODY_LENGTH_EXCEEDED = 2007
    MESSAGE_EXPIRED = 2008
    MESSAGE_NOT_DELIVERED_BY_MOBILE_NETWORK = 2009
    UNSUPPORTED_PAYLOAD_VERSION = 2010
    AUTHENTICATION_FAILURE = 2011
    THROTTLING_ERROR = 2015
    RECIPIENT_BLACKLISTED = 3000
    UNKNOWN_REASON = 9988


@dataclass
class UserOrderSummary:
    last_order_date: str
    first_order_date: str
    total_order_value_code: int
    total_orders: int


@dataclass
class UserData:
    user: "User"
    order_summary: UserOrderSummary
    marketing_campaign_id: Optional[str]


@dataclass
class UserReferralData:
    web_engage_user_id: str
    referred_count: int
    authorized_count: int

@dataclass
class SmsStatusData:
    message_id: str
    phone_number: str
    status: str
    status_code: SSPDeliveryStatusCode
    message: str


@dataclass
class EmailStatusEventData:
    message_id: str
    email: str
    event: str
    status_code: int
    message: str
    timestamp: int


@dataclass
class SmsMessage:
    receiver_number: str
    message_id: str
    body: str

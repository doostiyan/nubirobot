import dataclasses
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Callable

from exchange.accounts.kyc_param_notifier.enums import KYCParamForNotify, KYCParamNotifyType
from exchange.accounts.models import User


class NotifierInterface(ABC):
    """
    Interface for notifying users.

    This interface hides the actual implementation of the ``notifier`` module
    (see the notifier package) from the client.
    In the current case the facade object (instance of ``KYCParamNotifyFacade``)
    requires this interface for sending updates (SMS, Email, Notification) for
    users.
    """

    @staticmethod
    def configure_notifier(
        notify_type: KYCParamNotifyType, kyc_param: KYCParamForNotify, kyc_object: Any, user: User, confirmed: bool
    ) -> 'NotifierInterface':
        """
        Instantiate and return an object that provides this interface.

        Args:
            notify_type: EMAIL, NOTIFICATION, SMS,
            kyc_param: the parameter related to KYC (Identity, Mobile, ...) that
            got rejected or confirmed,
            kyc_object: the object that advocates the ``kyc_param`` being rejected or
            confirmed. for example a ``VerificationRequest`` object advocates that identity
            of user is rejected.
            user: the user we try to notify of its KYC parameter being confirmed or rejected.
            confirmed: shows whether the KYC parameter is confirmed or rejected.

        Returns:
            NotifierInterface: an object with the ``notify_user`` method.
        """
        from exchange.accounts.kyc_param_notifier.notify import Notifier, MessageBuilder, SMSMessageBuilder

        if notify_type == SMS:
            message_builder = SMSMessageBuilder(kyc_param, user, confirmed)
        else:
            message_builder = MessageBuilder(kyc_param, kyc_object, user, confirmed)
        return Notifier(notify_type, user, kyc_param, confirmed, message_builder)

    @abstractmethod
    def notify_user(self):
        """
        Notifies users in any type (SMS, Email, Notification) the notifier object finds relevant.

        The only interface clients of this interface must see from the notifier package.
        Returns:
            None
        """
        pass


EMAIL, NOTIFICATION, SMS = KYCParamNotifyType.EMAIL, KYCParamNotifyType.NOTIFICATION, KYCParamNotifyType.SMS


@dataclasses.dataclass
class NotifySituation:
    confirmation_status: List[bool]
    notify_types: List[KYCParamNotifyType]
    preconditions: Callable[[User, Any], bool] = lambda user, kyc_object: True


"""
Notify policies pairs off each kyc param (see ``KYCParamForNotify``) with a list of
situations that it must have a notify.

Examples
--------

The following example shows a policy for ``KYCParamForNotify.BANK_CARD`` which manifests
two situations. First one states that whenever a bank card gets confirmed or rejected
(``confirmation_status=[True, False]``) the system must notify by notification.
The second one states that whenever a bank card gets confirmed or rejected the system
must notify by SMS under the condition that the bank_card is being updated from cron
(``kyc_object.updating_from_cron``).

.. code-block:: python

    NOTIFY_POLICIES: Dict[KYCParamForNotify, List[NotifySituation]] = {
        # Other params go here
        KYCParamForNotify.BANK_CARD: [
            NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION]),
            NotifySituation(
                confirmation_status=[True, False], notify_types=[SMS],
                preconditions=lambda user, kyc_object: kyc_object.updating_from_cron
            ),
        ],
    }
"""
NOTIFY_POLICIES: Dict[KYCParamForNotify, List[NotifySituation]] = {
    KYCParamForNotify.EMAIL: [
        NotifySituation(
            confirmation_status=[True, ], notify_types=[NOTIFICATION, EMAIL],
            preconditions=lambda user, *_: user.has_verified_mobile_number,
        ),
    ],
    KYCParamForNotify.MOBILE: [
        NotifySituation(
            confirmation_status=[True, ], notify_types=[NOTIFICATION, EMAIL],
            preconditions=lambda user, *_: user.is_email_verified
        ),
    ],
    KYCParamForNotify.IDENTITY: [
        NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION, EMAIL]),
        NotifySituation(
            confirmation_status=[False], notify_types=[SMS],
            preconditions=lambda user, kyc_object: kyc_object.updating_from_cron
        ),
    ],
    KYCParamForNotify.MOBILE_IDENTITY: [
        NotifySituation(confirmation_status=[True], notify_types=[NOTIFICATION, EMAIL]),
    ],
    KYCParamForNotify.BANK_ACCOUNT: [
        NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION]),
    ],
    KYCParamForNotify.BANK_CARD: [
        NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION]),
    ],
    KYCParamForNotify.ADDRESS: [
        NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION, EMAIL]),
    ],
    KYCParamForNotify.SELFIE: [
        NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION, EMAIL, SMS]),
    ],
    KYCParamForNotify.AUTO_KYC: [
        NotifySituation(confirmation_status=[True, False], notify_types=[NOTIFICATION, EMAIL, SMS]),
    ]
}

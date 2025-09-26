from typing import Any, Generator

from exchange.accounts.kyc_param_notifier.enums import KYCParamForNotify, KYCParamNotifyType
from exchange.accounts.kyc_param_notifier.policy import NOTIFY_POLICIES, NotifierInterface, NotifySituation
from exchange.accounts.models import User


class KYCParamNotifyFacade:
    """
    Facade class for requiring the services of the ``kyc_param_notifier`` module.

    Instances of this class work as gates for triggering services related to KYC notify
    (whether the notify type is Email, Notification, SMS).

    An object of this facade instantiates the ``notify`` module (see the notify package)
    using the data received from its client and the data that resides in the
    ``policy`` module (see the policy.py file).

    Examples
    --------

    **Instantiating and Using:**

    .. code-block:: python

        notify_facade = KYCParamNotifyFacade(kyc_param, user, confirmed, kyc_object)
        notify_facade.try_notifying_kyc_param()
    """

    def __init__(self, kyc_param: KYCParamForNotify, user: User, confirmed: bool, kyc_object: Any):
        """
        Args:
            kyc_param: the parameter related to KYC (Identity, Mobile, ...) that
            got rejected or confirmed,
            user: the user we try to notify of its KYC parameter being confirmed or rejected.
            confirmed: shows whether the KYC parameter is confirmed or rejected.
            kyc_object: the object that advocates the ``kyc_param`` being rejected or
            confirmed. for example a ``VerificationRequest`` object advocates that identity
            of user is rejected.
        """
        self.kyc_param = kyc_param
        self.user = user
        self.confirmed = confirmed
        self.kyc_object = kyc_object

    def _compatible_with_notify_type(self, notify_type: KYCParamNotifyType) -> bool:
        if notify_type == KYCParamNotifyType.EMAIL and not self.user.is_email_verified:
            return False
        if notify_type == KYCParamNotifyType.SMS and not self.user.has_verified_mobile_number:
            return False
        return True

    def _get_notify_situations(self) -> Generator[NotifySituation, None, None]:
        for situation in NOTIFY_POLICIES[self.kyc_param]:
            if self.confirmed in situation.confirmation_status and situation.preconditions(self.user, self.kyc_object):
                yield situation

    def _try_notifying_kyc_param_in_situation(self, situation: NotifySituation):
        for notify_type in situation.notify_types:
            if self._compatible_with_notify_type(notify_type):
                NotifierInterface.configure_notifier(
                    notify_type, self.kyc_param, self.kyc_object, self.user, self.confirmed
                ).notify_user()

    def try_notifying_kyc_param(self):
        for situation in self._get_notify_situations():
            self._try_notifying_kyc_param_in_situation(situation)


def try_notifying_kyc_param(
    kyc_param: KYCParamForNotify, user: User, confirmed: bool, kyc_object: Any
):
    """
    Easy access to `KYCParamNotifyFacade`.
    """
    KYCParamNotifyFacade(kyc_param, user, confirmed, kyc_object).try_notifying_kyc_param()

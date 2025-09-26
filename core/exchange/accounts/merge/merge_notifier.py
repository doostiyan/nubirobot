from exchange.accounts.functions import hide_email_address, hide_mobile_number
from exchange.accounts.merge import MergeRequestStatusChangedContext, UserData
from exchange.accounts.models import User, UserMergeRequest, UserSms
from exchange.base.tasks import send_email


class MergeNotifier:
    """
    The implementation of sending notifications (Email, SMS).
    This class notifies users after merge request accepted by Support Team.
    This class requires the merge_request object and the merge_data,
      which contains user information prior to merging the users.

    Public Method:
    - send: Sends notifications to both users.

    Usage:
    1. Create an instance of the MergeNotifier class.
    2. Call the send() method to trigger the notification process,
       which will notify the second user and the main user.
    """

    def __init__(self, merge_request: UserMergeRequest, merge_data: MergeRequestStatusChangedContext) -> None:
        self.merge_request = merge_request
        self.merge_data = merge_data

    def _get_users_data_base_on_merge_kind(self):
        """
        This function provides the user data that needs to be included in the text notification.
        """
        main_accounts = (
            hide_mobile_number(self.merge_data.main_user.mobile)
            if self.merge_data.main_user.mobile
            else hide_email_address(self.merge_data.main_user.email)
        )
        if self.merge_request.merge_by == UserMergeRequest.MERGE_BY.email:
            return main_accounts, hide_email_address(self.merge_data.second_user.email)
        return main_accounts, hide_mobile_number(self.merge_data.second_user.mobile)

    def _notify_by_sms(self, receiver: User, mobile: str) -> None:
        main_account_data, second_account_data = self._get_users_data_base_on_merge_kind()
        duration = '۲۴ساعت'
        UserSms.objects.create(
            user=receiver,
            tp=UserSms.TYPES.user_merge,
            to=mobile,
            template=UserSms.TEMPLATES.user_merge_successful,
            text=second_account_data + '\n' + main_account_data + '\n' + duration,
        )

    def _notify_by_email(self, email: str) -> None:
        main_account_data, second_account_data = self._get_users_data_base_on_merge_kind()
        data = {
            'second_account': main_account_data,
            'main_account': second_account_data,
        }
        send_email(email, 'merge/successful_message', data=data, priority='medium')

    def _notify_user(self, user: User, user_data: UserData):
        """
        Notifies user on the available contact methods(mobile, email)
        """
        if user_data.mobile and user_data.is_mobile_confirmed:
            self._notify_by_sms(user, user_data.mobile)

        if user_data.email and user_data.is_email_confirmed:
            self._notify_by_email(user_data.email)

    def send(self):
        """
        Sends notifications to main and second user in merge request
        """
        self._notify_user(self.merge_request.main_user, self.merge_data.main_user)
        self._notify_user(self.merge_request.second_user, self.merge_data.second_user)

from typing import Optional

from django.conf import settings
from django.db.models import Q
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from exchange.accounts.exceptions import (
    CheckMobileIdentityError,
    HasActiveMergeRequestError,
    HasReferralProgramError,
    HasTransactionError,
    IncompatibleUserLevelError,
    InvalidUserError,
    MaxMergeRequestExceededError,
    OTPVerificationError,
    SameUserError,
    UserHasEmailError,
)
from exchange.accounts.merge import MergeHandler
from exchange.accounts.models import User, UserMergeRequest
from exchange.base.api import APIView, Http404, ParseError, SemanticAPIError
from exchange.base.normalizers import normalize_email, normalize_mobile
from exchange.base.parsers import parse_str


def merge_request_ratelimit(group, request):
    """Ratelimit checker for leadership request POST and GET APIs. Used for increasing ratelimit for testnet."""
    return '5/h' if settings.IS_PROD else '30/h'


class CreateMergeRequestView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_email = False

    @method_decorator(ratelimit(key='user_or_ip', rate=merge_request_ratelimit, method='POST', block=True))
    def post(self, request):
        """API for merge request

        POST users/create-merge-request
        """
        email = parse_str(self.g('email'))
        mobile = parse_str(self.g('mobile'))
        if email and mobile:
            raise ParseError('Fill one of Email Or Mobile Fields.')
        self.is_email = bool(email)

        second_account = self._identify_second_account(email, mobile)
        try:
            merge_request = self._merge_request(request.user, second_account)
        except SameUserError as e:
            raise SemanticAPIError('SameUserError', 'User can not merge with self.') from e
        except InvalidUserError as e:
            raise SemanticAPIError('InvalidUserError', 'User Does Not Exist.') from e
        except IncompatibleUserLevelError as e:
            raise SemanticAPIError('IncompatibleUserLevelError', 'User has not allowed request: ' + str(e)) from e
        except HasTransactionError as e:
            raise SemanticAPIError('HasTransactionError', 'User has transaction.') from e
        except HasReferralProgramError as e:
            raise SemanticAPIError('HasReferralProgramError', 'User has referral program.') from e
        except HasActiveMergeRequestError as e:
            raise SemanticAPIError('HasActiveMergeRequestError', 'User has active merge request.') from e
        except CheckMobileIdentityError as e:
            raise SemanticAPIError('CheckMobileIdentityError', 'Check mobile identity error.') from e
        except UserHasEmailError as e:
            raise SemanticAPIError('UserHasEmailError', 'User has email.') from e
        except MaxMergeRequestExceededError as e:
            raise SemanticAPIError(
                'MaxMergeRequestExceededError', 'User has exceeded the maximum allowed merge requests.'
            ) from e

        if merge_request is None:
            raise ParseError('Fill Email Or Mobile Field.')

        return self.response(
            {
                'status': 'ok',
                'merge_request': merge_request,
            },
        )

    def _identify_second_account(self, email: Optional[str] = None, mobile: Optional[str] = None) -> User:
        if self.is_email:
            email = normalize_email(email)
            the_query = Q(email=email)
        else:
            mobile = normalize_mobile(mobile)
            the_query = Q(mobile=mobile)

        return User.objects.filter(the_query).first()

    def _merge_request(self, main_account: User, second_account: User):
        merge_by = UserMergeRequest.MERGE_BY.email if self.is_email else UserMergeRequest.MERGE_BY.mobile
        if main_account is None:
            raise InvalidUserError
        if second_account is None:
            raise InvalidUserError
        return MergeHandler(main_account, second_account, merge_by).initiate_request()


class VerifyMergeRequestView(APIView):

    @classmethod
    def get_merge_request(cls, user: User):
        merge_request = UserMergeRequest.objects.filter(
            main_user=user,
            status__in=[
                UserMergeRequest.STATUS.email_otp_sent,
                UserMergeRequest.STATUS.new_mobile_otp_sent,
                UserMergeRequest.STATUS.old_mobile_otp_sent,
            ],
        ).last()
        if not merge_request:
            raise Http404
        return merge_request

    @method_decorator(ratelimit(key='user_or_ip', rate=merge_request_ratelimit, method='POST', block=True))
    def post(self, request, **_):
        """API for merge request

        POST users/verify-merge-request
        """
        otp = parse_str(self.g('otp'), required=True)
        merge_request: UserMergeRequest = self.get_merge_request(self.request.user)
        try:
            merge_request = MergeHandler(
                merge_request.main_user,
                merge_request.second_user,
                merge_request.merge_by,
            ).proceed_request(
                otp,
                merge_request,
            )

        except IncompatibleUserLevelError as e:
            raise SemanticAPIError('IncompatibleUserLevelError', 'User has not allowed request: '+ str(e)) from e
        except HasTransactionError as e:
            raise SemanticAPIError('HasTransactionError', 'User has transaction.') from e
        except HasReferralProgramError as e:
            raise SemanticAPIError('HasReferralProgramError', 'User has referral program.') from e
        except HasActiveMergeRequestError as e:
            raise SemanticAPIError('HasActiveMergeRequestError', 'User has active merge request.') from e
        except OTPVerificationError as e:
            raise SemanticAPIError('OTPVerificationError', 'OTP does not verified:' + str(e)) from e
        except UserHasEmailError as e:
            raise SemanticAPIError('UserHasEmailError', 'User has email.') from e

        return self.response(
            {
                'status': 'ok',
                'merge_request': merge_request,
            },
        )

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List

from django.contrib.contenttypes.models import ContentType
from django.db.models import F, Q

from exchange.accounts.models import (
    AdminConsideration,
    ChangeMobileRequest,
    UpgradeLevel3Request,
    User,
    VerificationProfile,
    VerificationRequest,
)


@dataclass
class RejectionReason:
    reason: str
    reason_fa: str
    description: str = ''

    def fill_description(self, vr: VerificationRequest) -> None:
        _content_type = ContentType.objects.get(model='verificationrequest')
        admin_consideration: AdminConsideration = (
            AdminConsideration.objects.filter(content_type=_content_type, object_id=vr.id)
            .order_by('-created_at')
            .first()
        )
        self.description = admin_consideration.user_consideration if admin_consideration else ''


class ReasonTypes(Enum):
    USER_NO_MOBILE = RejectionReason('UserDoesNotHaveMobile', 'کاربر موبایل ندارد.')
    USER_ADDRESS_NOT_VALID = RejectionReason('UserAddressIsNotValid', 'اطلاعات سکونتی کاربر تکمیل نیست.')
    IDENTITY_REJECTED = RejectionReason('IdentityRequestRejected', 'اطلاعات هویتی رد شده است.', '')
    SELFIE_REJECTED = RejectionReason('SelfieRequestRejected', 'درخواست احراز هویت شما رد شده است.')
    AUTO_KYC_REJECTED = RejectionReason('AutoKycRequestRejected', 'درخواست احراز خودکار شما رد شده است.')


class VRRejectionReason:
    """verification request rejection explanations"""

    def __init__(self, vr_type_list: List[int]):
        self.vr_type_list = vr_type_list

    def _make_reason_response(self, vr_type, vr: VerificationRequest) -> RejectionReason:
        reject_reason = {
            VerificationRequest.TYPES.identity: ReasonTypes.IDENTITY_REJECTED.value,
            VerificationRequest.TYPES.selfie: ReasonTypes.SELFIE_REJECTED.value,
            VerificationRequest.TYPES.address: ReasonTypes.USER_ADDRESS_NOT_VALID.value,
            VerificationRequest.TYPES.auto_kyc: ReasonTypes.AUTO_KYC_REJECTED.value,
        }.get(vr_type)
        reject_reason.fill_description(vr)
        return reject_reason

    def get_rejection_explanation(self, user: User) -> List[RejectionReason]:
        list_reasons = []
        for vr_type in self.vr_type_list:
            _vr_type_filter = Q(tp=vr_type)
            vr: VerificationRequest = user.verification_requests.filter(
                _vr_type_filter,
                status=VerificationRequest.STATUS.rejected,
            ).order_by('-created_at').first()
            if vr:
                list_reasons.append(self._make_reason_response(vr_type, vr))
        return list_reasons


class LevelsRejectionReasonHandler(ABC):
    vr_type_list: []

    def __init__(self, user):
        self.user = user
        self.vp: VerificationProfile = self.user.get_verification_profile()

    def get_rejection_explanation(self) -> List[RejectionReason]:
        return VRRejectionReason(self.vr_type_list).get_rejection_explanation(self.user)

    @abstractmethod
    def get_rejection_reasons(self) -> List[RejectionReason]:
        pass


class Level1RejectionHandler(LevelsRejectionReasonHandler):
    vr_type_list = [VerificationRequest.TYPES.identity]

    def get_rejection_reasons(self) -> List[RejectionReason]:
        list_reasons = []
        last_mobile_req: ChangeMobileRequest = self.user.mobile_change_requests.order_by('-created_at').first()
        if last_mobile_req and last_mobile_req.status != ChangeMobileRequest.STATUS.success and \
                not self.user.has_verified_mobile_number:

            list_reasons.append(ReasonTypes.USER_NO_MOBILE.value)
        if not self.vp.identity_confirmed:
            list_reasons.extend(self.get_rejection_explanation())
        return list_reasons


class Level2RejectionHandler(LevelsRejectionReasonHandler):
    vr_type_list = [
        VerificationRequest.TYPES.selfie,
        VerificationRequest.TYPES.auto_kyc,
        VerificationRequest.TYPES.address,
    ]

    def get_rejection_reasons(self) -> List[RejectionReason]:
        list_reasons = []
        if not all([self.vp.identity_liveness_confirmed, self.vp.selfie_confirmed]) or not self.vp.address_confirmed:
            list_reasons = self.get_rejection_explanation()
        return list_reasons


class Level3RejectionHandler(LevelsRejectionReasonHandler):
    def get_rejection_reasons(self) -> List[RejectionReason]:
        list_reasons = []
        if self.user.user_type >= User.USER_TYPES.verified:
            return list_reasons

        _request = (
            UpgradeLevel3Request.objects.filter(
                user=self.user,
            )
            .order_by(F('closed_at').desc(nulls_last=True))
            .first()
        )
        if not _request:
            list_reasons.append('Level3RequestNotFound')
        elif _request.status == UpgradeLevel3Request.STATUS.pre_conditions_approved and not _request.closed_at:
            list_reasons.append('PendingToApproveRequest')
        elif _request.status == UpgradeLevel3Request.STATUS.rejected:
            list_reasons.append(_request.reject_reason)

        return list_reasons


def get_rejection_reasons(user: User) -> List[RejectionReason]:
    level_rejection_handler = {
        User.USER_TYPES.level0: Level1RejectionHandler,
        User.USER_TYPES.level1: Level2RejectionHandler,
        User.USER_TYPES.level2: Level3RejectionHandler,
    }[user.user_type](user)
    return level_rejection_handler.get_rejection_reasons()

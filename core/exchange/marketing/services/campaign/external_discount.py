import uuid
from typing import Any, Dict, Optional

from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Q, When

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.decorators import cached_method
from exchange.marketing.exceptions import (
    InvalidCampaignException,
    InvalidUserIDException,
    MissionHasNotBeenCompleted,
    NoDiscountCodeIsAvailable,
    RewardHasBeenAlreadyAssigned,
)
from exchange.marketing.models import ExternalDiscount
from exchange.marketing.services.campaign.base import (
    CampaignType,
    MobileVerificationBasedCampaign,
    RewardBasedCampaign,
    UserCampaignInfo,
    UserIdentifier,
    UserIdentifierType,
    UTMParameters,
)
from exchange.marketing.services.mission.base import BaseMission, BaseMissionProgressStatus
from exchange.marketing.types import UserInfo
from exchange.marketing.utils import parse_time
from exchange.web_engage.services.ssp import queue_message_to_send
from exchange.web_engage.tasks import task_send_user_campaign_data_to_web_engage
from exchange.web_engage.types import SmsMessage


class ExternalDiscountCampaign(MobileVerificationBasedCampaign, RewardBasedCampaign):

    type = CampaignType.EXTERNAL_DISCOUNT

    def __init__(self, _id, mission: BaseMission):
        self.id = _id
        self.mission = mission

    def verify_otp(
        self,
        user_identifier: UserIdentifier,
        verification_code: str,
        utm_params: UTMParameters,
    ) -> UserCampaignInfo:
        result = super().verify_otp(user_identifier, verification_code, utm_params)
        if not self.mission:
            return result

        return self.join(result.user_details, utm_params)

    def join(self, user_info: UserInfo, utm_params=None) -> UserCampaignInfo:
        self.check_campaign_date()

        if user_info.user_id:
            user_identifier = UserIdentifier(user_info.user_id, type=UserIdentifierType.SYSTEM_USER_ID)
        else:
            user_identifier = UserIdentifier(user_info.mobile_number, type=UserIdentifierType.MOBILE)

        details = self.mission.initiate(user_info, self.id)
        details = self._append_campaign_details(user_identifier, details)

        if user_info.webengage_id:
            task_send_user_campaign_data_to_web_engage.delay(
                webengage_user_id=user_info.webengage_id,
                campaign_id=self.id,
            )

        return UserCampaignInfo(user_details=user_info, campaign_details=details)

    def check_campaign_date(self):
        current_time = ir_now()
        settings = self.get_settings()

        if 'end_time' in settings:
            end_time = parse_time(settings['end_time'], '%Y-%m-%d %H:%M:%S')
            if current_time > end_time:
                raise InvalidCampaignException('campaign is expired')

        if 'start_time' in settings:
            start_time = parse_time(settings['start_time'], '%Y-%m-%d %H:%M:%S')
            if current_time < start_time:
                raise InvalidCampaignException('campaign is not started')

    def get_campaign_details(self, user_info: UserInfo) -> Dict[str, Any]:
        if user_info.user_id is None:
            raise InvalidUserIDException()

        details = self.mission.get_progress_details(user_info, self.id) if self.mission else {}
        return self._append_campaign_details(
            UserIdentifier(user_info.user_id, UserIdentifierType.SYSTEM_USER_ID), details
        )

    def _append_campaign_details(self, user_identifier: UserIdentifier, details) -> Dict[str, Any]:
        discount = self._get_discount_by_user_identifier(user_identifier)
        if discount:
            details['status'] = 'REWARDED'
            details['reward_content'] = discount.code

        return details

    def _check_mission_is_completed(self, user: User):
        if not self.mission:
            return

        user_info = UserInfo(
            user_id=user.pk,
            mobile_number=user.mobile,
            level=user.user_type,
            webengage_id=user.get_webengage_id(),
        )
        if not self.mission.is_done(user_info, self.id):
            raise MissionHasNotBeenCompleted()

    @transaction.atomic
    def send_reward(self, user_identifier: UserIdentifier, **kwargs):
        try:
            user = self._get_user_by_identifier(user_identifier)
            self._check_mission_is_completed(user)
            discount = self.assign_discount(user)
            self.send_discount_sms(user, discount)
        except IntegrityError as e:
            raise RewardHasBeenAlreadyAssigned(
                'there is an external discount for the requested user and campaign'
            ) from e

    def assign_discount(self, user: User):
        current_time = ir_now()

        discount = (
            ExternalDiscount.objects.select_for_update(skip_locked=True)
            .filter(enabled_at__lte=current_time, campaign_id=self.id, user__isnull=True)
            .order_by('id')
            .first()
        )
        if not discount:
            raise NoDiscountCodeIsAvailable()

        discount.user = user
        discount.assigned_at = current_time
        discount.save(update_fields=['user', 'assigned_at'])
        return discount

    def send_discount_sms(self, user: User, discount: ExternalDiscount):
        """sending sms message through marketing ssp service"""
        sms_template = self.get_settings().get('reward_sms_template', '')
        if sms_template.strip() == '':
            return

        sms_text = sms_template.format(name=user.first_name, discount_code=discount.code)
        queue_message_to_send(
            SmsMessage(message_id='cmp-' + str(uuid.uuid4()), receiver_number=user.get_webengage_id(), body=sms_text),
        )

    def _get_discount_by_user_identifier(self, user_identifier: UserIdentifier) -> Optional[ExternalDiscount]:
        return ExternalDiscount.objects.filter(
            **self._get_user_query_filter(user_identifier, user_prefix=True),
            campaign_id=self.id,
        ).first()

    def is_user_participated(self, user_info: UserInfo) -> Optional[bool]:
        status = self.mission.get_progress_details(user_info, self.id).get('status', '')
        return status != BaseMissionProgressStatus.NOT_STARTED.value

    @classmethod
    def _get_user_query_filter(cls, user_identifier: UserIdentifier, user_prefix: bool = False):
        relation_prefix = 'user__' if user_prefix else ''
        if user_identifier.type == UserIdentifierType.WEBENGAGE_USER_ID:
            return {relation_prefix + 'webengage_cuid': user_identifier.id}
        if user_identifier.type == UserIdentifierType.SYSTEM_USER_ID:
            return {relation_prefix + 'pk': user_identifier.id}
        if user_identifier.type == UserIdentifierType.MOBILE:
            return {relation_prefix + 'mobile': user_identifier.id}
        if user_identifier.type == UserIdentifierType.EMAIL:
            return {relation_prefix + 'email': user_identifier.id}

        raise InvalidUserIDException()

    @classmethod
    def _get_user_by_identifier(cls, user_identifier: UserIdentifier) -> User:
        user = User.objects.filter(**cls._get_user_query_filter(user_identifier)).first()
        if user is None:
            raise User.DoesNotExist
        return user

    @cached_method(timeout=30)
    def get_capacity_details(self) -> Dict[str, Any]:
        counts = ExternalDiscount.objects.filter(campaign_id=self.id).aggregate(
            total_discounts=Count('id'),
            free_discounts=Count(
                Case(
                    When(Q(user__isnull=True) & Q(enabled_at__lte=ir_now()), then=1),
                    output_field=IntegerField(),
                )
            ),
            assigned_discounts=Count(Case(When(user__isnull=False, then=1), output_field=IntegerField())),
        )
        return {
            'total': counts.get('total_discounts', 0),
            'available': counts.get('free_discounts', 0),
            'assigned': counts.get('assigned_discounts', 0),
        }

from enum import Enum
from typing import Any, Dict

from django.core.cache import cache
from django.utils import timezone

from exchange.accounts.models import ReferralProgram, User, UserReferral
from exchange.marketing.exceptions import InvalidUserIDException
from exchange.marketing.services.mission.base import BaseMission
from exchange.marketing.types import UserInfo


class MissionTarget(Enum):
    KYC = 'KYC'
    USER_REFER = 'USER_REFER'


class MissionProgressStatus(Enum):
    NOT_STARTED = 'NOT_STARTED'
    NEEDS_KYC = 'NEEDS_KYC'
    NEEDS_REFER_A_USER = 'NEEDS_REFER_A_USER'
    DONE = 'DONE'


class KycOrReferMission(BaseMission):

    validity_duration = 20 * 24 * 60 * 60  # 20 days

    @classmethod
    def initiate(cls, user_info: UserInfo, campaign_id: str) -> Dict[str, Any]:
        if not user_info.mobile_number:
            raise InvalidUserIDException('user must have mobile number')

        history = cache.get(cls._get_cache_key(campaign_id, user_info.mobile_number))
        if history:
            return cls._get_progress_details(user_info, campaign_id, history)

        mission_target = (
            MissionTarget.USER_REFER
            if user_info.user_id and user_info.level >= User.USER_TYPE_LEVEL1
            else MissionTarget.KYC
        )
        referral_program = None
        if mission_target == MissionTarget.USER_REFER:
            referral_program = cls._get_or_create_referral_program(user_info.user_id, campaign_id)

        history = {
            'target': mission_target.value,
            'user_level': user_info.level if user_info.level else -1,
            'timestamp': timezone.now(),
        }
        cache.set(cls._get_cache_key(campaign_id, user_info.mobile_number), history, timeout=cls.validity_duration)
        return cls._get_progress_details(user_info, campaign_id, history, referral_program)

    @classmethod
    def _get_or_create_referral_program(cls, user_id, campaign_id):
        campaign_mission_tag = cls._get_campaign_tag(campaign_id)
        target_referral, err = ReferralProgram.create(
            User(id=user_id), 0, agenda=ReferralProgram.AGENDA.default, description=campaign_mission_tag
        )
        if target_referral:
            return target_referral

        if err != 'TooManyReferralLinks':
            raise Exception(err)

        target_referral = (
            ReferralProgram.objects.filter(user_id=user_id, agenda=ReferralProgram.AGENDA.default)
            .order_by('-created_at')
            .first()
        )
        target_referral.description = campaign_mission_tag
        target_referral.save(update_fields=['description'])
        return target_referral

    @staticmethod
    def _get_campaign_tag(campaign_id: str) -> str:
        return f'campaign_mission->{campaign_id}'

    @classmethod
    def is_done(cls, user_info: UserInfo, campaign_id):
        return cls.get_progress_details(user_info, campaign_id)['status'] == MissionProgressStatus.DONE.value

    @classmethod
    def get_progress_details(cls, user_info: UserInfo, campaign_id) -> Dict[str, Any]:
        history = cache.get(cls._get_cache_key(campaign_id, user_info.mobile_number))
        if not history:
            return {'status': MissionProgressStatus.NOT_STARTED.value}

        return cls._get_progress_details(user_info, campaign_id, history)

    @classmethod
    def _get_progress_details(cls, user_info: UserInfo, campaign_id, history, referral_program=None) -> Dict[str, Any]:
        if history['target'] == MissionTarget.KYC.value:
            return {
                'status': cls._get_progress_status(history, user_info).value,
            }

        if user_info.user_id and not referral_program:
            referral_program = ReferralProgram.objects.filter(
                user_id=user_info.user_id,
                agenda=ReferralProgram.AGENDA.default,
                description=cls._get_campaign_tag(campaign_id),
            ).first()

        return {
            'status': cls._get_progress_status(history, user_info).value,
            'referral_code': referral_program.referral_code if referral_program else None,
        }

    @classmethod
    def _get_progress_status(cls, history, user_info: UserInfo):
        if history['target'] == MissionTarget.KYC.value:
            return (
                MissionProgressStatus.DONE
                if user_info.level and user_info.level > history['user_level']
                else MissionProgressStatus.NEEDS_KYC
            )

        # for refer target ->
        referral_count = cls._get_referral_count(user_info.user_id, history['timestamp'])
        return MissionProgressStatus.DONE if referral_count > 0 else MissionProgressStatus.NEEDS_REFER_A_USER

    @staticmethod
    def _get_referral_count(user_id, timestamp_from):
        return UserReferral.objects.filter(
            parent_id=user_id,
            child__user_type__gte=User.USER_TYPES.level1,
            created_at__gte=timestamp_from,
        ).count()

    @staticmethod
    def _get_cache_key(campaign_id, mobile_number):
        return f'campaign_mission:{campaign_id}:{mobile_number}'

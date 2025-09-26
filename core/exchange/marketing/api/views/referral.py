from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status

from exchange.accounts.models import User
from exchange.base.api import APIView
from exchange.base.models import Settings
from exchange.marketing.services.campaign.base import CampaignType, to_user_info
from exchange.marketing.services.campaign.selector import choose_campaign_by_type


class ReferralCampaign(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='50/10m', method='GET', block=True))
    def get(self, request):
        """GET /marketing/campaign/referral
        This API returns the count of bonuses that the user has earned in the referral campaign.
        """
        user: User = request.user
        shamsi_start_date = Settings.get_value('referral_campaign_start_date')
        shamsi_end_date = Settings.get_value('referral_campaign_end_date')
        if not all([shamsi_end_date, shamsi_start_date]):
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'ValidationError',
                    'message': 'Date range of the campaign is not defined',
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        service = choose_campaign_by_type(CampaignType.REFERRAL)
        details = service.get_campaign_details(to_user_info(user))

        return self.response(
            {
                'status': 'ok',
                'referredCount': details.get('users_referred_count') or 0,
                'authorizedCount': details.get('authorized_user_referrals') or 0,
                'totalBonus': details.get('total_bonus') or 0,
            }
        )

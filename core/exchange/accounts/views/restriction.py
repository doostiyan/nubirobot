from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import UserRestriction
from exchange.base.api import APIView


class UserRestrictionView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='30/h', method='GET', block=True))
    def get(self, request):
        allowed_restrictions = [
            UserRestriction.RESTRICTION.WithdrawRequest,
            UserRestriction.RESTRICTION.ShetabDeposit,
            UserRestriction.RESTRICTION.WithdrawRequestCoin,
            UserRestriction.RESTRICTION.WithdrawRequestRial,
        ]

        restrictions = (
            UserRestriction.objects.filter(user=request.user, restriction__in=allowed_restrictions)
            .order_by('-created_at')
            .prefetch_related('restriction_removals')
        )
        return self.response({'status': 'ok', 'restrictions': restrictions})

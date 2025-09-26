from django.http import Http404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.response import Response

from exchange.asset_backed_credit.api.views import InternalABCView, exceptions
from exchange.asset_backed_credit.api.views.exceptions import APIError422
from exchange.asset_backed_credit.exceptions import ThirdPartyError, UpdateClosedUserService, UserServiceHasActiveDebt
from exchange.asset_backed_credit.models import UserService
from exchange.asset_backed_credit.services.user_service import force_close_user_service, get_user_service_debt
from exchange.base.api_v2_1 import InternalAPIView
from exchange.base.decorators import measure_api_execution
from exchange.base.internal.permissions import AllowedServices
from exchange.base.internal.services import Services

ALLOWED_SERVICES_PERMISSION = AllowedServices((Services.ADMIN,))


class UserServiceDebtView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcUserServiceDebt'))
    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request, user_service_id):
        """
        GET /asset-backed-credit/services/<int:user_service_id>/debt
        """
        try:
            used_balance = get_user_service_debt(user_service_id, request.user)
            return self.response({'status': 'ok', 'usedBalance': used_balance})
        except UserService.DoesNotExist as e:
            raise Http404() from e
        except ThirdPartyError as e:
            raise APIError422(
                message=e.__class__.__name__,
                description=str(e),
            ) from e
        except NotImplementedError as e:
            raise exceptions.APIError501(
                message=e.__class__.__name__,
                description=str(e),
            ) from e


class UserServiceForceCloseView(InternalAPIView):
    permission_classes = [ALLOWED_SERVICES_PERMISSION]

    @method_decorator(measure_api_execution(api_label='abcUserFinancialServiceLimitCreate'))
    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request, user_service_id, *args, **kwargs):
        try:
            force_close_user_service(user_service_id)
        except UserService.DoesNotExist:
            return Response(
                data={'status': 'failure', 'message': 'UserServiceDoesNotExist'}, status=status.HTTP_404_NOT_FOUND
            )
        except (UpdateClosedUserService, NotImplementedError, UserServiceHasActiveDebt, ThirdPartyError) as e:
            return Response(
                data={'status': 'failure', 'message': e.__class__.__name__}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        return Response(data={'status': 'ok', 'message': 'user service closed'}, status=status.HTTP_200_OK)

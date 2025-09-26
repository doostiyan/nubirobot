from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from exchange.explorer.accounts.serializers import UserSerializer
from exchange.explorer.accounts.services import get_user_dto
from exchange.explorer.authentication.services.jwt import StatefulAPIAuthentication


class UserDashboardView(APIView):
    renderer_classes = (JSONRenderer,)
    authentication_classes = [StatefulAPIAuthentication, ]
    permission_classes = [IsAuthenticated, ]

    @swagger_auto_schema(
        operation_id='user_dashboard',
        operation_description='Retrieve dashboard of account.'
    )
    def get(self, request: Request) -> Response:
        user = request.user
        user_dto = get_user_dto(user)
        user_serializer = UserSerializer(instance=user_dto)
        user_data = user_serializer.data
        return Response(data=user_data)

from django.contrib.auth import authenticate, login
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from exchange.explorer.authentication.serializers.jwt import JWTAuthSerializer
from exchange.explorer.authentication.services.jwt import get_auth_token_dto_for_user
from exchange.explorer.utils.prometheus import exceptions_counter, get_request_info


class LoginView(APIView):
    @swagger_auto_schema(
        operation_id='login',
        operation_description='Login by an account.',
    )
    def post(self, request: Request) -> Response:
        labels = get_request_info(request)
        if 'username' not in request.data or 'password' not in request.data:
            exceptions_counter.lables(**labels, type='bad_request').inc()
            exceptions_counter.labels()
            return Response({'msg': 'Credentials missing'}, status=status.HTTP_400_BAD_REQUEST)
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            auth_token_dto = get_auth_token_dto_for_user(request.user)
            auth_token_serializer = JWTAuthSerializer(data=auth_token_dto.get_data())
            auth_token_serializer.is_valid(raise_exception=True)
            auth_token_data = auth_token_serializer.data
            return Response({'msg': 'Login Success', 'data': auth_token_data}, status=status.HTTP_200_OK)
        exceptions_counter.lables(**labels, type='authentication_failed').inc()
        return Response({'msg': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from drf_yasg.utils import swagger_auto_schema

from ..services import decode_token


class TokenBlacklistView(APIView):
    @swagger_auto_schema(
        operation_id='token_blacklist',
        operation_description='This endpoint handles the blacklisting of a refresh token, which essentially revokes its validity.'
    )
    def post(self, request):
        try:
            refresh = request.data["refresh"]
            refresh_token = decode_token(token_str=refresh, token_type='refresh')
            refresh_token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            # TODO raise appropriate exception
            return Response(status=status.HTTP_400_BAD_REQUEST)


class TokenObtainPairView(APIView):
    @swagger_auto_schema(
        operation_id='token_obtain_pair',
        operation_description='This endpoint is responsible for generating a new pair of tokens: an access token and a refresh token, which are typically used in JWT-based authentication.'
    )
    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    @swagger_auto_schema(
        operation_id='token_refresh',
        operation_description='This endpoint allows a user to obtain a new access token using a valid refresh token.'
    )
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(serializer.validated_data, status=status.HTTP_200_OK)

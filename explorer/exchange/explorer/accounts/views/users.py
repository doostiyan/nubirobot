from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.views import APIView, Response

from exchange.explorer.accounts.serializers import RegistrationSerializer, UserSerializer
from exchange.explorer.accounts.services import delete_api_key, get_api_keys_dto, get_user_dtos
from exchange.explorer.authentication.serializers import APIKeySerializer
from exchange.explorer.authentication.services.jwt import StatefulAPIAuthentication
from exchange.explorer.utils.exception import BadRequestException, ErrorDTO
from exchange.explorer.utils.prometheus import exceptions_counter, get_request_info
from exchange.explorer.utils.views import PermissionRequiredAPIView


class UserListView(PermissionRequiredAPIView):
    authentication_classes = [StatefulAPIAuthentication, ]
    permission_classes = [IsAdminUser, ]
    permission_required = {
        'get': ['accounts.view_user', ],
        'post': ['accounts.add_user', ],
    }

    @swagger_auto_schema(
        responses={200: UserSerializer(many=True)},
        operation_description='Get information of  registered users'
    )
    def get(self) -> Response:
        user_dtos = get_user_dtos()
        users_serializer = UserSerializer(instance=user_dtos, many=True)
        return Response(data=users_serializer.data)

    @swagger_auto_schema(
        responses={201: RegistrationSerializer(many=False)},
        request_body=RegistrationSerializer(many=False),
        operation_description='Register a new user'
    )
    def post(self, request: Request) -> Response:
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        message_code = BadRequestException.message_code
        response = ErrorDTO(code=BadRequestException.code,
                            message_code=message_code,
                            detail=serializer.errors).get_data()
        labels = get_request_info(request)
        exceptions_counter.labels(**labels, type=message_code).inc()
        return Response(response, status=response['code'])


class UserAPIKeyView(APIView):
    renderer_classes = (JSONRenderer,)
    authentication_classes = [StatefulAPIAuthentication, ]
    permission_classes = [IsAdminUser, ]
    permission_required = {
        'post': ['authentication.add_user_api_key', ],
    }

    @swagger_auto_schema(
        operation_id='api_key_list',
        operation_description='List all API keys for a user',
    )
    def get(self, request: Request) -> Response:
        revoked = request.query_params.get('revoked', '').lower() == 'true'
        api_keys_dtos = get_api_keys_dto(revoked)
        api_keys_serializer = APIKeySerializer(instance=api_keys_dtos, many=True)
        return Response(data=api_keys_serializer.data)

    @swagger_auto_schema(
        responses={201: APIKeySerializer(many=False)},
        request_body=APIKeySerializer(many=False),
        operation_id='api_key_create',
        operation_description='Create a new API key for a user',
    )
    def post(self, request: Request) -> Response:
        serializer = APIKeySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        message_code = BadRequestException.message_code
        response = ErrorDTO(code=BadRequestException.code,
                            message_code=message_code,
                            detail=serializer.errors).get_data()
        labels = get_request_info(request)
        exceptions_counter.labels(**labels, type=message_code).inc()
        return Response(response, status=response['code'])

    @swagger_auto_schema(
        operation_id='api_key_delete',
        operation_description='Delete an API key for a user',
    )
    def delete(self, request: Request) -> Response:
        api_key = request.query_params.get('api_key')
        delete_api_key(api_key)
        return Response({'API Key deactivate successfully.'}, status=status.HTTP_204_NO_CONTENT)

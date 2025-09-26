from django.contrib.auth import logout
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class LogoutView(APIView):
    @swagger_auto_schema(
        operation_id='logout',
        operation_description='Logout a user.'
    )
    def post(self, request:Request) -> Response:
        logout(request)
        return Response({'msg': 'Successfully Logged out'}, status=status.HTTP_200_OK)

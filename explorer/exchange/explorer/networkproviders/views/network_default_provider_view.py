from pickle import FALSE

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from exchange.blockchain.ws.rpc_pb2 import Failure
from ..serializers import (NetworkDefaultProviderDetailSerializer,
                           NetworkDefaultProviderSerializer)
from ..services.network_default_provider_service import NetworkDefaultProviderService
from ...authentication.services import StatefulAPIAuthentication


class NetworkDefaultProviderListView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser]


    @swagger_auto_schema(
        operation_id='networkproviders_defaultproviders_list',
        operation_description='Retrieve list of all default providers',
        responses={200: NetworkDefaultProviderSerializer(many=False)},
    )
    def get(self, request):
        ndps = NetworkDefaultProviderService.get_all_default_providers()

        return Response(NetworkDefaultProviderDetailSerializer(ndps, many=True).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_defaultproviders_create',
        operation_description='Update or create a default provider for a network',
        responses={200: NetworkDefaultProviderSerializer(many=False)},
        request_body=NetworkDefaultProviderSerializer(many=False),
    )
    def post(self, request):
        data = request.data
        serializer = NetworkDefaultProviderSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        provider_id = data.get('provider_id')
        operation = data.get('operation')
        network_name = data.get('network')
        ndp = NetworkDefaultProviderService.update_or_create_default_provider(provider_id, operation, network_name)
        if ndp:
            return Response(NetworkDefaultProviderSerializer(ndp).data, status=status.HTTP_201_CREATED)
        else:
            return Response(
                data={'msg': 'Failed to update or create default provider.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NetworkDefaultProviderDetailByNameView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser]

    operation_param = openapi.Parameter(
        'operation',
        openapi.IN_QUERY,
        description="Comma-separated list of operations to filter providers by",
        type=openapi.TYPE_STRING
    )

    @swagger_auto_schema(
        operation_id='networkproviders_defaultproviders_read',
        operation_description='Get detailed information of a network provider and operation',
        responses={200: NetworkDefaultProviderDetailSerializer(many=False)},
        manual_parameters=[operation_param]

    )
    def get(self,  request, network_name):
        operation = request.query_params.get('operation')

        ndps = NetworkDefaultProviderService.get_default_providers_by_network_name_filter_operation(
            network_name,
            operation
        )

        return Response(NetworkDefaultProviderDetailSerializer(ndps, many=True).data, status=status.HTTP_200_OK)

from django.db import models
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from drf_yasg.utils import swagger_auto_schema


from ..models import Network
from ..serializers import NetworkSerializer
from ..services.network_service import NetworkService
from ...authentication.services import StatefulAPIAuthentication


class NetworkListView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_networks_list',
        operation_description='Retrieve list of all networks',
        responses={200: NetworkSerializer(many=False)},
    )
    def get(self, request):
        networks = NetworkService.get_all_networks()

        return Response(NetworkSerializer(networks, many=True).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_networks_create',
        operation_description='Create a network',
        responses={200: NetworkSerializer(many=False)},
        request_body=NetworkSerializer(many=False),
    )
    def post(self, request):
        data = request.data
        serializer = NetworkSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        name = data.get('name')
        block_limit_per_req = data.get('block_limit_per_req')

        network = NetworkService.create_network(name, block_limit_per_req)

        return Response(NetworkSerializer(network).data, status=status.HTTP_201_CREATED)


class NetworkDetailByIdView(APIView):
    authentication_classes = [StatefulAPIAuthentication, ]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_networks_read',
        operation_description='Get detailed information of a network by network id',
        responses={200: NetworkSerializer(many=False)},
    )
    def get(self, request, network_id):
        network = NetworkService.get_network_by_id(network_id)

        return Response(NetworkSerializer(network).data, status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_networks_update',
        operation_description='Update information of a network by network id like network name or new_block_limit_per_req',
        responses={200: NetworkSerializer(many=False)},
        request_body=NetworkSerializer(many=False),
    )
    def put(self, request, network_id):
        data = request.data
        try:
            instance = Network.objects.get(id=network_id)
        except models.ObjectDoesNotExist:
            raise Http404(f"Network id {network_id} does not exists.")
        serializer = NetworkSerializer(instance, data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        new_name = data.get('name')
        new_block_limit_per_req = data.get('block_limit_per_req')

        network = NetworkService.update_network(network_id, new_name, new_block_limit_per_req)

        return Response(NetworkSerializer(network).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_networks_delete',
        operation_description='Delete information of a network by network id',
        responses={200: NetworkSerializer(many=False)},
    )
    def delete(self, request, network_id):
        NetworkService.delete_network(network_id)

        return Response(status=status.HTTP_204_NO_CONTENT)


class NetworkDetailByNameView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_networks_read_name',
        operation_description='Get detailed information of a network by network name',
        responses={200: NetworkSerializer(many=False)},
    )
    def get(self, request, network_name):
        network = NetworkService.get_network_by_name(network_name)

        return Response(NetworkSerializer(network).data, status.HTTP_200_OK)

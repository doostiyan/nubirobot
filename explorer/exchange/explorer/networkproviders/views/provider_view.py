from django.http import Http404
from django.db import models
from drf_yasg import openapi
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from drf_yasg.utils import swagger_auto_schema


from ..models import Provider
from ..serializers import ProviderDetailSerializer, ProviderSerializer
from ..serializers.provider_serializer import CheckProviderSerializer, CheckProviderResultSerializer
from ..serializers.url_serializer import URLSerializer
from ..services.check_network_provider_service import CheckNetworkProviderService
from ..services.provider_service import ProviderService
from ...authentication.services import StatefulAPIAuthentication


class ProviderListView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_providers_list',
        operation_description='Retrieve list of all providers',
        responses={200:  ProviderSerializer(many=False)},
    )
    def get(self, request):
        providers = ProviderService.get_all_providers()
        return Response(ProviderDetailSerializer(providers, many=True).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_providers_create',
        operation_description='Create a provider for network with operations',
        responses={200: ProviderSerializer(many=False)},
        request_body=ProviderSerializer(many=False),
    )
    def post(self, request):
        data = request.data
        serializer = ProviderSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        name = data.get('name')
        network_id = data.get('network_id')
        support_batch = data.get('support_batch')
        batch_block_limit = data.get('batch_block_limit')
        supported_operations = data.get('supported_operations')
        default_url = data.get('default_url')

        provider = ProviderService.create_provider(name, network_id, support_batch, batch_block_limit,
                                                   supported_operations, default_url)
        return Response(ProviderSerializer(provider).data, status=status.HTTP_201_CREATED)


class ProviderDetailByIdView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_providers_read_id',
        operation_description='Get provider details by provider_id',
        responses={200: ProviderDetailSerializer(many=False)},
    )
    def get(self, request, provider_id):
        provider = ProviderService.get_provider_by_id(provider_id)
        return Response(ProviderDetailSerializer(provider).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_providers_update_id',
        operation_description='Update provider details by provider_id',
        responses={200: ProviderDetailSerializer(many=False)},
        request_body=ProviderDetailSerializer(many=False),
    )
    def put(self, request, provider_id):
        data = request.data
        try:
            instance = Provider.objects.get(id=provider_id)
        except models.ObjectDoesNotExist:
            raise Http404(f"Provider id {provider_id} does not exists.")
        serializer = ProviderSerializer(instance, data=data, partial=False)
        serializer.is_valid(raise_exception=True)
        new_name = data.get('name')
        new_network_id = data.get('network_id')
        new_support_batch = data.get('support_batch')
        new_batch_block_limit = data.get('batch_block_limit')
        new_supported_operations = data.getlist('supported_operations')
        new_default_url = data.get('default_url')

        provider = ProviderService.update_provider(provider_id, new_name, new_network_id, new_support_batch,
                                                   new_batch_block_limit, new_supported_operations, new_default_url)

        return Response(ProviderSerializer(provider).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_providers_delete_id',
        operation_description='Delete provider details by provider_id',
        responses={200: ProviderDetailSerializer(many=False)},
    )
    def delete(self, request, provider_id):
        ProviderService.delete_provider(provider_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderDetailByNetworkView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser]

    operations_param = openapi.Parameter(
        'operations',
        openapi.IN_QUERY,
        description="Comma-separated list of operations to filter providers by",
        type=openapi.TYPE_STRING
    )

    @swagger_auto_schema(
        operation_id='networkproviders_providers_read_detail_name',
        operation_description='Get detailed information of a provider by network and operations',
        responses={200: CheckProviderSerializer(many=False)},
        manual_parameters=[operations_param]
    )
    def get(self, request, network_name):
        operations = request.query_params.get('operations')
        operation_list = operations.replace(" ", "").split(',') if operations else []

        providers = ProviderService.get_providers_by_network_name_and_operation(network_name, operation_list)
        return Response(ProviderDetailSerializer(providers, many=True).data, status=status.HTTP_200_OK)


class URLListByProviderIdView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_id='networkproviders_providers_urls_list',
        operation_description='Get list of urls for a provider by provider_id',
        responses={200: URLSerializer(many=False)},
    )
    def get(self, request, provider_id):
        urls = ProviderService.get_all_urls(provider_id)
        return Response(URLSerializer(urls, many=True).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_providers_urls_create',
        operation_description='Create url for a provider by provider_id',
        responses={200: URLSerializer(many=False)},
        request_body=URLSerializer(many=False),
    )
    def post(self, request, provider_id):
        data = request.data
        try:
            instance = Provider.objects.get(id=provider_id)
        except models.ObjectDoesNotExist:
            raise Http404(f"Provider id {provider_id} does not exists.")
        serializer = ProviderSerializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        url_id = data.get('url_id')
        provider = ProviderService.add_url_to_provider(instance, url_id)
        return Response(ProviderSerializer(provider).data, status=status.HTTP_200_OK)


class URLDetailByProviderIdView(APIView):

    @swagger_auto_schema(
        operation_id='networkproviders_providers_urls_delete',
        operation_description='Delete a url for a provider by provider_id and url_id',
        responses={200: URLSerializer(many=False)},
    )
    def delete(self, request, provider_id, url_id):
        data = request.data
        try:
            instance = Provider.objects.get(id=provider_id)
        except models.ObjectDoesNotExist:
            raise Http404(f"Provider id {provider_id} does not exists.")
        serializer = ProviderSerializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        provider = ProviderService.remove_url_from_provider(provider_id, url_id)
        return Response(ProviderSerializer(provider).data, status=status.HTTP_200_OK)


class CheckProviderByIdView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser]

    @swagger_auto_schema(
        operation_id='networkproviders_providers_check_create',
        operation_description='Check a provider by provider_id, operation and base_url',
        responses={200: CheckProviderResultSerializer(many=False)},
        request_body=CheckProviderSerializer(many=False),
    )
    def post(self, request, provider_id):
        serializer = CheckProviderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.data
        base_url = data.get('base_url')
        operation = data.get('operation')
        result_dto = CheckNetworkProviderService.check_provider(provider_id=provider_id,
                                                                base_url=base_url,
                                                                operation=operation)

        data = CheckProviderResultSerializer(instance=result_dto).data

        return Response(data=data)

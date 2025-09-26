from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response

from exchange.explorer.authentication.services import StatefulAPIAuthentication
from exchange.explorer.networkproviders.serializers.url_serializer import URLSerializer
from exchange.explorer.networkproviders.services.url_service import UrlService


class URLListView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_urls_list',
        operation_description='Retrieve list of all urls',
        responses={200: URLSerializer(many=False)},
    )
    def get(self, request):
        urls = UrlService.get_all_urls()
        serializer = URLSerializer(urls, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_urls_create',
        operation_description='Create a url',
        responses={200: URLSerializer(many=False)},
        request_body=URLSerializer(many=False),
    )
    def post(self, request):
        data = request.data
        serializer = URLSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        use_proxy = data.get('use_proxy', False)
        url = UrlService.create_url(data.get('url'), use_proxy=use_proxy)

        return Response(URLSerializer(url).data, status=status.HTTP_201_CREATED)


class URLDetailView(APIView):
    authentication_classes = [StatefulAPIAuthentication]
    permission_classes = [IsAdminUser, ]

    @swagger_auto_schema(
        operation_id='networkproviders_urls_read',
        operation_description='Get a url details by url_id',
        responses={200: URLSerializer(many=False)},
    )
    def get(self, request, url_id):
        url = UrlService.get_url_by_id(url_id)
        serializer = URLSerializer(url)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_urls_update',
        operation_description='Update a url details by url_id',
        responses={200: URLSerializer(many=False)},
        request_body=URLSerializer(many=False),
    )
    def put(self, request, url_id):
        data = request.data
        new_url = data.get('url')
        new_use_proxy = data.get('use_proxy', False)
        updated_url = UrlService.update_url(url_id, new_url=new_url, new_use_proxy=new_use_proxy)
        serializer = URLSerializer(updated_url)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_id='networkproviders_urls_delete',
        operation_description='Delete a url by url_id',
        responses={200: URLSerializer(many=False)},
    )
    def delete(self, request, url_id):
        UrlService.delete_url(url_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

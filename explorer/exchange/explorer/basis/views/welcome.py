from drf_yasg.utils import swagger_auto_schema

from django.shortcuts import HttpResponse
from rest_framework.views import APIView


class WelcomeView(APIView):
    swagger_schema = None

    def get(self, request):
        return HttpResponse('Welcome!')

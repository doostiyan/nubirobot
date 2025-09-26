from rest_framework.permissions import IsAdminUser
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView, Response
from drf_yasg.utils import swagger_auto_schema

from ..authentication.services.jwt import StatefulAPIAuthentication
from ..utils.cache import CacheUtils


# Create your views here.
class MonitorApiView(APIView):
    renderer_classes = (JSONRenderer,)
    authentication_classes = [StatefulAPIAuthentication, ]
    permission_classes = [IsAdminUser]

    swagger_schema = None

    def get(self, request, format=None):
        key = request.query_params['key']
        cache_name = request.query_params['cache']
        value = CacheUtils.read_from_local_cache(key, cache_name)
        return Response(data={key: value})

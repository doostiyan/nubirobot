from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from exchange.explorer.authentication.permissions import UserHasAPIKey
from exchange.explorer.authentication.services.throttling import APIKeyRateThrottle
from exchange.explorer.utils.exception import QueryParamMissingException

from .serializers.block import BlockHeadSerializer, BlockInfoSerializer
from .services import BlockExplorerService


class BlockInfoView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        responses={200: BlockInfoSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter(
                'after_block_number',
                openapi.IN_QUERY,
                description='Start from a specific block number',
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
            openapi.Parameter(
                'to_block_number',
                openapi.IN_QUERY,
                description='To a specific block number',
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
        ],
        operation_id='block_info',
        operation_description='Retrieve the transactions(including details) of blocks by setting a from and '
                              'to block_number in specific network.'
    )
    # @histogram_observer
    def get(self, request: Request, network: str) -> Response:
        required_params = ['after_block_number', 'to_block_number']
        missing_params = list(
            filter(lambda p: p not in request.query_params or not request.query_params[p], required_params))
        if missing_params:
            raise QueryParamMissingException(missing_params=missing_params)

        network = network.upper()

        after_block_number = int(request.query_params.get('after_block_number'))
        to_block_number = int(request.query_params.get('to_block_number'))

        block_info_dto = BlockExplorerService.get_latest_block_info_dto(
            network=network,
            after_block_number=after_block_number,
            to_block_number=to_block_number,
            include_inputs=True,
            include_info=True,
        )
        block_info_serializer = BlockInfoSerializer(instance=block_info_dto)
        return Response(data=block_info_serializer.data)


class BlockHeadView(APIView):
    permission_classes = [UserHasAPIKey]
    throttle_classes = [APIKeyRateThrottle]

    @swagger_auto_schema(
        operation_id='block_head',
        operation_description='Retrieve the blockhead of a network.',
        responses={200: BlockHeadSerializer(many=False)},
    )
    # @histogram_observer
    def get(self, _: Request, network: str) -> Response:
        network = network.upper()
        block_head_dto = BlockExplorerService.get_block_head(network)
        block_head_serializer = BlockHeadSerializer(block_head_dto)
        return Response(data=block_head_serializer.data)

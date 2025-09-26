import json
from uuid import uuid4

import websocket
from django.conf import settings
from django.http import Http404, JsonResponse
from rest_framework import status
from websocket import WebSocketTimeoutException

from exchange.base.api_v2_1 import api, public_api
from exchange.ws.healthcheck import healthcheck_publisher


@api(POST='5/1m')
def healthcheck_ws_publish(request):
    if not settings.IS_TESTNET and not settings.DEBUG:
        raise Http404

    is_ok, data = healthcheck_publisher(channel_postfix=f'#{request.user.id}', message=request.data)
    if is_ok is False:
        return JsonResponse(
            {
                'status': 'failed',
                'error': data,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return JsonResponse(
        {
            'status': 'ok',
            'published_message': data.message,
            'channel': data.channel,
        },
        status=status.HTTP_200_OK,
    )


@public_api('5/1m')
def ws_status(request):
    ws = websocket.WebSocket()
    try:
        ws.settimeout(3)
        try:
            ws.connect(settings.WS_URL)
        except ConnectionRefusedError:
            return JsonResponse(
                {'status': 'failed', 'error': 'connection refused'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        ws.send(
            json.dumps(
                {
                    'id': 1,
                    'connect': {},
                },
            ),
        )
        try:
            ws.recv()
        except WebSocketTimeoutException:
            return JsonResponse(
                {'status': 'failed', 'error': 'connection timed out'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        unique_identifier = uuid4().hex[:6]
        channel_postfix = f'-status-check{unique_identifier}'
        channel_name = f'public:healthcheck{channel_postfix}'

        ws.send(
            json.dumps(
                {
                    'id': 2,
                    'subscribe': {'channel': channel_name},
                },
            ),
        )
        try:
            ws.recv()
        except WebSocketTimeoutException:
            return JsonResponse(
                {'status': 'failed', 'error': 'subscription timed out'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        random_string = uuid4().hex[:6]
        expected_message = {'status': f'expected_message {random_string}'}
        is_ok, publish_data = healthcheck_publisher(channel_postfix=channel_postfix, message=expected_message)
        if is_ok is False:
            return JsonResponse(
                {'status': 'failed', 'error': f'publish error {publish_data}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            data = json.loads(ws.recv())
        except WebSocketTimeoutException:
            return JsonResponse(
                {'status': 'failed', 'error': 'healthcheck push message timed out'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if data.get('push', {}).get('pub', {}).get('data') != expected_message:
            return JsonResponse(
                {'status': 'failed', 'error': f'invalid push data: {data}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return JsonResponse({'status': 'ok'}, status=status.HTTP_200_OK)
    finally:
        ws.close()

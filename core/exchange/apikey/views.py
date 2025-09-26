import datetime
import typing

import pydantic
from django.core import exceptions
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit
from rest_framework.request import Request

from exchange.accounts.functions import check_user_otp
from exchange.accounts.models import User
from exchange.apikey.cryptography import eddsa
from exchange.apikey.errors import convert_pydantic_validation_error
from exchange.apikey.models import Key
from exchange.apikey.notify import APIKeyNotifications
from exchange.apikey.serializers import (
    KeyCreationResponse,
    KeyListResponse,
    KeyRequest,
    KeySerializer,
    KeyUpdateRequest,
    KeyUpdateResponse,
)
from exchange.base.api import NobitexAPIError, get_api, post_api
from exchange.base.http import get_client_ip
from exchange.base.logstash_logging import loggers


def __audit_log(
    msg: str,
    user: User,
    request: Request,
    action: str,
    key: typing.Optional[str] = None,
    **kwargs,
):
    ip = get_client_ip(request)

    loggers.logstash_logger.info(
        msg,
        extra={
            'params': {
                'ip': ip,
                'method': action,
                'uid': user.uid,
                'key': key if key else '',
                'user_agent': str(request.headers.get('user-agent')),
                **kwargs,
            },
            'index_name': 'api_key_logger',
        },
    )

def __validate_otp(user: User, request: Request):
    otp = request.headers.get('x-totp')

    if not otp:
        raise NobitexAPIError(message='Missing2FA', description='2FA is required', status_code=400)

    is_2fa_enabled = user.requires_2fa
    if not is_2fa_enabled:
        raise NobitexAPIError(message='UserWithout2FA', description='Use 2FA shoud be enabled', status_code=400)

    if not check_user_otp(otp, user):
        raise NobitexAPIError(message='Invalid2FA', description='2FA is invalid', status_code=400)

@ratelimit(key='user_or_ip', rate='10/m', block=True)
@post_api
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def create_key_request(request: Request):
    """creates an api key owned by the requester. key should have a name, description
    and permissions. Permissions are not allow to change.

    POST /apikeys/create
    """
    user: User = request.user

    __validate_otp(user, request)

    private_key, public_key = eddsa.EDDSA().generate_api_key_pair()

    try:
        serializer = KeyRequest.model_validate(request.data, from_attributes=False)
    except pydantic.ValidationError as exp:
        raise NobitexAPIError(
            'ParseError',
            convert_pydantic_validation_error(exp),
            status_code=400,
        ) from exp

    key: Key = Key(
        key=public_key,
        owner=user,
        name=serializer.name,
        description=serializer.description,
        permissions=serializer.permissions,
        ip_addresses_whitelist=[str(ip) for ip in serializer.ip_addresses_whitelist],
        expiration_date=serializer.expiration_date,
    )
    try:
        key.save()
    except exceptions.ValidationError as exp:
        raise NobitexAPIError(
            'ValidationError',
            exp.message,
            status_code=400,
        ) from exp

    APIKeyNotifications.CREATION.send(
        user,
        email_data={
            'email_title': 'ایجاد API Key جدید',
            'created_at': key.created_at,
        },
    )

    __audit_log(
        msg='new api key is created',
        user=user,
        request=request,
        action='create',
        key=key.key,
    )

    return KeyCreationResponse(
        status='ok',
        private_key=private_key,
        key=KeySerializer.model_validate(key, from_attributes=True),
    )


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@get_api
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def list_keys_request(request: Request):
    """lists api keys owned by the requester.

    GET /apikeys/list
    """
    user: User = request.user

    keys = Key.objects.filter(owner=user).all()

    return KeyListResponse(
        status='ok',
        keys=[KeySerializer.model_validate(key, from_attributes=True) for key in keys],
    )


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@post_api
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def delete_key_request(request: Request, public_key: str):
    """delete an api key owned by the requester that has id.

    GET /apikeys/delete/<str:public_key>
    """
    user: User = request.user

    __validate_otp(user, request)

    get_object_or_404(Key, owner=user, key=public_key).delete()

    APIKeyNotifications.DELETION.send(
        user,
        email_data={
            'email_title': 'حذف یک API Key',
            'now': datetime.datetime.now(),
        },
    )

    __audit_log(
        msg='api key is deleted',
        user=user,
        request=request,
        action='delete',
        key=public_key,
    )

    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@post_api
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def update_key_request(request: Request, public_key: str):
    """updates an api key owned by the requester.

    POST /apikeys/update/<str:public_key>
    """
    user: User = request.user

    __validate_otp(user, request)

    key = get_object_or_404(Key, owner=user, key=public_key)

    try:
        serializer = KeyUpdateRequest.model_validate(request.data, from_attributes=False)
    except pydantic.ValidationError as exp:
        raise NobitexAPIError(
            'ParseError',
            convert_pydantic_validation_error(exp),
            status_code=400,
        ) from exp

    need_save = False

    if serializer.name is not None:
        key.name = serializer.name
        need_save = True
    if serializer.description is not None:
        key.description = serializer.description
        need_save = True
    if serializer.ip_addresses_whitelist is not None:
        key.ip_addresses_whitelist = [str(ip) for ip in serializer.ip_addresses_whitelist]
        need_save = True

    if need_save:
        try:
            key.save()
        except exceptions.ValidationError as exp:
            raise NobitexAPIError(
                'ValidationError',
                exp.message,
                status_code=400,
            ) from exp

        if serializer.ip_addresses_whitelist is not None:
            APIKeyNotifications.UPDATE.send(
                user,
                email_data={
                    'email_title': 'ویرایش API Key',
                    'updated_at': key.updated_at,
                },
            )

            __audit_log(
                msg='api key is updated',
                user=user,
                request=request,
                action='update',
                key=public_key,
                ip_addresses_whitelist=[str(ip) for ip in serializer.ip_addresses_whitelist],
            )

    return KeyUpdateResponse(
        status='ok',
        key=KeySerializer.model_validate(key, from_attributes=True),
    )

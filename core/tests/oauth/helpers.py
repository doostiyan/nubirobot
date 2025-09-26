import base64
import datetime
import hashlib
import os
import random
import string

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.oauth.models import AccessToken, Application, Grant, RefreshToken


def create_application(user: User, **kwargs) -> Application:
    default_args = {
        'client_type': Application.CLIENT_CONFIDENTIAL,
        'authorization_grant_type': Application.GRANT_AUTHORIZATION_CODE,
        'name': ''.join(random.choice(string.ascii_lowercase) for _ in range(12)),
    }
    if kwargs:
        default_args.update(kwargs)
    app = Application(user=user, **default_args)
    app.actual_client_secret = app.client_secret
    app.save()
    return app


def create_grant(application: Application, user: User, code_verifier=None, **kwargs) -> Grant:
    if not code_verifier:
        code_verifier = ''.join(random.choices(string.ascii_uppercase + string.digits, k=48))
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest())
        .decode('utf-8')
        .replace('=', '')
    )
    default_args = {
        'code': ''.join(random.choice(string.ascii_letters) for _ in range(20)),
        'redirect_uri': 'https://google.com',
        'scope': 'read',
        'expires': ir_now() + datetime.timedelta(days=10),
        'code_challenge': code_challenge,
        'code_challenge_method': Grant.CODE_CHALLENGE_S256,
    }
    if kwargs:
        default_args.update(kwargs)
    grant = Grant.objects.create(user=user, application=application, **default_args)
    grant.code_verifier = code_verifier
    return grant


def create_access_token(application: Application, user: User, **kwargs) -> AccessToken:
    default_args = {
        'token': ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(20)),
        'expires': ir_now() + datetime.timedelta(days=10),
        'scope': 'read',
    }
    if kwargs:
        default_args.update(kwargs)
    access_token = AccessToken.objects.create(user=user, application=application, **default_args)
    return access_token


def create_refresh_token(access_token: AccessToken, **kwargs) -> RefreshToken:
    token_kwargs = {
        'token': base64.b64encode(os.urandom(20)).decode('utf8'),
        'user': access_token.user,
        'application': access_token.application,
        'access_token': access_token,
        **kwargs,
    }
    return RefreshToken.objects.create(**token_kwargs)

from typing import List
from urllib.parse import parse_qs, urlparse

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.oauth.exceptions import AuthorizationException
from exchange.oauth.models import AccessToken, Application


def raise_error_from_uri(uri):
    """
    The django oauth toolkit returns some authorization errors in the redirect_uri field, but
    we need to raise the error with our convention
    this function we raise appropriate error from uri
    Args:
        uri: redirect uri

    Returns:
            None
    """

    parsed_url = urlparse(uri)
    queries = parse_qs(parsed_url.query)
    error = queries.get('error')
    error_description = queries.get('error_description')
    if error:
        if error[0] == 'invalid_scope':
            raise AuthorizationException(code='InvalidScope', message='Scope is invalid.')
        elif error[0] == 'unsupported_response_type':
            raise AuthorizationException(code='UnsupportedResponseType', message='Unsupported response_type.')
        elif error[0] == 'invalid_request' and error_description[0] == 'Transform algorithm not supported.':
            raise AuthorizationException(
                code='InvalidCodeChallengeMethod', message='Transform algorithm not supported.'
            )
        else:
            raise AuthorizationException()


def get_latest_tokens(user: User):
    """
    Returns the latest AccessTokens of a user per pairs of application and scope regardless of its expiration
    Args:
        user: the user whose AccessToken's we want to find

    Returns:
        The latest AccessTokens of a user grouped by the group_by_fields
    """

    return AccessToken.objects.filter(
        id__in=(
            AccessToken.objects.filter(user=user)
            .order_by('application', 'scope', '-created')
            .distinct('application', 'scope')
            .values_list('id', flat=True)
        ),
    ).order_by('-created')


def get_unauthorized_scopes_of_app(user: User, app: Application, scopes: [str]) -> List[str]:
    """
    This function return a subset of received scopes that are within the app's scopes & the user has not authorized yet.
    Args:
        user: the user authorizing the app's scopes
        app: containing the client's information
        scopes: the received scopes for which the application will be asking for authorization

    Returns:
        A list subset of scopes, containing some the app's scopes which the user has not authorized yet.
    """
    token_scopes = list(
        AccessToken.objects.filter(user=user, application=app, expires__gt=ir_now()).values_list('scope', flat=True)
    )
    authorized_scopes = []
    for scope in token_scopes:
        authorized_scopes.extend(scope.split())
    unauthorized_scopes = [scope for scope in scopes if scope not in authorized_scopes and app.has_scope(scope)]
    return unauthorized_scopes

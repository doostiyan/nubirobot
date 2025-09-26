from exchange.base.serializers import register_serializer
from exchange.oauth.constants import Scopes
from exchange.oauth.models import AccessToken, Application


@register_serializer(model=Application)
def serialize_application(app: Application, opts: dict) -> dict:
    application_info = {
        'clientName': app.name,
        'authorizationGrantType': app.authorization_grant_type,
    }
    scopes = [scope for scope in app.scope.split()]
    scopes = opts.get('scopes') if opts and 'scopes' in opts else scopes
    if 'exclude_scopes' not in opts or not opts.get('exclude_scopes', False):
        application_info['scopes'] = [Scopes.get_all()[scope] for scope in scopes]
    return application_info


@register_serializer(model=AccessToken)
def serialize_access_token(access_token: AccessToken, opts: dict) -> dict:
    return {
        'id': access_token.id,
        'scope': {scope: Scopes.get_all()[scope] for scope in access_token.scope.split()},
        'client': serialize_application(access_token.application, opts={'exclude_scopes': True}),
        'createdAt': access_token.created,
        'lastUpdate': access_token.updated,
        'expiration': access_token.expires,
    }

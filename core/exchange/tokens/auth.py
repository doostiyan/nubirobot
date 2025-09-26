from dj_rest_auth.registration.views import TokenModel


def get_user_token_ttl(user):
    """Return token validity time for this user in seconds"""
    if user.logout_threshold:
        return user.logout_threshold * 60
    if getattr(user, 'remembered_login', False):
        return 2592000  # 30d
    return 14400  # 4h


def create_token(user):
    return TokenModel.objects.get_or_create(user=user)[0]

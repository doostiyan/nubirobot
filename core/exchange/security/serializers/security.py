from exchange.base.serializers import register_serializer

from exchange.security.models import LoginAttempt


@register_serializer(model=LoginAttempt)
def serialize_login_attempt(attempt, opts):
    return {
        'username': attempt.username,
        'ip': attempt.ip,
        'ipCountry': attempt.ip_country,
        'userAgent': attempt.user_agent,
        'createdAt': attempt.created_at,
        'isKnown': attempt.is_known,
        'deviceId': attempt.device_id,
        'status': 'Successful' if attempt.is_successful else 'Failed',
    }

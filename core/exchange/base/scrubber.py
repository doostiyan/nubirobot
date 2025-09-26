from django.conf import settings


def scrub(data, scrub_value: str = '*****'):
    from exchange.base.models import Settings  # to avoid circular import

    sensitive_fields = set(
        Settings.get_cached_json('scrubber_sensitive_fields', []) + settings.SCRUBBER_SENSITIVE_FIELDS
    )

    if isinstance(data, (list, set, tuple)):
        return [scrub(item) for item in data]
    if isinstance(data, dict):
        for key, value in data.items():
            if key in sensitive_fields:
                data[key] = scrub_value
            else:
                data[key] = scrub(value)
        return data
    return data

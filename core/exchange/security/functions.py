from typing import Optional
from django.urls import reverse


def get_emergency_cancel_url(user) -> Optional[str]:
    from exchange.base.helpers import get_base_api_url
    from exchange.security.models import EmergencyCancelCode

    # Cancel code
    cancel_code = EmergencyCancelCode.get_emergency_cancel_code(user)
    if cancel_code:
        emergency_cancel_url = f'{get_base_api_url(trailing_slash=False)}' \
                               f'{reverse("emergency_cancel")}' \
                               f'?code={cancel_code}'
    else:
        emergency_cancel_url = None
    return emergency_cancel_url

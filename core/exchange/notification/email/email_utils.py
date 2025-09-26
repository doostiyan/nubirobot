from typing import List, Optional

from django.conf import settings

from exchange.base.models import Settings
from exchange.notification.email.email_constants import LIMITED_SEND_DOMAINS, NO_SEND_DOMAINS, OPTIONAL_TEMPLATES


def filter_no_send_emails(emails: List[str], template: Optional[str] = None) -> List[str]:
    email_whitelist = Settings.get_list('email_whitelist')
    email_blacklist = Settings.get_list('email_blacklist')

    _emails = []
    for e in emails:
        e = e.strip()
        if '@' not in e:
            continue

        email_domain = e.split('@', 1)[1]

        # Internal Email Blacklist
        if email_domain in NO_SEND_DOMAINS:
            continue

        if e in email_blacklist:
            continue

        # Only send selected emails in testnet
        if not settings.IS_PROD and e not in email_whitelist:
            continue

        # Select sending backend, or skip sending
        is_limited_send_domain = email_domain in LIMITED_SEND_DOMAINS
        if template in OPTIONAL_TEMPLATES and is_limited_send_domain:
            continue

        if template in ['new_device_notif'] and is_limited_send_domain:
            continue

        _emails.append(e)

    return _emails

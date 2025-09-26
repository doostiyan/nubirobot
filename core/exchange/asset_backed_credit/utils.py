import re
from typing import Optional

from django.http import HttpRequest


def is_user_agent_android(
    request: HttpRequest, min_version: Optional[str] = None, max_version: Optional[str] = None
) -> bool:
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if not user_agent:
        return False

    is_android = user_agent.lower().startswith('android')
    if not min_version and not max_version:
        return is_android

    version = extract_version(user_agent)
    if not version:
        return False

    return is_android and is_supported_version(version, min_version, max_version)


def is_supported_version(version: str, min_version: Optional[str] = None, max_version: Optional[str] = None) -> bool:
    # Check if min_version is provided and if version is >= min_version
    if min_version and compare_versions(version, min_version) < 0:
        return False

    # Check if max_version is provided and if version is <= max_version
    if max_version and compare_versions(version, max_version) > 0:
        return False

    return True


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    Returns:
    - 0 if v1 == v2
    - 1 if v1 > v2
    - -1 if v1 < v2
    """

    v1_parts = [int(x) for x in v1.split('.')]
    v2_parts = [int(x) for x in v2.split('.')]

    if not len(v1_parts) == len(v2_parts):
        raise ValueError()

    # Compare the versions part by part
    for v1_part, v2_part in zip(v1_parts, v2_parts):
        if v1_part < v2_part:
            return -1
        elif v1_part > v2_part:
            return 1
    return 0  # versions are equal


def extract_version(user_agent: str) -> Optional[str]:
    match = re.search(r'Android/(\d+\.\d+\.\d+)', user_agent)
    if match:
        return match.group(1)
    return None


def parse_clients_error(request, message: str, description) -> (str, str):
    if is_user_agent_android(request):
        return description, message
    return message, description

import os

from django.conf import settings


def get_all_permission_filenames():
    """Return full filenames of all permissions.yaml files in project."""
    apps_filenames = []
    for app in settings.INSTALLED_APPS:
        app_parts = app.split('.')
        if len(app_parts) < 2 or app_parts[0] != 'exchange':
            continue
        app_name = app_parts[1]
        permissions_filename = os.path.join(settings.BASE_DIR, 'exchange', app_name, 'permissions.yaml')
        if os.path.exists(permissions_filename):
            apps_filenames.append(permissions_filename)
    return apps_filenames

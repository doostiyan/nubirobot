from django.conf import settings

INTERNAL_IPS = ('127.0.0.1',)


def custom_show_toolbar(request):
    if settings.DEBUG:
        return True
    else:
        return False


DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': custom_show_toolbar,
}

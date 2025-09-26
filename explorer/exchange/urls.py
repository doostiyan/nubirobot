from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django_prometheus import exports
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser

schema_view = get_schema_view(
    openapi.Info(
        title='Nobitex explorer API',
        default_version='v1',
        description='Have fun with your ultimate documentation :)',
        terms_of_service='https://www.google.com/policies/terms/',
        contact=openapi.Contact(email='m.ghaffari662@gmail.com'),
        license=openapi.License(name='BSD License'),
    ),
    permission_classes=[IsAdminUser],
    authentication_classes=[SessionAuthentication],
    public=True,
)

urlpatterns = [
    path('', include('exchange.explorer.basis.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('exchange.explorer.accounts.urls')),
    path('auth/', include('exchange.explorer.authentication.urls')),
    path('monitoring/', include('exchange.explorer.monitoring.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('metrics', exports.ExportToDjangoView, name='prometheus-django-metrics'),
    path('staking/', include('exchange.explorer.staking.urls')),
]

if settings.IS_DIFF:
    urlpatterns += [
        path('<slug:network>/transactions/', include('exchange.explorer.transactions.urls')),
    ]
else:
    urlpatterns += [
        path('<slug:network>/transactions/', include('exchange.explorer.transactions.urls')),
        # the line above could be removed but we keep it to facilitate development.
        path('<slug:network>/wallets/', include('exchange.explorer.wallets.urls')),
        path('<slug:network>/blocks/', include('exchange.explorer.blocks.urls')),
        path('networkproviders/', include('exchange.explorer.networkproviders.urls')),
        path('', include('exchange.explorer.core.urls'))
    ]
# In this way we keep views separated.


if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls)), *urlpatterns]

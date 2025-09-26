from django.db.models import QuerySet

from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.models.store import Store
from exchange.asset_backed_credit.services.providers.dispatcher import STORE_DISPATCHER, store_dispatcher
from exchange.base.logging import report_exception


def get_stores() -> QuerySet[Store]:
    return Store.objects.all()


def fetch_stores() -> None:
    providers = STORE_DISPATCHER.keys()

    for provider in providers:
        try:
            _fetch_provider_stores(provider)
        except Exception:
            report_exception()


def _fetch_provider_stores(provider: int) -> None:
    service = Service.objects.get(provider=provider)
    stores = store_dispatcher(provider=provider).get_stores()

    active_stores_urls = {s.url for s in stores}

    for store in stores:
        Store.objects.update_or_create(
            service=service,
            url=store.url,
            defaults={
                'title': store.title,
                'active': True,
            },
        )

    Store.objects.filter(service=service).exclude(url__in=active_stores_urls).update(active=False)

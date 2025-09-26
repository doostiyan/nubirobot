from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from exchange.asset_backed_credit.api.mixins import FiltersMixin
from exchange.asset_backed_credit.api.views import InternalABCView
from exchange.asset_backed_credit.services.store import get_stores
from exchange.asset_backed_credit.types import StoreSchema
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import paginate


class StoreListView(InternalABCView, FiltersMixin):
    permission_classes = ()

    @method_decorator(ratelimit(key='ip', rate='20/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='abcStoreList'))
    def get(self, request):
        """
        This API returns stores
        GET /asset-backed-credit/stores
        """

        filters = self.get_filters(request=request)

        stores = get_stores()
        stores, has_next = paginate(stores, page=filters.page, page_size=filters.page_size, check_next=True)
        stores = [StoreSchema(**store).model_dump(by_alias=True) for store in stores]
        return self.response({'status': 'ok', 'stores': stores, 'hasNext': has_next})

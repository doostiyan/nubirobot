import jdatetime

from exchange.asset_backed_credit.types import RequestFilters


class FiltersMixin:
    DEFAULT_PAGE = 0
    MAX_PAGE = 100
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 20

    def get_filters(self, request) -> RequestFilters:
        try:
            page = min(int(request.query_params.get('page')), self.MAX_PAGE)
            page_size = min(int(request.query_params.get('pageSize')), self.MAX_PAGE_SIZE)
        except (TypeError, ValueError):
            page = self.DEFAULT_PAGE
            page_size = self.DEFAULT_PAGE_SIZE

        from_date = request.query_params.get('fromDate')
        to_date = request.query_params.get('toDate')
        if from_date:
            try:
                from_date = jdatetime.datetime.strptime(from_date, '%Y-%m-%d').togregorian().date()
            except Exception:
                from_date = None

        if to_date:
            try:
                to_date = jdatetime.datetime.strptime(to_date, '%Y-%m-%d').togregorian().date()
            except Exception:
                to_date = None

        return RequestFilters(
            page=page,
            page_size=page_size,
            from_date=from_date,
            to_date=to_date,
        )

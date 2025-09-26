from django.core.cache import caches
from django.core.management.base import BaseCommand
from django.db.models import Q, Value
from django.db.models.functions import Replace

from exchange.charts.models import Chart, StudyTemplate
from exchange.market.models import UserMarketsPreferences


def copy_cache_data(_from, _to):
    cache = caches['chart_api']
    key_pattern = f'marketdata_{_from}_*'
    keys_iter = cache.client.get_client().scan_iter(match=key_pattern, count=1000)
    with cache.client.get_client().pipeline() as pipe:
        for key in keys_iter:
            src_key = key.decode('utf-8')
            new_key = src_key.replace(_from, _to)
            value = cache.get(src_key)
            ttl = cache.ttl(src_key)
            if value is not None:
                pipe.set(cache.make_key(new_key), value, ex=ttl if ttl > 0 else None)

        pipe.execute()


class Command(BaseCommand):
    """
    This command tries to rename all side things that are supposed to be a valid market name but are
    not direct foreign and are hard-coded in `CharField`s or `TextField`s.
    for example a `CharField` that keeps a symbol name in database needs to be updated when we rename
    that particular symbol.

    This command assumes that we have only `IRT` and `USDT` as our dst currencies.
    This assumption is for an edge case that a token name could be frequent in a normal text.
    For example:
        assume a token named `HEL` that should be renamed to `AHEL`
        in this case our queries would replace all strings `HEL` to `AHEL`,
        so, if there are any strings like `HELLO WORLD` will be updated to
        `AHELLO WORLD` in the fields, while they shouldn't.
        That's the reason for hard-coding IRT and USDT in the string:
        we will replace `HELIRT` and `HELUSDT` to `AHELIRT` and `AHELUSDT`
        and in this case `HELLO WORLD` wouldn't match with the query since
        it has not `IRT` or `USDT` after the `HEL` part.
    """

    help = 'Update hard-coded market names in database, when renaming a market.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--from',
            dest='from_name',
            type=str,
            help='Current name of the token. Ex: RNDR',
            required=True,
        )
        parser.add_argument('--to', type=str, help='New name for the token. Ex: RENDER', required=True)
        parser.add_argument(
            '--user-id',
            type=str,
            help='Restrict to only a single user. Ex: 210',
            required=False,
        )
        parser.add_argument(
            '-n',
            '--no-copy-cache',
            action='store_true',
            help='Disables copying market and candles data within cache. '
            'No value needed; just pass the flag and it disables the behavior.',
            required=False,
            default=False,
        )

    def handle(self, *, from_name: str, to: str, no_copy_cache: bool, user_id: str, **kwargs):
        from_name = from_name.upper()
        to = to.upper()

        user_markets_preferences = UserMarketsPreferences.objects.filter(favorite_markets__contains=from_name)
        charts = Chart.objects.filter(Q(symbol__contains=from_name) | Q(content__contains=from_name))
        study_template = StudyTemplate.objects.filter(content__contains=from_name)

        if user_id:
            user_markets_preferences = user_markets_preferences.filter(user_id=user_id)
            charts = charts.filter(ownerSource='nobitex', ownerId=user_id)
            study_template = study_template.filter(ownerSource='nobitex', ownerId=user_id)

        for dst_currency in ['IRT', 'USDT']:
            _from = from_name + dst_currency
            _to = to + dst_currency

            user_markets_preferences.update(favorite_markets=Replace('favorite_markets', Value(_from), Value(_to)))
            charts.update(
                symbol=Replace('symbol', Value(_from), Value(_to)),
                content=Replace('content', Value(_from), Value(_to)),
            )
            study_template.update(
                content=Replace('content', Value(_from), Value(_to)),
            )

            if not no_copy_cache:
                copy_cache_data(_from, _to)

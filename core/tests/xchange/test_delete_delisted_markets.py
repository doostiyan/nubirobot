from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from exchange.xchange.models import Currencies, MarketStatus
from tests.xchange.helpers import upsert_dict_as_currency_pair_status
from tests.xchange.mocks import NEAR_USDT_STATUS, SOL_USDT_STATUS, XRP_USDT_STATUS


class DeleteDelistedMarketsCommandTest(TestCase):
    def setUp(self):
        upsert_dict_as_currency_pair_status(NEAR_USDT_STATUS)
        upsert_dict_as_currency_pair_status(SOL_USDT_STATUS)
        upsert_dict_as_currency_pair_status(XRP_USDT_STATUS)
        MarketStatus.objects.filter(
            base_currency__in=[Currencies.near, Currencies.xrp],
            quote_currency=Currencies.usdt,
        ).update(
            status=MarketStatus.STATUS_CHOICES.delisted,
        )

    def test_delete_delisted_markets(self):
        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 2

        call_command('xchange__delete_delisted_markets', '--all')

        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 0
        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.available).count() == 1

    def test_delete_specific_pair(self):
        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 2

        call_command('xchange__delete_delisted_markets', '--pair', 'NEARUSDT')

        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 1
        assert not MarketStatus.objects.filter(base_currency=Currencies.near, quote_currency=Currencies.usdt).exists()
        assert MarketStatus.objects.filter(base_currency=Currencies.sol, quote_currency=Currencies.usdt).exists()
        assert MarketStatus.objects.filter(base_currency=Currencies.xrp, quote_currency=Currencies.usdt).exists()

    def test_delete_non_delisted_pair_without_force(self):
        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 2

        call_command('xchange__delete_delisted_markets', '--pair', 'SOLUSDT')

        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 2
        assert MarketStatus.objects.filter(base_currency=Currencies.sol, quote_currency=Currencies.usdt).exists()
        assert MarketStatus.objects.filter(base_currency=Currencies.near, quote_currency=Currencies.usdt).exists()
        assert MarketStatus.objects.filter(base_currency=Currencies.xrp, quote_currency=Currencies.usdt).exists()

    def test_delete_non_delisted_pair_with_force(self):
        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 2

        call_command('xchange__delete_delisted_markets', '--pair', 'SOLUSDT', '--force')

        assert MarketStatus.objects.filter(status=MarketStatus.STATUS_CHOICES.delisted).count() == 2
        assert not MarketStatus.objects.filter(base_currency=Currencies.sol, quote_currency=Currencies.usdt).exists()
        assert MarketStatus.objects.filter(base_currency=Currencies.near, quote_currency=Currencies.usdt).exists()
        assert MarketStatus.objects.filter(base_currency=Currencies.xrp, quote_currency=Currencies.usdt).exists()

    def test_missing_options(self):
        out = StringIO()
        call_command('xchange__delete_delisted_markets', stdout=out)
        assert 'You must specify either --pair or --all.' in out.getvalue()

    def test_both_options(self):
        out = StringIO()
        call_command('xchange__delete_delisted_markets', '--pair', 'NEARUSDT', '--all', stdout=out)
        assert 'You cannot use --pair and --all together.' in out.getvalue()

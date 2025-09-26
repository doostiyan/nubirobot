from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from exchange.base.models import Currencies
from exchange.staking.errors import MarkPriceNotAvailableError
from exchange.staking.externals.price import PriceProvider


@patch('exchange.staking.externals.price.MarkPriceCalculator.get_mark_price')
class PriceProviderTests(TestCase):
    def test_get_mark_price_success(self, mocked_mark_price):
        PriceProvider(Currencies.btc, Currencies.rls).get_mark_price()

        mocked_mark_price.assert_called_once_with(Currencies.btc, Currencies.rls)

    def test_when_mark_price_is_none_then_error_is_raised(self, mocked_mark_price):
        mocked_mark_price.return_value = None
        with self.assertRaises(MarkPriceNotAvailableError):
            PriceProvider(Currencies.btc, Currencies.rls).get_mark_price()

        mocked_mark_price.assert_called_once_with(Currencies.btc, Currencies.rls)

    def test_when_source_and_destination_are_same_then_one_is_returned(self, mocked_mark_price):
        price = PriceProvider(Currencies.usdt, Currencies.usdt).get_mark_price()

        assert price == Decimal('1.0')
        mocked_mark_price.assert_not_called()

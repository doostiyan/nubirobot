import datetime
import random
from decimal import Decimal
from typing import Any, Optional

from django.core.cache import cache
from django.core.management import call_command
from django.db.models.signals import post_save
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone
from django.utils.cache import get_cache_key
from django.utils.timezone import now

from exchange.accounts.models import User, UserRestriction, VerificationRequest
from exchange.base.calendar import ir_now
from exchange.base.models import ADDRESS_TYPE, Currencies, Settings
from exchange.blockchain.models import Transaction as BlockchainTransaction
from exchange.market.models import Market, Order, OrderMatching
from exchange.matcher.matcher import Matcher, post_processing_matcher_round
from exchange.wallet.deposit import save_deposit_from_blockchain_transaction
from exchange.wallet.models import Wallet, WalletDepositAddress, WithdrawRequest, WithdrawRequestPermit


def set_initial_values():
    Settings.set_cached_json('prices_binance',
        {'btc': 48985.5, 'eth': 1787.56, 'bch': 710.34, 'xrp': 0.5544, 'eos': 4.831, 'ltc': 213.55,
        'trx': 0.05291, 'etc': 14.966, 'link': 32.644, 'xlm': 0.50076, 'ada': 0.88515, 'xmr': 227.42, 'shib': 0.036,
        'dash': 265.6, 'bnb': 130.537, 'atom': 25.532, 'usdt': 1, 'sol': 175.51}
    )
    Settings.set_dict('usd_value', {'buy': 266000, 'sell': 270500})
    Settings.set_datetime('prices_binance_last_update', now())
    Settings.set_cached_json('prices_binance_futures', {
        'btc': 48979.38, 'eth': 1786.09, 'bch': 713.63, 'xrp': 0.5491, 'eos': 4.865,
        'ltc': 213.73559, 'trx': 0.05290, 'etc': 14.9897, 'link': 32.604, 'xlm': 0.5038,
        'ada': 0.8897484, 'xmr': 228.500, 'shib': 0.0360976, 'dash': 264.9347, 'bnb': 130.7247,
        'atom': 25.37114, 'usdt': 0.99981, 'sol': 173.96031}
    )
    Settings.set_datetime('prices_binance_futures_last_update', now())

    cache.set('okx_prices', {'btc': 49276.566, 'eth': 1772.8078, 'bch': 715.0628, 'xrp': 0.552153,
        'eos': 4.847, 'ltc': 211.925, 'trx': 0.053146, 'etc': 14.8646, 'link': 32.5404,
        'xlm': 0.49955, 'ada': 0.88417, 'xmr': 229.34159, 'shib': 0.0359, 'dash': 266.3682,
        'bnb': 130.628, 'atom': 25.3038, 'usdt': 1.0017, 'sol': 177.0457}
    )
    cache.set('okx_prices_last_update', now())
    usdt_price = Settings.get_dict('usd_value')
    market_prices = Settings.get_dict('prices_binance')
    for currency_codename in market_prices:
        for side in usdt_price:
            price = Decimal(market_prices[currency_codename])
            cache.set(f'orderbook_{currency_codename.upper()}USDT_best_active_{side}', price)
            cache.set(f'orderbook_{currency_codename.upper()}IRT_best_active_{side}', price * usdt_price[side])


def do_matching_round(market, *, reinitialize_caches=False, settle_positions_command=True):
    matcher = Matcher(market)
    if reinitialize_caches:
        matcher.reinitialize_caches()
    matcher.do_matching_round()
    if market.symbol in Matcher.get_symbols_that_use_async_stop_process():
        post_processing_matcher_round(market, matcher.MARKET_PRICE_RANGE.get(market.id))
    if settle_positions_command:
        call_command('create_pool_pnl_transactions', '--once')


def temporary_withdraw_permissions(user, currency):
    UserRestriction.add_restriction(user=user, restriction='WithdrawRequest', duration=datetime.timedelta(seconds=3))
    WithdrawRequestPermit.objects.create(user=user,
                                         currency=currency,
                                         amount_limit=Decimal('1000'),
                                         effective_time=now() + datetime.timedelta(seconds=3))


def create_order(user, src, dst, amount, price, sell=True, market=False, balance=None, charge_ratio=None,
                 validate=True, stop=None, pair=None, client_order_id=None):
    charge_ratio = charge_ratio or Decimal(1)
    if amount is not None:
        amount = Decimal(amount)
    if price is not None:
        price = Decimal(price)
    if stop is not None:
        stop = Decimal(stop)

    # Order parameters
    param1 = None
    order_type = Order.ORDER_TYPES.sell if sell else Order.ORDER_TYPES.buy
    if stop:
        execution_type = Order.EXECUTION_TYPES.stop_market if market else Order.EXECUTION_TYPES.stop_limit
        param1 = stop
    else:
        execution_type = Order.EXECUTION_TYPES.market if market else Order.EXECUTION_TYPES.limit

    # Create transaction to provide needed wallet balance
    if sell:
        wallet_src = Wallet.get_user_wallet(user, src)
        tr1 = wallet_src.create_transaction(tp='manual', amount=(balance or amount) * charge_ratio)
    else:
        wallet_dst = Wallet.get_user_wallet(user, dst)
        total_price = balance or (amount * price)
        tr1 = wallet_dst.create_transaction(tp='manual', amount=total_price * charge_ratio)
    tr1.commit()

    # Create the order
    order, error = Order.create(
        user=user,
        order_type=order_type,
        execution_type=execution_type,
        src_currency=src,
        dst_currency=dst,
        amount=amount,
        price=price,
        param1=param1,
        pair=pair,
        is_validated=not validate,
        client_order_id=client_order_id,
    )
    if error:
        print('Create Order Failed:', error)
    elif pair:
        pair.pair = order
        pair.save(update_fields=('pair',))
    return order


def create_trade(
    seller, buyer, src_currency=None, dst_currency=None, amount=None, price=None, fee_rate=0, created_at=None
):
    # Set default values
    src_currency = src_currency or Currencies.btc
    dst_currency = dst_currency or Currencies.rls
    market = Market.objects.get(src_currency=src_currency, dst_currency=dst_currency)
    if amount is None:
        amount = Decimal('0.001') * random.randint(1, 200)
    if price is None:
        price = Decimal('310_000_0') * random.randint(900, 1100)
    sell_order = create_order(seller, src_currency, dst_currency, amount, price, sell=True)
    buy_order = create_order(buyer, src_currency, dst_currency, amount, price, sell=False)
    buy_fee = Decimal(amount) * Decimal(fee_rate)
    sell_fee = buy_fee * Decimal(price)
    rial_value = Decimal(amount) * Decimal(price)
    if dst_currency == Currencies.usdt:
        rial_value *= Decimal('50_000_0')
    trade = OrderMatching.objects.create(
        created_at=created_at or now(),
        market=market,
        seller=seller,
        buyer=buyer,
        sell_order=sell_order,
        buy_order=buy_order,
        is_seller_maker=True,
        matched_price=price,
        matched_amount=amount,
        sell_fee_amount=sell_fee,
        buy_fee_amount=buy_fee,
        rial_value=rial_value,
    )
    # Commit trade simulation
    cache.delete('user_{}_trade_status'.format(trade.seller_id))
    cache.delete('user_{}_trade_status'.format(trade.buyer_id))
    return trade


def create_withdraw_request(
    user,
    currency,
    amount,
    address='',
    status=4,
    created_at=None,
    network=None,
    withdraw_type=WithdrawRequest.TYPE.normal,
    tag=None,
    pk: Optional[int] = None,
    fee: Optional[Decimal] = None,
    blockchain_url: Optional[str] = None,
):
    amount = Decimal(amount)
    wallet = Wallet.get_user_wallet(user, currency)
    transaction = wallet.create_transaction(tp='manual', amount=amount)
    transaction.commit()
    if pk is None:
        withdraw = WithdrawRequest.objects.create(
            tp=withdraw_type,
            wallet=wallet,
            target_address=address or 'WaLlEtAdDrEsS1',
            amount=amount,
            status=status,
            tag=tag,
            fee=fee,
            blockchain_url=blockchain_url,
        )
    else:
        withdraw = WithdrawRequest(
            pk=pk,
            tp=withdraw_type,
            wallet=wallet,
            target_address=address or 'WaLlEtAdDrEsS1',
            amount=amount,
            status=status,
            tag=tag,
            fee=fee,
            blockchain_url=blockchain_url,
        )
        withdraw.save()
    if created_at:
        withdraw.created_at = created_at
        withdraw.save(update_fields=['created_at'])
    if network:
        withdraw.network = network
        withdraw.save(update_fields=['network'])
    return withdraw


def create_deposit(user, currency, amount=Decimal('1'), address='', tx_hash='', confirmations=99, created_at=None, type=ADDRESS_TYPE.standard):
    wallet = Wallet.get_user_wallet(user, currency)
    addr = WalletDepositAddress.objects.create(
        wallet=wallet,
        address=address,
        type=type
    )
    tx = BlockchainTransaction(
        address=address,
        hash=tx_hash,
        timestamp=now(),
        value=amount or Decimal('1'),
        confirmations=confirmations,
        is_double_spend=False,
    )
    save_deposit_from_blockchain_transaction(tx, addr)


class CachedViewTestMixin:
    """Clear request cache after api call

    Use in conjunction with `APITestCase` derivations.
    """
    BASE_URL = ''
    CACHE_PREFIX = ''

    def get_response(self, path):
        """Request GET path and clear cache"""
        response = self.client.get(f'{self.BASE_URL}/{path}')
        cache_key = get_cache_key(request=response.wsgi_request, key_prefix=self.CACHE_PREFIX)
        cache.delete(cache_key)
        return response.json()


class TransactionTestFastFlushMixin:
    """Truncate TransactionTestCase faster

    Use in conjunction with `TransactionTestCase` derivations.
    """
    truncate_models = ()

    def setUp(self):
        self.objects = []
        post_save.connect(self.pile_created_objects)

    def pile_created_objects(self, sender, instance, created, **_):
        if created:
            self.objects.append(instance)

    def clear_created_objects(self):
        for instance in reversed(self.objects):
            if instance.pk:
                instance.delete()
        self.objects.clear()

    def tearDown(self):
        self.clear_created_objects()
        post_save.disconnect(self.pile_created_objects)
        for model in self.truncate_models:
            model.objects.all().delete()

    def _fixture_teardown(self):
        """Evade flushing whole tables to save time"""
        pass


class NobitexRequestFactory(RequestFactory):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = {}

    def post(self, path, data=None, **extra):
        request = super().post(path, data=data, **extra)
        request.data = data
        return request


def check_nobitex_response(json_response, nobitex_status, code, message):
    assert json_response.get('status') == nobitex_status
    assert json_response.get('code') == code
    assert json_response.get('message') == message


def check_response(
    response: HttpResponse,
    status_code: int,
    status_data: Optional[str] = None,
    code: Optional[str] = None,
    message: Optional[str] = None,
    special_key: Optional[str] = None,
    special_value: Any = None,
):
    assert response.status_code == status_code, (response.status_code, status_code)
    data = response.json()
    if status_data:
        assert data['status'] == status_data, (data['status'], status_data)
    if code:
        assert data['code'] == code, (data['code'], code)
    if message:
        assert data['message'] == message, (data['message'], message)
    if special_key:
        assert data[special_key] == special_value, (data['special_value'], special_value)
    return data


def set_feature_status(feature: str, status: bool = True) -> bool:
    feature_cache_key = f'is_{feature}_feature_enabled'
    feature_key = f'{feature}_feature_status'
    try:
        feature_obj = Settings.objects.get(key=feature_key)
    except Settings.DoesNotExist:
        feature_obj = Settings(key=feature_key)
    feature_obj.value = 'enabled' if status else 'disabled'
    feature_obj.save()
    cache.set(feature_cache_key, status, 600)
    return status


def mock_on_commit(func, *args, **kwargs):
    func()


def make_user_upgradable_to_level3(user: User, use_day_limitation=True, mobile_identity=True, add_trades=True):
    vp = user.get_verification_profile()
    if mobile_identity:
        vp.mobile_identity_confirmed = True
        vp.address_confirmed = True
    else:
        vp.mobile_identity_confirmed = False
    vp.save()

    vr = VerificationRequest.objects.create(
        user=user,
        tp=VerificationRequest.TYPES.auto_kyc,
        explanations='test',
    )
    vr_date = ir_now() - timezone.timedelta(days=62) if use_day_limitation else ir_now() - timezone.timedelta(days=25)
    vr.status = VerificationRequest.STATUS.confirmed
    vr.created_at = vr_date
    vr.save()
    if add_trades:
        create_trade(user, user, amount=4, src_currency=Currencies.btc, dst_currency=Currencies.rls)

dummy_caching = override_settings(
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}}
)  # For not caching purpose

import datetime
import random
import time
from decimal import Decimal, ROUND_DOWN

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils.timezone import now

from exchange.base.crypto import unique_random_string
from exchange.base.logging import report_exception
from exchange.base.models import (
    Currencies, AVAILABLE_CRYPTO_CURRENCIES, ACTIVE_CRYPTO_CURRENCIES, ACTIVE_NON_STABLE_CRYPTO_CURRENCIES, RIAL,
    PRICE_PRECISIONS, AMOUNT_PRECISIONS, Settings, get_currency_codename, get_market_symbol,
)
from exchange.base.money import humanize_number
from exchange.accounts.models import User
from exchange.base.exchangeconnection import ExchangeConnectionManager
from exchange.market.models import Market, Order, AutoTradingPermit
from exchange.wallet.models import Wallet


CURRENCIES_CHOICES = {
    'all': ACTIVE_CRYPTO_CURRENCIES,
    'all-crypto': ACTIVE_NON_STABLE_CRYPTO_CURRENCIES,
    'all-available': AVAILABLE_CRYPTO_CURRENCIES,
}

ORDERING_PLANS = {
    'simple': [(Decimal('.01'), Decimal('1'))],
    'simple0': [(Decimal('0'), Decimal('1'))],
    'step3': [(Decimal('.02'), Decimal('0.3')), (Decimal('.03'), Decimal('0.5')), (Decimal('.04'), Decimal('0.2'))],
    'step30': [(Decimal('0'), Decimal('0.3')), (Decimal('.015'), Decimal('0.5')), (Decimal('.025'), Decimal('0.2'))],
    'step50': [(Decimal('0'), Decimal('0.3')), (Decimal('.015'), Decimal('0.25')), (Decimal('.025'), Decimal('0.2')),
                (Decimal('.035'), Decimal('0.15')), (Decimal('.045'), Decimal('0.1'))],
    'step70': [(Decimal('0'), Decimal('0.3')), (Decimal('.015'), Decimal('0.2')), (Decimal('.025'), Decimal('0.15')),
                (Decimal('.035'), Decimal('0.1')), (Decimal('.045'), Decimal('0.1')), (Decimal('.05'), Decimal('0.1')),
                (Decimal('.06'), Decimal('0.05'))],
}


def get_atp_uid(frequency=None, uid=None):
    atp_uid = 'System:autotrading:'
    if frequency is not None:
        atp_uid += '{}:'.format(frequency)
    if uid is not None:
        atp_uid += str(uid)
    return atp_uid


def filter_autotrade_orders(user=None, frequency=None, market=None):
    atp_uid = 'System:autotrading:'
    if frequency is not None:
        atp_uid += '{}:'.format(frequency)
    orders = Order.objects.filter(description__startswith=atp_uid, status=Order.STATUS.active)
    if user is not None:
        orders = orders.filter(user=user)
    if market is not None:
        orders = orders.filter(src_currency=market.src_currency, dst_currency=market.dst_currency)
    return orders


def do_autotrade_round(frequency):
    """ Run autotrade round

        Note: Order invalidation (unhandled)
    """
    # Check if autotrading is enabled
    if Settings.is_disabled('module_autotrader_engine'):
        print('[Notice] Autotrading Engine Disabled')
        # Cancel any order put by autotrade engine because they will be stale
        filter_autotrade_orders().update(status=Order.STATUS.canceled)
        return
    # Process AutoTradingPermits
    atps = list(AutoTradingPermit.objects.all().select_related('user'))
    random.shuffle(atps)
    print('[{}] Processing {} AutoTradePermits - {} Round'.format(now().strftime('%b%d %H:%m'), len(atps), AutoTradingPermit.FREQUENCY[frequency]))
    for atp in atps:
        user = atp.user
        permits = atp.permits
        permits_updated = False
        values = {}
        new_orders = []

        # Access control for this feature
        print('User: {}'.format(user.username))
        if user.user_type < User.USER_TYPES.nobitex:
            print('\tAccessDenied!')
            continue

        # Common variables
        user_wallets = {wallet.currency: wallet for wallet in Wallet.get_user_wallets(user, tp=Wallet.WALLET_TYPE.spot)}
        closed_markets = [(market.src_currency, market.dst_currency) for market in Market.objects.filter(is_active=False)]

        # Process user algorithms
        for options in permits:
            # Do not process inactive permits
            if not options.get('active'):
                continue
            # Check for run frequency
            option_frequency = options.get('frequency') or AutoTradingPermit.FREQUENCY.normal
            if int(option_frequency) != frequency:
                continue

            # Set UID for permits (if not exists)
            uid = options.get('uid')
            if not uid:
                uid = unique_random_string()
                options['uid'] = uid
                permits_updated = True
            values[uid] = {'consumedBudget': 0, 'openOrders': 0}
            order_uid = get_atp_uid(frequency=frequency, uid=uid)

            # Parsing options
            option_currencies = options.get('srcCurrency', 'all')
            if option_currencies in CURRENCIES_CHOICES:
                option_currencies = CURRENCIES_CHOICES[option_currencies]
            else:
                option_currencies = option_currencies.split(',')
                option_currencies = [getattr(Currencies, c, None) for c in option_currencies]
            dst_currency = getattr(Currencies, options.get('dstCurrency') or 'rls', RIAL)
            target_market = options.get('market', 'binance')
            margin = Decimal(options.get('margin') or '0') * Decimal('0.01')
            is_sell = options.get('orderType') == 'sell'

            # Coin Price Range
            min_coin_price = options.get('minCoinPrice')
            if min_coin_price:
                min_coin_price = Decimal(min_coin_price)
            max_coin_price = options.get('maxCoinPrice')
            if max_coin_price:
                max_coin_price = Decimal(max_coin_price)

            # Budget Options
            available_budget = None
            consumed_budget = None
            total_budget = options.get('totalBudget')
            if total_budget:
                try:
                    total_budget = Decimal(total_budget)
                except:
                    report_exception()
                    total_budget = Decimal('0')
                consumed_budget = Order.objects.filter(
                    user=user,
                    description__startswith=order_uid,
                ).aggregate(sum=Sum('matched_total_price'))['sum'] or Decimal('0')
                values[uid]['consumedBudget'] = str(consumed_budget)
                available_budget = total_budget - consumed_budget
                if available_budget <= Decimal('1e-8'):
                    options['active'] = False
                    permits_updated = True
                    continue

            # Going to place order, print info
            print('\tpermit #{}\t({})'.format(uid, '{}/{}'.format(consumed_budget, total_budget) if total_budget else 'U'))

            # Placing orders, for each currency
            for currency in option_currencies:
                currency_name = get_currency_codename(currency)
                if not currency or not currency_name:
                    continue

                # Check if market is open for this pair
                if currency == dst_currency:
                    continue
                if (currency, dst_currency) in closed_markets:
                    print('\t\t[Warning] Market not active for {}/{}'.format(currency, dst_currency))
                    continue

                # Check user wallet for this currency
                if currency not in user_wallets:
                    continue
                available_balance = user_wallets[currency].active_balance if is_sell else user_wallets[dst_currency].active_balance
                if available_balance < Decimal('1e-4'):
                    print('[Warning] No {} balance'.format(currency_name))
                    continue

                # Check coin price
                coin_price = ExchangeConnectionManager.get_crypto_price(currency, target_market)
                if coin_price < Decimal('0.001'):
                    print('[Warning] Price seems invalid: {}={}'.format(currency_name, coin_price))
                    continue
                # If price range is not met, this permit should not be executed - no warning needed
                if min_coin_price and coin_price < min_coin_price:
                    continue
                if max_coin_price and coin_price > max_coin_price:
                    continue

                # Determine target price
                if dst_currency == RIAL:
                    # Convert USD to RLS for rial target currencies
                    usd_value = AutoTradingPermit.get_permit_usd(options)
                    # Check USD value
                    if usd_value < Decimal('30000') or usd_value > Decimal('1000000'):
                        print('\t\t[Warning] USD price invalid: {}'.format(usd_value))
                        continue
                    dst_price = coin_price * usd_value
                else:
                    dst_price = coin_price

                # Apply margin to price
                if margin < Decimal('0'):
                    print('\t\t[Warning] Invalid margin value: {}'.format(margin))
                    continue
                if margin < Decimal('0.0005') and dst_currency != RIAL:
                    print('\t\t[Warning] Low margin value: {}'.format(margin))
                    continue
                margin_price_delta = (dst_price * margin).quantize(Decimal('1E-10')).normalize()
                if is_sell:
                    dst_price += margin_price_delta
                else:
                    dst_price -= margin_price_delta

                # Limit Options
                open_limit = options.get('openLimit')
                if open_limit:
                    open_limit = Decimal(open_limit)

                # Ordering Plan
                plan_name = options.get('plan', 'simple')
                plan = ORDERING_PLANS.get(plan_name)
                if not plan:
                    print('\t\t[Warning] Invalid order plan: {}'.format(plan_name))
                    continue

                # Sell
                if is_sell:
                    total_sell = open_limit or (available_balance * dst_price)
                    if available_budget is not None:
                        total_sell = min(total_sell, available_budget)
                    amount = (total_sell / dst_price).quantize(Decimal('1e-6'), rounding=ROUND_DOWN)
                    amount = min(amount, available_balance)

                # Buy
                else:
                    total_buy = open_limit or available_balance
                    if available_budget is not None:
                        total_buy = min(total_buy, available_budget)
                    amount = (total_buy / dst_price).quantize(Decimal('1e-6'), rounding=ROUND_DOWN)
                    amount = min(amount, available_balance)

                # Determine amount and price precision
                market_symbol = get_market_symbol(currency, dst_currency)
                amount_precision = AMOUNT_PRECISIONS.get(market_symbol)
                price_precision = PRICE_PRECISIONS.get(market_symbol)
                if not amount_precision or not price_precision:
                    print('\t\t[Warning] Unsupported market: {}'.format(market_symbol))
                    continue
                # To have more natural-looking amounts we do not use all decimal
                #  places available in the market
                if amount_precision < Decimal('0.1'):
                    amount_precision *= Decimal('10')

                # Create Order
                for plan_price_margin, plan_ratio in plan:
                    # Order amount
                    order_amount = amount * plan_ratio
                    if is_sell and order_amount > available_balance:
                        order_amount = available_balance
                    order_amount = humanize_number(
                        order_amount,
                        precision=amount_precision,
                    )
                    # Order price
                    order_price = dst_price
                    plan_margin_value = order_price * plan_price_margin
                    if is_sell:
                        order_price += plan_margin_value
                    else:
                        order_price -= plan_margin_value
                    order_price = humanize_number(
                        order_price,
                        multiplier=Decimal('0.1') if dst_currency == RIAL else None,
                        precision=price_precision,
                    )
                    # Validate order
                    order_total_price = order_amount * order_price
                    if order_amount < Decimal('1e-8') or order_total_price < settings.NOBITEX_OPTIONS['minOrders'][dst_currency]:
                        continue
                    # Placing order
                    new_orders.append({
                        'uid': uid,
                        'user': user,
                        'order_type': Order.ORDER_TYPES.sell if is_sell else Order.ORDER_TYPES.buy,
                        'src_currency': currency,
                        'dst_currency': dst_currency,
                        'amount': order_amount,
                        'price': order_price,
                        'description': order_uid,
                    })

        for market in Market.objects.all():
            # Atomically: cancel old orders, place new orders, and update calculated values
            with transaction.atomic():
                Market.objects.select_for_update().get(pk=market.pk)
                filter_autotrade_orders(user=user, frequency=frequency, market=market).update(status=Order.STATUS.canceled)
                if not market.is_active:
                    # Market is not active, skip adding new orders
                    continue
                for new_order in new_orders:
                    if not (new_order['src_currency'] == market.src_currency and new_order['dst_currency'] == market.dst_currency):
                        # Only add current market orders in each pass
                        continue
                    uid = new_order.pop('uid')
                    order, err = Order.create(is_validated=True, channel=Order.CHANNEL.api_internal_old, **new_order)
                    if err is not None:
                        continue
                    values[uid]['openOrders'] += int(order.total_price)
                    print('\t\t{} {} {}   \t@{}'.format(order.get_order_type_display(), order.amount, order.market_display, order.price))

        # Save updates to user algorithm definitions if any change is made
        if permits_updated:
            atp.update_options({'permits': permits})
        # Update algorithm calculated values
        atp.update_values(values)

    # from exchange.base.debug import analyze_queries
    # analyze_queries()

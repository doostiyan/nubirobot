import datetime
import hashlib
from decimal import Decimal
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import BankAccount, Notification, User
from exchange.accounts.parsers import parse_files
from exchange.accounts.userlevels import UserLevelManager
from exchange.accounts.views.auth import check_user_otp
from exchange.base.api import ParseError, api, public_api, public_post_api
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, TETHER, Currencies, get_currency_codename
from exchange.base.normalizers import normalize_mobile
from exchange.base.parsers import parse_choices, parse_currency, parse_money, parse_uuid
from exchange.base.serializers import serialize_choices
from exchange.base.validators import validate_email
from exchange.gateway.constant_keys import *
from exchange.gateway.gateway import available_gateway
from exchange.gateway.models import (
    AVAILABLE_GATEWAY_CURRENCIES,
    GatewayCurrencies,
    PaymentGatewayInvoice,
    PaymentGatewayLog,
    PaymentGatewayUser,
    PaymentRequestRefund,
    PendingWalletRequest,
)
from exchange.market.inspector import gateway_exchange_amount
from exchange.market.models import Market
from exchange.wallet.models import Transaction, Wallet, WithdrawRequest
from exchange.wallet.serializers import serialize_wallet


def send_error(const_key, method, pg_user=None, description='', create_log=True):
    if create_log:
        try:
            code = int(const_key.get('code'))
        except:
            code = 0
        PaymentGatewayLog.objects.create(
            pg_user=pg_user,
            code=code,
            code_description=const_key.get('message'),
            description=description,
            method=method,
        )
    else:
        print('pg_user={}, code={}, code_description={}, description={}, method={}'.format(pg_user,
                                                                                           int(const_key.get('code')),
                                                                                           const_key.get('message'),
                                                                                           description, method))
    return {
        'status': 'failed',
        'code': const_key.get('code'),
        'message': const_key.get('message'),
    }


def get_api(api, request):
    if api == "DemoApiKey":
        demo_user = User.objects.filter(email='demo@nobitex.gateway').first()
        if not demo_user:
            raise ParseError('Cannot find demo user')
        callback_domain = 'nobitex.ir' if settings.IS_PROD else 'testnet.nobitex.ir'
        pg_demo_user = PaymentGatewayUser.objects.get_or_create(user=demo_user,
                                                                domain='https://{}/'.format(callback_domain),
                                                                site_name='Nobitex Testnet',
                                                                confirmed=True)[0]
        return pg_demo_user.api
    return parse_uuid(api)


@public_post_api
def send_data(request):
    """Accept request from recipient and create corresponding invoices.
    Contains this parameter in request

    -------------------------

    Request may contains:
        * api (string): You Nobitex API key
        * amount (integer): Transaction amount in rials, should be greater than 1000.
        * callbackURL (string): Urlencoded return address registered in Nobitex panel.
        * factorNumber (string): (optional).
        * mobile (string): (optional).
        * description (string): (optional).
        * currecncies (string): (optional) Methods which customer can be pay with. Default = AVALAILABLE_GATEWAY
    Return a dictionary on success with format of:
        {
            'status': 'success',

            'token': Token of payment request
        }


    On error return one of dictionary with format of:
        {
            'status': 'failed',

            'code': ERROR CODE,

            'message': ERROR MESSAGE
        }


    which ERROR CODE is one of:
        API_INVALID, API_NOT_FOUND, AMOUNT_INT, CURRENCY_INVALID, API_REQUIRED, AMOUNT_REQUIRED, AMOUNT_MIN,
        REDIRECT_REQUIRED, REDIRECT_FORMAT, API_RESTRICTED, FAILED_ERROR, REDIRECT_BAD_DOMAIN, DESCRIPTION_LENGTH,
        FAILED_ERROR




    :parameter request: HttpRequest
    :return: {'status', 'token'}

    """
    try:
        api = get_api(request.g('api'), request)
    except ParseError:
        return send_error(API_INVALID, 'send_data', description='API: {}'.format(request.g('api')))
    if not api:
        return send_error(API_REQUIRED, 'send_data')
    try:
        pg_user = PaymentGatewayUser.objects.get(api=api, confirmed=True)
    except PaymentGatewayUser.DoesNotExist:
        return send_error(API_NOT_FOUND, 'send_data', description='API: {}'.format(api))
    try:
        amount_rial = parse_money(request.g('amount'))
    except ParseError:
        return send_error(AMOUNT_INT, 'send_data', pg_user, 'Amount: {}'.format(request.g('amount')))
    try:
        amount_tether = parse_money(request.g('amountUSD'))
    except ParseError:
        return send_error(USD_AMOUNT_INT, 'send_data', pg_user, 'Amount: {}'.format(request.g('amountUSD')))

    mobile = normalize_mobile(request.g('mobile'))
    factor_number = request.g('factorNumber')
    description = request.g('description') or ''
    currencies_str = request.g('currencies')
    currencies = []
    if not currencies_str:
        currencies = AVAILABLE_GATEWAY_CURRENCIES
    else:
        try:
            for currency in currencies_str.split(','):
                try:
                    currencies.append(parse_choices(GatewayCurrencies, currency))
                except ParseError:
                    return send_error(CURRENCY_INVALID, 'send_data', pg_user, 'Currency not valid: {}'.format(get_currency_codename(currency)))
        except AttributeError as e:
            return send_error(CURRENCY_INVALID, 'send_data', pg_user, 'Currencies not valid: {}'.format(e.__str__()))
    if not currencies:
        currencies = AVAILABLE_GATEWAY_CURRENCIES

    # Check invoice amount
    if not amount_rial and not amount_tether:
        return send_error(AMOUNT_REQUIRED, 'send_data', pg_user)
    if amount_rial and amount_tether:
        return send_error(DUPLICATED_AMOUNT, 'send_error', pg_user)
    if amount_rial:
        min_order = settings.NOBITEX_OPTIONS['minOrders'][Currencies.rls] / 2
        if amount_rial < min_order:
            return send_error(AMOUNT_MIN, 'send_data', pg_user, 'Amount: {}'.format(request.g('amount')))
        if amount_rial > 50_000_000_0:
            return send_error(AMOUNT_MAX, 'send_data', pg_user, 'Amount: {}'.format(request.g('amount')))
    if amount_tether:
        min_order = settings.NOBITEX_OPTIONS['minOrders'][Currencies.usdt] / 2
        if amount_tether < min_order:
            return send_error(USD_AMOUNT_MIN, 'send_data', pg_user, 'USDAmount: {}'.format(amount_tether))
        if amount_tether > 5_000:
            return send_error(USD_AMOUNT_MAX, 'send_data', pg_user, 'USDAmount: {}'.format(amount_tether))

    # Check User Restrictions
    if pg_user.user.is_restricted('Gateway'):
        return send_error(API_RESTRICTED, 'send_data', pg_user, 'User is restricted.')

    # Check redirect url
    redirect_unparsed = request.g('callbackURL')
    if not redirect_unparsed:
        return send_error(REDIRECT_REQUIRED, 'send_data', pg_user)
    try:
        redirect_url = urlparse(redirect_unparsed)._replace(query='')._replace(fragment='')
    except ValueError:
        return send_error(REDIRECT_FORMAT, 'send_data', pg_user, 'Redirect: {}'.format(redirect_unparsed))
    if not redirect_url.netloc:
        return send_error(REDIRECT_FORMAT, 'send_data', pg_user, 'Redirect: {}'.format(redirect_unparsed))
    try:
        pg_url_domains = pg_user.get_domains_url()
    except ValueError as e:
        return send_error(FAILED_ERROR, 'send_data', pg_user, 'Domain: {}, error: {}'.format(pg_user.domain.lower(), e.__str__()))
    domain_is_allowed = redirect_url.netloc in pg_url_domains
    if not settings.IS_PROD:
        request_base_domain = redirect_url.netloc[:redirect_url.netloc.find(':')]
        if request_base_domain in ['localhost', '127.0.0.1']:
            domain_is_allowed = True
    if not domain_is_allowed:
        return send_error(
            REDIRECT_BAD_DOMAIN,
            'send_data',
            pg_user,
            'Redirect: {}, Domain: {}'.format(redirect_url.netloc, pg_url_domains),
        )

    # Check Description
    if len(description) > 255:
        return send_error(DESCRIPTION_LENGTH, 'send_data', pg_user, 'Description: {}'.format(description))

    # Add pending request
    pending_request = PaymentGatewayInvoice.objects.create(
        pg_user=pg_user,
        amount=amount_rial,
        amount_tether=amount_tether,
        redirect=redirect_url.geturl(),
        mobile=mobile,
        factor_number=factor_number,
        description=description
    )
    amount = pending_request.settle_amount
    for curr in currencies:
        crypto_amount = gateway_exchange_amount(Market.get_for(curr, pending_request.settle_tp), amount)
        if not crypto_amount or crypto_amount <= Decimal(0):
            return send_error(FAILED_ERROR, 'send_data', pg_user,
                              'Cannot get amount from price. market: {}, price: {}'.format(get_currency_codename(curr), amount))
        place = 8
        crypto_amount = round(crypto_amount + Decimal(5 * 10 ** (-1 * (place + 1))), place)
        rate = Decimal(amount)/Decimal(crypto_amount)
        res = available_gateway[curr].create_request(pending_request, rate,
                                                     {'amount': str(crypto_amount), 'memo': description,
                                                      'expiration': str(1800),
                                                      'force': True})

        if res.get('error'):
            if res.get('errorCode') == -1:
                notif_title = '♦️ *Server Error*'
                msg = '*Request to gateway server {} has been failed'.format(get_currency_codename(curr))
                Notification.notify_admins(msg, title=notif_title, channel='critical')
            return send_error(FAILED_ERROR, 'send_data', pg_user, 'Currency: {}, Error: {}'.format(get_currency_codename(curr), res.get('error')))
    return {
        'status': 'success',
        'token': pending_request.token.hex,
    }


@public_api
def get_request_data(request, token):
    """

    :param request:
    :param token:
    :return:
    """
    try:
        token = parse_uuid(token)
    except ParseError:
        return send_error(TOKEN_INVALID, 'get_request_data', description='Token: {}'.format(token), create_log=False)
    currencies_str = request.g('currencies')

    pg_invoice = PaymentGatewayInvoice.objects.filter(token=token).first()
    if not pg_invoice:
        return send_error(TOKEN_NOT_FOUND, 'get_request_data', description='Token: {}'.format(token), create_log=False)
    pg_user = pg_invoice.pg_user

    currencies = []
    if not currencies_str:
        currencies = AVAILABLE_GATEWAY_CURRENCIES
    else:
        try:
            for currency in currencies_str.split(','):
                try:
                    currencies.append(parse_choices(GatewayCurrencies, currency))
                except ParseError:
                    return send_error(CURRENCY_INVALID, 'get_request_data', pg_user,
                                      'Currency not valid: {}'.format(get_currency_codename(currency)))
        except AttributeError as e:
            return send_error(CURRENCY_INVALID, 'get_request_data', pg_user,
                              'Currencies not valid: {}'.format(e.__str__()))

    if not currencies:
        currencies = AVAILABLE_GATEWAY_CURRENCIES
    res = {
        'info': {
            'name': pg_user.site_name,
            'domain': pg_user.domain,
            'logo': None,
            'factorNumber': pg_invoice.factor_number,
            'description': pg_invoice.description,
            'callbackUrl': pg_invoice.redirect
        },
        'paymentData': {}
    }
    pending_requests = PendingWalletRequest.objects.filter(pg_req__token=token)
    if not pending_requests:
        return send_error(TOKEN_NOT_FOUND, 'get_request_data', pg_user,
                          'Request not exist for token: {}'.format(token))
    for currency in currencies:
        pg_wallet_requests = pending_requests.filter(tp=currency).first()
        if not pg_wallet_requests:
            continue
        update_pg_req = available_gateway.get(currency).get_request(pg_wallet_requests)
        if update_pg_req.get('error'):
            if update_pg_req.get('errorCode') == -1:
                notif_title = '♦️ *Server Error*'
                msg = '*Request to gateway server {} has been failed'.format(get_currency_codename(currency))
                Notification.notify_admins(msg, title=notif_title, channel='critical')

            return send_error(FAILED_ERROR, 'get_request_data', pg_user, 'error: {}, address: {}'.format(update_pg_req.get('error'), pg_wallet_requests.address))
        res['paymentData'][get_currency_codename(currency)] = update_pg_req['result']
        if update_pg_req['result']['status'].lower() == PendingWalletRequest.STATUS.unknown:
            notif_title = '♦️ *Server Error*'
            msg = '* {} server returns UNKNOWN status'.format(get_currency_codename(currency))
            Notification.notify_admins(msg, title=notif_title, channel='critical')
    return {
        'status': 'success',
        'result': res
    }


@public_post_api
def verify(request):
    """Verify payment.

    -------------------------

    Request may contains:
        * api (string): You API key to connect nobitex.market
        * token (integer): Token of PaymentRequest.
    Return a dictionary on success with format of:
        {
            'status': 1,
            'amount': Amount in rial,
            'cryptoAmount': Exchanged amount in crypto,
            'txHash': Hash of (factorNumber, amount, api-secret),
            'factorNumber': Factor number(optional),
            'mobile': Mobile number(optional),
            'description': Description(optional),
        }


    On error return one of dictionary with format of:
        {
            'status': 'failed',

            'code': ERROR CODE,

            'message': ERROR MESSAGE
        }


    which ERROR CODE is one of:
        API_INVALID, TOKEN_INVALID, API_REQUIRED, TOKEN_REQUIRED, API_NOT_FOUND, TOKEN_NOT_FOUND,
        UNVERIFIED, VERIFIED_BEFORE, FAILED_ERROR




    :parameter request: HttpRequest
    :return: {'status', 'token'}

    """
    with transaction.atomic():
        try:
            api = get_api(request.g('api'), request)
        except ParseError:
            return send_error(API_INVALID, 'verify', description='API: {}'.format(request.g('api')))
        try:
            token = parse_uuid(request.g('token'))
        except ParseError:
            return send_error(TOKEN_INVALID, 'verify', description='Token: {}'.format(request.g('token')))

        # Validations
        if not api:
            return send_error(API_REQUIRED, 'verify')

        if not token:
            return send_error(TOKEN_REQUIRED, 'verify')

        # Get models
        try:
            pg_user = PaymentGatewayUser.objects.get(api=api)
        except PaymentGatewayUser.DoesNotExist:
            return send_error(API_NOT_FOUND, 'verify', description='API: {}'.format(request.g('api')))

        try:
            pg_invoice = PaymentGatewayInvoice.objects.get(pg_user=pg_user, token=token)
        except PaymentGatewayInvoice.DoesNotExist:
            return send_error(TOKEN_NOT_FOUND, 'verify', pg_user, 'Token: {}'.format(token))
        pg_reqs = PendingWalletRequest.objects.filter(pg_req=pg_invoice)
        paid_pg_req = None
        for pg_req in pg_reqs:
            update_pg_req = available_gateway.get(pg_req.tp).get_request(pg_req)
            if update_pg_req.get('error'):
                return send_error(FAILED_ERROR, 'verify', pg_user, update_pg_req.get('error'))
            if pg_req.status == PendingWalletRequest.STATUS.paid:
                paid_pg_req = pg_req
                break
        if not paid_pg_req:
            return send_error(UNVERIFIED, 'verify', pg_user)

        if paid_pg_req.verify:
            return send_error(VERIFIED_BEFORE, 'verify', pg_user)
        paid_pg_req.verify = True
        paid_pg_req.save(update_fields=['verify'])
        tx_id = token.hex + str(pg_invoice.settle_amount) + pg_user.secret.hex
        tx_hash = hashlib.sha256(tx_id.encode())
        return {
            'status': 'success',
            'amount': pg_invoice.settle_amount,
            'cryptoAmount': paid_pg_req.crypto_amount,
            'txHash': tx_hash.hexdigest(),
            'factorNumber': pg_invoice.factor_number,
            'mobile': pg_invoice.mobile,
            'description': pg_invoice.description,
        }


@public_post_api
def request_refund(request):
    email = request.g('email')
    if not validate_email(email):
        return send_error(EMAIL_INVALID, 'request_refund', description='Email: {}'.format(email))
    try:
        token = parse_uuid(request.g('token'))
    except ParseError:
        return send_error(TOKEN_INVALID, 'request_refund', description='Token: {}'.format(request.g('token')))
    if not token:
        return send_error(TOKEN_REQUIRED, 'request_refund')
    try:
        currency = parse_currency(request.g('currency'))
    except ParseError:
        return send_error(CURRENCY_INVALID, 'request_refund', description='Currecny: {}'.format(request.g('currency')))
    pg_refund = PaymentRequestRefund(token=token, email=email)
    if currency:
        try:
            pg_req = PendingWalletRequest.objects.get(pg_req__token=token, tp=currency)
        except PaymentGatewayInvoice.DoesNotExist:
            return send_error(TOKEN_NOT_FOUND, 'request_refund',
                              description='Token: {}, Currency: {}'.format(token, get_currency_codename(currency)))
        if pg_req.status not in PendingWalletRequest.REFUND_STATUS:
            return send_error(REFUND_INVALID, 'request_refund',
                              description='Token: {}, Currency: {}'.format(token, get_currency_codename(currency)))

        pg_refund.pg_req = pg_req
    pg_refund.save()
    return {
        'status': 'success',
        'reference': pg_refund.reference_code.hex,
    }


@api
def user_gateways_list(request):
    user = request.user
    gateways = PaymentGatewayUser.objects.filter(user=user)
    return {
        'status': 'success',
        'gateways': gateways
    }


@api
def gateway_set_logo(request):
    files = parse_files(request.g('logo'))
    gateway = PaymentGatewayUser.objects.filter(user=request.user).first()
    if not gateway:
        return {
            'status': 0,
            'message': 'There is no gateway'
        }
    if not files:
        return {
            'status': 0,
            'message': 'no files uploaded'
        }
    gateway.logo_image = files[0]
    gateway.save(update_fields=['logo_image'])
    return {
        'status': 1,
        'message': 'ok!'
    }


@api
def gateway_withdraw(request):
    pass


@api
def user_transactions_list(request):
    user = request.user
    tp = request.g('type') # deposit, withdraw, otherwise both
    txs = []
    if tp == 'deposit':
        wallet_requests = PendingWalletRequest.objects.filter(pg_req__pg_user__user=user)\
            .select_related('settle_tx', 'pg_req').order_by('-created_time')
        for wr in wallet_requests:
            txs.append({
                'currency': get_currency_codename(wr.tp),
                'tp': 'deposit',
                'amount': wr.exact_crypto_amount,
                'factorNumber': wr.pg_req.factor_number,
                'fee': Decimal('0'),
                'created_at': wr.created_time,
                'status': wr.status,
            })
    elif tp == 'withdraw':
        withdraws = WithdrawRequest.objects.filter(wallet__user=user, tp=WithdrawRequest.TYPE.gateway)\
            .select_related('transaction').order_by('-created_at')
        for withdraw in withdraws:
            txs.append({
                'currency': get_currency_codename(withdraw.currency),
                'tp': 'withdraw',
                'amount': withdraw.amount,
                'factorNumber': withdraw.blockchain_url,
                'fee': Decimal('0'),
                'created_at': withdraw.transaction.created_at if withdraw.transaction else withdraw.created_at,
                'status': serialize_choices(WithdrawRequest.STATUS, withdraw.status),
            })
    else: # all gateway related transactions TODO: Add refund txs
        wallet_balances = {}
        transactions = Transaction.objects.filter(wallet__user=user, tp=Transaction.TYPE.gateway).order_by('created_at')
        for tx in transactions:
            balance = wallet_balances.get(tx.currency, Decimal('0')) + tx.amount
            wallet_balances[tx.currency] = balance
            txs.append({
                'pk': tx.pk,
                'currency': get_currency_codename(tx.currency),
                'tp': 'deposit' if tx.amount > 0 else 'withdraw',
                'amount': tx.amount,
                'balance': balance,
                'fee': Decimal('0'),
                'created_at': tx.created_at,
            })
        txs.reverse()

    return {
        'status': 'success',
        'txs': txs
    }



@api
def user_payments_list(request):
    user = request.user
    user_payments = PendingWalletRequest.objects.filter(pg_req__pg_user__user=user).select_related('pg_req')
    return {
        'status': 1,
        'payments': user_payments
    }

@api
def user_payment_verify(request):
    user = request.user
    id = request.g('paymentID')
    payment = PendingWalletRequest.objects.filter(pk=id).select_related('pg_req__pg_user').first()
    if not payment:
        return {
            'status': 0,
            'message': 'Invalid Payment id'
        }
    if payment.pg_req.pg_user.user != user:
        return  PermissionDenied
    payment.verify = True
    payment.save(update_fields=['verify'])
    return {
        'status': 1,
    }


@public_api
def get_exchange_amount(request):
    try:
        amount = parse_money(request.g('amount'))
    except ParseError:
        return send_error(AMOUNT_INT, 'get_exchange_amount', description='Amount: {}'.format(request.g('amount')), create_log=False)

    currencies_str = request.g('currencies')
    currencies = []
    if not currencies_str:
        currencies = AVAILABLE_GATEWAY_CURRENCIES
    else:
        try:
            for currency in currencies_str.split(','):
                try:
                    currencies.append(parse_choices(GatewayCurrencies, currency))
                except ParseError:
                    return send_error(CURRENCY_INVALID, 'get_exchange_amount',
                                      description='Currency not valid: {}'.format(get_currency_codename(currency)), create_log=False)
        except AttributeError as e:
            return send_error(CURRENCY_INVALID, 'get_exchange_amount', description='Currencies not valid: {}'.format(e.__str__()), create_log=False)

    if not currencies:
        currencies = AVAILABLE_GATEWAY_CURRENCIES

    dst_currency = parse_currency(request.g('dstCurrency', 'rls'), required=True)

    result = {}
    for currency in currencies:
        crypto_amount = gateway_exchange_amount(Market.get_for(currency, dst_currency), amount)
        if not crypto_amount or crypto_amount <= Decimal(0):
            return send_error(FAILED_ERROR, 'get_exchange_amount', description='Cannot get amount from price. market_src: {}, market_dst: {}, price: {}'.format(get_currency_codename(currency), get_currency_codename(dst_currency), amount), create_log=False)
        result[get_currency_codename(currency)] = crypto_amount
    return {
        'status': 'success',
        'res': result
    }


@ratelimit(key='user_or_ip', rate='5/h', block=True)
@api
def create_gateway_user(request):
    user = request.user
    domains = request.g('domains')
    site_name = request.g('siteName')
    logo_url = request.g('logoURL')
    if not domains:
        return send_error(DOMAIN_INVALID, 'create_gateway_user', description='Empty Domains')
    valid_domains = []
    for domain in domains.split(","):
        domain = domain.strip()
        try:
            validate = URLValidator(schemes=('http', 'https'))
            validate(domain)
            valid_domains.append(domain)
        except:
            return send_error(DOMAIN_INVALID, 'create_gateway_user', description='Invalid domain: {}'.format(domain))
    if not site_name:
        return send_error(SITENAME_INVALID, 'create_gateway_user', description='Invalid site name')
    PaymentGatewayUser.objects.create(
        user=user,
        domain=','.join(valid_domains),
        site_name=site_name,
        logo_image=logo_url
    )
    return {
        'status': 'success',
    }


@api
def gateways_chart_data(request):
    total_duration = datetime.timedelta(days=13)
    interval = datetime.timedelta(days=1)
    end = ir_now()
    start = end - total_duration

    dates = []
    rial_incomes = []
    tether_incomes = []
    tx_counts = []

    gp_txs = Transaction.objects.filter(tp=Transaction.TYPE.gateway, wallet__user=request.user)
    start_dt = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while start_dt < end:
        end_dt = start_dt + interval
        dt_txs = gp_txs.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        rial_income = dt_txs.filter(wallet__currency=RIAL).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        tether_income = dt_txs.filter(wallet__currency=TETHER).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        dates.append(start_dt.date())
        rial_incomes.append(rial_income)
        tether_incomes.append(tether_income)
        tx_counts.append(dt_txs.count())
        start_dt += interval

    return {
        'status': 'success',
        'data': {
            'dates': dates,
            'rialIncomes': rial_incomes,
            'tetherIncomes': tether_incomes,
            'txCounts': tx_counts
        }
    }


@api
def wallets_list(request):
    pg_wallets = Wallet.objects.filter(user=request.user, currency__in=[RIAL, TETHER], type=Wallet.WALLET_TYPE.spot)
    serialized_wallets = []
    for w in pg_wallets:
        serialized_wallets.append(serialize_wallet(w, {'level': 1}))
    return {
        'status': 'success',
        'wallets': serialized_wallets
    }

@api
def wallets_withdraw(request):
    user = request.user
    wallet = get_object_or_404(
        Wallet, pk=request.g('wallet'), user=user, currency__in=[RIAL, TETHER], type=Wallet.WALLET_TYPE.spot
    )
    amount = parse_money(request.g('amount'), required=True)
    target_address = request.g('address')
    explanations = request.g('explanations', '')
    otp = request.headers.get('x-totp')

    # Check User Restrictions
    if request.user.is_restricted('WithdrawRequest'):
        return send_error(WITHDRAW_UNAVAILABLE, 'wallets_withdraw')

    # Verify otp
    if user.requires_2fa and not check_user_otp(otp, user):
        return send_error(INVALID_2FA, 'wallets_withdraw')

    # Check User level limitation
    if not UserLevelManager.is_eligible_to_withdraw(user, wallet.currency, amount):
        return send_error(WITHDRAW_AMOUNT_LIMITATION, 'wallets_withdraw')

    # IRR Bank Account
    bank_account = None
    if wallet.currency == RIAL:
        bank_account = get_object_or_404(BankAccount, user=user, pk=target_address, confirmed=True)
        target_address = bank_account.display_name

    if amount > wallet.active_balance:
        return send_error(INSUFFICIENT_BALANCE, 'wallets_withdraw')

    if not WithdrawRequest.check_user_limit(user, wallet.currency):
        return send_error(WITHDRAW_LIMIT_REACHED, 'wallets_withdraw')

    if amount < settings.NOBITEX_OPTIONS['minWithdraws'][wallet.currency]:
        return send_error(AMOUNT_TOO_LOW, 'wallets_withdraw')

    if amount > settings.NOBITEX_OPTIONS['maxWithdraws'][wallet.currency]:
        return send_error(AMOUNT_TOO_HIGH, 'wallets_withdraw')

    withdraw_request = WithdrawRequest.objects.create(
        tp=WithdrawRequest.TYPE.gateway,
        wallet=wallet,
        target_address=target_address,
        target_account=bank_account,
        amount=amount,
        explanations=explanations,
        tag=None,
    )

    return {
        'status': 'success',
        'withdraw': withdraw_request,
    }

from datetime import datetime, timedelta
from decimal import Decimal

import pytz
import requests
from django.conf import settings
from django.db import transaction
from django.utils.timezone import now

from exchange.accounts.models import Notification, User
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.connections import (
    NobitexServerException,
    get_electrum_gateway,
    get_electrum_ltc_gateway,
    get_ripple_gateway,
)
from exchange.base.models import ACTIVE_CRYPTO_CURRENCIES, Currencies, get_currency_codename
from exchange.blockchain.explorer import BlockchainExplorer
from exchange.gateway.models import GatewayCurrencies, PaymentGatewayLog, PendingWalletRequest
from exchange.market.models import Order
from exchange.wallet.models import Wallet


class NobitexGatewayException(Exception):
    pass


class GeneralGateway:
    def get_client(self):
        raise NobitexGatewayException("This should be overridden by child")

    def create_request(self, pg_req, rate, option):
        raise NobitexGatewayException("This should be overridden by child")

    def get_request(self, pg_req):
        raise NobitexGatewayException("This should be overridden by child")

    def validate(self, pg_req):
        txs = BlockchainExplorer.get_wallet_transactions(pg_req.address, pg_req.tp)
        if not txs or len(txs) < 1:
            print('txs is null')
            return
        else:
            txs.sort()
            tx = txs[0]

            tx_hash = tx.hash
            if not tx_hash:
                return
            if tx_hash.startswith('0x') and len(tx_hash) > 20:
                tx_hash = tx_hash[2:]

            # Get deposited value
            if tx.value < Decimal('0'):
                print('[Withdraw]')
                return
            if tx.value == Decimal('0'):
                print('[Zero]')
                return

            # Check confirmations and add to wallet balance
            coin_info = CURRENCY_INFO.get(pg_req.tp)
            network = coin_info.get('default_network')
            needed_confirms = coin_info.get('network_list', {}).get(network, {}).get('min_confirm')
            if not needed_confirms:
                return
            print('confirms={}/{}'.format(tx.confirmations, needed_confirms), end='\t')
            if tx.is_double_spend:
                print('[!DoubleSpend]', end='\t')
                needed_confirms *= 3

            if tx.confirmations >= needed_confirms:
                return tx_hash
            return


class ElectrumBaseGateway(GeneralGateway):
    currency = GatewayCurrencies.btc

    def create_request(self, pg_req, rate, option):
        try:
            wallet_req = self.get_client().request('addrequest', option)
        except NobitexServerException as e:
            m = '[NobitexServerException] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': -1
            }
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': 0
            }
        if wallet_req.get('error'):
            return {
                'status': -1,
                'error': wallet_req.get('error'),
                'errorCode': 1
            }
        if not wallet_req.get('result'):
            return {
                'status': -1,
                'error': 'Unknown Error',
                'errorCode': 2
            }
        wallet_req = wallet_req['result']
        PendingWalletRequest.objects.create(
            req_id=wallet_req.get('id'),
            pg_req=pg_req,
            uri=wallet_req.get('URI'),
            address=wallet_req.get('address'),
            crypto_amount=wallet_req.get('amount'),
            expiry=int(wallet_req.get('exp', 0)) or 1800,
            status=wallet_req.get('status'),
            created_time=datetime.fromtimestamp(int(wallet_req.get('time')), tz=pytz.utc),
            tp=self.currency,
            rate=rate
        )
        return {
            'status': 1,
        }

    def get_request(self, pg_req):
        if pg_req.status.lower() in [PendingWalletRequest.STATUS.paid, PendingWalletRequest.STATUS.expired]:
            return {
                'status': 1,
                'result': {
                    'expireTime': now(),
                    'remainTime': 0,
                    'time': pg_req.created_time,
                    'amount': pg_req.crypto_amount,
                    'exp': pg_req.expiry,
                    'address': pg_req.address,
                    'memo': pg_req.pg_req.description,
                    'id': pg_req.req_id,
                    'URI': pg_req.uri,
                    'status': pg_req.status,
                    'confirmations': pg_req.confirmations,
                    'rate': pg_req.rate,
                },
            }
        try:
            req = self.get_client().request('getrequest', {'key': pg_req.address})
        except NobitexServerException as e:
            m = '[NobitexServerException] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': -1
            }
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': 0
            }
        if req.get('error'):
            return {
                'status': -1,
                'error': req.get('error'),
                'errorCode': 1
            }
        if not req.get('result'):
            return {
                'status': -1,
                'error': 'Unknown Error',
                'errorCode': 2
            }
        req_status = req['result'].get('status', PendingWalletRequest.STATUS.unknown)
        pg_req.confirmations = req['result'].get('confirmations', 0)
        if req_status.lower() == PendingWalletRequest.STATUS.paid:
            needed_confirmations = settings.NOBITEX_OPTIONS['requiredConfirms'][pg_req.tp] if settings.IS_PROD else 0
            # Partial paid
            if req['result'].get('amount') != pg_req.crypto_amount:
                pg_req.status = PendingWalletRequest.STATUS.partial

            # Unconfirmed paid
            elif req['result'].get('confirmations', 0) < needed_confirmations:
                pg_req.status = PendingWalletRequest.STATUS.unconfirmed

            else:
                # tx_hash = self.validate(pg_req)
                # if not tx_hash:
                #     pg_req.status = PendingWalletRequest.STATUS.unconfirmed
                # else:
                # pg_req.tx_hash = tx_hash
                pg_req.status = PendingWalletRequest.STATUS.paid

        else:
            pg_req.status = req_status.lower()
        pg_req.save(update_fields=['confirmations', 'status'])
        expire_time = pg_req.created_time + timedelta(seconds=pg_req.expiry)
        remaining_time = expire_time - now()
        res = {
            'expireTime': expire_time,
            'remainTime': remaining_time.total_seconds(),
            'time': pg_req.created_time,
            'amount': pg_req.crypto_amount,
            'exp': pg_req.expiry,
            'address': pg_req.address,
            'memo': pg_req.pg_req.description,
            'id': pg_req.req_id,
            'URI': pg_req.uri,
            'status': pg_req.status,
            'confirmations': pg_req.confirmations,
            'rate': pg_req.rate,
        }
        # print(res)
        return {
            'status': 1,
            'result': res,
        }


class ElectrumBTC(ElectrumBaseGateway):
    currency = GatewayCurrencies.btc

    def get_client(self):
        return get_electrum_gateway()


class ElectrumLTC(ElectrumBaseGateway):
    currency = GatewayCurrencies.ltc

    def get_client(self):
        return get_electrum_ltc_gateway()


class RippleXRP(GeneralGateway):
    currency = GatewayCurrencies.xrp

    def get_client(self):
        return get_ripple_gateway(settings.GATEWAY_XRP_JSONRPC_URL)

    def create_request(self, pg_req, rate, option):
        try:
            wallet_req = self.get_client().request('nobitex_addRequest', option)
        except NobitexServerException as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': -1
            }
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': 0
            }
        if wallet_req.get('error'):
            return {
                'status': -1,
                'error': wallet_req.get('error'),
                'errorCode': 1
            }
        if not wallet_req.get('result'):
            return {
                'status': -1,
                'error': 'Unknown Error',
                'errorCode': 2
            }
        wallet_req = wallet_req['result']
        pending_request = PendingWalletRequest.objects.create(
            pg_req=pg_req,
            address=wallet_req.get('address'),
            crypto_amount=int(float(option.get('amount'))*100),
            expiry=int(option.get('expiration', 0)) or 1800,
            status=PendingWalletRequest.STATUS.pending,
            created_time=now(),
            tp=GatewayCurrencies.xrp,
            rate=rate
        )
        pending_request.req_id = pending_request.pk
        pending_request.save(update_fields=['req_id'])
        return {
            'status': 1,
            'result': pending_request
        }

    def get_request(self, pg_req):
        if pg_req.status.lower() in [PendingWalletRequest.STATUS.paid, PendingWalletRequest.STATUS.expired]:
            return {
                'status': 1,
                'result': {
                    'expireTime': now(),
                    'remainTime': 0,
                    'time': pg_req.created_time,
                    'amount': pg_req.crypto_amount,
                    'exp': pg_req.expiry,
                    'address': pg_req.address,
                    'memo': pg_req.pg_req.description,
                    'id': pg_req.req_id,
                    'URI': pg_req.uri,
                    'status': pg_req.status,
                    'confirmations': pg_req.confirmations,
                    'rate': pg_req.rate,
                },
            }
        try:
            creation_time = pg_req.created_time.timestamp()
            req = self.get_client().request('nobitex_getRequest', {
                'address': pg_req.address,
                'tag': pg_req.req_id,
                'creationTime': creation_time,
                'expireTime': creation_time + pg_req.expiry,
                'amount': pg_req.crypto_amount
            })
        except NobitexServerException as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': -1
            }
        except Exception as e:
            m = '[Exception] {}'.format(str(e))
            print(m)
            return {
                'status': -1,
                'error': m,
                'errorCode': 0
            }
        if req.get('error'):
            return {
                'status': -1,
                'error': req.get('error'),
                'errorCode': 1
            }
        if not req.get('result'):
            return {
                'status': -1,
                'error': 'Unknown Error',
                'errorCode': 2
            }
        req_status = req['result'].get('status', PendingWalletRequest.STATUS.unknown)
        pg_req.confirmations = req['result'].get('confirmations', 0)

        if req_status.lower() == PendingWalletRequest.STATUS.paid:
            needed_confirmations = settings.NOBITEX_OPTIONS['requiredConfirms'][pg_req.tp] if settings.IS_PROD else 0
            # Partial paid
            paid_amount = round(req['result'].get('amount'))
            if paid_amount != pg_req.crypto_amount:
                pg_req.status = PendingWalletRequest.STATUS.partial

            # Unconfirmed paid
            elif req['result'].get('confirmations', 0) < needed_confirmations:
                pg_req.status = PendingWalletRequest.STATUS.unconfirmed

            else:
                # tx_hash = self.validate(pg_req)
                # if not tx_hash:
                #     pg_req.status = PendingWalletRequest.STATUS.unconfirmed
                # else:
                # pg_req.tx_hash = tx_hash
                pg_req.status = PendingWalletRequest.STATUS.paid

        else:
            pg_req.status = req_status.lower()
        pg_req.uri = req['result'].get('uri')
        pg_req.save(update_fields=['confirmations', 'status', 'uri'])
        expire_time = pg_req.created_time + timedelta(seconds=pg_req.expiry)
        remaining_time = expire_time - now()
        res = {
            'expireTime': expire_time,
            'remainTime': remaining_time.total_seconds(),
            'time': pg_req.created_time,
            'amount': pg_req.crypto_amount,
            'exp': pg_req.expiry,
            'address': pg_req.address,
            'dstTag': pg_req.req_id,
            'memo': pg_req.pg_req.description,
            'id': pg_req.req_id,
            'URI': pg_req.uri,
            'status': pg_req.status,
            'confirmations': pg_req.confirmations,
            'rate': pg_req.rate,
        }
        # print(res)
        return {
            'status': 1,
            'result': res,
        }


available_gateway = {
    Currencies.btc: ElectrumBTC(),
    Currencies.ltc: ElectrumLTC(),
    Currencies.xrp: RippleXRP(),
}


def create_gateway_order(pg_req):
    with transaction.atomic():
        if pg_req is None:
            return
        try:
            if pg_req.status not in [PendingWalletRequest.STATUS.unconfirmed, PendingWalletRequest.STATUS.paid]:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=101,
                    code_description='Status mismatched from unconfirmed or paid',
                    description='Status is {}'.format(pg_req.status),
                    method='create_gateway_order',
                )
                return
            if pg_req.tp not in ACTIVE_CRYPTO_CURRENCIES:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=102,
                    code_description='Gateway currency does not exist',
                    description='Currency is {}'.format(pg_req.tp),
                    method='create_gateway_order',
                )
                return
            if pg_req.crypto_amount is None or pg_req.crypto_amount <= 0:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=103,
                    code_description='Amount is negative',
                    description='Currency is {}'.format(pg_req.crypto_amount),
                    method='create_gateway_order',
                )
                return
            bot_gateway = User.objects.filter(email='gateway@internal.com').first()
            if not bot_gateway:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=104,
                    code_description='Gateway bot does not exist',
                    description='',
                    method='create_gateway_order',
                )
                return
            if pg_req.create_order:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=105,
                    code_description='Order created before',
                    description='',
                    method='create_gateway_order',
                )
                return
            order, err = Order.create(
                user=bot_gateway,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.market,
                src_currency=pg_req.tp,
                dst_currency=pg_req.pg_req.settle_tp,
                amount=pg_req.exact_crypto_amount,
                price=0,
                is_validated=True,
            )
            if err:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=106,
                    code_description='Order creation error',
                    description=err,
                    method='create_gateway_order',
                )
                return
            pg_req.create_order = True
            pg_req.save(update_fields=['create_order'])
        except AttributeError as e:
            PaymentGatewayLog.objects.create(
                code=107,
                code_description='Attribute error',
                description=e.__str__(),
                method='create_gateway_order',
            )
            return


def create_gateway_transaction(pg_req):
    with transaction.atomic():
        if pg_req is None:
            return
        try:
            if pg_req.status != PendingWalletRequest.STATUS.paid:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=111,
                    code_description='Status mismatched from paid',
                    description='Status is {}'.format(pg_req.status),
                    method='create_gateway_transaction',
                )
                return
            if pg_req.pg_req is None or pg_req.pg_req.settle_amount <= 0:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=112,
                    code_description='Amount is negative',
                    description='Amount is {}'.format(pg_req.pg_req.settle_amount),
                    method='create_gateway_transaction',
                )
                return
            if pg_req.settle:
                PaymentGatewayLog.objects.create(
                    pg_user=pg_req.pg_req.pg_user,
                    code=113,
                    code_description='Settled before',
                    description='',
                    method='create_gateway_transaction',
                )
                return
            w = Wallet.get_user_wallet(pg_req.pg_req.pg_user.user, pg_req.pg_req.settle_tp)
            tr = w.create_transaction(
                'gateway',
                pg_req.pg_req.settle_amount,
                description='Gateway Payment: token {}'.format(pg_req.pg_req.token),
            )
            tr.commit()
            pg_req.settle = True
            pg_req.settle_tx = tr
            pg_req.save(update_fields=['settle', 'settle_tx'])
        except AttributeError as e:
            PaymentGatewayLog.objects.create(
                code=117,
                code_description='Attribute error',
                description=e.__str__(),
                method='create_gateway_transaction',
            )
            return


def create_callback_request(pg_req):
    params = {'status': 1, 'token': pg_req.pg_req.token}
    requests.get(url=pg_req.pg_req.redirect, params=params, proxies=settings.DEFAULT_PROXY)

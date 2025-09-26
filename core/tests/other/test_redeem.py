from decimal import Decimal

from django.test import TestCase, Client

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.market.models import Order
from exchange.redeem.models import RedeemRequest
from exchange.base.serializers import serialize
from exchange.usermanagement.block import BalanceBlockManager
from exchange.wallet.models import Wallet


class RedeemRequestTest(TestCase):

    def test_redeem_process(self):
        user = User.objects.get(pk=201)
        gala_wallet = Wallet.get_user_wallet(user, Currencies.gala)
        tx = gala_wallet.create_transaction(tp='manual', amount=Decimal('100000.12'))
        tx.commit()
        req = RedeemRequest.objects.create(
            plan=RedeemRequest.PLAN.pgala2022,
            user=user,
            amount=Decimal('99999.9'),
            redeem_value=Decimal('613009386.99'),
            status=RedeemRequest.STATUS.new,
        )
        assert serialize(req) == {
            'plan': 'PGala2020',
            'user': user.email,
            'amount': '99999.9',
            'redeemValue': '613009386.99',
            'status': 'New',
            'srcTransactionId': None,
            'hasSana': False,
            'dstTransactionId': None,
        }
        # No allow redeem while new
        result, err = req.do_redeem()
        assert result is False
        assert err == 'StatusNotRedeemable'
        req.status = RedeemRequest.STATUS.allowed
        req.save(update_fields=['status'])
        # Do redeem
        irr_wallet = Wallet.get_user_wallet(user, Currencies.rls)
        assert irr_wallet.balance == Decimal('0')
        result, err = req.do_redeem()
        assert err is None
        assert result is True
        gala_wallet.refresh_from_db()
        assert gala_wallet.balance == Decimal('0.22')
        irr_wallet.refresh_from_db()
        assert irr_wallet.balance == Decimal('613009386.99')
        req.refresh_from_db()
        assert req.status == RedeemRequest.STATUS.confirmed
        assert req.src_transaction.pk
        assert req.src_transaction.amount == Decimal('-99999.9')
        assert req.src_transaction.wallet == gala_wallet
        assert req.dst_transaction.pk
        assert req.dst_transaction.amount == Decimal('613009386.99')
        assert req.dst_transaction.wallet == irr_wallet
        assert req.dst_transaction.ref_module == 54
        assert req.dst_transaction.ref_id == req.id
        assert Order.objects.filter(
            user=user,
            src_currency=Currencies.gala,
            dst_currency=Currencies.rls,
            amount=Decimal('99999.9'),
            price=Decimal('6130.1'),
            channel=Order.CHANNEL.system_block,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.limit,
            status=Order.STATUS.active,
        ).count() == 1
        assert BalanceBlockManager.get_balance_in_order(irr_wallet, use_cache=False) == Decimal('613009386.99')
        assert BalanceBlockManager.get_balance_in_order(gala_wallet, use_cache=False) == Decimal('0')
        # Do Unblock before sana
        result, err = req.do_unblock()
        assert err == 'MissingSanaConfirmation'
        assert not result
        assert req.status == RedeemRequest.STATUS.confirmed
        assert BalanceBlockManager.get_balance_in_order(irr_wallet, use_cache=False) == Decimal('613009386.99')
        # Do Unblock after sana
        req.has_sana = True
        req.save(update_fields=['has_sana'])
        result, err = req.do_unblock()
        assert err is None
        assert result
        assert req.terms_accepted_at is not None
        assert req.terms_accepted_at > req.requested_at
        assert req.status == RedeemRequest.STATUS.done
        assert not Order.objects.filter(
            user=user,
            src_currency=Currencies.gala,
            dst_currency=Currencies.rls,
            status=Order.STATUS.active,
        ).exists()
        assert BalanceBlockManager.get_balance_in_order(irr_wallet, use_cache=False) == Decimal('0')
        assert BalanceBlockManager.get_balance_in_order(gala_wallet, use_cache=False) == Decimal('0')

    def test_redeem_api(self):
        user = User.objects.get(pk=201)
        client = Client(HTTP_AUTHORIZATION='Token user201token')
        # No RedeemRequest
        r = client.post('/redeem/pgala2022/info').json()
        assert r['status'] == 'failed'
        assert r['code'] == 'NoRedeemRequest'
        # Create request
        gala_wallet = Wallet.get_user_wallet(user, Currencies.gala)
        tx = gala_wallet.create_transaction(tp='manual', amount=Decimal('100'))
        tx.commit()
        RedeemRequest.objects.create(
            plan=RedeemRequest.PLAN.pgala2022,
            user=user,
            amount=Decimal('100'),
            redeem_value=Decimal('120_000_0'),
            status=RedeemRequest.STATUS.allowed,
        )
        # Get info
        r = client.post('/redeem/pgala2022/info').json()
        assert r['status'] == 'ok'
        assert r['redeem']['status'] == 'Allowed'
        assert r['redeem']['amount'] == '100'
        assert r['redeem']['redeemValue'] == '1200000'
        # Do redeem
        r = client.post('/redeem/pgala2022/request').json()
        assert r['status'] == 'ok'
        assert r['redeem']['user'] == user.email
        assert r['redeem']['status'] == 'Done'
        assert r['redeem']['amount'] == '100'
        assert r['redeem']['redeemValue'] == '1200000'
        assert isinstance(r['redeem']['srcTransactionId'], int)
        assert isinstance(r['redeem']['dstTransactionId'], int)
        # Do unblock
        r = client.post('/redeem/pgala2022/unblock').json()
        assert r['status'] == 'failed'
        assert r['code'] == 'AlreadyUnblocked'

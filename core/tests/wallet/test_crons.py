from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import User, Notification
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.wallet.crons import MarginBlockedBalanceCheckerCron
from exchange.wallet.models import Wallet


class MarginBlockedBalanceCheckerCronTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        user = User.objects.get(pk=201)
        cls.wallet = Wallet.get_user_wallet(user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)

    def test_consistent_blocked_balance_no_position(self):
        assert self.wallet.balance_blocked == 0
        with patch.object(Notification, 'notify_admins') as notify_admins:
            MarginBlockedBalanceCheckerCron().run()
            assert not notify_admins.called

    def test_consistent_blocked_balance_with_position(self):
        defaults = dict(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            status=Position.STATUS.open,
        )
        for values in (
            {'collateral': '64.81'},
            {'collateral': '77.6', 'src_currency': Currencies.ltc},
            {'collateral': '35.92', 'pnl': '10.23', 'status': Position.STATUS.liquidated},
        ):
            Position.objects.create(**{**defaults, **values})
        Wallet.objects.filter(pk=self.wallet.pk).update(balance_blocked='142.41')
        with patch.object(Notification, 'notify_admins') as notify_admins:
            MarginBlockedBalanceCheckerCron().run()
            assert not notify_admins.call_args

    def test_inconsistent_blocked_balance_no_position(self):
        Wallet.objects.filter(pk=self.wallet.pk).update(balance_blocked='167.82')
        with patch.object(Notification, 'notify_admins') as notify_admins:
            MarginBlockedBalanceCheckerCron().run()
            assert notify_admins.called
            assert '+167.82 Tether' in notify_admins.call_args[0][0]

    def test_inconsistent_blocked_balance_with_position(self):
        defaults = dict(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            status=Position.STATUS.open,
        )
        for values in (
            {'collateral': '64.81'},
            {'collateral': '517E4', 'dst_currency': Currencies.rls},
            {'collateral': '77.6', 'src_currency': Currencies.ltc},
            {'collateral': '50', 'user_id': 202},
            {'collateral': '35.92', 'pnl': '10.23', 'status': Position.STATUS.liquidated},
        ):
            Position.objects.create(**{**defaults, **values})
        Wallet.objects.filter(pk=self.wallet.pk).update(balance_blocked='64.81')
        with patch.object(Notification, 'notify_admins') as notify_admins:
            MarginBlockedBalanceCheckerCron().run()
            assert notify_admins.called
            assert '-77.6 Tether' in notify_admins.call_args[0][0]

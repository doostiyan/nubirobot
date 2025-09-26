from decimal import Decimal

from django.test import TestCase, override_settings

from exchange.accounts.models import User
from exchange.base.models import Currencies, ADDRESS_TYPE
from exchange.wallet.models import Wallet, WalletDepositAddress, WalletDepositTag
from exchange.wallet.serializers import serialize_wallet_addresses
from exchange.wallet.views import get_user_blocked_withdraws
from ..base.utils import create_withdraw_request


class WalletsApiTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)

    def test_get_user_blocked_withdraws(self):
        btc, eth = Currencies.btc, Currencies.eth
        assert get_user_blocked_withdraws(self.user) == {}
        create_withdraw_request(self.user, btc, '0.1')
        assert get_user_blocked_withdraws(self.user) == {}
        pw1 = create_withdraw_request(self.user, btc, '0.12', status=3)
        assert get_user_blocked_withdraws(self.user) == {btc: Decimal('0.12')}
        pw2 = create_withdraw_request(self.user, btc, '0.03', status=3)
        assert get_user_blocked_withdraws(self.user) == {btc: Decimal('0.15')}
        pw3 = create_withdraw_request(self.user, eth, '0.7231', status=2)
        assert get_user_blocked_withdraws(self.user) == {btc: Decimal('0.15'), eth: Decimal('0.7231')}
        pw2.create_transaction()
        assert get_user_blocked_withdraws(self.user) == {btc: Decimal('0.12'), eth: Decimal('0.7231')}
        pw1.create_transaction()
        assert get_user_blocked_withdraws(self.user) == {eth: Decimal('0.7231')}
        pw3.create_transaction()
        assert get_user_blocked_withdraws(self.user) == {}

    @override_settings(SEGWIT_ENABLED=True)
    def test_serialize_wallet_addresses(self):
        # Simple addresses
        w1 = Wallet.get_user_wallet(self.user, Currencies.ltc)
        assert serialize_wallet_addresses(w1) == {
            'depositAddress': None,
            'depositInfo': {
                'LTC': {'address': None, 'tag': None},
                'BSC': {'address': None, 'tag': None},
            },
            'depositTag': None,
        }
        w1.get_current_deposit_address(create=True)
        address = WalletDepositAddress.objects.get(wallet=w1).address
        assert serialize_wallet_addresses(w1) == {
            'depositAddress': address,
            'depositInfo': {
                'LTC': {'address': address, 'tag': None},
                'BSC': {'address': None, 'tag': None},
            },
            'depositTag': None,
        }
        # Addresses with tag
        w2 = Wallet.get_user_wallet(self.user, Currencies.bnb)
        assert serialize_wallet_addresses(w2) == {
            'depositAddress': None,
            'depositInfo': {
                'BNB': {'address': None, 'tag': None},
                'BSC': {'address': None, 'tag': None}
            },
            'depositTag': None,
        }
        # Bitcoin with 2 types of addresses
        w3 = Wallet.get_user_wallet(self.user, Currencies.btc)
        assert serialize_wallet_addresses(w3) == {
            'depositAddress': None,
            'depositInfo': {
                'BTC': {'address': None, 'tag': None},
                'BSC': {'address': None, 'tag': None},
                'BTCLN': {'address': None, 'tag': None},
            },
            'depositTag': None,
        }
        assert serialize_wallet_addresses(w3) == {
            'depositAddress': None,
            'depositInfo': {
                'BTC': {'address': None, 'tag': None},
                'BSC': {'address': None, 'tag': None},
                'BTCLN': {'address': None, 'tag': None},
            },
            'depositTag': None,
        }
        w3.get_current_deposit_address(create=True)
        w3.get_current_deposit_address(create=True, address_type=ADDRESS_TYPE.standard)
        segwit_address = WalletDepositAddress.objects.get(wallet=w3, type=ADDRESS_TYPE.segwit).address
        assert serialize_wallet_addresses(w3) == {
            'depositAddress': segwit_address,
            'depositInfo': {
                'BTC': {'address': segwit_address, 'tag': None},
                'BSC': {'address': None, 'tag': None},
                'BTCLN': {'address': None, 'tag': None},
            },
            'depositTag': None,
        }

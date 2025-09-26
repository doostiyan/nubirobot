from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, VerificationProfile
from exchange.base.cache import CacheManager
from exchange.base.models import BABYDOGE, CURRENCY_CODENAMES, Currencies
from exchange.features.models import QueueItem
from exchange.wallet.estimator import PriceEstimator
from exchange.wallet.models import AutomaticWithdraw, AvailableHotWalletAddress, Transaction, Wallet
from exchange.wallet.withdraw import WithdrawProcessor
from exchange.xchange.constants import ALL_XCHANGE_PAIRS_CACHE_KEY
from exchange.xchange.types import XchangeCurrencyPairPrices
from tests.base.utils import create_order, create_withdraw_request


class WalletsApiClientTest(APITestCase):
    user: User

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        PriceEstimator.get_price_range.clear()  # clean up

    def check_wallet_v2(self, response, wallet):
        assert isinstance(response['id'], int)
        assert isinstance(response['balance'], str)
        assert isinstance(response['blocked'], str)
        assert response['id'] == wallet.id
        assert Decimal(response['balance']) == wallet.balance
        assert Decimal(response['blocked']) == wallet.blocked_balance

    def test_v2_wallets_spot(self):
        btc, eth, rls = Currencies.btc, Currencies.eth, Currencies.rls
        # Check two wallets in zero balance
        response = self.client.post('/v2/wallets', {'currencies': 'rls,btc'})
        data = response.json()
        assert data['status'] == 'ok'
        assert isinstance(data['wallets'], dict)
        wallets = data['wallets']
        assert sorted(list(wallets.keys())) == ['BTC', 'RLS']
        wallet_rls = Wallet.get_user_wallet(self.user, rls)
        wallet_btc = Wallet.get_user_wallet(self.user, btc)
        self.check_wallet_v2(wallets['RLS'], wallet_rls)
        self.check_wallet_v2(wallets['BTC'], wallet_btc)
        # Create some balance and blocked_balance
        wallet_btc.balance = Decimal('0.599')
        wallet_btc.save(update_fields=['balance'])
        create_withdraw_request(self.user, btc, '0.1')  # A negative transaction is also created here
        create_withdraw_request(self.user, btc, '0.12', status=3)  # but this is included in balance
        create_order(self.user, eth, rls, '0.1', '123_455_432_1', sell=False, charge_ratio=2)
        wallet_rls.refresh_from_db()
        wallet_btc.refresh_from_db()
        # Recheck for blocked withdraw balances
        response = self.client.post('/v2/wallets', {'currencies': 'rls,btc'})
        data = response.json()
        assert data['status'] == 'ok'
        assert isinstance(data['wallets'], dict)
        wallets = data['wallets']
        assert sorted(list(wallets.keys())) == ['BTC', 'RLS']
        self.check_wallet_v2(wallets['RLS'], wallet_rls)
        self.check_wallet_v2(wallets['BTC'], wallet_btc)
        assert Decimal(wallets['BTC']['balance']) == Decimal('0.719')
        assert Decimal(wallets['BTC']['blocked']) == Decimal('0.12')
        assert Decimal(wallets['RLS']['balance']) == Decimal('246910864.2')
        assert Decimal(wallets['RLS']['blocked']) == Decimal('123455432')
        # Check all currencies response
        response = self.client.post('/v2/wallets')
        data = response.json()
        assert data['status'] == 'ok'
        assert isinstance(data['wallets'], dict)
        wallets = data['wallets']
        user_wallets = Wallet.get_user_wallets(self.user, tp=Wallet.WALLET_TYPE.spot)
        assert sorted(list(wallets.keys())) == sorted(CURRENCY_CODENAMES[w.currency] for w in user_wallets)
        for w in user_wallets:
            self.check_wallet_v2(wallets[CURRENCY_CODENAMES[w.currency]], w)

    def test_v2_wallets_margin_no_margin_wallet(self):
        response = self.client.get('/v2/wallets', {'type': 'margin'})
        data = response.json()
        assert data['status'] == 'ok'
        for wallet_id, currency_code in enumerate(('RLS', 'USDT'), start=1):
            assert currency_code in data['wallets']
            assert data['wallets'][currency_code]['id'] == wallet_id
            assert data['wallets'][currency_code]['balance'] == '0'
            assert data['wallets'][currency_code]['blocked'] == '0'

    def no_test_wallets_generate_address(self):
        # User level restriction
        r = self.client.post('/users/wallets/generate-address', {'currency': 'btc'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'CoinDepositLimitation'
        # Allow deposit
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        # Unsupported currency
        r = self.client.post('/users/wallets/generate-address', {'currency': 'lrc'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'InvalidCurrency'
        # No available address
        r = self.client.post('/users/wallets/generate-address', {'currency': 'doge'}).json()
        assert r['status'] == 'ok'
        assert r['address'] is None
        assert r['tag'] is None
        # Check that wallet object is created
        assert Wallet.objects.filter(user=self.user, currency=Currencies.doge, type=Wallet.WALLET_TYPE.spot).exists()

    def no_test_wallets_generate_address_xchange(self):
        # User level restriction
        r = self.client.post('/users/wallets/generate-address', {'currency': 'near'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'CoinDepositLimitation'
        # Allow deposit
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()
        # Unsupported currency
        r = self.client.post('/users/wallets/generate-address', {'currency': 'lrc'}).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'InvalidCurrency'
        # No available address
        r = self.client.post('/users/wallets/generate-address', {'currency': 'near', 'network': 'BSC'}).json()
        assert r['status'] == 'ok'
        assert r['address'] == '0xb26653a22de444f95cbf584a0cec39b19b75f65d'
        assert r['tag'] is None
        # Check that wallet object is created
        assert Wallet.objects.filter(user=self.user, currency=Currencies.near, type=Wallet.WALLET_TYPE.spot).exists()

    def _test_unsuccessful_wallets_generate_address(self, wallet, status_code: int, expected_response: dict = None):
        response = self.client.post('/users/wallets/generate-address', {'wallet': wallet.id})
        assert response.status_code == status_code
        if expected_response is not None:
            response_data = response.json()
            for key in expected_response.keys():
                assert expected_response[key] == response_data[key]

    def test_wallets_generate_address_wrong_wallet(self):
        self.user.user_type = User.USER_TYPES.level1
        self.user.save(update_fields=('user_type',))

        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self._test_unsuccessful_wallets_generate_address(margin_wallet, status.HTTP_404_NOT_FOUND)

        other_user = User.objects.get(pk=202)
        other_user_wallet = Wallet.get_user_wallet(other_user, Currencies.rls)
        self._test_unsuccessful_wallets_generate_address(other_user_wallet, status.HTTP_404_NOT_FOUND)

        spot_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.spot)
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        self._test_unsuccessful_wallets_generate_address(spot_wallet, 400, dict(status='failed', code='UnverifiedEmail'))

    def _test_successful_wallets_transfer(self, data, expected_src_balance, expected_dst_balance):
        currency = getattr(Currencies, data.get('currency'), 0)
        response = self.client.post('/wallets/transfer', data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['srcWallet']['id']
        assert data['srcWallet']['balance'] == expected_src_balance
        assert data['dstWallet']['id']
        assert data['dstWallet']['balance'] == expected_dst_balance
        for wallet_data in (data['srcWallet'], data['dstWallet']):
            wallet = Wallet.objects.get(user=self.user, currency=currency, id=wallet_data['id'])
            assert wallet.balance == Decimal(wallet_data['balance'])

    def _test_unsuccessful_wallets_transfer(self, data, code):
        currency = getattr(Currencies, data.get('currency'), 0)
        initial_transactions = Transaction.objects.count()
        initial_balances = list(Wallet.objects.filter(currency=currency, user=self.user).order_by('type'))
        response = self.client.post('/wallets/transfer', data)
        assert response.status_code == (status.HTTP_400_BAD_REQUEST if code == 'ParseError' else status.HTTP_200_OK)
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        assert Transaction.objects.count() == initial_transactions
        assert list(Wallet.objects.filter(currency=currency, user=self.user).order_by('type')) == initial_balances

    def test_wallets_transfer_spot_to_margin(self):
        spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        spot_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_successful_wallets_transfer(
            {'currency': 'usdt', 'amount': '10.4', 'src': 'spot', 'dst': 'margin'},
            expected_src_balance='20.2',
            expected_dst_balance='10.4',
        )

    def test_wallets_transfer_margin_to_spot(self):
        margin_wallet = Wallet.get_user_wallet(self.user, Currencies.rls, Wallet.WALLET_TYPE.margin)
        margin_wallet.create_transaction('manual', amount='1200000').commit()
        self._test_successful_wallets_transfer(
            {'currency': 'rls', 'amount': 80_000_0, 'src': 'margin', 'dst': 'spot'},
            expected_src_balance='400000',
            expected_dst_balance='800000',
        )

    def test_wallets_transfer_spot_to_credit(self):
        spot_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        spot_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_successful_wallets_transfer(
            {'currency': 'usdt', 'amount': '10.4', 'src': 'spot', 'dst': 'credit'},
            expected_src_balance='20.2',
            expected_dst_balance='10.4',
        )

    def test_wallets_transfer_credit_to_spot(self):
        credit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.credit)
        credit_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_unsuccessful_wallets_transfer(
            {'currency': 'usdt', 'amount': '10.4', 'src': 'credit', 'dst': 'spot'},
            'InvalidSrc',
        )

    def test_wallets_transfer_fails_from_debit_to_spot(self):
        debit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.debit)
        debit_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_unsuccessful_wallets_transfer(
            {'currency': 'usdt', 'amount': '10.4', 'src': 'debit', 'dst': 'spot'},
            'InvalidSrc',
        )

    def test_wallets_transfer_fails_from_spot_to_debit(self):
        debit_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.spot)
        debit_wallet.create_transaction('manual', amount='30.6').commit()
        self._test_unsuccessful_wallets_transfer(
            {'currency': 'usdt', 'amount': '10.4', 'src': 'spot', 'dst': 'debit'},
            'InvalidDst',
        )

    def test_wallets_transfer_wrong_inputs(self):
        data = {'currency': 'usdt', 'amount': '10', 'src': 'spot', 'dst': 'margin'}
        self._test_unsuccessful_wallets_transfer({**data, 'currency': 'us'}, 'ParseError')
        for amount in ('-31', '', '1,223.00'):
            self._test_unsuccessful_wallets_transfer({**data, 'amount': amount}, 'ParseError')
        self._test_unsuccessful_wallets_transfer({**data, 'amount': '1E-10'}, 'InvalidAmount')
        for src, dst in ((125, 127), ('', 'margin'), ('spot', ''), ('s', 'm')):
            self._test_unsuccessful_wallets_transfer({**data, 'src': src, 'dst': dst}, 'ParseError')
        self._test_unsuccessful_wallets_transfer({**data, 'src': 'spot', 'dst': 'spot'}, 'SameDestination')
        self._test_unsuccessful_wallets_transfer({**data, 'src': 'margin', 'dst': 'margin'}, 'SameDestination')

    def test_wallets_transfer_for_amount_above_active_balance(self):
        create_order(self.user, Currencies.btc, Currencies.usdt, '0.001', '18900', sell=False, charge_ratio=2)
        # wallet.active_balance == $18.9
        self._test_unsuccessful_wallets_transfer(
            {'currency': 'rls', 'amount': '19', 'src': 'spot', 'dst': 'margin'}, 'InsufficientBalance'
        )

    def test_wallets_transfer_for_non_dst_currencies(self):
        self._test_unsuccessful_wallets_transfer(
            {'currency': 'btc', 'amount': '0.1', 'src': 'margin', 'dst': 'spot'},
            'WalletNotFound',
        )
        spot_wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        spot_wallet.create_transaction('manual', amount='0.6').commit()
        self._test_unsuccessful_wallets_transfer(
            {'currency': 'btc', 'amount': '0.1', 'src': 'spot', 'dst': 'margin'},
            'UnsupportedCoin',
        )

    def _test_successful_v1_wallets(self, tp: str = '', expected_keys: tuple = (), prohibited_keys: tuple = ()):
        base_keys = ('currency', 'balance', 'blockedBalance', 'activeBalance', 'rialBalance', 'rialBalanceSell')
        data = {'type': tp} if tp else {}
        response = self.client.get('/users/wallets/list', data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['wallets']
        for wallet in data['wallets']:
            assert wallet['id']
            for key in base_keys + expected_keys:
                assert key in wallet
            for key in prohibited_keys:
                assert key not in wallet

    def _test_unsuccessful_v1_wallets(self, data):
        response = self.client.get('/users/wallets/list', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'ParseError'

    def test_v1_wallets_spot(self):
        expected_keys = ('depositAddress', 'depositTag', 'depositInfo')
        self._test_successful_v1_wallets(expected_keys=expected_keys)
        self._test_successful_v1_wallets('spot', expected_keys=expected_keys)

    def test_v1_wallets_margin(self):
        prohibited_keys = ('depositAddress', 'depositTag', 'depositInfo')
        self._test_successful_v1_wallets('margin', prohibited_keys=prohibited_keys)

    def test_v1_wallets_wrong_inputs(self):
        self._test_unsuccessful_v1_wallets({'type': 'futures'})
        self._test_unsuccessful_v1_wallets({'type': 2})

    def test_v1_wallets_deposit_address_cache(self):
        CacheManager.invalidate_user_wallets(self.user.id)
        self.assertNumQueries(5, self._test_successful_v1_wallets, tp='margin')
        self._test_successful_v1_wallets(tp='spot')  # Create cache with 50~60 queries -- hard to maintain exact number
        self.assertNumQueries(7, self._test_successful_v1_wallets, tp='spot')
        self.assertNumQueries(5, self._test_successful_v1_wallets, tp='margin')
        self.assertNumQueries(7, self._test_successful_v1_wallets, tp='spot')

    def test_hdwallet_hotwallet_creation(self):
        old_address = '0x912ce59144191c1204e64559fe8253a0e49e6548'
        new_address = '0xc71300423326ece9a769e477ac84943a246abd9b'
        old_hw = AvailableHotWalletAddress.objects.create(address=old_address, currency=Currencies.eth, network='ETH', active=True)
        response = self.client.post('/webhooks/hot/e7rSvUIrFsGK9zJxtUz4vyLr/hot_wallet_creation/',
                                    data={'secret': '123', 'oldAddress': old_address, 'newAddress': new_address, 'network': 'ETH'},
                                    content_type="application/json")
        print(response)
        self.assertEqual(response.status_code, 200)
        old_hw.refresh_from_db()
        self.assertEqual(old_hw.active, False)
        assert AvailableHotWalletAddress.objects.filter(address=new_address, network='ETH', active=True).exists()

    @classmethod
    def test_hdwallet_bsc_withdraw(cls):
        bnb_wtd = create_withdraw_request(user=cls.user, currency=Currencies.bnb, address='0x43AEAf5f56530e59E3C6eD8d80f6d083d2F2005C', amount=Decimal('1'), network='BSC', status=1)
        mkr_wtd = create_withdraw_request(user=cls.user, currency=Currencies.mkr, address='0x43AEAf5f56530e59E3C6eD8d80f6d083d2F2005C', amount=Decimal('1'), network='BSC', status=1)
        babydoge_wtd = create_withdraw_request(user=cls.user, currency=BABYDOGE, address='0x43AEAf5f56530e59E3C6eD8d80f6d083d2F2005C', amount=Decimal('1'), network='BSC', status=1)
        bnb_wtd.do_verify()
        mkr_wtd.do_verify()
        babydoge_wtd.do_verify()
        WithdrawProcessor[Currencies.bnb].process_withdraws([bnb_wtd], bnb_wtd.status)
        WithdrawProcessor[Currencies.mkr].process_withdraws([mkr_wtd], mkr_wtd.status)
        WithdrawProcessor[BABYDOGE].process_withdraws([babydoge_wtd], babydoge_wtd.status)
        bnb_wtd.refresh_from_db()
        mkr_wtd.refresh_from_db()
        babydoge_wtd.refresh_from_db()
        cls.user.refresh_from_db()
        assert bnb_wtd.auto_withdraw.tp == AutomaticWithdraw.TYPE.bsc_hd_hotwallet
        assert mkr_wtd.auto_withdraw.tp == AutomaticWithdraw.TYPE.bsc_hd_hotwallet_bep20
        assert babydoge_wtd.auto_withdraw.tp == AutomaticWithdraw.TYPE.fake

    @patch('exchange.wallet.estimator.XCHANGE_CURRENCIES', [Currencies.bnt])
    def test_get_wallet_balance_with_exchange_coins(self):
        QueueItem.objects.create(user=self.user, feature=QueueItem.FEATURES.new_coins, status=QueueItem.STATUS.done)
        cache.set(ALL_XCHANGE_PAIRS_CACHE_KEY, [(Currencies.bnt, Currencies.rls)])
        bnt_wallet = Wallet.get_user_wallet(self.user, Currencies.bnt)
        bnt_wallet.balance = 2.5
        bnt_wallet.save()
        cache.set(
            'xchange_pair_price_182_2',
            vars(XchangeCurrencyPairPrices(buy_price=Decimal('432955.86978'), sell_price=Decimal('424317.663'))),
        )

        response = self.client.get('/users/wallets/list')

        assert response.status_code == 200
        output = response.json()
        assert output['wallets'][21]['currency'] == 'bnt'
        assert output['wallets'][21]['balance'] == '2.5'
        assert output['wallets'][21]['rialBalance'] == 1082389
        assert output['wallets'][21]['rialBalanceSell'] == 1060794

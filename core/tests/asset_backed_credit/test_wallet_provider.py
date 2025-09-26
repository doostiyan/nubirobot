from decimal import Decimal

import pytest
import responses
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import FeatureUnavailable
from exchange.asset_backed_credit.exceptions import InternalAPIError
from exchange.asset_backed_credit.externals.wallet import WalletListAPI, WalletProvider, WalletTransferAPI
from exchange.asset_backed_credit.models import InternalUser, WalletTransferLog
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins


class WalletProviderTransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.internal_user = InternalUser.objects.create(uid=self.user.uid, user_type=self.user.user_type)
        self.internal_api_success_response = {'id': 2}
        self.internal_api_fail_response = {'body': 'can not proceed with request'}

        self.source_wallet = ExchangeWallet.WALLET_TYPE.spot
        self.destination_wallet = ExchangeWallet.WALLET_TYPE.credit
        self.transfers = {Currencies.btc: Decimal('12.1230'), Currencies.usdt: Decimal('30.50')}

        self.transfer_log = WalletTransferLog.create(
            user=self.user,
            internal_user=self.internal_user,
            src_wallet_type=self.source_wallet,
            dst_wallet_type=self.destination_wallet,
            transfer_items=self.transfers,
        )
        Settings.set('abc_use_wallet_transfer_internal_api', 'yes')

    @responses.activate
    def test_transfer_with_spot_to_credit(self):
        responses.post(
            url=WalletTransferAPI.url,
            json=self.internal_api_success_response,
            status=status.HTTP_200_OK,
        )

        result, _ = WalletProvider.transfer(self.transfer_log)

        actual = result.model_dump(mode='json')
        assert actual.pop('createdAt') != None
        expected = {
            'dstType': 'credit',
            'id': self.internal_api_success_response['id'],
            'rejectionReason': '',
            'srcType': 'spot',
            'status': 'new',
            'transfers': [{'amount': '12.1230', 'currency': 'btc'}, {'amount': '30.50', 'currency': 'usdt'}],
        }
        assert actual == expected

    @responses.activate
    def test_transfer_with_internal_api_not_responding_successfully(self):
        responses.post(
            url=WalletTransferAPI.url,
            json=self.internal_api_fail_response,
            status=status.HTTP_400_BAD_REQUEST,
        )

        schema, response = WalletProvider.transfer(self.transfer_log)
        assert response is not None
        assert schema is None

    def test_call_internal_api_raises_exception_when_internal_api_is_not_enabled(self):
        Settings.set('abc_use_wallet_transfer_internal_api', 'no')

        with pytest.raises(FeatureUnavailable):
            WalletProvider.transfer(self.transfer_log)


class WalletProviderGetUserWalletTests(ABCMixins, TestCase):
    def setUp(self):
        self.user1 = User.objects.get(id=201)
        self.user2 = User.objects.get(id=203)
        self.wallet_type = ExchangeWallet.WALLET_TYPE.spot
        self.wallet_type_name = 'spot'
        self.internal_api_user1_response = {
            str(self.user1.uid): [
                {
                    "activeBalance": "0.1000000000",
                    "balance": "0.1000000000",
                    "blockedBalance": "0E-10",
                    "currency": "btc",
                    "type": self.wallet_type_name,
                    "userId": str(self.user1.uid)
                },
                {
                    "activeBalance": "0.2000000000",
                    "balance": "0.2000000000",
                    "blockedBalance": "0E-10",
                    "currency": "eth",
                    "type": self.wallet_type_name,
                    "userId": str(self.user1.uid)
                }
            ]
        }
        self.internal_api_user2_response = {
            str(self.user2.uid): [
                {
                    "activeBalance": "0.1000000000",
                    "balance": "0.7",
                    "blockedBalance": "0E-10",
                    "currency": "eth",
                    "type": self.wallet_type_name,
                    "userId": str(self.user2.uid)
                }, ]
        }
        self.internal_api_multiple_users_response = {
            **self.internal_api_user1_response,
            **self.internal_api_user2_response

        }

    @responses.activate
    def test_get_user_spot_wallets_with_internal_api_being_enabled(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json=self.internal_api_user1_response,
            status=status.HTTP_200_OK,
        )

        user_wallets = WalletProvider.get_user_wallets(self.user1.uid, self.user1.id, self.wallet_type)

        assert len(user_wallets) == len(self.internal_api_user1_response[str(self.user1.uid)])
        assert user_wallets[0].user_id == self.user1.uid
        assert user_wallets[1].user_id == self.user1.uid
        assert user_wallets[0].currency == Currencies.btc
        assert user_wallets[1].currency == Currencies.eth
        assert user_wallets[0].type == self.wallet_type
        assert user_wallets[1].type == self.wallet_type
        assert str(user_wallets[0].balance) == self.internal_api_user1_response[str(self.user1.uid)][0]['balance']
        assert str(user_wallets[1].balance) == self.internal_api_user1_response[str(self.user1.uid)][1]['balance']

    @responses.activate
    def test_get_user_wallets_when_user_has_no_such_wallets(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json=self.internal_api_user1_response,
            status=status.HTTP_200_OK,
        )

        user_wallets = WalletProvider.get_user_wallets(self.user2.uid, self.user2.id, self.wallet_type)

        assert user_wallets == []

    @responses.activate
    def test_get_user_wallets_when_internal_api_is_enabled_but_raises_error(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )

        with pytest.raises(InternalAPIError):
            WalletProvider.get_user_wallets(self.user1.uid, self.user1.id, self.wallet_type)

    @responses.activate
    def test_get_users_wallets_with_internal_api_being_enabled(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json=self.internal_api_multiple_users_response,
            status=status.HTTP_200_OK,
        )

        users_wallets = WalletProvider.get_wallets([self.user1, self.user2], self.wallet_type)

        user1_wallets = users_wallets[self.user1.id]
        user2_wallets = users_wallets[self.user2.id]
        assert len(user1_wallets) == len(self.internal_api_multiple_users_response[str(self.user1.uid)])
        assert len(user2_wallets) == len(self.internal_api_multiple_users_response[str(self.user2.uid)])

        assert user2_wallets[0].user_id == self.user2.uid
        assert user2_wallets[0].currency == Currencies.eth
        assert user2_wallets[0].type == self.wallet_type
        assert str(user2_wallets[0].balance) == self.internal_api_multiple_users_response[str(self.user2.uid)][0][
            'balance']

    @responses.activate
    def test_get_users_wallets_with_internal_api_is_enabled_but_raises_error(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={},
            status=status.HTTP_400_BAD_REQUEST,
        )

        with pytest.raises(InternalAPIError):
            WalletProvider.get_wallets([self.user1, self.user2], self.wallet_type)

    @responses.activate
    def test_get_users_wallet_with_users_not_having_such_wallets(self):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json=self.internal_api_multiple_users_response,
            status=status.HTTP_200_OK,
        )

        user_ids = [self.create_user(), self.create_user()]
        users_wallets = WalletProvider.get_wallets(user_ids, self.wallet_type)
        assert users_wallets[user_ids[0].id] == []
        assert users_wallets[user_ids[1].id] == []

import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytz

from exchange.blockchain.api.ftm.ftm_graphql import FantomGraphQlAPI
from exchange.blockchain.staking.staking_interface import StakingInterface
from exchange.blockchain.staking.staking_models import CoinType, StakingInfo


class TestFtmStakingInterface(TestCase):

    def test_ftm_get_staking_data(self):
        address = '0xb6b008de290bb5a9730abe8a1d0d001078455fba'
        api = FantomGraphQlAPI.get_api()
        api.request = Mock()
        get_staking_info_response = {
            'data': {
                'account': {
                    'address': '0xb6b008de290bb5a9730abe8a1d0d001078455fba', 'balance': '0x21879456fe6c9e92222',
                    'totalValue': '0x1c5afbc15ff7b892f260f', 'txCount': '0x9ae',
                    'delegations': {'totalCount': '0x8', 'edges': [{
                        'delegation': {'createdTime': '0x62597980',
                                       'amountDelegated': '0x7491cbd49c5a9e2443fc',
                                       'lockedUntil': '0x64d3fbba',
                                       'claimedReward': '0x319ef87d010c2b76600',
                                       'pendingRewards': {
                                           'amount': '0x26db89b95c93498a17',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '6263ad4b5ada9e4660742770',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x614b3840',
                                       'amountDelegated': '0x7130e0c596013bc55b96',
                                       'lockedUntil': '0x64e39cf6',
                                       'claimedReward': '0x10ffdd6ed44e1ab60000',
                                       'pendingRewards': {
                                           'amount': '0x28a48b61e5e2c47838',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '6261a72f5ada9e46605745bb',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x5f65fc10',
                                       'amountDelegated': '0x6eb78d786b64d0b3f0aa',
                                       'lockedUntil': '0x647ffed9',
                                       'claimedReward': '0x1757569e7fe4d7a24a00',
                                       'pendingRewards': {
                                           'amount': '0x273f0fb8e66b8e3351',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '626029ac5ada9e466077f6da',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x5f6f9606',
                                       'amountDelegated': '0x6e80aa7f3822a57fbef2',
                                       'lockedUntil': '0x646c44b3',
                                       'claimedReward': '0x1bcbbf2976eaaa420a00',
                                       'pendingRewards': {
                                           'amount': '0x259cf7abcd0984507a',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '62602ba75ada9e4660788dd1',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x5fe738d6',
                                       'amountDelegated': '0x0',
                                       'lockedUntil': '0x0',
                                       'claimedReward': '0x9b90b49ce2b07c00e00',
                                       'pendingRewards': {
                                           'amount': '0x0',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '62603b6d5ada9e46607d2ed5',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x62597bd7',
                                       'amountDelegated': '0x0',
                                       'lockedUntil': '0x0',
                                       'claimedReward': '0x146a24139c8acd18600',
                                       'pendingRewards': {
                                           'amount': '0x0',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '6263ad4f5ada9e46607429b4',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x5fe660b5',
                                       'amountDelegated': '0x0',
                                       'lockedUntil': '0x0',
                                       'claimedReward': '0x4bfe049cb69fe55f600',
                                       'pendingRewards': {
                                           'amount': '0x22239bb84082ea5',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '62603b515ada9e46607d26a4',
                        '__typename': 'DelegationListEdge'}, {
                        'delegation': {'createdTime': '0x5e64583a',
                                       'amountDelegated': '0x0',
                                       'lockedUntil': '0x0',
                                       'claimedReward': '0x7b3f482bf5b0af823000',
                                       'pendingRewards': {
                                           'amount': '0x0',
                                           '__typename': 'PendingRewards'},
                                       '__typename': 'Delegation'},
                        'cursor': '62601de25ada9e4660745705',
                        '__typename': 'DelegationListEdge'}],
                                    '__typename': 'DelegationList'}, '__typename': 'Account'}}}
        api.request.return_value = get_staking_info_response

        staking_info = StakingInterface.get_info('FTM', address)
        assert staking_info == StakingInfo(
            address='0xb6b008de290bb5a9730abe8a1d0d001078455fba',
            total_balance=Decimal('2139589.266827449605714256'),
            staked_balance=Decimal('2129693.073490252283072302'),
            rewards_balance=Decimal('2884.483144958536627391'),
            free_balance=None,
            delegated_balance=None,
            pending_rewards=None,
            end_staking_plan=datetime.datetime(2023, 8, 9, 20, 48, 58,
                                               tzinfo=pytz.utc),
            coin_type=CoinType.NON_PERIODIC_REWARD)

from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.sol.sol_solanabeach import SolanaBeachAPI


class TestSolanaBeachMock(TestCase):
    api = SolanaBeachAPI()

    def test_get_stake_account_info(self):
        address = '7VMTVroogF6GhVunnUWF9hX8JiXqPHiZoG3VKAe64Ckt'
        self.api.request = Mock()
        self.api.request.return_value = {'totalPages': 1, 'data': [{'pubkey': {'address': '2Ls7ywRZTSeViL17DKZCoBZVb1u9oB7jyjowqqCNaxvq'}, 'lamports': 1106709729630252, 'data': {'state': 2, 'meta': {'rent_exempt_reserve': 2282880, 'authorized': {'staker': {'address': '7VMTVroogF6GhVunnUWF9hX8JiXqPHiZoG3VKAe64Ckt'}, 'withdrawer': {'address': '7VMTVroogF6GhVunnUWF9hX8JiXqPHiZoG3VKAe64Ckt'}}, 'lockup': {'unix_timestamp': 1743724800, 'epoch': 0, 'custodian': {'address': 'Mc5XB47H3DKJHym5RLa9mPzWv5snERsF3KNv5AauXK8'}}}, 'stake': {'delegation': {'voter_pubkey': {'address': 'DQ7D6ZRtKbBSxCcAunEkoTzQhCBKLPdzTjPRRnM6wo1f'}, 'stake': 1106709727347372, 'activation_epoch': 275, 'deactivation_epoch': 18446744073709552000, 'warmup_cooldown_rate': 0.25, 'validatorInfo': {'name': 'StakeWolf', 'website': 'http://www.stakewolf.com/', 'identityPubkey': 'HzrEstnLfzsijhaD6z5frkSE2vWZEH5EUfn3bU9swo1f', 'keybaseUsername': 'stakewolf', 'details': 'Stake is Money, Stakewolf is Stake', 'image': 'https://s3.amazonaws.com/keybase_processed_uploads/895b994ddf7bdb1fd8016f36d0fc0005_360_360.jpg'}}, 'credits_observed': 140252753}}}]}
        response = self.api.get_stake_account_info(address)

        assert response == '2Ls7ywRZTSeViL17DKZCoBZVb1u9oB7jyjowqqCNaxvq'

    def test_get_delegated_balance(self):
        address = '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'
        self.api.request = Mock()
        self.api.request.return_value = [{'transactionHash': '3jwwpBvdnpqRF2pM8T5RHms6wB5Z5uBFyweANLXP4KhCmqH1dhBrWB6yjxrrK5MoUPgRL1bBTfQqLadHaVwB83pc', 'blockNumber': 161401417, 'accounts': [{'account': {'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}, 'writable': True, 'signer': True}, {'account': {'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}, 'writable': True, 'signer': True}, {'account': {'name': 'System Program', 'address': '11111111111111111111111111111111'}, 'program': True}, {'account': {'address': 'Pond1QyT1sQtiru3fi9G5LGaLRGeUpJKR1a2gdbq2u4'}}, {'account': {'name': 'Stake Program', 'address': 'Stake11111111111111111111111111111111111111'}, 'program': True}, {'account': {'address': 'StakeConfig11111111111111111111111111111111'}}, {'account': {'name': 'Sysvar: Clock', 'address': 'SysvarC1ock11111111111111111111111111111111'}}, {'account': {'name': 'Sysvar: Rent', 'address': 'SysvarRent111111111111111111111111111111111'}}, {'account': {'name': 'Sysvar: Stake History', 'address': 'SysvarStakeHistory1111111111111111111111111'}}], 'header': {'numReadonlySignedAccounts': 0, 'numReadonlyUnsignedAccounts': 7, 'numRequiredSignatures': 2}, 'instructions': [{'parsed': {'CreateAccount': {'lamports': 28959000000000, 'space': 200, 'owner': {'name': 'Stake Program', 'address': 'Stake11111111111111111111111111111111111111'}, 'fundingAccount': {'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}, 'newAccount': {'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}, 'signers': [{'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}, {'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}], 'writable': [{'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}, {'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}]}}, 'programId': {'name': 'System Program', 'address': '11111111111111111111111111111111'}}, {'parsed': {'Initialize': {'authorized': {'staker': {'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}, 'withdrawer': {'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}}, 'lockup': {'unixTimestamp': 0, 'epoch': 0, 'custodian': {'name': 'System Program', 'address': '11111111111111111111111111111111'}}, 'stakePubkey': {'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}, 'rentSysVar': {'name': 'Sysvar: Rent', 'address': 'SysvarRent111111111111111111111111111111111'}, 'signers': [], 'writable': [{'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}]}}, 'programId': {'name': 'Stake Program', 'address': 'Stake11111111111111111111111111111111111111'}}, {'parsed': {'Delegate': {'stakePubkey': {'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}, 'votePubkey': {'address': 'Pond1QyT1sQtiru3fi9G5LGaLRGeUpJKR1a2gdbq2u4'}, 'clockSysVar': {'name': 'Sysvar: Clock', 'address': 'SysvarC1ock11111111111111111111111111111111'}, 'stakeHistorySysVar': {'name': 'Sysvar: Stake History', 'address': 'SysvarStakeHistory1111111111111111111111111'}, 'stakeConfigId': {'address': 'StakeConfig11111111111111111111111111111111'}, 'authorizedPubkey': {'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}, 'signers': [{'address': '2ay2fnFfy4tGaxYbPQakKDer5ihmPmWsHv9gNP6nuvCG'}], 'writable': [{'address': '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'}]}}, 'programId': {'name': 'Stake Program', 'address': 'Stake11111111111111111111111111111111111111'}}], 'recentBlockhash': 'Eg8Cw1ZkvBq9mWF499fNTztw3bQH7pF7iFr4v15YkPkX', 'signatures': ['3jwwpBvdnpqRF2pM8T5RHms6wB5Z5uBFyweANLXP4KhCmqH1dhBrWB6yjxrrK5MoUPgRL1bBTfQqLadHaVwB83pc', 'qJTinv1CSCzxkc47CaHEwwZeKJPDQmvoXUHgXzAk8isbyxcJXHf9f6cq3KkF1CGz9atrxa63GtDB48ZDbsNEY3S'], 'meta': {'err': None, 'fee': 10000, 'loadedAddresses': {'readonly': [], 'writable': []}, 'logMessages': ['Program 11111111111111111111111111111111 invoke [1]', 'Program 11111111111111111111111111111111 success', 'Program Stake11111111111111111111111111111111111111 invoke [1]', 'Program Stake11111111111111111111111111111111111111 success', 'Program Stake11111111111111111111111111111111111111 invoke [1]', 'Program Stake11111111111111111111111111111111111111 success'], 'postBalances': [1919960000, 28959000000000, 1, 26858640, 1, 960480, 1169280, 1009200, 114979200], 'postTokenBalances': [], 'preBalances': [28960919970000, 0, 1, 26858640, 1, 960480, 1169280, 1009200, 114979200], 'preTokenBalances': [], 'rewards': [], 'status': {'Ok': None}}, 'valid': True, 'blocktime': {'absolute': 1668621745, 'relative': 1668683058}, 'mostImportantInstruction': {'name': 'Delegate', 'weight': 1, 'index': 2}}]
        response = self.api.get_delegated_balance(address)

        assert response == 28959.000000000


@pytest.mark.slow
class TestSolanaBeachLive(TestCase):
    api = SolanaBeachAPI()

    def test_get_stake_account_info_live(self):
        address = '7VMTVroogF6GhVunnUWF9hX8JiXqPHiZoG3VKAe64Ckt'
        response = self.api.request('get_stake_account', address=address)
        assert list(response) == ['totalPages', 'data']
        assert list(response.get('data')[0]) == ['pubkey', 'lamports', 'data']
        assert list(response.get('data')[0].get('pubkey')) == ['address']
        assert type(response.get('data')[0].get('lamports')) == int

    def test_get_delegated_balance_live(self):
        address = '7k2qG2jra4VuWftA2e7BmUdrwf7jhCE8icWW2nBa4hze'
        response = self.api.request('get_txs', address=address, limit=25)
        assert list(response[0]) == ['transactionHash', 'blockNumber', 'accounts', 'header', 'instructions', 'recentBlockhash', 'signatures', 'meta', 'valid', 'blocktime', 'mostImportantInstruction']
        assert list(response[0].get('meta')) == ['err', 'fee', 'loadedAddresses', 'logMessages', 'postBalances', 'postTokenBalances', 'preBalances', 'preTokenBalances', 'rewards', 'status']
        assert list(response[0].get('mostImportantInstruction')) == ['name', 'weight', 'index']
        assert len(response[0].get('meta').get('postBalances')) == len(response[0].get('meta').get('preBalances'))
        assert len(response[0].get('meta').get('postBalances')) == len(response[0].get('accounts'))

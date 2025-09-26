import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from pytz import UTC

from exchange.base.parsers import parse_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.api.filecoin.filecoin_explorer_interface import FilecoinExplorerInterface

from exchange.blockchain.api.filecoin.filecoin_filfox import FilecoinFilfoxApi


@pytest.mark.slow
class TestFilfoxFilecoinApiCalls(TestCase):
    api = FilecoinFilfoxApi
    addresses_of_account = ['f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y',
                            'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                            ]
    hash_of_transactions = ['bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms',
                            'bafy2bzacecfxhra72l2nievebqxwbmrroldhu7fldep2yfe7x2qgcdwtegux4']
    # height 3085955
    block_hashes = ['bafy2bzacedtwqndikvo3klgzs6gq3evsql5qt7d7g6dbiamecq2btcybls63w',
                    'bafy2bzacebrtkr5pwasrd2cjqifaympzncplw47l2h5etkq2taksisfeivv5w',
                    'bafy2bzacebuqhd7ptk7svjbc32fpy3e3xy2nclla7kygwqagcvo43jx2sknau']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):

        keys = {'id', 'robust', 'actor', 'createHeight', 'createTimestamp', 'lastSeenHeight', 'lastSeenTimestamp',
                'balance', 'messageCount', 'transferCount', 'tokenTransferCount', 'timestamp', 'tokens', 'ethAddress', 'ownedMiners', 'workerMiners',
                'benefitedMiners', 'address'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result, keys)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('balance'), str)

    def test_get_address_txs_api(self):

        address_keys = {'totalCount', 'messages', 'methods'}
        transaction_keys = {'cid', 'height', 'timestamp', 'from', 'to', 'nonce', 'value', 'method', 'receipt'}
        for address in self.addresses_of_account:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response, address_keys)
            assert len(get_address_txs_response) > 0
            for transaction in get_address_txs_response.get('messages'):
                assert transaction_keys.issubset(set(transaction.keys()))

    def test_get_block_head_api(self):

        blockhead_keys = {'height', 'timestamp', 'baseFee'}
        get_block_head_response = self.api.get_block_head()[0]
        assert self.check_general_response(get_block_head_response, blockhead_keys)
        assert type(get_block_head_response.get('height')) == int
        assert type(get_block_head_response.get('timestamp')) == int
        assert type(get_block_head_response.get('baseFee')) == str

    def test_get_tx_details_api(self):

        transaction_keys = {
            'cid', 'height', 'timestamp', 'confirmations', 'blocks', 'version', 'from', 'fromId', 'fromActor', 'to',
            'toId', 'toActor', 'nonce', 'value', 'gasLimit', 'gasFeeCap', 'gasPremium', 'method', 'methodNumber',
            'params', 'receipt', 'decodedParams', 'decodedReturnValue', 'size', 'error', 'baseFee', 'fee', 'subcalls',
            'transfers', 'eventLogs', 'tokenTransfers'}
        for tx_hash in self.hash_of_transactions:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response, transaction_keys)

    def test_get_block_txs_api(self):
        block_txs_response_keys = {'totalCount', 'messages', 'methods'}
        block_transaction_keys = {'cid', 'from', 'to', 'value', 'method', 'receipt'}
        for block_hash in self.block_hashes:
            get_block_txs_response = self.api.get_block_txs(block_hash)
            assert len(get_block_txs_response) != 0
            assert self.check_general_response(get_block_txs_response[0], block_txs_response_keys)
            if len(get_block_txs_response[0].get('messages')) != 0:
                for tx in get_block_txs_response[0].get('messages'):
                    assert self.check_general_response(tx, block_transaction_keys)


class TestFilfoxFilecoinFromExplorer(TestCase):
    api = FilecoinFilfoxApi
    currency = Currencies.fil
    addresses_of_account = ['f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy']

    hash_of_transactions = ['bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2',
                            'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye',
                            'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms'
                            ]
    address_txs = ['f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna']

    def test_get_balance(self):
        balance_mock_response = [{'id': 'f01067288', 'robust': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                                  'actor': 'account', 'createHeight': 873274, 'createTimestamp': 1624504620,
                                  'lastSeenHeight': 3086242, 'lastSeenTimestamp': 1690893660,
                                  'balance': '299980922586592246', 'messageCount': 5775, 'timestamp': 1690909800,
                                  'ownedMiners': [], 'workerMiners': [], 'benefitedMiners': [],
                                  'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy'}]
        self.api.get_balance = Mock(side_effect=balance_mock_response)
        FilecoinExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'FIL': self.addresses_of_account}, Currencies.fil)
        expected_balances = {Currencies.fil: [{'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                                               'balance': Decimal('0.299980922586592246'),
                                               'received': Decimal('0.299980922586592246'),
                                               'sent': Decimal('0'),
                                               'rewarded': Decimal('0')}]}

        assert self.currency in balances.keys()
        expected_values = expected_balances.values()
        expected_merged_list = []
        for sublist in expected_values:
            expected_merged_list.extend(sublist)
        for balance, expected_balance in zip(balances.get(Currencies.fil), expected_merged_list):
            assert balance == expected_balance

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            [{'baseFee': '5249503', 'height': 3087223, 'timestamp': 1690923090}],
            {'cid': 'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2', 'height': 2349511,
             'timestamp': 1668791730, 'confirmations': 829294,
             'blocks': ['bafy2bzacedgp6a7dv76dfx5yi2vqaefyg5qaqqf46u3arxyai7byigyhw4z5q',
                        'bafy2bzaceciscaefmreqhsqhti2moe45u63msegv5rnh5zxurcaoqto2jaxjk',
                        'bafy2bzaceap7i4rzkmsxlfuu7rpsdtx25dv6jwvo4ormzdbte76sesukvfens'], 'version': 0,
             'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'fromId': 'f01477629', 'fromActor': 'account',
             'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji', 'toId': 'f01571048', 'toActor': 'account', 'nonce': 112,
             'value': '1600000000000000000', 'gasLimit': 532474, 'gasFeeCap': '529990634', 'gasPremium': '164002',
             'method': 'Send', 'methodNumber': 0, 'params': '0x',
             'receipt': {'exitCode': 0, 'return': '0x', 'gasUsed': 490568}, 'decodedParams': '',
             'decodedReturnValue': '', 'size': 76, 'error': '', 'baseFee': '260409471',
             'fee': {'baseFeeBurn': '127748553369528', 'overEstimationBurn': '0', 'minerPenalty': '0',
                     'minerTip': '87326800948', 'refund': '154370352678040'}, 'subcalls': [], 'transfers': [
                {'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'fromId': 'f01477629', 'to': 'f01130671',
                 'toId': 'f01130671', 'value': '87326800948', 'type': 'miner-fee'},
                {'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'fromId': 'f01477629', 'to': 'f099',
                 'toId': 'f099', 'value': '127748553369528', 'type': 'burn-fee'},
                {'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y', 'fromId': 'f01477629',
                 'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji', 'toId': 'f01571048', 'value': '1600000000000000000',
                 'type': 'transfer'}], 'eventLogs': [], 'tokenTransfers': []},
            [{'baseFee': '5249503', 'height': 3087223, 'timestamp': 1690923090}],
            {'cid': 'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye', 'height': 2349569,
             'timestamp': 1668793470, 'confirmations': 829267,
             'blocks': ['bafy2bzacea6677pkhqexwfufl3q36jocjyepl5h2fm66fihzgogt2tmrr3i6u'], 'version': 0,
             'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
             'fromId': 'f01263696', 'fromActor': 'account', 'to': 'f01156883', 'toId': 'f01156883',
             'toActor': 'storageminer', 'nonce': 20422, 'value': '1944530995624041453', 'gasLimit': 199615728,
             'gasFeeCap': '375721897', 'gasPremium': '163343', 'method': 'ProveReplicaUpdates', 'methodNumber': 27,
             'params': '0x818187190e350200d82a5829000182e20381e802206cf2ac23fd640b8163311d72a3aeae33d9dbbe3df31054ab3b5ad4d5358a543a811a00f86c2803590c00a44623af884d0a852bd5cc52ee3fcd2dd2f61eea020f8d6d23194758d00e69ff8dc89e81fcef75f73cd0a609e68b2e8983eda78e8a5eb843b7466c91924dcdd931dfa4421f8b60ed1b845409055bddac3df6e7dacb0c0d72e3c7450ba8b2be0a0ce86dd6f1f14f5ea9fddfaf28d44efc98cb265bfc9bd8a202d84dc9381487f333545e0e05d742478a456efdacfebc579077aa5cc790019d168abefc7163343954cd7bec44d43a61c90b00e68f31e2906d4c5a30c91ac44fcdab012ce95fbff6a30df5da159dee8236b1928dcd4d33def75f23b07ad9b0d10483f770c14370bef4b6169e41255c6c02943172dc63e1f9b8edbaab427e3740492c6470ae704620ed2b3878c3bb7d3311461402b9e06d6fb519f21db1a633dc5ad5bbf9a1efe8ec15b0e1b99514193bbf7d2289c26c2df1ee02d750538f7e7f5bb32cfa7a870c720070efd67acc1e1edb361094ccbc87a88fc1ab844abe0a1f41ad51e3e5ca1b20be4a293f0aa9dfc7a13224442a0a4b71a5d61241090c00d343bd5082982b71f78861baac6785b202f4a77461d373804165cde64a4281b272c489df051d3449c93c541bbbf02468fa19e898d7adf056ad9963a618438fe6dbf55cbaf56ce8fdb6245becf09d488b22fc0812764622790765591c1f8684dfbe18c2b6e1d4af65380035bcb010deda452fd5dc88edb92ea384d46ea4f126623190e5b0568d52a2095f6d33f81beba1c41fe252c823752511894bd3072427f2015fc0a533149a3ea203a3f66bfd09347d1e3fcb92bdd4c800a0955d9cec9785daeeefc08248938f0282246728ac5180b5469cbd3d4e87d4e40e75f01fd16f91129e01862a784236443217eb23b856a271057dd8e00dda2e36b19157490919d9c311d06abdc40c99a9a7a3a04d8bc58c2f2fa41456aa8093cba2528c3f39730d6e84da0e66105ff2cf0753d8b57b1a295498c64a4dc2c52eea238b3a996de458392c874bb524724ce8351713e4cbbed2b384341eed7fd2b39988214d943b2ce05cd20bfd45f3bd7206b5c4ce7ed85434637ef5baf947c881d0316d3bbae5ef5887619ed51d03cba960aab3f0524657948154e33a01867f7b7c6733be12f0c85a16c194d91e30f0ba54601066d85babfaf4c612d885e0cb24ef8df22b095b95909a3cb3237a315b64b0025acccf9077c3e978bb9d94a61bf6084035c0cc840f630708db3942cd760a740978b44de3398ae07881dd592b60dcb9fc704e5cf5ec2da3b5a217b79168771beb6c870f8ace44867387b72d57f0206596944dc5ce71581ddacc305cf6d9e7884e6b30dc764bb226e4eee1d285eb44966549f868b3904b229b255ea409287e1383a74ec8710d48872f85aec4fa6a2f5b23a90e7f218d123bbb08b739a43f482f3a9f0209383e1a65d50cf05bb9a1cd5bb936729c61621ceaa585c02c89dd6efb9910e56206d4baa7c7115474dbe68129f0aa02c16ad87f8f93977f7d95281b871496178dc5dddf4d9b8cb86bb17f6c2a5698a407173a93549b63b7966bd74c49a4315b3ce4b0d27e4a20da7dbbc098309666913d7d41218913818c23591e89ef7213a661088b2cc254654af72c463acc1df24eaab391f3548f70bd214e3cc7cea24eba6ad87892bcf9270c7659e34dc79277df4362cb24dc61eb9ea402d16e2b9085c2d5994e862144efdfe9e0102f4db6cb4c86a91d19f0ba7dda477f48a32386a09c9d981a99f76a4a1ef322d1965bd7a05a5cfcf9d64c9a5cebefbff47a5d151f57fa226faed5d43b8e8400f2c43385d9358cd3a128dd227134696327476a19101afca5c3b768ddec2e85bbcb1f12a9bb650cf8e53b5f379fe6f23bfadf6443b835a2b7aa3799d7d2a6ca40b383b47237fa17cbbc2c0945d1b19606574e69aa60be4bd51bad7bd74b22381fdd899e8e5a19c12769af5a7df0858cbc89ebd1395ef02318abb738546f00a5a119fa37b900c546a1d8249b4a3cdddb82032f5ea31507ed23e2353a3f8b703a1e550233611479546c150776e3cbfb629093578608d8ea24fcfc7e7761686c0b9f98b6596c5ee0d7b89651f102b88809faa74b3d0a7bd4a8b35bc80de230c851f8376ce68819d53e6fba8837a7eb48f27bcb22621e74850ccbc87e51bbe0e762f2f111abc77090490bfa5565f7bdc21a08db17a4ab5a5458ee94b11d49b06ec90474615117194e3453fc549c97a20a668f20619a5101fd7c1c3d1c9bfcdfb666d94c09eb929caee8fef68d96ad3addf51bffb68d9fa21aad2b2ddaa26c4e8405500299aa84e3533c7c29f57d577415700fb3ba6d0587e492f343ec3913ddc81f1633b119730ea3805ebb28b85eab0b6636d23fd03948792271b06270d5904a548349f37387e7eccdbbfe0148d14282fb7bcbbb91e375db1e87bc8227419e84504c26696d0a7b893dd67b18d1dd2d5a054acf5c61b9b904ca2da5f72bcd537e16c45cad84da2adb5ba2f47aa48f97daf183897374dfcf08b8909d91e8e998ecd5a6b9d927b5c6fb36d388c90d0e3c886c930734c783552d50070db0592e7f0464b48d4faacc94c6d8ae2c5a8de3a5fbc464d185981814af8c8284e48583071af4d9aa48d6cdf0761411fa160b4373dfd9e827dd577b9c3e14d86d833e331565245194b9be964c4bcd7f82f2e8762bb61e82e05a6252201f3a3d8fc3cb2e7ec025d1cc575a21f8d1e8891ddea738e1ba725862c3fba8de5698fd28b6db5ccbce262903b711bde92e867b6834c7855c132355e7c91d90adfc8bebbc5e1ba7faaca6228ef730a2222417bb714d7652a34430e9e93de4484af7bdd88697b2a6e31f0780157b15060d71ed3251c84edfd7a1d4b2ad01bf034cd0ca1bd01c9f5bc571a0aaf8c51237b3f23bc838fd7a3d6f9bd535ddfb94be94e34916a3f16c861298a2abf1a21ba1d7b940192b0f3750d50460444ac2ee438e7141a5ba6a5bca9b750d0bb801f6450ac5a4ece46d2ae2e4e26962bf3fc787a9a3e75e544c668b156f5ead0dfb441260e7617584b534fde3ecf703ca15dd9261fade27436e4599077eb789797fa5af86c1b619eb93facadda1f6db394859eef502cb218608a0fb25cc4bc5bb04518be6a80e4c08fde87b423b8766d2a6ae02b9942bea9daf83ea9fb5aea2a058680ea9dbeba7d48ea4044a5b75c88363c6ff322f9832d2d801cd0fb8b6764c0405ac97751ac0eafc82c6fe1de9c6b84e39d9bff442620dc1c5274196a81817ef02331a4743a8408cdaa986470e90c394c298648da38fefc7dcffb669bd66e2eff0de622e131eb9721bc576bb1c9714b8b98a42d0a965a6d435307e9380e70630b196952f9dbcf4751af4d10069e144573f89fdcc33e2d628038c041ba2b2ee8f4f7e569f6d92f7c189b08e54196255a42010d27dc722a18b4739cb2e7094031693adbd7437366624c3c41a07302baf078a6edd9f32ab4264305c0e4d07cb3e3da1aec9a23c67f7b75a82caa911dd7adbe3271f86db69b329d137b55aeb979d625981e1c9e2745a06c96ea8aaca23fffd05856dd27ea946fccb4ca67a9debc0cef3fa56f0cc9ee2fe99656ea7f6c109919d014cb3d917d9204e2a7edb03178d11b88689d230c6aee8b95b344e31dfbf485461915cec6a46ed41d33e48819fef85c7ebde36d9d045ed4cd669a12f663fb8ce1849edc6d6f0eef9247d88b4140ccc7e30d6f90b8a1df9c13f68e526958f400184939b2ca0bd4130422fda906b947eb28a789d96d40ec461e0ecf890b6290a5cebf76c0fbe336f4a68ab9161157ed2715891339597f8a632361463bb5adc2dfab299c69caac847a1406e242371928e1a7d59c726ed60e77471ce31bbfd3abe9f65bbfabbd255930e6b63bb4ea0dcf12da6f793a7c11841d9a3239a9523a58c6b874dc868b3a1daab9e8cdd96f4949dc9f22a5f9dca41fb8a659fcfb80ce8b9fb124edda8889695a61d2b18efe67e42da25359c02f89ab16fd8cb13b8423dda4d87e1470639d869874092298abc3c411cad11520df19a5e575f6d5343b739ffc075fcf6f799b0c5c02b4cab4b4418fe2a625dda0803f769d54af5692407e45e5d966b9f8861484f84e045c49d9494b1561a10c19fb31b8bcfa5653a6bd9b6afe290ba4134eff84e24569254ab4bf2bbab9823f58aece62f00548bb457cf5c0e4821c35c66a85d3a75753105741927adaa24fa26ad518aa268f542d9c593dbf9a60084e4bc961d9fed96ec4503e25f3250bec2560dd56f0f92992e38e67ebf7daf37cc5693dd522dfbcc6a00d943056bdea371fdd1ac552572ecb7c27c0eea00a4de25b237830da1a71bace3f012d78e4d7873dedb6d33de6555302816c46e94ea',
             'receipt': {'exitCode': 0, 'return': '0x43a09623', 'gasUsed': 159983071}, 'decodedParams': {'Updates': [
                {'SectorNumber': 3637, 'Deadline': 2, 'Partition': 0,
                 'NewSealedSectorCID': 'bagboea4b5abca3hsvqr72zalqfrtchlsuoxk4m6z3o7d34yqksvtwwwu2u2yuvb2',
                 'Deals': [16280616], 'UpdateProofType': 3,
                 'ReplicaProof': '0xa44623af884d0a852bd5cc52ee3fcd2dd2f61eea020f8d6d23194758d00e69ff8dc89e81fcef75f73cd0a609e68b2e8983eda78e8a5eb843b7466c91924dcdd931dfa4421f8b60ed1b845409055bddac3df6e7dacb0c0d72e3c7450ba8b2be0a0ce86dd6f1f14f5ea9fddfaf28d44efc98cb265bfc9bd8a202d84dc9381487f333545e0e05d742478a456efdacfebc579077aa5cc790019d168abefc7163343954cd7bec44d43a61c90b00e68f31e2906d4c5a30c91ac44fcdab012ce95fbff6a30df5da159dee8236b1928dcd4d33def75f23b07ad9b0d10483f770c14370bef4b6169e41255c6c02943172dc63e1f9b8edbaab427e3740492c6470ae704620ed2b3878c3bb7d3311461402b9e06d6fb519f21db1a633dc5ad5bbf9a1efe8ec15b0e1b99514193bbf7d2289c26c2df1ee02d750538f7e7f5bb32cfa7a870c720070efd67acc1e1edb361094ccbc87a88fc1ab844abe0a1f41ad51e3e5ca1b20be4a293f0aa9dfc7a13224442a0a4b71a5d61241090c00d343bd5082982b71f78861baac6785b202f4a77461d373804165cde64a4281b272c489df051d3449c93c541bbbf02468fa19e898d7adf056ad9963a618438fe6dbf55cbaf56ce8fdb6245becf09d488b22fc0812764622790765591c1f8684dfbe18c2b6e1d4af65380035bcb010deda452fd5dc88edb92ea384d46ea4f126623190e5b0568d52a2095f6d33f81beba1c41fe252c823752511894bd3072427f2015fc0a533149a3ea203a3f66bfd09347d1e3fcb92bdd4c800a0955d9cec9785daeeefc08248938f0282246728ac5180b5469cbd3d4e87d4e40e75f01fd16f91129e01862a784236443217eb23b856a271057dd8e00dda2e36b19157490919d9c311d06abdc40c99a9a7a3a04d8bc58c2f2fa41456aa8093cba2528c3f39730d6e84da0e66105ff2cf0753d8b57b1a295498c64a4dc2c52eea238b3a996de458392c874bb524724ce8351713e4cbbed2b384341eed7fd2b39988214d943b2ce05cd20bfd45f3bd7206b5c4ce7ed85434637ef5baf947c881d0316d3bbae5ef5887619ed51d03cba960aab3f0524657948154e33a01867f7b7c6733be12f0c85a16c194d91e30f0ba54601066d85babfaf4c612d885e0cb24ef8df22b095b95909a3cb3237a315b64b0025acccf9077c3e978bb9d94a61bf6084035c0cc840f630708db3942cd760a740978b44de3398ae07881dd592b60dcb9fc704e5cf5ec2da3b5a217b79168771beb6c870f8ace44867387b72d57f0206596944dc5ce71581ddacc305cf6d9e7884e6b30dc764bb226e4eee1d285eb44966549f868b3904b229b255ea409287e1383a74ec8710d48872f85aec4fa6a2f5b23a90e7f218d123bbb08b739a43f482f3a9f0209383e1a65d50cf05bb9a1cd5bb936729c61621ceaa585c02c89dd6efb9910e56206d4baa7c7115474dbe68129f0aa02c16ad87f8f93977f7d95281b871496178dc5dddf4d9b8cb86bb17f6c2a5698a407173a93549b63b7966bd74c49a4315b3ce4b0d27e4a20da7dbbc098309666913d7d41218913818c23591e89ef7213a661088b2cc254654af72c463acc1df24eaab391f3548f70bd214e3cc7cea24eba6ad87892bcf9270c7659e34dc79277df4362cb24dc61eb9ea402d16e2b9085c2d5994e862144efdfe9e0102f4db6cb4c86a91d19f0ba7dda477f48a32386a09c9d981a99f76a4a1ef322d1965bd7a05a5cfcf9d64c9a5cebefbff47a5d151f57fa226faed5d43b8e8400f2c43385d9358cd3a128dd227134696327476a19101afca5c3b768ddec2e85bbcb1f12a9bb650cf8e53b5f379fe6f23bfadf6443b835a2b7aa3799d7d2a6ca40b383b47237fa17cbbc2c0945d1b19606574e69aa60be4bd51bad7bd74b22381fdd899e8e5a19c12769af5a7df0858cbc89ebd1395ef02318abb738546f00a5a119fa37b900c546a1d8249b4a3cdddb82032f5ea31507ed23e2353a3f8b703a1e550233611479546c150776e3cbfb629093578608d8ea24fcfc7e7761686c0b9f98b6596c5ee0d7b89651f102b88809faa74b3d0a7bd4a8b35bc80de230c851f8376ce68819d53e6fba8837a7eb48f27bcb22621e74850ccbc87e51bbe0e762f2f111abc77090490bfa5565f7bdc21a08db17a4ab5a5458ee94b11d49b06ec90474615117194e3453fc549c97a20a668f20619a5101fd7c1c3d1c9bfcdfb666d94c09eb929caee8fef68d96ad3addf51bffb68d9fa21aad2b2ddaa26c4e8405500299aa84e3533c7c29f57d577415700fb3ba6d0587e492f343ec3913ddc81f1633b119730ea3805ebb28b85eab0b6636d23fd03948792271b06270d5904a548349f37387e7eccdbbfe0148d14282fb7bcbbb91e375db1e87bc8227419e84504c26696d0a7b893dd67b18d1dd2d5a054acf5c61b9b904ca2da5f72bcd537e16c45cad84da2adb5ba2f47aa48f97daf183897374dfcf08b8909d91e8e998ecd5a6b9d927b5c6fb36d388c90d0e3c886c930734c783552d50070db0592e7f0464b48d4faacc94c6d8ae2c5a8de3a5fbc464d185981814af8c8284e48583071af4d9aa48d6cdf0761411fa160b4373dfd9e827dd577b9c3e14d86d833e331565245194b9be964c4bcd7f82f2e8762bb61e82e05a6252201f3a3d8fc3cb2e7ec025d1cc575a21f8d1e8891ddea738e1ba725862c3fba8de5698fd28b6db5ccbce262903b711bde92e867b6834c7855c132355e7c91d90adfc8bebbc5e1ba7faaca6228ef730a2222417bb714d7652a34430e9e93de4484af7bdd88697b2a6e31f0780157b15060d71ed3251c84edfd7a1d4b2ad01bf034cd0ca1bd01c9f5bc571a0aaf8c51237b3f23bc838fd7a3d6f9bd535ddfb94be94e34916a3f16c861298a2abf1a21ba1d7b940192b0f3750d50460444ac2ee438e7141a5ba6a5bca9b750d0bb801f6450ac5a4ece46d2ae2e4e26962bf3fc787a9a3e75e544c668b156f5ead0dfb441260e7617584b534fde3ecf703ca15dd9261fade27436e4599077eb789797fa5af86c1b619eb93facadda1f6db394859eef502cb218608a0fb25cc4bc5bb04518be6a80e4c08fde87b423b8766d2a6ae02b9942bea9daf83ea9fb5aea2a058680ea9dbeba7d48ea4044a5b75c88363c6ff322f9832d2d801cd0fb8b6764c0405ac97751ac0eafc82c6fe1de9c6b84e39d9bff442620dc1c5274196a81817ef02331a4743a8408cdaa986470e90c394c298648da38fefc7dcffb669bd66e2eff0de622e131eb9721bc576bb1c9714b8b98a42d0a965a6d435307e9380e70630b196952f9dbcf4751af4d10069e144573f89fdcc33e2d628038c041ba2b2ee8f4f7e569f6d92f7c189b08e54196255a42010d27dc722a18b4739cb2e7094031693adbd7437366624c3c41a07302baf078a6edd9f32ab4264305c0e4d07cb3e3da1aec9a23c67f7b75a82caa911dd7adbe3271f86db69b329d137b55aeb979d625981e1c9e2745a06c96ea8aaca23fffd05856dd27ea946fccb4ca67a9debc0cef3fa56f0cc9ee2fe99656ea7f6c109919d014cb3d917d9204e2a7edb03178d11b88689d230c6aee8b95b344e31dfbf485461915cec6a46ed41d33e48819fef85c7ebde36d9d045ed4cd669a12f663fb8ce1849edc6d6f0eef9247d88b4140ccc7e30d6f90b8a1df9c13f68e526958f400184939b2ca0bd4130422fda906b947eb28a789d96d40ec461e0ecf890b6290a5cebf76c0fbe336f4a68ab9161157ed2715891339597f8a632361463bb5adc2dfab299c69caac847a1406e242371928e1a7d59c726ed60e77471ce31bbfd3abe9f65bbfabbd255930e6b63bb4ea0dcf12da6f793a7c11841d9a3239a9523a58c6b874dc868b3a1daab9e8cdd96f4949dc9f22a5f9dca41fb8a659fcfb80ce8b9fb124edda8889695a61d2b18efe67e42da25359c02f89ab16fd8cb13b8423dda4d87e1470639d869874092298abc3c411cad11520df19a5e575f6d5343b739ffc075fcf6f799b0c5c02b4cab4b4418fe2a625dda0803f769d54af5692407e45e5d966b9f8861484f84e045c49d9494b1561a10c19fb31b8bcfa5653a6bd9b6afe290ba4134eff84e24569254ab4bf2bbab9823f58aece62f00548bb457cf5c0e4821c35c66a85d3a75753105741927adaa24fa26ad518aa268f542d9c593dbf9a60084e4bc961d9fed96ec4503e25f3250bec2560dd56f0f92992e38e67ebf7daf37cc5693dd522dfbcc6a00d943056bdea371fdd1ac552572ecb7c27c0eea00a4de25b237830da1a71bace3f012d78e4d7873dedb6d33de6555302816c46e94ea'}]},
             'decodedReturnValue': '3637', 'size': 3227, 'error': '', 'baseFee': '229045245',
             'fee': {'baseFeeBurn': '36643361693047395', 'overEstimationBurn': '1341047311986525', 'minerPenalty': '0',
                     'minerTip': '32605831858704', 'refund': '36982985158303392'}, 'subcalls': [
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f05', 'toId': 'f05',
                 'toActor': 'storagemarket', 'value': '0', 'method': 'ActivateDeals', 'methodNumber': 6,
                 'params': '0x82811a00f86c281a003b929e', 'receipt': {'exitCode': 0, 'return': '0x', 'gasUsed': 0},
                 'decodedParams': {'DealIDs': [16280616], 'SectorExpiry': 3904158}, 'decodedReturnValue': None,
                 'error': '', 'subcalls': []},
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f05', 'toId': 'f05',
                 'toActor': 'storagemarket', 'value': '0', 'method': 'VerifyDealsForActivation', 'methodNumber': 5,
                 'params': '0x8181821a003b929e811a00f86c28',
                 'receipt': {'exitCode': 0, 'return': '0x8181831b0000000800000000404800b8cdb000000000', 'gasUsed': 0},
                 'error': '', 'subcalls': []},
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f05', 'toId': 'f05',
                 'toActor': 'storagemarket', 'value': '0', 'method': 'ComputeDataCommitment', 'methodNumber': 8,
                 'params': '0x818182811a00f86c2808', 'receipt': {'exitCode': 0,
                                                                 'return': '0x8181d82a5828000181e2039220209ecba29f1b8f2b1a1a9d9c6ec0edad159f8c3daf059ff62a0fd601df01b9343e',
                                                                 'gasUsed': 0},
                 'decodedParams': {'Inputs': [{'DealIDs': [16280616], 'SectorType': 8}]},
                 'decodedReturnValue': {'CommDs': ['baga6ea4seaqj5s5ct4ny6ky2dkozy3wa5wwrlh4mhwxqlh7wfih5mao7ag4tipq']},
                 'error': '', 'subcalls': []},
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f02', 'toId': 'f02',
                 'toActor': 'reward', 'value': '0', 'method': 'ThisEpochReward', 'methodNumber': 3, 'params': '0x',
                 'receipt': {'exitCode': 0,
                             'return': '0x8282581a00054dfb860d508046c9d4b6fe912aaac665103ed628196ed39d57010cbe588e28c0939f7ae018b922a8e1c7195ac8aa6e524900bcc0916f8e3c3a1d',
                             'gasUsed': 0}, 'decodedParams': None, 'decodedReturnValue': {'ThisEpochRewardSmoothed': {
                    'PositionEstimate': '33297634361888780732328207770722985517177769657132192289693',
                    'VelocityEstimate': '-4767923902417077884709058211078476975940549032439378'},
                    'ThisEpochBaselinePower': '13601030782972607005'},
                 'error': '', 'subcalls': []},
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f04', 'toId': 'f04',
                 'toActor': 'storagepower', 'value': '0', 'method': 'CurrentTotalPower', 'methodNumber': 9,
                 'params': '0x', 'receipt': {'exitCode': 0,
                                             'return': '0x844900fd1738d8000000004a00012dbab80b444900004c006feb42bf8e22be7382b76082581a00012d9f96d99c4767bc2b804820e581c422ac8db51428fac652570008f7e6ae12bf2de7a966535a2837d9f2a8866579e4d4',
                                             'gasUsed': 0}, 'decodedParams': None,
                 'decodedReturnValue': {'RawBytePower': '18237107716424204288',
                                        'QualityAdjPower': '21741892509614276608',
                                        'PledgeCollateral': '135301753388815179162236768', 'QualityAdjPowerSmoothed': {
                         'PositionEstimate': '7395784138948399269615701101257100893582663818836545554002',
                         'VelocityEstimate': '3355463207514452321666259562153591245456102106195156'}}, 'error': '',
                 'subcalls': []},
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f04', 'toId': 'f04',
                 'toActor': 'storagepower', 'value': '0', 'method': 'UpdatePledgeTotal', 'methodNumber': 6,
                 'params': '0x49001857e362ebf04494', 'receipt': {'exitCode': 0, 'return': '0x', 'gasUsed': 0},
                 'decodedParams': '1754120593888789652', 'decodedReturnValue': None, 'error': '', 'subcalls': []},
                {'from': 'f01156883', 'fromId': 'f01156883', 'fromActor': 'storageminer', 'to': 'f04', 'toId': 'f04',
                 'toActor': 'storagepower', 'value': '0', 'method': 'UpdateClaimedPower', 'methodNumber': 3,
                 'params': '0x82404600461db00000', 'receipt': {'exitCode': 0, 'return': '0x', 'gasUsed': 0},
                 'decodedParams': {'RawByteDelta': '0', 'QualityAdjustedDelta': '301145784320'},
                 'decodedReturnValue': None, 'error': '', 'subcalls': []}], 'transfers': [
                {'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                 'fromId': 'f01263696', 'to': 'f0126478', 'toId': 'f0126478', 'value': '32605831858704',
                 'type': 'miner-fee'},
                {'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                 'fromId': 'f01263696', 'to': 'f099', 'toId': 'f099', 'value': '37984409005033920', 'type': 'burn-fee'},
                {'from': 'f3qxbtvbj5mlaltsh6e6mlxgprcl3r75j4e6g2d65ci5uipplni77cwpgr7dbgpcprjqgj3x4pjrvnpt7bqsva',
                 'fromId': 'f01263696', 'to': 'f01156883', 'toId': 'f01156883', 'value': '1944530995624041453',
                 'type': 'transfer'}], 'eventLogs': [], 'tokenTransfers': []},
            [{'baseFee': '5249503', 'height': 3087223, 'timestamp': 1690923090}],
            {'cid': 'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms', 'height': 2268538,
             'timestamp': 1666362540, 'confirmations': 818655,
             'blocks': ['bafy2bzaceclq7ns2qhskpotjqmmfwzleoa256heicqwkghelhqcrxkgvigstu',
                        'bafy2bzaceammlbygtphzogvxl2okewawglorbs5bj6snfgtxjxoevsqp7265g',
                        'bafy2bzaceczkdyq7xfadxnhjbg5dhli6s5yqsvnhiirgxw74iyumwtwdhw7zo'], 'version': 0,
             'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
             'fromId': 'f01503519', 'fromActor': 'account',
             'to': 'f3qvhtg33nq56e4qunx5cvnj5rzykfwszl6kuvetbd7jqngmf4uzgmlcbxqxbqqy5etuw23dvdbodhgamogdra',
             'toId': 'f01264055', 'toActor': 'account', 'nonce': 10223, 'value': '5000000000000000000',
             'gasLimit': 588835, 'gasFeeCap': '2029397450', 'gasPremium': '285835', 'method': 'Send', 'methodNumber': 0,
             'params': '0x', 'receipt': {'exitCode': 6, 'return': '0x', 'gasUsed': 477568}, 'decodedParams': '',
             'decodedReturnValue': '', 'size': 135,
             'error': 'message failed with backtrace:\n--> caused by: send::send -- sender does not have funds to transfer (balance 4406125658903694419, transfer 5000000000000000000) (5: insufficient funds)\n (RetCode=6)',
             'baseFee': '46054059',
             'fee': {'baseFeeBurn': '21993944848512', 'overEstimationBurn': '681461911023', 'minerPenalty': '0',
                     'minerTip': '168309652225', 'refund': '1172136531058990'}, 'subcalls': [], 'transfers': [
                {'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
                 'fromId': 'f01503519', 'to': 'f01782222', 'toId': 'f01782222', 'value': '168309652225',
                 'type': 'miner-fee'},
                {'from': 'f3ugesb7mvq6wsph7ajymfaxber34ucttqu5agdy4xs72jgaxl7dctnuzmxfot5qjkrnztli4ngapgjmxnjldq',
                 'fromId': 'f01503519', 'to': 'f099', 'toId': 'f099', 'value': '22675406759535', 'type': 'burn-fee'}],
             'eventLogs': [], 'tokenTransfers': []}

        ]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        FilecoinExplorerInterface.tx_details_apis[0] = self.api
        txs_details = BlockchainExplorer.get_transactions_details(self.hash_of_transactions, 'FIL')
        expected_txs_details = [
            {'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2': {
                'hash': 'bafy2bzacedng6z2vcuxcrz2xxl5h44d74itvvhx6afnelpusfhib7iarcndp2',
                'success': True, 'block': 2349511,
                'date': datetime.datetime(2022, 11, 18, 17, 15, 30,
                                          tzinfo=UTC), 'fees': Decimal(
                    '0.000127835880170476'), 'memo': None, 'confirmations': 738891, 'raw': None,
                'inputs': [], 'outputs': [], 'transfers': [
                    {'type': 'MainCoin', 'symbol': 'FIL', 'currency': Currencies.fil,
                     'from': 'f15425tij5zososhjq7g3vnsnkccrw3xwddrqhi5y',
                     'to': 'f1mzw4fhuobcdaamwyyk343otpo2sldu776uojbji',
                     'value': Decimal('1.600000000000000000'),
                     'is_valid': True, 'memo': None, 'token': None}]}},
            {'bafy2bzaceaq24cuu6uurwtpyb3fymv7burkkl4rbv52mri427gvzmid5wxqye': {'success': False}},
            {'bafy2bzacedjn33wphjyplalpldglnsdobuh2thbgovwtpwkrwjcut6u454mms': {'success': False}},
        ]

        for expected_tx_details, tx_hash in zip(expected_txs_details, self.hash_of_transactions):
            assert txs_details[tx_hash].get('success') == expected_tx_details[tx_hash].get('success')
            if txs_details[tx_hash].get('success'):
                txs_details[tx_hash]['confirmations'] = expected_tx_details[tx_hash]['confirmations']
                assert txs_details[tx_hash] == expected_tx_details[tx_hash]

    def test_get_address_txs(self):
        address_txs_mock_responses = [
            [{'baseFee': '5249503', 'height': 3087223, 'timestamp': 1690923090}],
            {'totalCount': 3, 'messages': [
                {'cid': 'bafy2bzacecxq5ol6qdvlwh5a64vw4ndjlt4jvnreieog6qapyfc64elcda5kg', 'height': 1965653,
                 'timestamp': 1657275990, 'from': 'f1susdjal2rogayvfr6m7wypfhawcmuc3ny7v7osi',
                 'to': 'f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna',
                 'nonce': 430119, 'value': '110000000000000000000', 'method': 'Send', 'receipt': {'exitCode': 0}},
                {'cid': 'bafy2bzacedzpep5y6kq77jaynwxfvv4hdia3qnpwdnxdzawmscvq4sxo7j57e', 'height': 1590902,
                 'timestamp': 1646033460, 'from': 'f1susdjal2rogayvfr6m7wypfhawcmuc3ny7v7osi',
                 'to': 'f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna',
                 'nonce': 368867, 'value': '100000000000000000000', 'method': 'Send', 'receipt': {'exitCode': 0}},
                {'cid': 'bafy2bzaced2cpqxpbyxuk6blhmlgusnzh5iawrog4e7524oeol27ghz4ovj7k', 'height': 1573107,
                 'timestamp': 1645499610,
                 'from': 'f3uukoae6gcpbsgqtdvg7slh7tygqhtiv2qus5p2c574v76gnts36dnunk2wxvfyfgcqeimnos6shll6madv7q',
                 'to': 'f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna',
                 'nonce': 214, 'value': '0', 'method': 'Send', 'receipt': {'exitCode': 0}}],
             'methods': ['DeclareFaultsRecovered', 'Send', 'SubmitWindowedPoSt']}]
        self.api.request = Mock(side_effect=address_txs_mock_responses)
        FilecoinExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [
            {'address': 'f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna',
             'block': 1965653, 'confirmations': 1121571,
             'details': {},
             'contract_address': None,
             'from_address': ['f1susdjal2rogayvfr6m7wypfhawcmuc3ny7v7osi'],
             'hash': 'bafy2bzacecxq5ol6qdvlwh5a64vw4ndjlt4jvnreieog6qapyfc64elcda5kg',
             'huge': False,
             'invoice': None,
             'is_double_spend': False,
             'tag': None,
             'timestamp': datetime.datetime(2022, 7, 8, 10, 26, 30, tzinfo=UTC),
             'value': Decimal('110.000000000000000000')},
            {'address': 'f3wrzbnrhrltyqb5osk74bqu5kh4xl4nultxyre2dlsef2xtxul6krfhawx4tq2cb6y6me26cqznaenutlvzna',
             'block': 1590902,
             'confirmations': 1496322,
             'details': {},
             'contract_address': None,
             'from_address': ['f1susdjal2rogayvfr6m7wypfhawcmuc3ny7v7osi'],
             'hash': 'bafy2bzacedzpep5y6kq77jaynwxfvv4hdia3qnpwdnxdzawmscvq4sxo7j57e',
             'huge': False,
             'invoice': None,
             'is_double_spend': False,
             'tag': None,
             'timestamp': datetime.datetime(2022, 2, 28, 7, 31, tzinfo=UTC),
             'value': Decimal('100.000000000000000000')}
        ]

        for address, expected_address_txs in zip(self.address_txs, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.fil, 'FIL')
            assert len(expected_addresses_txs) == len(address_txs.get(Currencies.fil))
            for expected_address_tx, address_tx in zip(expected_addresses_txs, address_txs.get(Currencies.fil)):
                assert address_tx.confirmations >= expected_address_tx.get('confirmations')
                address_tx.confirmations = expected_address_tx.get('confirmations')
                assert address_tx.__dict__ == expected_address_tx

    def test_get_block_txs(self):
        cache.delete('latest_block_height_processed_fil')
        block_txs_mock_responses = [
            [{'baseFee': '26947375', 'height': 3088339, 'timestamp': 1690956570}],
            {'height': 3088335, 'timestamp': 1690956450, 'messageCount': 118, 'blocks': [
                {'cid': 'bafy2bzaceb7xnhi24xk37ldu2eqd3dtseya4fhfkdu3nczfkeac7rd7oiuaoc', 'miner': 'f01776299',
                 'messageCount': 78, 'winCount': 1, 'reward': '13183470273226259909', 'penalty': '0'},
                {'cid': 'bafy2bzacecahpcghofl62kk74lbwnprcnq3frxfo4ll6gnwmn3mxqioubtudg', 'miner': 'f01228108',
                 'messageCount': 85, 'winCount': 1, 'reward': '13172640355905581310', 'penalty': '0'}]},
            {'totalCount': 1, 'messages': [{'cid': 'bafy2bzaceddp4det46vss4trcav6swf6vlkrclqdxlf73rtq2fiohfuycpqcu',
                                            'from': 'f1d7mq36vf6osdhcd32i6k3wyb223mdjlxnafnala',
                                            'to': 'f13dtp2mt54qkv32ysgs3n7dlkr2qpgw7qlvz4q6q',
                                            'value': '78117200000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'ProveCommitSector', 'PublishStorageDeals', 'SubmitWindowedPoSt', 'Propose',
                         'Send']},
            {'messages': [],
             'methods': ['ProveCommitSector', 'SubmitWindowedPoSt', 'PreCommitSector', 'Send', 'Propose',
                         'PublishStorageDeals'], 'totalCount': 1},
            {'totalCount': 1, 'messages': [{'cid': 'bafy2bzaceddp4det46vss4trcav6swf6vlkrclqdxlf73rtq2fiohfuycpqcu',
                                            'from': 'f1d7mq36vf6osdhcd32i6k3wyb223mdjlxnafnala',
                                            'to': 'f13dtp2mt54qkv32ysgs3n7dlkr2qpgw7qlvz4q6q',
                                            'value': '78117200000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['ProveCommitSector', 'SubmitWindowedPoSt', 'PreCommitSector', 'Send', 'Propose',
                         'PublishStorageDeals']},
            {'messages': [],

             'methods': ['Propose', 'ProveCommitSector', 'SubmitWindowedPoSt', 'PublishStorageDeals', 'PreCommitSector',
                         'Send'], 'totalCount': 1},
            {'height': 3088336, 'timestamp': 1690956480, 'messageCount': 192, 'blocks': [
                {'cid': 'bafy2bzaceap6cr5fujnim3kjvkfbzawsyjwmujxzufys6p62tzz35mjz7rqlw',
                 'miner': 'f0441240', 'messageCount': 108, 'winCount': 1,
                 'reward': '13183420629219312157', 'penalty': '0'},
                {'cid': 'bafy2bzacecp4uyflye6ibhcb2zlvnyxisuknlmumrlpn2oscdgucmcxole4tg',
                 'miner': 'f02091127', 'messageCount': 109, 'winCount': 1,
                 'reward': '13167065853801942469', 'penalty': '0'},
                {'cid': 'bafy2bzacedhamsqscgdiboruwmtqqmf2poso5l5a6utdkzgxnnoi7p7avdplg',
                 'miner': 'f090889', 'messageCount': 99, 'winCount': 1,
                 'reward': '13168984643971112863', 'penalty': '0'},
                {'cid': 'bafy2bzacec3pna5ddjvmr6kw3pr4m3jtgbwcapwesiuzybzwiorchvbrn57cw',
                 'miner': 'f0745192', 'messageCount': 94, 'winCount': 1,
                 'reward': '13167343143558894140', 'penalty': '0'},
                {'cid': 'bafy2bzacedkudcb2ufiigei4oe57lmphxveyabzazc2bopdkxhbv7d4r7dqxg',
                 'miner': 'f0849554', 'messageCount': 56, 'winCount': 1,
                 'reward': '13180116866843845770', 'penalty': '0'},
                {'cid': 'bafy2bzacebo7j7ryowltlr7iie2hleueikvjonk67l46exgb6aaa3hywiplba',
                 'miner': 'f01826715', 'messageCount': 81, 'winCount': 1,
                 'reward': '13172921889573788660', 'penalty': '0'}]},
            {'totalCount': 6, 'messages': [{'cid': 'bafy2bzacedzooa377zxlfbz6bdjaflugb5zjz77jbbieiu6dalzg77hlzsl5i',
                                            'from': 'f1frtyzq4zsyfyflxvi5mrj4el3dsnkyemw6gpyoi',
                                            'to': 'f124nc7soxqejtehk7fvyoxufy7ydyvur3c3ky2ai',
                                            'value': '134718793509980960', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebx5pfwzg3rwdi76ushmgv7bg3y3znwdcdrzi6lnimge6qleombsq',
                                            'from': 'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq',
                                            'to': 'f1zd5suda26l7zynqyss2vnke5jgylfpzyrfqc5wq',
                                            'value': '39814794930000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                            'value': '9480000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                            'value': '1020000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                            'value': '4880000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                            'value': '2970000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'Send', 'ProveReplicaUpdates', 'ProveCommitSector', 'PublishStorageDeals',
                         'SubmitWindowedPoSt', 'WithdrawBalance (miner)', 'AddBalance']},
            {'messages': [],
             'methods': ['PreCommitSector', 'Send', 'PublishStorageDeals', 'ProveCommitSector', 'ProveReplicaUpdates',
                         'WithdrawBalance (miner)', 'SubmitWindowedPoSt', 'AddBalance'], 'totalCount': 6},
            #
            {'totalCount': 6, 'messages': [{'cid': 'bafy2bzacedzooa377zxlfbz6bdjaflugb5zjz77jbbieiu6dalzg77hlzsl5i',
                                            'from': 'f1frtyzq4zsyfyflxvi5mrj4el3dsnkyemw6gpyoi',
                                            'to': 'f124nc7soxqejtehk7fvyoxufy7ydyvur3c3ky2ai',
                                            'value': '134718793509980960', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebx5pfwzg3rwdi76ushmgv7bg3y3znwdcdrzi6lnimge6qleombsq',
                                            'from': 'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq',
                                            'to': 'f1zd5suda26l7zynqyss2vnke5jgylfpzyrfqc5wq',
                                            'value': '39814794930000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                            'value': '9480000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                            'value': '1020000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                            'value': '4880000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                            'value': '2970000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['ProveCommitSector', 'AddBalance', 'PreCommitSector', 'Send', 'SubmitWindowedPoSt',
                         'PublishStorageDeals', 'WithdrawBalance (miner)', 'ProveReplicaUpdates']},
            {'messages': [],
             'methods': ['PreCommitSector', 'Send', 'AddBalance', 'SubmitWindowedPoSt', 'WithdrawBalance (miner)',
                         'ProveReplicaUpdates', 'ProveCommitSector', 'PublishStorageDeals'], 'totalCount': 6},
            #
            {'totalCount': 4, 'messages': [{'cid': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                            'value': '9480000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                            'value': '1020000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                            'value': '4880000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                            'value': '2970000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'Send', 'SubmitWindowedPoSt', 'PublishStorageDeals',
                         'WithdrawBalance (miner)', 'ProveReplicaUpdates', 'ProveCommitSector', 'AddBalance']},
            {'messages': [],
             'methods': ['PreCommitSector', 'Send', 'ProveReplicaUpdates', 'ProveCommitSector', 'PublishStorageDeals',
                         'SubmitWindowedPoSt', 'WithdrawBalance (miner)', 'AddBalance'], 'totalCount': 4},
            {'totalCount': 4, 'messages': [{'cid': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                            'value': '9480000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                            'value': '1020000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                            'value': '4880000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                            'value': '2970000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'ProveCommitSector', 'AddBalance', 'WithdrawBalance (miner)',
                         'ProveReplicaUpdates', 'PublishStorageDeals', 'SubmitWindowedPoSt', 'Send']},
            {'messages': [],
             'methods': ['PreCommitSector', 'Send', 'AddBalance', 'SubmitWindowedPoSt', 'WithdrawBalance (miner)',
                         'ProveReplicaUpdates', 'ProveCommitSector', 'PublishStorageDeals'], 'totalCount': 4},
            {'totalCount': 4, 'messages': [{'cid': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                            'value': '9480000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                            'value': '1020000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                            'value': '4880000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                            'value': '2970000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['Send', 'PreCommitSectorBatch', 'PublishStorageDeals', 'ProveCommitSector',
                         'SubmitWindowedPoSt', 'AddBalance', 'PreCommitSector']},
            {'messages': [],
             'methods': ['AddBalance', 'Send', 'PreCommitSector', 'PublishStorageDeals', 'SubmitWindowedPoSt',
                         'PreCommitSectorBatch', 'ProveCommitSector'], 'totalCount': 4},
            {'totalCount': 4, 'messages': [{'cid': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                            'value': '9480000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                            'value': '1020000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                            'value': '4880000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                                            'from': 'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                            'to': 'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                            'value': '2970000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'PreCommitSectorBatch', 'ProveCommitSector', 'AddBalance',
                         'PublishStorageDeals', 'SubmitWindowedPoSt', 'Send']},
            {'messages': [],
             'methods': ['Send', 'PreCommitSectorBatch', 'ProveCommitSector', 'AddBalance', 'SubmitWindowedPoSt',
                         'PublishStorageDeals', 'PreCommitSector'], 'totalCount': 4},
            # n
            {'height': 3088337, 'timestamp': 1690956510, 'messageCount': 53, 'blocks': [
                {'cid': 'bafy2bzacebf2t2gtnamk6toe2prn6fkdncu5h4gcmwcyat67b3ukf3go6ydrs',
                 'miner': 'f01885088', 'messageCount': 27, 'winCount': 1,
                 'reward': '13183239260333081711', 'penalty': '0'},
                {'cid': 'bafy2bzacebtrtqabm4n2wgen2zungk2olpvn4df54re34nb5wv6b5rca6fca6',
                 'miner': 'f01844613', 'messageCount': 43, 'winCount': 1,
                 'reward': '13172976962251746025', 'penalty': '0'},
                {'cid': 'bafy2bzaceckojwr6rfosyhkx3su4p6ro23b6krr7gajuen6wtb4e6qpnyrka6',
                 'miner': 'f0844271', 'messageCount': 41, 'winCount': 1,
                 'reward': '13167235922801253328', 'penalty': '0'}]},
            {'messages': [],
             'methods': ['ProveReplicaUpdates', 'PreCommitSector', 'ProveCommitSector', 'PublishStorageDeals',
                         'AddBalance', 'SubmitWindowedPoSt'], 'totalCount': 0},
            {'totalCount': 2, 'messages': [{'cid': 'bafy2bzacecqdxdoxbexa2hytnr3qc22no7l53x555f3ml2smzoyfgnrtfzgxu',
                                            'from': 'f1u7p45twtkavv6h7yvjzyppz4m4lmhhpsgksxmea',
                                            'to': 'f1b6zutbs4qobyabuvvaduecpddlumdbg35qmjzji',
                                            'value': '190000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}},
                                           {'cid': 'bafy2bzaceahcsdilvjcv6dzu4qhwvb7qt7zfldwgrmuhkv3ry2arzpqj7drmy',
                                            'from': 'f1rvrckgrz6qjdqlsbxis6gihlch6bk3qn4iejtay',
                                            'to': 'f1gvm6xe33vq6pu7l7sg6u7of6x5jzkgfvwambagy',
                                            'value': '46090000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['Send', 'ProveCommitSector', 'AddBalance', 'ProveReplicaUpdates', 'SubmitWindowedPoSt',
                         'PublishStorageDeals', 'PreCommitSector']},
            {'messages': [],
             'methods': ['ProveCommitSector', 'SubmitWindowedPoSt', 'Send', 'PreCommitSector', 'AddBalance',
                         'ProveReplicaUpdates', 'PublishStorageDeals'], 'totalCount': 2},
            {'totalCount': 1, 'messages': [{'cid': 'bafy2bzaceahcsdilvjcv6dzu4qhwvb7qt7zfldwgrmuhkv3ry2arzpqj7drmy',
                                            'from': 'f1rvrckgrz6qjdqlsbxis6gihlch6bk3qn4iejtay',
                                            'to': 'f1gvm6xe33vq6pu7l7sg6u7of6x5jzkgfvwambagy',
                                            'value': '46090000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['SubmitWindowedPoSt', 'ProveCommitSector', 'Send', 'PreCommitSector', 'AddBalance',
                         'ProveReplicaUpdates', 'PublishStorageDeals']},
            {'messages': [], 'methods': ['SubmitWindowedPoSt', 'ProveCommitSector', 'PublishStorageDeals', 'AddBalance',
                                         'ProveReplicaUpdates', 'Send', 'PreCommitSector'], 'totalCount': 1},
            # nn
            {'height': 3088338, 'timestamp': 1690956540, 'messageCount': 161, 'blocks': [
                {'cid': 'bafy2bzacebsvzvyfbwpkfgf6tsgum3fxluc73ikpxgnga4l4sohkpyztft6zs',
                 'miner': 'f01825301', 'messageCount': 58, 'winCount': 1,
                 'reward': '13183451721206538000', 'penalty': '0'},
                {'cid': 'bafy2bzaceat7czebu6viqhqqxoi6sbahx3ubdp7wn4gbrbteq34tpxvgnwy6o',
                 'miner': 'f083625', 'messageCount': 85, 'winCount': 1,
                 'reward': '13171050633649293177', 'penalty': '0'},
                {'cid': 'bafy2bzaced3lkobnuvxkjs3myson5a7eortvdnwwyndg6rzczrmsf2yd2ip4k',
                 'miner': 'f02013434', 'messageCount': 128, 'winCount': 1,
                 'reward': '13177098431705798434', 'penalty': '0'}]},
            {'totalCount': 1, 'messages': [{'cid': 'bafy2bzacebo27xemy6pf4cjyo4gpeo42ismoygwlouc3trq3fulqjyorcfioq',
                                            'from': 'f1ypwgpxdyp6n4k6i5ffwyuspjhrzdd7swb7rpnfq',
                                            'to': 'f1r7rjrrlbdnsjhomwkv26hao3yitaj2wph2qpvwi',
                                            'value': '9080000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'InvokeContract', 'ProveCommitSector', 'PublishStorageDeals',
                         'SubmitWindowedPoSt', 'DeclareFaultsRecovered', 'Send']},
            {'messages': [], 'methods': ['PreCommitSector', 'Send', 'DeclareFaultsRecovered', 'SubmitWindowedPoSt',
                                         'PublishStorageDeals', 'ProveCommitSector', 'InvokeContract'],
             'totalCount': 1},
            {'totalCount': 1, 'messages': [{'cid': 'bafy2bzacebo27xemy6pf4cjyo4gpeo42ismoygwlouc3trq3fulqjyorcfioq',
                                            'from': 'f1ypwgpxdyp6n4k6i5ffwyuspjhrzdd7swb7rpnfq',
                                            'to': 'f1r7rjrrlbdnsjhomwkv26hao3yitaj2wph2qpvwi',
                                            'value': '9080000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'Send', 'ProveCommitSector', 'PublishStorageDeals', 'AddBalance',
                         'SubmitWindowedPoSt', 'DeclareFaultsRecovered']},
            {'messages': [],
             'methods': ['PreCommitSector', 'Send', 'ProveCommitSector', 'PublishStorageDeals', 'AddBalance',
                         'SubmitWindowedPoSt', 'DeclareFaultsRecovered'], 'totalCount': 1},
            {'totalCount': 1, 'messages': [{'cid': 'bafy2bzacebo27xemy6pf4cjyo4gpeo42ismoygwlouc3trq3fulqjyorcfioq',
                                            'from': 'f1ypwgpxdyp6n4k6i5ffwyuspjhrzdd7swb7rpnfq',
                                            'to': 'f1r7rjrrlbdnsjhomwkv26hao3yitaj2wph2qpvwi',
                                            'value': '9080000000000000000', 'method': 'Send',
                                            'receipt': {'exitCode': 0}}],
             'methods': ['PreCommitSector', 'Send', 'SubmitWindowedPoSt', 'ProveCommitSector', 'PublishStorageDeals',
                         'AddBalance']},
            {'messages': [],
             'methods': ['PreCommitSector', 'Send', 'SubmitWindowedPoSt', 'PublishStorageDeals', 'ProveCommitSector',
                         'AddBalance'], 'totalCount': 1},
            # Nnnn
            {'height': 3088339, 'timestamp': 1690956570, 'messageCount': 234, 'blocks': [
                {'cid': 'bafy2bzaceat6zatayem74jzdozwobhilmpcc45cw2aaf4t5y6g2exestn52no',
                 'miner': 'f01106276', 'messageCount': 96, 'winCount': 1,
                 'reward': '13187113637951814998', 'penalty': '0'},
                {'cid': 'bafy2bzacebae7huhbeugjhiw4bikhyy6i35dejkshuwi7pd26sxyyk36hk7b4',
                 'miner': 'f01853077', 'messageCount': 83, 'winCount': 1,
                 'reward': '13171289377544903063', 'penalty': '0'},
                {'cid': 'bafy2bzaceazwscotagytamuexfzlesivcfzxjp3z4tanyr7mnspxauwkbq33e',
                 'miner': 'f01825902', 'messageCount': 97, 'winCount': 1,
                 'reward': '13172013808157449906', 'penalty': '0'},
                {'cid': 'bafy2bzacebchdhx2zrskr6jmjdxw2eaa7gvtlqdhqehpuvhjemrhcgpewydns',
                 'miner': 'f01780412', 'messageCount': 97, 'winCount': 1,
                 'reward': '13169214933260984392', 'penalty': '0'},
                {'cid': 'bafy2bzacedul3jz4jp33sqmf52edcoiwrhm2okrdazwtkkfuuypn3xwsgzbxq',
                 'miner': 'f02233608', 'messageCount': 60, 'winCount': 1,
                 'reward': '13172027502130043217', 'penalty': '0'},
                {'cid': 'bafy2bzaceaai5d7fszuekpgg4ijywhuswveblxfr457wg4e6c346i2vr24dlg',
                 'miner': 'f02042992', 'messageCount': 93, 'winCount': 1,
                 'reward': '13174327540192472259', 'penalty': '0'},
                {'cid': 'bafy2bzacedoh4hwq5wa2hrgjc6fgmnzeszymg6y4taep2nyk34j6smzln7tfa',
                 'miner': 'f02128256', 'messageCount': 73, 'winCount': 1,
                 'reward': '13169714159838983536', 'penalty': '0'}]},
            {'messages': [],
             'methods': ['ProveReplicaUpdates', 'DeclareFaultsRecovered', 'SubmitWindowedPoSt', 'InvokeContract',
                         'AddBalance', 'PreCommitSector', 'PublishStorageDeals', 'ProveCommitSector'], 'totalCount': 0},
            {'messages': [],
             'methods': ['ProveCommitSector', 'InvokeContract', 'SubmitWindowedPoSt', 'PublishStorageDeals',
                         'PreCommitSector', 'DeclareFaultsRecovered'], 'totalCount': 0},
            {'messages': [],
             'methods': ['ProveCommitSector', 'SubmitWindowedPoSt', 'PublishStorageDeals', 'ProveReplicaUpdates',
                         'InvokeContract', 'PreCommitSector', 'DeclareFaultsRecovered'], 'totalCount': 0},
            {'messages': [], 'methods': ['SubmitWindowedPoSt', 'ProveCommitSector', 'PreCommitSector', 'InvokeContract',
                                         'DeclareFaultsRecovered', 'ProveReplicaUpdates', 'PublishStorageDeals'],
             'totalCount': 0},
            {'messages': [],
             'methods': ['PreCommitSector', 'DeclareFaultsRecovered', 'SubmitWindowedPoSt', 'PublishStorageDeals',
                         'ProveCommitSector', 'AddBalance'], 'totalCount': 0},
            {'messages': [],
             'methods': ['PublishStorageDeals', 'WithdrawBalance (miner)', 'ProveCommitSector', 'AddBalance',
                         'PreCommitSector', 'SubmitWindowedPoSt'], 'totalCount': 0},
            {'messages': [],
             'methods': ['InvokeContract', 'PublishStorageDeals', 'ProveCommitSector', 'SubmitWindowedPoSt',
                         'AddBalance', 'PreCommitSector'], 'totalCount': 0}

        ]
        self.api.request = Mock(side_effect=block_txs_mock_responses)
        settings.USE_TESTNET_BLOCKCHAINS = False
        FilecoinExplorerInterface.block_txs_apis[0] = self.api
        expected_txs_addresses = {'input_addresses': {'f1d7mq36vf6osdhcd32i6k3wyb223mdjlxnafnala',
                                                      'f1ypwgpxdyp6n4k6i5ffwyuspjhrzdd7swb7rpnfq',
                                                      'f1frtyzq4zsyfyflxvi5mrj4el3dsnkyemw6gpyoi',
                                                      'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq',
                                                      'f1rvrckgrz6qjdqlsbxis6gihlch6bk3qn4iejtay',
                                                      'f1u7p45twtkavv6h7yvjzyppz4m4lmhhpsgksxmea',
                                                      'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq'},
                                  'output_addresses': {'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q',
                                                       'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a',
                                                       'f1b6zutbs4qobyabuvvaduecpddlumdbg35qmjzji',
                                                       'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq',
                                                       'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui',
                                                       'f13dtp2mt54qkv32ysgs3n7dlkr2qpgw7qlvz4q6q',
                                                       'f1zd5suda26l7zynqyss2vnke5jgylfpzyrfqc5wq',
                                                       'f1gvm6xe33vq6pu7l7sg6u7of6x5jzkgfvwambagy',
                                                       'f1r7rjrrlbdnsjhomwkv26hao3yitaj2wph2qpvwi',
                                                       'f124nc7soxqejtehk7fvyoxufy7ydyvur3c3ky2ai'}}

        expected_txs_info = {
            'outgoing_txs': {
                'f1d7mq36vf6osdhcd32i6k3wyb223mdjlxnafnala': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceddp4det46vss4trcav6swf6vlkrclqdxlf73rtq2fiohfuycpqcu',
                     'value': Decimal('78.117200000000000000'),
                     'block_height': 3088335, 'symbol':'FIL'}]},
                'f1frtyzq4zsyfyflxvi5mrj4el3dsnkyemw6gpyoi': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedzooa377zxlfbz6bdjaflugb5zjz77jbbieiu6dalzg77hlzsl5i',
                     'value': Decimal('0.134718793509980960'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1ph6a2baxrrokhmaopp7wl4guhlx7pouos7af3iq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebx5pfwzg3rwdi76ushmgv7bg3y3znwdcdrzi6lnimge6qleombsq',
                     'value': Decimal('39.814794930000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1vwvhgyjd5at4ikbqklwq2xdj4kc2hhwso4vshvq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                     'value': Decimal('4.880000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'},
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                     'value': Decimal('2.970000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'},
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                     'value': Decimal('1.020000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'},
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                     'value': Decimal('9.480000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1u7p45twtkavv6h7yvjzyppz4m4lmhhpsgksxmea': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecqdxdoxbexa2hytnr3qc22no7l53x555f3ml2smzoyfgnrtfzgxu',
                     'value': Decimal('0.190000000000000000'),
                     'block_height': 3088337, 'symbol':'FIL'}]},
                'f1rvrckgrz6qjdqlsbxis6gihlch6bk3qn4iejtay': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceahcsdilvjcv6dzu4qhwvb7qt7zfldwgrmuhkv3ry2arzpqj7drmy',
                     'value': Decimal('46.090000000000000000'),
                     'block_height': 3088337, 'symbol':'FIL'}]},
                'f1ypwgpxdyp6n4k6i5ffwyuspjhrzdd7swb7rpnfq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebo27xemy6pf4cjyo4gpeo42ismoygwlouc3trq3fulqjyorcfioq',
                     'value': Decimal('9.080000000000000000'),
                     'block_height': 3088338, 'symbol':'FIL'}]}
            },
            'incoming_txs': {
                'f13dtp2mt54qkv32ysgs3n7dlkr2qpgw7qlvz4q6q': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceddp4det46vss4trcav6swf6vlkrclqdxlf73rtq2fiohfuycpqcu',
                     'value': Decimal('78.117200000000000000'),
                     'block_height': 3088335, 'symbol':'FIL'}]},
                'f124nc7soxqejtehk7fvyoxufy7ydyvur3c3ky2ai': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedzooa377zxlfbz6bdjaflugb5zjz77jbbieiu6dalzg77hlzsl5i',
                     'value': Decimal('0.134718793509980960'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1zd5suda26l7zynqyss2vnke5jgylfpzyrfqc5wq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebx5pfwzg3rwdi76ushmgv7bg3y3znwdcdrzi6lnimge6qleombsq',
                     'value': Decimal('39.814794930000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1pdsncjplxlxchvlyxzfabuid3dsw5kdokr7bl5q': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebkwu4paezscnnu2ygyjjie6mts7tk77b6hu2ghiz3gdt56e7vfva',
                     'value': Decimal('9.480000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1hkwr6btfrevyarlhhxmve5wmzyml5veftrhq4gq': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacedvd5twrqvszfc63iiqqmtyt4gny2cryvbeh2sooztk7zk5ew7ysu',
                     'value': Decimal('1.020000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f12wuva4qze4fthmfmxebea3k4kjyxqmsp4fgy47a': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceccl75sgu47fywoyasa3ozudk3s5ceffikmyop2tpr6jk3763qbn6',
                     'value': Decimal('4.880000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1qhfbwfkzmo2yponjajlrnbduy7u2g4hdyca2sui': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebmusy7hl2q6dvkrfx6fpi3s2ks3lztsoawtrv36xjpw63gvxkbri',
                     'value': Decimal('2.970000000000000000'),
                     'block_height': 3088336, 'symbol':'FIL'}]},
                'f1b6zutbs4qobyabuvvaduecpddlumdbg35qmjzji': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacecqdxdoxbexa2hytnr3qc22no7l53x555f3ml2smzoyfgnrtfzgxu',
                     'value': Decimal('0.190000000000000000'),
                     'block_height': 3088337, 'symbol':'FIL'}]},
                'f1gvm6xe33vq6pu7l7sg6u7of6x5jzkgfvwambagy': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzaceahcsdilvjcv6dzu4qhwvb7qt7zfldwgrmuhkv3ry2arzpqj7drmy',
                     'value': Decimal('46.090000000000000000'),
                     'block_height': 3088337, 'symbol':'FIL'}]},
                'f1r7rjrrlbdnsjhomwkv26hao3yitaj2wph2qpvwi': {Currencies.fil: [
                    {'contract_address': None,
                     'tx_hash': 'bafy2bzacebo27xemy6pf4cjyo4gpeo42ismoygwlouc3trq3fulqjyorcfioq',
                     'value': Decimal('9.080000000000000000'),
                     'block_height': 3088338, 'symbol':'FIL'}]}
            }
        }
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('FIL', None, None, True, True)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)
